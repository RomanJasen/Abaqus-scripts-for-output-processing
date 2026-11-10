"""
rpy_views.py - read view settings from an Abaqus replay file (abaqus.rpy).

Everything you do in Abaqus/CAE or Viewer is written to abaqus.rpy as Python
commands. Every "File > Print" is written as session.printToFile(...), so each
print marks one SHOT. For every print this module rebuilds the complete display
state at that moment and returns it as short command lists:

  view      camera, section (view) cuts, display group, contour type, visible
            edges, annotations, background, deformation scale, ...
  variable  primary variable, plot state (contours / plain)
  limits    contour limits of the picture (stored with the view, per variable)

How the state is rebuilt from the command stream:
  * setValues(...) calls are MERGED per object (latest value of every argument
    wins) - Abaqus often writes only the changed values, e.g. zoom without
    cameraPosition
  * display group operations (replace/remove/add/either/intersect) are kept in
    order since the last 'replace', with the leaf definitions they use
  * cliCommand(...) wrappers (commands typed in the command line) are unwrapped
  * session.viewports['Viewport: 1'] / [session.currentViewportName] -> vp

Print names: "<view>__<variable>" groups prints of one view; the part before "__"
becomes the view name. A later print of the same view name replaces it.

No Abaqus import: runs in any Python. Stand-alone: prints what would be captured
from the newest abaqus.rpy (next to A_2_Image_export_Auto.py or in the current folder):
    python rpy_views.py [path/to/abaqus.rpy]
"""
from __future__ import print_function

import os
import re
import ast
import sys
import glob
from collections import OrderedDict

VIEW_OBJECT_ORDER = ("session.graphicsOptions", "vp", "vp.viewportAnnotationOptions")
# contourOptions arguments that are contour LIMITS (stored per view and variable),
# not part of the view's general look
LIMIT_KEYS = ("maxAutoCompute", "maxValue", "minAutoCompute", "minValue", "intervalType", "intervalValues",
              "outsideLimitsMode", "outsideLimitsAboveColor", "outsideLimitsBelowColor",
              "showMaxLocation", "showMinLocation")
# arguments never captured (they point to objects that do not exist in another session)
SKIP_KEYS = {"vp": ("displayedObject",),
             "vp.odbDisplay": ("visibleDisplayGroups", "freeBodyNames", "freeBody")}
PRINT_OBJECTS = ("session.printOptions", "session.pngOptions", "session.tiffOptions",
                 "session.svgOptions", "session.epsOptions", "session.psOptions")
# objects whose settings are not part of a view (animation, CAE model/part display)
EXCLUDED_TARGETS = ("vp.animationController", "vp.assemblyDisplay", "vp.partDisplay")

_VP = [re.compile(r"session\.viewports\[\s*session\.currentViewportName\s*\]"),
       re.compile(r"session\.viewports\[\s*'[^']*'\s*\]"),
       re.compile(r'session\.viewports\[\s*"[^"]*"\s*\]')]
_CALL = re.compile(r"^(?P<target>[A-Za-z_][\w\.]*(?:\[[^\]]*\])?(?:\.[A-Za-z_]\w*)*)\.(?P<method>[A-Za-z_]\w*)\((?P<args>.*)\)\s*$", re.S)
_ASSIGN = re.compile(r"^(?P<name>[A-Za-z_]\w*)\s*=(?!=)\s*(?P<value>.+)$", re.S)
_CLI = re.compile(r'^cliCommand\(\s*(?:"""|\'\'\')(?P<inner>.*)(?:"""|\'\'\')\s*\)\s*$', re.S)


# ---------------------------------------------------------------------------
# Reading statements
# ---------------------------------------------------------------------------
def find_newest_rpy(folders):
    """Newest abaqus.rpy* (by modification time) in the given folders, or None."""
    files = []
    for folder in folders:
        if folder and os.path.isdir(folder):
            files.extend(f for f in glob.glob(os.path.join(folder, "abaqus.rpy*"))
                         if re.search(r"abaqus\.rpy(\.\d+)?$", f, re.I))
    return max(files, key=os.path.getmtime) if files else None


def _complete(text):
    """True when brackets are balanced outside string literals."""
    depth, i, q = 0, 0, None
    while i < len(text):
        c = text[i]
        if q:
            if text.startswith(q, i) and (len(q) == 3 or text[i - 1] != "\\"):
                i += len(q) - 1
                q = None
        elif text.startswith('"""', i) or text.startswith("'''", i):
            q = text[i:i + 3]
            i += 2
        elif c in "'\"":
            q = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return depth <= 0 and q is None


