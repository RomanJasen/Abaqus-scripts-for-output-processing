"""
image_export.py - Abaqus side of A_2_Image_export_Auto.py.

* Replayer   runs view / variable command lines (as captured by rpy_views or
             written by hand) with session, the Abaqus constants, dgo and vp,
             and restores the starting values between views so that no view
             inherits settings from the previous one
* choose_frames      uniform / every n-th / indices / times / all / last
* print_png          one screenshot of the current viewport
* zip_folder         optional: one ZIP per job (far fewer files to copy)
(the curves with the exported frames marked: pushover_curve.py)

Needs Abaqus/CAE or Viewer for the Replayer and printing; the frame and zip
helpers run anywhere.
"""
from __future__ import print_function

import os
import re
import sys
import math
import shutil
import zipfile
import inspect
from collections import OrderedDict

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import odb_tools
import rpy_views
from odb_tools import log

RESET_DISPLAY_GROUP = "vp.odbDisplay.displayGroup.replace(leaf=dgo.Leaf(leafType=DEFAULT_MODEL))"
_VIEWCUT_DEF = re.compile(r"^vp\.odbDisplay\.ViewCut\(")


# ---------------------------------------------------------------------------
# Running command lines
# ---------------------------------------------------------------------------
class Replayer(object):
    """Executes command lines in a namespace like the Abaqus command line."""

    def __init__(self, strict=False, report=None):
        from abaqus import session
        import abaqusConstants
        import displayGroupOdbToolset as dgo
        self.session = session
        self.ns = dict((k, getattr(abaqusConstants, k)) for k in dir(abaqusConstants) if not k.startswith("_"))
        self.ns["session"] = session
        self.ns["dgo"] = dgo
        self.strict = strict
        self.report = report or log   # where warnings go
        self.warned = set()
        self.baseline = {}   # (target, argument) -> value before any view was applied

    @property
    def vp(self):
        return self.session.viewports[self.session.currentViewportName]

    def run(self, commands, label):
        """Execute the commands; returns the commands that failed (completely or partly)."""
        self.ns["vp"] = self.vp
        failures = []
        for cmd in commands:
            if _VIEWCUT_DEF.match(cmd):  # a custom view cut is defined only once
                p = rpy_views.parse_call(cmd)
                name = rpy_views.literal(p[3].get("name", "''"), "") if p else ""
                if name and name in self.vp.odbDisplay.viewCuts.keys():
                    continue
            try:
                exec(compile(cmd, "<%s>" % label, "exec"), self.ns)
            except Exception as e:
                if self.strict:
                    raise
                failed = self._one_by_one(cmd, label)
                if failed is None:
                    failed = "%s: %s" % (type(e).__name__, e)
                if failed:
                    failures.append(cmd)
                    if (label, cmd) not in self.warned:
                        self.warned.add((label, cmd))
                        self.report("  WARNING in %s: %s\n           -> %s" % (label, cmd[:150], failed))
        return failures

    def _one_by_one(self, cmd, label):
        """A failed setValues(a=.., b=..) is retried argument by argument, so one unknown or
        read-only argument does not lose the others. Returns a note on the arguments that
        still failed ("" if none), or None when cmd is no multi-argument setValues."""
        p = rpy_views.parse_call(cmd)
        if not p or p[1] != "setValues" or p[2] or len(p[3]) < 2:
            return None
        bad = []
        for k, v in p[3].items():
            try:
                exec(compile(rpy_views.build_call(p[0], "setValues", (), {k: v}), "<%s>" % label, "exec"), self.ns)
            except Exception as e:
                bad.append("%s (%s)" % (k, e))
        return ("skipped: " + ", ".join(bad)) if bad else ""

    # -- starting values --------------------------------------------------------
    @staticmethod
    def pairs(command_lists):
        """{(target, argument)} set by setValues(...) in the command lists."""
        out = set()
        for commands in command_lists:
            for target, keys in rpy_views.setvalues_objects(commands):
                out.update((target, k) for k in keys)
        return out

    def snapshot(self, pairs):
        """Remember the current value of every (object, argument) pair."""
        self.ns["vp"] = self.vp
        for target, key in pairs:
            if (target, key) in self.baseline:
                continue
            try:
                self.baseline[(target, key)] = getattr(eval(target, self.ns), key)
            except Exception:
                pass

    def restore(self, pairs, label):
        """Put the remembered starting values back for the given pairs."""
        self.ns["vp"] = self.vp
        by_target = {}
        for target, key in pairs:
            if (target, key) in self.baseline:
                by_target.setdefault(target, {})[key] = self.baseline[(target, key)]
        for target, values in by_target.items():
            try:
                obj = eval(target, self.ns)
            except Exception:
                continue
            try:
                obj.setValues(**values)
            except Exception:
                for key, value in values.items():  # one by one, skipping read-only ones
                    try:
                        obj.setValues(**{key: value})
                    except Exception:
                        pass


