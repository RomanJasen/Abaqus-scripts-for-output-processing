"""
odb_tools.py - shared helpers for working with Abaqus output databases.

* listing / opening ODB files
* IMPLICIT / EXPLICIT detection
* frame selection -> FrameRecord list (the ONE source of truth for frame sync)
* node / element set lookup, nodal and element-nodal value reading
  (single / double precision handled automatically)
* resolve_demo_inputs(): how the stand-alone demos of all modules get their input

FRAME SYNC - why FrameRecord.index is the key
---------------------------------------------
frame.frameId is NOT the frame's position in step.frames: in Abaqus/Explicit it
equals the increment number (0, 45633, 91266, ...). Everything that addresses a
frame (step.frames[i], session activeFrames, the Frame slider in Abaqus/CAE) uses
the position. FrameRecord.index is that position and is used to key every result.

STAND-ALONE RUN of this module: prints the frame table of an ODB.
Edit DEMO_SETTINGS below, then Abaqus/CAE or Viewer: File > Run Script...
"""
from __future__ import print_function

import os
import sys
import time
import inspect

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:  # Abaqus/CAE kernel
    from abaqus import session
except ImportError:  # plain python, or abaqus python without CAE
    session = None

# =============================================================================
# DEMO SETTINGS - only used when THIS file is run on its own
# =============================================================================
DEMO_SETTINGS = {
    "ODB": None,             # full path to .odb, None -> see resolve_demo_inputs()
    "STEP": None,            # None -> step of the last export, else the last step
    "MIN_DT": None,          # min. step time between frames, None = every frame
    "FRAME_INDICES": None,   # e.g. [0, 10, -1] to test only a few frames, None = all
}
# =============================================================================


class FrameSyncError(RuntimeError):
    """Raised when force and displacement data cannot be matched frame by frame."""


# ---------------------------------------------------------------------------
# Progress messages
# ---------------------------------------------------------------------------
_LOG_PATH = [None]


def set_log_file(path, header=""):
    """Start a new log file (overwritten); every log() message is appended to it."""
    _LOG_PATH[0] = path
    try:
        with open(path, "w") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), header))
    except (IOError, OSError) as e:
        _LOG_PATH[0] = None
        print("WARNING: log file %s could not be created: %s" % (path, e))


def log(message=""):
    """print() that is shown at once and also written to the log file.
    Abaqus/CAE and Viewer buffer script output and often show it only when the
    script ends - the flush and the log file make progress visible while it runs."""
    print(message)
    try:
        sys.stdout.flush()
    except Exception:
        pass
    if _LOG_PATH[0]:
        try:
            with open(_LOG_PATH[0], "a") as f:
                f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), message))
        except Exception:
            pass


def progress(message, done, total, what=""):
    """Progress in the Abaqus status bar (CAE/Viewer GUI only; silently ignored elsewhere)."""
    try:
        from abaqus import milestone
        milestone(message, what, done, total)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Text type (Abaqus <= 2023 = Python 2: Abaqus functions reject 'unicode')
# ---------------------------------------------------------------------------
try:
    _UNICODE = unicode  # noqa: F821  Python 2
except NameError:
    _UNICODE = None     # Python 3 (Abaqus 2024+)
_FS_ENCODING = sys.getfilesystemencoding() or "mbcs"