def split_statements(text):
    """Python statements of an rpy text: comments dropped, continuation lines joined,
    cliCommand wrappers removed, viewport references replaced by 'vp'."""
    out, cur = [], ""
    for line in text.splitlines():
        if not cur and (not line.strip() or line.lstrip().startswith("#")):
            continue
        cur = (cur + " " + line.strip()) if cur else line.strip()
        if _complete(cur):
            m = _CLI.match(cur)
            if m:
                out.extend(split_statements(m.group("inner")))
            else:
                for p in _VP:
                    cur = p.sub("vp", cur)
                cur = re.sub(r"([(\[]) +", r"\1", cur)  # "( x" left by joined lines ("x, )" tuples stay intact)
                out.append(cur)
            cur = ""
    return out


def read_statements(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = None
    for codec in ("utf-8", "mbcs", "latin-1"):  # rpy files are written in the Windows code page (mbcs)
        try:
            text = raw.decode(codec)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    return split_statements(text)


# ---------------------------------------------------------------------------
# Parsing one call
# ---------------------------------------------------------------------------
def split_args(args):
    """'a, b=1, c=(1, 2), ' -> (['a'], OrderedDict(b='1', c='(1, 2)'))."""
    parts, cur, depth, q = [], "", 0, None
    i = 0
    while i < len(args):
        c = args[i]
        if q:
            cur += c
            if c == q and args[i - 1] != "\\":
                q = None
        elif c in "'\"":
            q = c
            cur += c
        elif c in "([{":
            depth += 1
            cur += c
        elif c in ")]}":
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    if cur.strip():
        parts.append(cur.strip())
    positional, kwargs = [], OrderedDict()
    for p in parts:
        m = re.match(r"^([A-Za-z_]\w*)\s*=(?!=)\s*(.*)$", p, re.S)
        if m:
            kwargs[m.group(1)] = m.group(2).strip()
        elif p:
            positional.append(p)
    return positional, kwargs


def parse_call(stmt):
    """(target, method, positional, kwargs) or None for statements that are no call."""
    m = _CALL.match(stmt)
    if not m:
        return None
    pos, kw = split_args(m.group("args"))
    return m.group("target"), m.group("method"), pos, kw


def build_call(target, method, positional=(), kwargs=None):
    args = list(positional) + ["%s=%s" % (k, v) for k, v in (kwargs or {}).items()]
    return "%s.%s(%s)" % (target, method, ", ".join(args))


def literal(text, default=None):
    try:
        return ast.literal_eval(text)
    except Exception:
        return default


def setvalues_objects(commands):
    """[(target, [kwarg names])] of the setValues(...) calls in a command list."""
    out = []
    for c in commands:
        p = parse_call(c)
        if p and p[1] == "setValues" and p[3]:
            out.append((p[0], list(p[3].keys())))
    return out


# ---------------------------------------------------------------------------
# Capturing views from the statement stream
# ---------------------------------------------------------------------------
def sanitize(name):
    """Safe for folder / file names: letters, digits, '_' and '-' only."""
    name = re.sub(r"[^\w\-]+", "_", str(name)).strip("_")
    return name or "view"


def variable_name(primary_stmt, plot_state):
    """'S' + (INVARIANT, 'Max. Principal') -> 'S_Max_Principal'; no contours -> 'plain'."""
    if plot_state is not None and "CONTOURS" not in plot_state.upper():
        return "plain"
    if not primary_stmt:
        return "shape"
    p = parse_call(primary_stmt)
    kw = p[3] if p else {}
    label = literal(kw.get("variableLabel", "''"), "var")
    ref = kw.get("refinement")
    if ref:
        m = re.findall(r"'([^']*)'|\"([^\"]*)\"", ref)
        comp = "".join(a or b for a, b in m)
        if comp:
            if comp.upper().startswith(label.upper()):
                return sanitize(comp)
            return sanitize("%s_%s" % (label, comp))
    return sanitize(label)


class _State(object):
    def __init__(self):
        self.merged = OrderedDict()      # target -> OrderedDict(kwarg -> value text)
        self.limits = OrderedDict()      # contour limit kwargs (stored with the view, per variable)
        self.plot = OrderedDict()        # display.setValues kwargs (variable)
        self.primary = None
        self.extra_vars = OrderedDict()  # setDeformedVariable / setSymbolVariable
        self.camera_base = None
        self.camera = OrderedDict()
        self.camera_rel = []
        self.dg_seq = []
        self.assign = {}
        self.cut_defs = OrderedDict()
        self.printing = OrderedDict()
        self.step = None
        self.odb = None
        self.odb_vars = set()   # variable names holding an ODB (o2 = session.openOdb(...), odb = session.odbs[...])
        self.shows_odb = True   # False while an XY plot, CAE model etc. is displayed

    def merge(self, target, kwargs):
        d = self.merged.setdefault(target, OrderedDict())
        for k, v in kwargs.items():
            if k in SKIP_KEYS.get(target, ()):
                continue
            d.pop(k, None)
            d[k] = v
        if not d:
            del self.merged[target]

    def feed(self, stmt):
        a = _ASSIGN.match(stmt)
        if a and not stmt.startswith("vp."):
            value = a.group("value").strip()
            if value.startswith("dgo."):
                self.assign[a.group("name")] = stmt
            elif value.startswith("session.openOdb("):
                kw = split_args(value[len("session.openOdb("):-1])[1]
                self.odb = literal(kw.get("name", "None"))
                self.odb_vars.add(a.group("name"))
            elif value.startswith("session.odbs["):
                self.odb_vars.add(a.group("name"))
            else:
                self.odb_vars.discard(a.group("name"))
            return
        p = parse_call(stmt)
        if not p:
            return
        target, method, pos, kw = p
        if target.startswith(EXCLUDED_TARGETS):
            return
        if target == "vp" and method == "setValues" and "displayedObject" in kw:
            shown = kw["displayedObject"]
            self.shows_odb = (shown in self.odb_vars or "odbs[" in shown or "openOdb" in shown)
        if target in PRINT_OBJECTS and method == "setValues":
            d = self.printing.setdefault(target, OrderedDict())
            d.update(kw)
        elif target == "vp.view":
            if method in ("fitView", "setViewpoint") or (method == "setValues" and pos):
                self.camera_base = build_call(target, method, pos, {} if method == "setValues" else kw)
                self.camera = OrderedDict()
                self.camera_rel = []
                if method == "setValues":
                    self.camera.update(kw)
            elif method == "setValues":
                for k, v in kw.items():
                    self.camera.pop(k, None)
                    self.camera[k] = v
            else:
                self.camera_rel.append(stmt)
        elif target == "vp.odbDisplay" and method == "setPrimaryVariable":
            self.primary = stmt
        elif target == "vp.odbDisplay" and method in ("setDeformedVariable", "setSymbolVariable", "setStatusVariable"):
            self.extra_vars[method] = stmt
        elif target == "vp.odbDisplay" and method == "setFrame":
            self.step = literal(kw.get("step", "None"), self.step)
        elif target == "vp.odbDisplay" and method == "ViewCut":
            self.cut_defs[literal(kw.get("name", "''"), stmt)] = stmt
        elif target == "vp.odbDisplay.displayGroup":
            leaf = kw.get("leaf")
            pre = [self.assign[leaf]] if leaf in self.assign else []
            if method == "replace":
                self.dg_seq = pre + [stmt]
            else:
                self.dg_seq.extend(pre + [stmt])
        elif method == "setValues" and target == "vp.odbDisplay.contourOptions":
            view_kw = OrderedDict((k, v) for k, v in kw.items() if k not in LIMIT_KEYS)
            for k, v in kw.items():
                if k in LIMIT_KEYS:
                    self.limits.pop(k, None)
                    self.limits[k] = v
            if view_kw:
                self.merge(target, view_kw)
        elif method == "setValues" and target == "vp.odbDisplay.display":
            for k, v in kw.items():
                self.plot.pop(k, None)
                self.plot[k] = v
        elif method == "setValues" and (target == "session.graphicsOptions" or target == "vp"
                                        or target.startswith("vp.")):
            if not target.startswith("vp.assemblyDisplay") and not target.startswith("vp.partDisplay"):
                self.merge(target, kw)

    # -- snapshot at a print -------------------------------------------------
    def view_commands(self):
        cmds, done = [], set()

        def emit(target):
            if target in self.merged and target not in done:
                cmds.append(build_call(target, "setValues", (), self.merged[target]))
                done.add(target)

        for t in VIEW_OBJECT_ORDER:
            emit(t)
        for t in self.merged:            # other viewport-level objects
            if t.startswith("vp.") and not t.startswith("vp.odbDisplay"):
                emit(t)
        for t in self.merged:            # odbDisplay option objects
            if t.startswith("vp.odbDisplay.") and "viewCuts[" not in t:
                emit(t)
        cmds.extend(self.extra_vars.values())
        cmds.extend(self.dg_seq)
        cmds.extend(self.cut_defs.values())
        for t in self.merged:
            if "viewCuts[" in t:
                emit(t)
        emit("vp.odbDisplay")
        if self.camera_base:
            cmds.append(self.camera_base)
        if self.camera:
            cmds.append(build_call("vp.view", "setValues", (), self.camera))
        cmds.extend(self.camera_rel)
        return cmds

    def variable_commands(self):
        cmds = []
        if self.primary:
            cmds.append(self.primary)
        if self.plot:
            cmds.append(build_call("vp.odbDisplay.display", "setValues", (), self.plot))
        if self.limits:
            cmds.append(build_call("vp.odbDisplay.contourOptions", "setValues", (), self.limits))
        return cmds

    def print_commands(self):
        return [build_call(t, "setValues", (), kw) for t, kw in self.printing.items() if kw]


def capture(statements, source=""):
    """Views, variables and print options of every print in the statement list.
    Returns a dict: views, variables, print_commands, prints, step, odb, source."""
    st = _State()
    views, variables, prints, skipped = OrderedDict(), OrderedDict(), 0, 0
    print_cmds = []
    for stmt in statements:
        p = parse_call(stmt)
        if p and p[0] == "session" and p[1] == "printToFile":
            if not st.shows_odb:   # an XY plot or other non-ODB display was printed
                skipped += 1
                continue
            prints += 1
            fname = literal(p[3].get("fileName", "''"), "") or "print%d" % prints
            base = os.path.splitext(os.path.basename(str(fname).replace("\\", "/")))[0]
            vname = sanitize(base.split("__")[0])
            vcmds = st.view_commands()
            var_cmds = st.variable_commands()
            limits = [c for c in var_cmds if c.startswith("vp.odbDisplay.contourOptions.setValues(")]
            var_cmds = [c for c in var_cmds if c not in limits]
            plot_state = st.plot.get("plotState")
            var_name = variable_name(st.primary, plot_state)
            variables[var_name] = {"name": var_name, "commands": var_cmds}   # latest wins
            old = views.get(vname)
            var_list = old["variables"] if old else []
            if var_name not in var_list:
                var_list.append(var_name)
            view = {"name": vname, "jobs_containing": "", "variables": var_list, "commands": vcmds}
            view_limits = dict(old.get("limits", {})) if old else {}
            if limits:            # contour limits belong to this picture (view + variable)
                view_limits[var_name] = limits[0]
            if view_limits:
                view["limits"] = view_limits
            views[vname] = view
            print_cmds = st.print_commands()
        else:
            st.feed(stmt)
    return {"source": source, "prints": prints, "skipped_prints": skipped, "step": st.step, "odb": st.odb,
            "views": list(views.values()), "variables": list(variables.values()),
            "print_commands": print_cmds}


def capture_file(path):
    return capture(read_statements(path), path)


def state_at_end(path):
    """Display state at the end of an rpy file (= now, for the file of the running
    session): {"display_group": [commands], "primary": command or None}.
    Used by the live snapshot for what Abaqus cannot report (display group content)."""
    st = _State()
    for stmt in read_statements(path):
        st.feed(stmt)
    return {"display_group": list(st.dg_seq), "primary": st.primary}


def summary(result):
    lines = ["Source: %s" % result["source"],
             "%d print(s) found -> %d view(s), %d variable(s); last step used: %s; ODB: %s" % (
                 result["prints"], len(result["views"]), len(result["variables"]), result["step"], result["odb"])]
    if result.get("skipped_prints"):
        lines.append("  (%d print(s) of XY plots / non-ODB displays skipped)" % result["skipped_prints"])
    for v in result["views"]:
        lines.append("  VIEW %-24s variables: %s" % (v["name"], ", ".join(v["variables"]) or "(all)"))
        for c in v["commands"]:
            lines.append("       %s" % (c if len(c) < 150 else c[:147] + "..."))
        for var, c in sorted(v.get("limits", {}).items()):
            lines.append("       limits for %s: %s" % (var, c))
    for v in result["variables"]:
        lines.append("  VARIABLE %-20s %s" % (v["name"], " | ".join(v["commands"])))
    for c in result["print_commands"]:
        lines.append("  PRINT OPTIONS %s" % c)
    return "\n".join(lines)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0] else "."))
    args = [a for a in sys.argv[1:] if not a.lower().endswith(".py")]
    path = args[0] if args else find_newest_rpy([os.getcwd(), os.path.dirname(here)])
    if not path:
        raise SystemExit("No abaqus.rpy found - pass a path: python rpy_views.py path/to/abaqus.rpy")
    print(summary(capture_file(path)))