# ---------------------------------------------------------------------------
# Contour limits (stored per view and variable)
# ---------------------------------------------------------------------------
LIMITS_TARGET = "vp.odbDisplay.contourOptions"
AUTO_LIMITS = LIMITS_TARGET + ".setValues(maxAutoCompute=ON, minAutoCompute=ON)"
LIMITS_HELP = "auto | 0, 0.5 | auto, 1 | max 0.1 | min 0"
MINMAX_KEYS = ("maxAutoCompute", "maxValue", "minAutoCompute", "minValue")


def is_limit_command(command):
    """True for vp.odbDisplay.contourOptions.setValues(...) with limit arguments only
    (max / min values and auto flags, intervals, outside-limit colours, min / max marks)."""
    p = rpy_views.parse_call(command)
    return bool(p and p[0] == LIMITS_TARGET and p[1] == "setValues" and not p[2] and p[3]
                and all(k in rpy_views.LIMIT_KEYS for k in p[3]))


def split_limits(commands):
    """(other commands, limit commands) - see is_limit_command."""
    other, limits = [], []
    for c in commands:
        (limits if is_limit_command(c) else other).append(c)
    return other, limits


def _limit_value(text):
    """None = computed automatically, else the value (ValueError if neither)."""
    if text in ("auto", "automatic"):
        return None
    value = float(text)
    if math.isinf(value) or math.isnan(value):
        raise ValueError(text)
    return value


def parse_limits(text):
    """Limit command from short text, or None for "" (= as shown / not set).
      "auto"          -> min and max computed automatically
      "0, 0.5"        -> min 0, max 0.5 (fixed)       "auto, 1" -> min automatic, max 1
      "max 0.1"       -> max 0.1, min automatic        "min 0"   -> min 0, max automatic
      "min 0, max 1"  -> min 0, max 1 (fixed)
    A full limit command (see is_limit_command) is returned unchanged.
    ValueError if not understood."""
    if text is None:
        return None
    t = str(text).strip()
    if not t or t.lower() in ("as shown", "none"):
        return None
    if t.startswith("vp."):
        if not is_limit_command(t):
            raise ValueError("contour limits: %r is no %s.setValues(...) with limit arguments only (%s)"
                             % (t, LIMITS_TARGET, ", ".join(rpy_views.LIMIT_KEYS)))
        return t
    low = t.lower()
    if low in ("auto", "automatic"):
        return AUTO_LIMITS
    if re.search(r"\d,\d", low) and "." not in low:
        raise ValueError("contour limits: %r is ambiguous - write decimals with a point and put ', ' "
                         "between min and max (e.g. 0, 0.5)" % text)
    words = [w for w in re.split(r"[\s,;=:]+", low) if w]
    try:
        if words and words[0] in ("min", "max"):
            keys, values = words[::2], words[1::2]
            if len(keys) != len(values) or len(set(keys)) != len(keys) or not set(keys) <= set(["min", "max"]):
                raise ValueError(t)
            given = dict(zip(keys, values))
        elif len(words) == 2:
            given = {"min": words[0], "max": words[1]}
        else:
            raise ValueError(t)
        lo, hi = _limit_value(given.get("min", "auto")), _limit_value(given.get("max", "auto"))
    except ValueError:
        raise ValueError("contour limits: %r not understood - examples: %s" % (text, LIMITS_HELP))
    if lo is not None and hi is not None and lo >= hi:
        raise ValueError("contour limits: min (%r) must be smaller than max (%r)" % (lo, hi))
    pieces = ["%sAutoCompute=ON" % w if v is None else "%sAutoCompute=OFF, %sValue=%r" % (w, w, v)
              for w, v in (("min", lo), ("max", hi))]
    return "%s.setValues(%s)" % (LIMITS_TARGET, ", ".join(pieces))


def merge_limits(base, override):
    """Limit command: base (e.g. the limits shown in Abaqus, incl. intervals and outside
    colours) with its min / max part replaced by the one of override (e.g. typed limits)."""
    if not base or not override:
        return override or base
    kw = rpy_views.parse_call(base)[3]
    for k in MINMAX_KEYS:
        kw.pop(k, None)
    kw.update(rpy_views.parse_call(override)[3])
    return rpy_views.build_call(LIMITS_TARGET, "setValues", (), kw)