def native(value):
    """Convert text - also inside lists, tuples and dicts - to the plain 'str' type.

    Abaqus 2021 runs Python 2 and its functions refuse 'unicode' arguments:
        TypeError: name; found 'unicode', expecting a recognized type filling string dict
    Tkinter (Browse..., edited fields, list items) and os.listdir(u'...') return
    unicode, so every string that goes to Abaqus passes through here first.
    Non-ASCII paths are encoded with the file-system code page (mbcs on Windows)."""
    if isinstance(value, dict):
        return dict((native(k), native(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return type(value)(native(v) for v in value)
    if _UNICODE is not None:
        if isinstance(value, _UNICODE):
            try:
                return value.encode("ascii")
            except UnicodeEncodeError:
                return value.encode(_FS_ENCODING)
        return value
    if isinstance(value, bytes):
        return value.decode(_FS_ENCODING)
    if isinstance(value, str):
        return str(value)  # also turns str subclasses into a plain str
    return value


def to_text(value):
    """Opposite of native() (also inside lists, tuples and dicts): text for GUI
    widgets and JSON (unicode in Python 2), so non-ASCII paths round-trip correctly."""
    if isinstance(value, dict):
        return dict((to_text(k), to_text(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return type(value)(to_text(v) for v in value)
    if _UNICODE is not None and isinstance(value, str):
        return value.decode(_FS_ENCODING)
    return value


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
def list_odbs(folder, name_filter=""):
    """Sorted (reverse, as the original A_Read_all_jobs) list of .odb names in folder."""
    names = [native(f) for f in os.listdir(native(folder))
             if f.lower().endswith(".odb") and name_filter.upper() in f.upper()]
    names.sort(reverse=True)
    return names


def job_name(odb_path):
    """'C:/x/My_job.odb' -> 'MY_JOB' (upper case, as used for database folders)."""
    base = os.path.basename(odb_path)
    if base.lower().endswith(".odb"):
        base = base[:-4]
    return base.upper()


def open_odb(odb_path, read_only=True):
    """Open an ODB in the CAE session (needed for free-body cuts), else via odbAccess."""
    odb_path = native(odb_path)
    if not os.path.isfile(odb_path):
        raise IOError("ODB file not found: %s" % odb_path)
    if session is not None:
        return session.openOdb(name=odb_path, readOnly=read_only)
    from odbAccess import openOdb
    return openOdb(path=odb_path, readOnly=read_only)


def _same_file(a, b):
    return os.path.normcase(os.path.abspath(native(a))) == os.path.normcase(os.path.abspath(native(b)))


def find_open_odb(odb_path):
    """The Odb if this file is already open in the CAE/Viewer session, else None."""
    if session is None:
        return None
    try:
        for key in session.odbs.keys():
            o = session.odbs[key]
            if _same_file(key, odb_path) or _same_file(o.name, odb_path):
                return o
    except Exception:
        pass
    return None


def open_or_reuse(odb_path, read_only=True):
    """(odb, opened_here). An ODB that is already open in the session (e.g. shown in
    the viewport) is reused, and opened_here=False tells the caller not to close it."""
    odb = find_open_odb(odb_path)
    if odb is not None:
        return odb, False
    return open_odb(odb_path, read_only), True


def get_step(odb, step_name):
    """Return the step, accepting case differences. Raises KeyError listing available steps.
    The repository is always indexed with its own key (a plain str)."""
    keys = list(odb.steps.keys())
    wanted = native(step_name)
    for k in keys:
        if k == wanted:
            return odb.steps[k]
    for k in keys:
        if k.upper() == str(wanted).upper():
            return odb.steps[k]
    raise KeyError("Step %r not found in ODB. Available steps: %s" % (step_name, keys))


def detect_analysis_type(odb, step_name=None):
    """Return 'EXPLICIT' or 'IMPLICIT'."""
    try:
        code = str(odb.jobData.analysisCode).upper()
        if "EXPLICIT" in code:
            return "EXPLICIT"
        if "STANDARD" in code:
            return "IMPLICIT"
    except Exception:
        pass
    if step_name is not None:
        try:
            if "EXPLICIT" in str(get_step(odb, step_name).procedure).upper():
                return "EXPLICIT"
        except Exception:
            pass
    return "IMPLICIT"


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------
class FrameRecord(object):
    """One exported frame.

    index       position in step.frames  (= Abaqus/CAE frame number)  <- SYNC KEY
    frame_id    frame.frameId            (= increment number in Explicit)
    increment   frame.incrementNumber
    step_time   frame.frameValue
    total_time  step.totalTime + frame.frameValue (x-axis of session XY data)
    """
    __slots__ = ("index", "frame_id", "increment", "step_time", "total_time", "frame")

    def __init__(self, index, frame, step_total_time):
        self.index = index
        self.frame = frame
        self.frame_id = frame.frameId
        self.increment = frame.incrementNumber
        self.step_time = float(frame.frameValue)
        self.total_time = float(step_total_time) + self.step_time

    def __repr__(self):
        return "FrameRecord(index=%d, frameId=%d, increment=%d, t=%g)" % (
            self.index, self.frame_id, self.increment, self.step_time)


def select_frames(odb, step_name, min_time_increment=None, frame_indices=None):
    """Build the list of frames to export.

    min_time_increment  keep a frame only if it is at least this much step time
                        after the previously kept frame (first frame always kept).
                        None / 0 -> keep every frame.
    frame_indices       optional explicit list of frame positions (overrides the above).
    """
    step = get_step(odb, step_name)
    frames = step.frames  # fetch the repository once (see Scripting Guide 9.9.x)
    n = len(frames)
    total = step.totalTime

    if frame_indices is not None:
        idx = sorted(set(i if i >= 0 else n + i for i in frame_indices))
        return [FrameRecord(i, frames[i], total) for i in idx if 0 <= i < n]

    records = []
    last_t = None
    for i in range(n):
        fr = frames[i]
        t = float(fr.frameValue)
        if min_time_increment and last_t is not None:
            if t - last_t < min_time_increment * (1.0 - 1e-6):
                continue
        records.append(FrameRecord(i, fr, total))
        last_t = t
    return records


def print_frame_table(records, limit=None):
    print("  %6s %10s %10s %14s %14s" % ("index", "frameId", "increment", "step time", "total time"))
    for k, r in enumerate(records):
        if limit is not None and limit <= k < len(records) - 3:
            if k == limit:
                print("  ... (%d more)" % (len(records) - limit - 3))
            continue
        print("  %6d %10d %10d %14.6g %14.6g" % (r.index, r.frame_id, r.increment, r.step_time, r.total_time))


# ---------------------------------------------------------------------------
# Sets and field values
# ---------------------------------------------------------------------------
def set_key(repo, set_name, kind="Node"):
    """The repository's own key for set_name (exact match first, then case-insensitive)."""
    keys = list(repo.keys())
    wanted = native(set_name)
    for k in keys:
        if k == wanted:
            return k
    for k in keys:
        if k.upper() == wanted.upper():
            return k
    raise KeyError("%s set %r not found in rootAssembly: %s" % (kind, set_name, keys))


def _get_set(repo, set_name, kind):
    return repo[set_key(repo, set_name, kind)]


def get_node_set(odb, set_name):
    """Assembly-level node set, accepting the upper-casing Abaqus applies to names."""
    return _get_set(odb.rootAssembly.nodeSets, set_name, "Node")


def get_element_set(odb, set_name):
    """Assembly-level element set, accepting the upper-casing Abaqus applies to names."""
    return _get_set(odb.rootAssembly.elementSets, set_name, "Element")


def node_key(instance_name, label):
    """Unique node / element id across instances."""
    return (instance_name or "", int(label))


def set_nodes(node_set):
    """[(key, (x, y, z)), ...] for every node of an assembly set (all instances)."""
    out = []
    for block in node_set.nodes:  # one block per instance
        for n in block:
            out.append((node_key(n.instanceName, n.label), n.coordinates))
    return out


def set_elements(element_set):
    """[(element_key, [node_key, ...]), ...] for every element of an assembly set."""
    out = []
    for block in element_set.elements:
        for e in block:
            inst = e.instanceName
            out.append((node_key(inst, e.label), [node_key(inst, n) for n in e.connectivity]))
    return out


def has_field(frame, name):
    return name in frame.fieldOutputs.keys()


def _value_reader(values):
    """Pick .dataDouble for double-precision output (typical for Explicit), else .data."""
    try:
        from abaqusConstants import DOUBLE_PRECISION
        if len(values) and values[0].precision == DOUBLE_PRECISION:
            return lambda v: v.dataDouble
    except Exception:
        pass
    return lambda v: v.data


def read_nodal_vectors(frame, region, field="U"):
    """{node_key: vector} for all nodes of region, in ONE getSubset call."""
    values = frame.fieldOutputs[field].getSubset(region=region).values
    read = _value_reader(values)
    out = {}
    for v in values:
        inst = v.instance.name if v.instance is not None else ""
        out[node_key(inst, v.nodeLabel)] = read(v)
    return out


def read_element_nodal(frame, element_region, field):
    """{(element_key, node_key): value} of an element-nodal field (e.g. NFORC1)."""
    values = frame.fieldOutputs[field].getSubset(region=element_region).values
    read = _value_reader(values)
    out = {}
    for v in values:
        inst = v.instance.name if v.instance is not None else ""
        out[(node_key(inst, v.elementLabel), node_key(inst, v.nodeLabel))] = read(v)
    return out


# ---------------------------------------------------------------------------
# Demo input resolution (shared by the stand-alone runs of all modules)
# ---------------------------------------------------------------------------
def script_args():
    """Arguments after '--' on the command line.
    Inside Abaqus/CAE sys.argv holds Abaqus' own options (e.g. '-lmlog ON'),
    so without '--' nothing is taken from it."""
    argv = list(sys.argv)
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    if session is None:  # plain python / abaqus python: normal argv
        return [a for a in argv[1:] if not a.lower().endswith(".py")]
    return []


def saved_export_defaults(script_dir=None):
    """(odb_path, step) for demos, from the settings of the last export
    (1_Export_Auto_settings.json in the folder of A_1_Export_Auto.py = the parent of
    this module's folder); otherwise the first .odb in that folder or in the
    current folder. (None, None) if nothing is found."""
    script_dir = script_dir or os.path.dirname(_HERE)
    saved = {}
    try:
        import export_settings  # imported here: export_settings itself imports odb_tools
        saved = export_settings.saved_settings(script_dir)
    except Exception:
        pass
    step = saved.get("STEP") or None
    for folder in (saved.get("ODB_FOLDER"), script_dir, os.getcwd()):
        if not folder or not os.path.isdir(folder):
            continue
        try:
            available = list_odbs(folder)
        except OSError:
            continue
        preferred = saved.get("ODB_NAMES") if folder == saved.get("ODB_FOLDER") else None
        for n in list(preferred or []) + available:
            if n in available:
                return os.path.join(folder, n), step
    return None, step


def viewport_odb():
    """The ODB shown in the current viewport of Abaqus/CAE or Viewer, or None."""
    if session is None:
        return None
    try:
        obj = session.viewports[session.currentViewportName].displayedObject
        if obj is not None and hasattr(obj, "steps") and hasattr(obj, "rootAssembly"):
            return obj
    except Exception:
        pass
    return None


def _gui_available():
    return session is not None and "nogui" not in " ".join(sys.argv).lower()


def ask_file(title="Select ODB file", filetypes=(("Abaqus ODB", "*.odb"),)):
    """Tk file dialog; returns '' if Tk is unavailable or cancelled."""
    try:
        try:
            import Tkinter as tk
            import tkFileDialog as fd
        except ImportError:
            import tkinter as tk
            from tkinter import filedialog as fd
        root = tk.Tk()
        root.withdraw()
        path = fd.askopenfilename(title=title, filetypes=filetypes, parent=root)
        root.destroy()
        del root
        return path or ""
    except Exception:
        return ""
    finally:
        import gc
        gc.collect()   # the Tk interpreter must not outlive the dialog in the Abaqus kernel


def ask_choice(prompt, options, default):
    """Abaqus getInput prompt listing options (only with the CAE/Viewer GUI), else default."""
    if not _gui_available():
        return default
    try:
        from abaqus import getInput
        shown = options if len(options) <= 40 else options[:40] + ["... (%d more)" % (len(options) - 40)]
        answer = getInput("%s\nAvailable:\n  %s" % (prompt, "\n  ".join(shown)), default)
    except Exception:
        return default
    if answer is None:
        raise SystemExit("Cancelled by user")
    return answer.strip() or default


class DemoInputs(object):
    """Result of resolve_demo_inputs(). Call close() at the end (only closes ODBs it opened)."""

    def __init__(self, odb, odb_path, step, set_name, frames, owns_odb):
        self.odb, self.odb_path, self.step, self.set_name = odb, odb_path, step, set_name
        self.frames, self.owns_odb = frames, owns_odb

    def close(self):
        if self.owns_odb:
            self.odb.close()


def resolve_demo_inputs(settings, set_filter=None, need_set=True):
    """Inputs for a stand-alone demo run.

    settings  the module's DEMO_SETTINGS dict (keys ODB, STEP, SET, MIN_DT, FRAME_INDICES)

    ODB : DEMO_SETTINGS["ODB"] -> args after '--' -> ODB open in the current viewport
          -> first ODB of the last export (1_Export_Auto_settings.json) or first .odb
             in the folder of A_1_Export_Auto.py -> file dialog
    STEP: DEMO_SETTINGS["STEP"] -> 2nd arg -> step of the last export -> last step of the ODB
    SET : DEMO_SETTINGS["SET"] -> 3rd arg -> prompt (GUI) listing suitable sets
          -> first suitable set (set_filter(name, odb) -> bool decides what is suitable)
    """
    args = script_args()
    odb_path = native(settings.get("ODB") or (args[0] if len(args) > 0 else None))
    step = native(settings.get("STEP") or (args[1] if len(args) > 1 else None))
    set_name = native(settings.get("SET") or (args[2] if len(args) > 2 else None))

    odb, owns = None, True
    if not odb_path:
        odb = viewport_odb()
        if odb is not None:
            odb_path, owns = odb.name, False
            print("Using the ODB open in the viewport:", odb_path)
    saved_path, saved_step = saved_export_defaults()
    if not odb_path:
        odb_path = saved_path
    if not odb_path:
        odb_path = ask_file()
    if not odb_path:
        raise SystemExit("No ODB given: set DEMO_SETTINGS['ODB'] at the top of the module, open the ODB "
                         "in the viewport, or run  abaqus cae noGUI=<module>.py -- <path.odb> [STEP] [SET]")
    if odb is None:
        odb_path = native(odb_path)
        odb, owns = open_or_reuse(odb_path)

    steps = list(odb.steps.keys())
    if not step:
        step = saved_step if saved_step in steps else steps[-1]

    if need_set and not set_name:
        names = sorted(odb.rootAssembly.nodeSets.keys())
        candidates = [n for n in names if set_filter is None or set_filter(n, odb)]
        if not candidates:
            raise SystemExit("No suitable SET found in %s. Sets: %s" % (odb_path, names))
        set_name = native(ask_choice("SET to use for the demo:", candidates, candidates[0]))

    frames = select_frames(odb, step, min_time_increment=settings.get("MIN_DT"),
                           frame_indices=settings.get("FRAME_INDICES"))
    print("DEMO INPUT  odb=%s\n            step=%s  set=%s  frames=%d  (%s analysis)" % (
        odb_path, step, set_name, len(frames), detect_analysis_type(odb, step)))
    return DemoInputs(odb, odb_path, step, set_name, frames, owns)


if __name__ == "__main__":
    demo = resolve_demo_inputs(DEMO_SETTINGS, need_set=False)
    try:
        print("Steps:", list(demo.odb.steps.keys()))
        print("Selected frames of step %s:" % demo.step)
        print_frame_table(demo.frames, limit=15)
    finally:
        demo.close()