def limits_for(view, variable):
    """Limit command(s) of one picture: the view's own limits for this variable, else the
    limit commands kept in the variable (older settings), else [] (= automatic)."""
    own = (view.get("limits") or {}).get(variable["name"])
    if own:
        return [parse_limits(own)]
    return split_limits(variable["commands"])[1]


def normalize_limits(settings):
    """Older settings kept the contour limits in the variable, shared by all its views.
    Hand them to every view that shows the variable without own limits for it and remove
    them from the variable - the pictures stay the same. Returns new settings."""
    settings = dict(settings)
    moved, variables = {}, []
    for var in settings["VARIABLES"]:
        other, limits = split_limits(var["commands"])
        if limits:
            kw = OrderedDict()
            for c in limits:                     # several commands act like one merged command
                kw.update(rpy_views.parse_call(c)[3])
            moved[var["name"]] = rpy_views.build_call(LIMITS_TARGET, "setValues", (), kw)
            var = dict(var, commands=other)
        variables.append(var)
    if not moved:
        return settings
    views = []
    for view in settings["VIEWS"]:
        own = dict(view.get("limits") or {})
        for name, command in moved.items():
            if name not in own and (not view.get("variables") or name in view["variables"]):
                own[name] = command
        views.append(dict(view, limits=own) if own else view)
    settings["VIEWS"], settings["VARIABLES"] = views, variables
    return settings


def describe_limits(commands):
    """'min 0 (fixed) / max 1 (fixed)', 'automatic', ... for limit command(s) or text."""
    if isinstance(commands, (str, type(u""))):
        commands = [parse_limits(commands)] if parse_limits(commands) else []
    kw = {}
    for c in commands or []:
        p = rpy_views.parse_call(c)
        if p:
            kw.update(p[3])
    if not kw:
        return "not stored (automatic)"
    on = lambda v: str(v).strip() in ("ON", "True", "1")

    def one(which):
        auto = kw.get(which + "AutoCompute")
        if auto is None and which + "Value" not in kw:
            return "%s unchanged" % which
        if auto is not None and on(auto):
            return "%s automatic" % which
        return "%s %s (fixed)" % (which, kw.get(which + "Value", "?"))
    text = "%s / %s" % (one("min"), one("max"))
    return "automatic" if text == "min automatic / max automatic" else text


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------
FRAMES_HELP = "5 | all | last | every 3 | 0, 25, -1 | times 1.5, 3.0"


def parse_frames(spec):
    """Frame choice as a dict, from a dict or from short text; None = not set.
      "5" / 5 / "uniform 5"  -> 5 frames evenly spread (first and last included)
      "all", "last"
      "every 3"              -> every 3rd frame (+ the last one)
      "0, 25, -1"            -> these frame numbers (negative = counted from the end)
      "indices 7"            -> a single frame number
      "times 1.5, 3.0"       -> the frames nearest to these step times
      "" / "default"         -> None (use the default)
    Raises ValueError for text it does not understand."""
    if spec is None or isinstance(spec, dict):
        return spec
    if isinstance(spec, bool):
        raise ValueError("frames: %r not understood (%s)" % (spec, FRAMES_HELP))
    if isinstance(spec, int):
        spec = str(spec)
    text = str(spec).strip().lower()
    if text in ("", "default", "none"):
        return None
    if text in ("all", "last"):
        return {"MODE": text}
    m = re.match(r"^(?:uniform\s+)?(\d+)$", text)
    if m:
        if int(m.group(1)) == 0:   # would silently give the last frame
            raise ValueError("frames: 0 frames? For frame number 0 write  indices 0  (or  0, 10, -1)")
        return {"MODE": "uniform", "COUNT": int(m.group(1))}
    m = re.match(r"^every\s+(\d+)$", text)
    if m:
        return {"MODE": "every", "EVERY": int(m.group(1)), "INCLUDE_LAST": True}
    m = re.match(r"^(?:t|times?)\s+(.+)$", text)
    try:
        if m:
            return {"MODE": "times", "TIMES": [float(x) for x in re.split(r"[,;\s]+", m.group(1).strip()) if x]}
        body = re.sub(r"^indices?\s+", "", text)
        values = [int(x) for x in re.split(r"[,;\s]+", body) if x]
        if values and ("," in text or ";" in text or text.startswith("indic") or len(values) > 1 or values[0] < 0):
            return {"MODE": "indices", "INDICES": values}
    except ValueError:
        pass
    raise ValueError("frames: %r not understood - examples: %s" % (spec, FRAMES_HELP))


def describe_frames(spec):
    s = parse_frames(spec)
    if not s:
        return "default"
    mode = str(s.get("MODE", "uniform")).lower()
    if mode == "uniform":
        return "%s evenly spread" % s.get("COUNT", 10)
    if mode == "every":
        return "every %s" % s.get("EVERY", 5)
    if mode == "indices":
        return "frames %s" % ", ".join(str(i) for i in s.get("INDICES", []))
    if mode == "times":
        return "at t = %s" % ", ".join("%g" % t for t in s.get("TIMES", []))
    return mode


def choose_frames(records, spec):
    """Pick frames from all FrameRecords of the step. spec: dict or short text (see
    parse_frames); MODE "uniform" (COUNT, evenly spread incl. first and last), "every"
    (EVERY, INCLUDE_LAST), "indices" (INDICES, negative = from the end), "times" (TIMES,
    step time, nearest frame), "all", "last". None -> 10 evenly spread."""
    spec = parse_frames(spec) or {"MODE": "uniform", "COUNT": 10}
    n = len(records)
    if n == 0:
        return []
    mode = str(spec.get("MODE", "uniform")).lower()
    if mode == "all":
        idx = range(n)
    elif mode == "last":
        idx = [n - 1]
    elif mode == "every":
        every = max(1, int(spec.get("EVERY", 5)))
        idx = list(range(0, n, every))
        if spec.get("INCLUDE_LAST", True):
            idx.append(n - 1)
    elif mode == "indices":
        idx = [i if i >= 0 else n + i for i in spec.get("INDICES", [])]
    elif mode == "times":
        idx = [min(range(n), key=lambda j: abs(records[j].step_time - float(t))) for t in spec.get("TIMES", [])]
    else:  # uniform
        count = max(1, int(spec.get("COUNT", 10)))
        if count >= n:
            idx = range(n)
        elif count == 1:
            idx = [n - 1]
        else:  # round half up (Python 2 and 3 round() differ at .5)
            idx = [int(math.floor(i * (n - 1) / float(count - 1) + 0.5)) for i in range(count)]
    return [records[i] for i in sorted(set(i for i in idx if 0 <= i < n))]


def frames_at_times(records, times):
    """FrameRecords nearest to the given step times."""
    out = []
    for t in times:
        out.append(min(records, key=lambda r: abs(r.step_time - t)))
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def image_path(image_root, job, variable, view, rec):
    name = "f%04d_t%s.png" % (rec.index, ("%g" % round(rec.step_time, 6)).replace("-", "m"))
    return os.path.join(image_root, job, rpy_views.sanitize(variable), rpy_views.sanitize(view), name)


def print_png(session, vp, path, png_constant):
    """path ends with .png and is passed complete: Abaqus adds '.png' itself only when
    the name has no extension - 'f0006_t0.6' would count as having the extension '.6'
    and be saved without .png."""
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    session.printToFile(fileName=odb_tools.native(path), format=png_constant, canvasObjects=(vp,))


def repair_missing_extension(path):
    """Images saved by an earlier version without '.png' get it added (they are fine
    otherwise), so they count as existing and are not exported again."""
    bare = path[:-4]
    if not os.path.isfile(path) and os.path.isfile(bare):
        os.rename(bare, path)
    return os.path.isfile(path)


def zip_folder(folder, zip_path, delete=True):
    """Store a job folder as one ZIP (PNGs do not shrink, but 1 file copies much faster)."""
    zf = zipfile.ZipFile(zip_path + ".tmp", "w", zipfile.ZIP_STORED, allowZip64=True)
    try:
        for root, _, files in os.walk(folder):
            for fn in sorted(files):
                full = os.path.join(root, fn)
                zf.write(full, os.path.relpath(full, os.path.dirname(folder)))
    finally:
        zf.close()
    if os.path.exists(zip_path):
        os.remove(zip_path)
    os.rename(zip_path + ".tmp", zip_path)
    if delete:
        shutil.rmtree(folder)


if __name__ == "__main__":
    # quick check inside Abaqus: one screenshot of the current viewport + frame choice
    if odb_tools.session is None:
        raise SystemExit("Run this inside Abaqus/CAE or Viewer (File > Run Script) with an ODB displayed.")
    import tempfile
    rep = Replayer()
    odb = odb_tools.viewport_odb()
    if odb is None:
        raise SystemExit("Display an ODB in the viewport first.")
    step = list(odb.steps.keys())[-1]
    recs = odb_tools.select_frames(odb, step)
    chosen = choose_frames(recs, {"MODE": "uniform", "COUNT": 10})
    log("Step %s: %d frames, uniform 10 -> indices %s" % (step, len(recs), [r.index for r in chosen]))
    path = os.path.join(tempfile.gettempdir(), "image_export_test.png")
    print_png(rep.session, rep.vp, path, rep.ns["PNG"])
    log("Test screenshot of the current viewport: %s" % path)
