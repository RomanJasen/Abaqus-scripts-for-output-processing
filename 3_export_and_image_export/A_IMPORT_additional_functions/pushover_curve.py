"""
pushover_curve.py - curves (e.g. pushover: force vs displacement) from the results
database of A_1_Export_Auto.py, with the frames of the exported images marked.

WHAT A CURVE IS
  Two axes. Each axis is one term, or two terms combined, times a factor:
      {"a": "V_PIER&RU&2&0:Fx"}                        Fx of one section
      {"a": "V_PIER&RU&2&0:Ux", "op": "-", "b": "V_PIER&RU&1&0:Ux"}
                                                       relative displacement of two sections
      {"a": "V_PIER&RU&2&0:Fx", "op": "/", "b": "V_PIER&RU&2&0:Fz"}
                                                       ratio of two force components
      "factor": -1 (sign) or 0.001 (N -> kN), "label": text of the axis (optional)
  A term is "<section>:<variable>": section = SET folder of the database (a unique part
  of the name is enough, e.g. "PIER&RU&2&0"), variable = column of its files (Time, Ux,
  Uy, Uz, fix, fiy, fiz, Fx, Fy, Fz, Mx, My, Mz). Two terms are paired by their time.
  Operations: - + * /

  In the settings of A_2_Image_export_Auto.py (CURVE_PLOT):
      "CURVES": [{"name": "Pushover", "jobs_containing": "SHEAR",
                  "x": {"a": "V_PIER&RU&2&0:Ux"},
                  "y": {"a": "V_PIER&RU&2&0:Fx", "factor": 0.001, "label": "Fx [kN]"}}]
  Easiest: A_2_Image_save_view.py with "edit" in its curve field -> dialog with drop-down
  lists of the sections and variables found in the database (edit_curves below).

OUTPUT per job and curve (next to the images of the job)
  _curve_<name>.png   the curve; the frames of the images are marked with their number
                      (f12 = the images f0012_t....png)
  _curve_<name>.csv   Time, X, Y and the image frames of every point

No Abaqus import: runs in any Python. The plot needs matplotlib (part of Abaqus 2021).
Stand-alone: dialog, then a preview PNG of the chosen curve for one job:
    abaqus python pushover_curve.py [results database] [job]      (or plain python)
"""
from __future__ import print_function, division

import gc
import os
import re
import sys
import bisect
import inspect

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import odb_tools
import database_io
from odb_tools import log

# (text in the dialog, operation)
OPERATIONS = (("none", ""), ("A - B", "-"), ("A + B", "+"), ("A * B", "*"), ("A / B", "/"))
_OPS = {"-": lambda a, b: a - b, "+": lambda a, b: a + b,
        "*": lambda a, b: a * b, "/": lambda a, b: a / b}
DEFAULT_VARIABLES = [h for h in database_io.HEADER if h != "frameId"]

_txt = odb_tools.to_text      # text for Tk / matplotlib (unicode in Python 2)
_nat = odb_tools.native       # text for Abaqus / the settings (plain str)


class CurveError(ValueError):
    """A curve cannot be drawn for a job (missing section, job or variable)."""


# ---------------------------------------------------------------------------
# Definition: terms, axes, curves
# ---------------------------------------------------------------------------
def split_term(term):
    """'V_PIER&RU&2&0:Ux' -> ('V_PIER&RU&2&0', 'Ux')."""
    text = str(term or "").strip()
    section, _, variable = text.rpartition(":")
    if not section.strip() or not variable.strip():
        raise ValueError("%r: write <section>:<variable>, e.g. V_PIER&RU&2&0:Ux" % text)
    return section.strip(), variable.strip()


def axis_spec(axis):
    """Axis as {"a", "op", "b", "factor", "label"}; a plain "section:variable" is allowed."""
    if not isinstance(axis, dict):
        axis = {"a": axis}
    factor = axis.get("factor")
    return {"a": axis.get("a") or "", "op": axis.get("op") or "", "b": axis.get("b") or "",
            "factor": 1.0 if factor in (None, "") else factor, "label": axis.get("label") or ""}


def check_axis(axis, which="axis"):
    """ValueError with a readable message if the axis cannot be used."""
    spec = axis_spec(axis)
    try:
        split_term(spec["a"])
        if spec["op"] not in ("",) + tuple(_OPS):
            raise ValueError("operation %r unknown - use - + * /" % spec["op"])
        if spec["op"]:
            split_term(spec["b"])
        try:
            float(spec["factor"])
        except (TypeError, ValueError):
            raise ValueError("factor %r is no number" % (spec["factor"],))
    except ValueError as e:
        raise ValueError("%s: %s" % (which, e))


def check_curve(curve):
    name = str(curve.get("name", "")).strip()
    if not name:
        raise ValueError("a curve without a name")
    for ax in ("y", "x"):
        if not curve.get(ax):
            raise ValueError("curve %s: no %s axis" % (name, ax.upper()))
        check_axis(curve[ax], "curve %s, %s axis" % (name, ax.upper()))


def _term_text(term):
    section, variable = split_term(term)
    return "%s(%s)" % (variable, section)


def axis_text(axis):
    """'Ux(V_PIER&RU&2&0) - Ux(V_PIER&RU&1&0)', with the factor in front."""
    spec = axis_spec(axis)
    text = _term_text(spec["a"])
    if spec["op"]:
        text = "%s %s %s" % (text, spec["op"], _term_text(spec["b"]))
    factor = float(spec["factor"])
    if factor != 1.0:
        text = ("%g * (%s)" if spec["op"] else "%g * %s") % (factor, text)
    return text


def axis_label(axis):
    return axis_spec(axis)["label"] or axis_text(axis)


def describe(curve):
    """'Pushover: Y = Fx(V_PIER&RU&2&0), X = Ux(V_PIER&RU&2&0)  (jobs containing SHEAR)'."""
    try:
        check_curve(curve)
    except ValueError as e:
        return "%s: INVALID - %s" % (curve.get("name"), e)
    jobs = []
    if str(curve.get("jobs_containing") or "").strip():
        jobs.append("containing %s" % curve["jobs_containing"])
    if str(curve.get("jobs_excluding") or "").strip():
        jobs.append("not containing %s" % curve["jobs_excluding"])
    return "%s: Y = %s, X = %s  (jobs %s)" % (curve.get("name"), axis_text(curve["y"]), axis_text(curve["x"]),
                                            ", ".join(jobs) if jobs else "all")


def file_name(curve):
    return "_curve_" + (re.sub(r"[^\w\-]+", "_", str(curve.get("name", ""))).strip("_") or "curve")


def curves_of(cfg):
    """The curves of CURVE_PLOT. Older settings (SET_CONTAINS, X, Y, RULES: one section,
    column names only) are turned into the same curves."""
    if cfg.get("CURVES") is not None:
        return list(cfg["CURVES"])
    section = cfg.get("SET_CONTAINS", "")
    rules = cfg.get("RULES", [])
    curves = []
    for rule in rules:
        x, y = rule.get("X", cfg.get("X", "fiy")), rule.get("Y", cfg.get("Y", "My"))
        curves.append({"name": "%s_vs_%s" % (y, x), "jobs_containing": rule.get("JOB_CONTAINS", ""),
                       "x": {"a": "%s:%s" % (section, x)}, "y": {"a": "%s:%s" % (section, y)}})
    x, y = cfg.get("X", "fiy"), cfg.get("Y", "My")
    curves.append({"name": "%s_vs_%s" % (y, x), "jobs_excluding": ",".join(r.get("JOB_CONTAINS", "") for r in rules),
                   "x": {"a": "%s:%s" % (section, x)}, "y": {"a": "%s:%s" % (section, y)}})
    return curves


def _words(text):
    return [w.strip().upper() for w in str(text or "").split(",") if w.strip()]


def curve_applies(curve, job):
    """jobs_containing: empty = every job, else one of the (comma separated) texts;
    jobs_excluding: none of them."""
    up = job.upper()
    wanted, excluded = _words(curve.get("jobs_containing")), _words(curve.get("jobs_excluding"))
    return (not wanted or any(w in up for w in wanted)) and not any(x in up for x in excluded)


def curves_for_job(cfg, job):
    return [c for c in curves_of(cfg) if curve_applies(c, job)]


# ---------------------------------------------------------------------------
# Results database
# ---------------------------------------------------------------------------
def _dirs(path):
    if not path or not os.path.isdir(path):
        return []
    return sorted(_nat(n) for n in os.listdir(path) if os.path.isdir(os.path.join(path, n)))


def list_sections(db):
    """SET folders of the database."""
    return _dirs(db)


def list_jobs(db, section):
    return _dirs(os.path.join(db, section)) if db else []


def list_variables(db):
    """Columns of the first section file found (without frameId)."""
    for section in list_sections(db):
        for job in list_jobs(db, section):
            path = database_io.section_file_path(db, section, job)
            if os.path.isfile(path):
                with open(path) as f:
                    header = [h.strip() for h in f.readline().split(",") if h.strip()]
                return [h for h in header if h != "frameId"] or list(DEFAULT_VARIABLES)
    return list(DEFAULT_VARIABLES)


def resolve_section(sections, text):
    """(section, note): exact name (any case), else the sections containing text - the
    first one if several match (with a note). (None, reason) if none matches."""
    up = str(text).strip().upper()
    exact = [s for s in sections if s.upper() == up]
    if exact:
        return exact[0], ""
    part = [s for s in sections if up and up in s.upper()]
    if len(part) == 1:
        return part[0], ""
    if part:
        return part[0], "'%s' matches %d sections (%s) - %s used" % (text, len(part), ", ".join(part), part[0])
    return None, "section '%s' not in the results database" % text


def jobs_with_data(db, curve):
    """Jobs of the database with a file for every section the curve uses."""
    sections, needed = list_sections(db), []
    for ax in ("x", "y"):
        spec = axis_spec(curve[ax])
        for term in [spec["a"]] + ([spec["b"]] if spec["op"] else []):
            section = resolve_section(sections, split_term(term)[0])[0]
            if section is None:
                return []
            needed.append(section)
    jobs = set(list_jobs(db, needed[0]))
    for section in needed[1:]:
        jobs &= set(list_jobs(db, section))
    return sorted(j for j in jobs if all(os.path.isfile(database_io.section_file_path(db, s, j)) for s in needed))


def read_section_file(path):
    """{column: [floats]} of a Section_data...txt file (empty fields -> None)."""
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    header = [h.strip() for h in lines[0].split(",") if h.strip()] if lines else []
    data = dict((h, []) for h in header)
    for line in lines[1:]:
        vals = line.split(",")
        for i, h in enumerate(header):
            v = vals[i].strip() if i < len(vals) else ""
            try:
                data[h].append(float(v) if v else None)
            except ValueError:
                data[h].append(None)
    return data


def curve_data(db, job, curve, cache=None):
    """Points of one curve for one job:
    {"time": [...], "x": [...], "y": [...], "notes": [...], "error": None}
    or {"error": "why not"}. cache (dict) keeps files already read."""
    cache = {} if cache is None else cache
    notes = []
    if "sections" not in cache:
        cache["sections"] = list_sections(db)
    if not cache["sections"]:
        return {"error": "results database not found or empty: %s" % db}

    def column(term):
        section_text, variable = split_term(term)
        section, note = resolve_section(cache["sections"], section_text)
        if section is None:
            raise CurveError(note)
        if note and note not in notes:
            notes.append(note)
        key = (section, job)
        if key not in cache:
            path = database_io.section_file_path(db, section, job)
            cache[key] = read_section_file(path) if os.path.isfile(path) else None
        data = cache[key]
        if data is None:
            raise CurveError("no data of job %s in section %s" % (job, section))
        if variable not in data:
            raise CurveError("%s has no column %s (columns: %s)" % (section, variable, ", ".join(sorted(data))))
        if "Time" not in data:
            raise CurveError("%s has no Time column" % section)
        return dict((round(t, 6), v) for t, v in zip(data["Time"], data[variable]) if t is not None)

    def axis(ax):
        spec = axis_spec(ax)
        a = column(spec["a"])
        b = column(spec["b"]) if spec["op"] else None
        factor = float(spec["factor"])
        out = {}
        for t, va in a.items():
            if va is None:
                continue
            if b is not None:
                vb = b.get(t)
                if vb is None or (spec["op"] == "/" and vb == 0):
                    continue
                va = _OPS[spec["op"]](va, vb)
            out[t] = factor * va
        return out

    try:
        xs, ys = axis(curve["x"]), axis(curve["y"])
    except (CurveError, ValueError, KeyError) as e:
        return {"error": str(e)}
    times = sorted(set(xs) & set(ys))
    if not times:
        return {"error": "no points (the two axes have no common times)"}
    return {"time": times, "x": [xs[t] for t in times], "y": [ys[t] for t in times],
            "notes": notes, "error": None}


def mark_points(data, frames):
    """[(point index, label)] of the curve points of the image frames (FrameRecords,
    nearest time; frames outside the curve are left out). Label 'f12' = frame 12;
    frames that fall on the same point share it ('f12, f13')."""
    times = data.get("time") or []
    if not times or not frames:
        return []
    gaps = [b - a for a, b in zip(times, times[1:])]
    tol = (max(gaps) / 2.0 if gaps else 0.0) + 1e-6
    labels = {}
    for rec in sorted(frames, key=lambda r: (r.step_time, r.index)):
        k = bisect.bisect_left(times, rec.step_time)
        near = [j for j in (k - 1, k) if 0 <= j < len(times)]
        j = min(near, key=lambda i: abs(times[i] - rec.step_time))
        if abs(times[j] - rec.step_time) <= tol:
            label = "f%d" % rec.index
            if label not in labels.get(j, []):
                labels.setdefault(j, []).append(label)
    return [(j, ", ".join(labels[j])) for j in sorted(labels)]


def times_around_peak(times, values, before, after):
    """Times at the peak of |value|, where it first reaches before*peak and where it has
    dropped to after*peak (the extra frames of the old script)."""
    pts = [(t, abs(v)) for t, v in zip(times, values) if t is not None and v is not None]
    if not pts:
        return []
    k = max(range(len(pts)), key=lambda i: pts[i][1])
    peak = pts[k][1]
    out = [pts[k][0]]
    pre = [i for i in range(k) if pts[i][1] >= before * peak]
    if pre:
        out.append(pts[pre[0]][0])
    post = [i for i in range(k + 1, len(pts)) if pts[i][1] <= after * peak]
    if post:
        out.append(pts[post[0]][0])
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def plot(png_path, data, marks, title, xlabel, ylabel):
    """PNG of the curve with the marked points. False if matplotlib is missing.
    Uses matplotlib's Agg canvas directly (no pyplot): no window, nothing left open
    in the Abaqus kernel."""
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
    except Exception:
        return False
    fig = Figure(figsize=(8.0, 5.5))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(data["x"], data["y"], "-", color="#1f5fa8", lw=1.4, label=_txt("curve"))
    if marks:
        ax.plot([data["x"][j] for j, _ in marks], [data["y"][j] for j, _ in marks], "o", color="#c0392b",
                ms=5, label=_txt("exported images (%d frames)" % len(marks)))
        for j, label in marks:
            ax.annotate(_txt(label), (data["x"][j], data["y"][j]), xytext=(4, 4), textcoords="offset points",
                        fontsize=7, color="#c0392b")
    ax.set_xlabel(_txt(xlabel))
    ax.set_ylabel(_txt(ylabel))
    ax.set_title(_txt(title), fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    folder = os.path.dirname(png_path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    fig.savefig(png_path, dpi=110, bbox_inches="tight")
    return True


def write_points(path, data, marks, xlabel, ylabel):
    """CSV with every point of the curve and the image frames that fall on it."""
    at = dict(marks)
    clean = lambda s: str(s).replace(",", ";")
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w") as f:
        f.write("Time,%s,%s,image frames\n" % (clean(xlabel), clean(ylabel)))
        for j, (t, x, y) in enumerate(zip(data["time"], data["x"], data["y"])):
            f.write("%r,%r,%r,%s\n" % (t, x, y, clean(at.get(j, ""))))


def plot_job(db, job, curve, frames, folder, title=None, cache=None):
    """Curve of one job -> <folder>/_curve_<name>.png + .csv. Returns (png or None, message)."""
    data = curve_data(db, job, curve, cache)
    if data["error"]:
        return None, "curve %s: %s - skipped" % (curve.get("name"), data["error"])
    marks = mark_points(data, frames)
    base = os.path.join(folder, file_name(curve))
    xlabel, ylabel = axis_label(curve["x"]), axis_label(curve["y"])
    write_points(base + ".csv", data, marks, xlabel, ylabel)
    if not plot(base + ".png", data, marks, title or "%s  -  %s" % (job, curve.get("name")), xlabel, ylabel):
        return None, "curve %s: matplotlib not available - only %s.csv written" % (curve.get("name"), base)
    note = "".join("; note: %s" % n for n in data["notes"])
    return base + ".png", "curve %s: %d points, %d image frames marked -> %s.png%s" % (
        curve.get("name"), len(data["time"]), len(marks), base, note)


# ---------------------------------------------------------------------------
# Dialog with drop-down lists (Tk)
# ---------------------------------------------------------------------------
def _tk():
    try:
        import Tkinter as tk
        import ttk
        import tkFileDialog as fd
    except ImportError:
        import tkinter as tk
        from tkinter import ttk
        from tkinter import filedialog as fd
    return tk, ttk, fd


def _op_code(text):
    text = str(text or "").strip()
    for label, code in OPERATIONS:
        if text in (label, code):
            return code
    return text


def _op_label(code):
    for label, c in OPERATIONS:
        if c == (code or ""):
            return label
    return "none"


class CurveDialog(object):
    """Drop-down lists for one curve (sections and variables read from the database).
    Runs inside the Abaqus kernel: its buttons only read files - never call Abaqus from
    here (Abaqus/Viewer and its kernel would deadlock)."""

    FIELDS = ("a_sec", "a_var", "op", "b_sec", "b_var", "factor", "label")

    def __init__(self, curves, db, enabled=True, current=None, info=""):
        tk, ttk, fd = _tk()
        self.fd = fd
        self.curves = [dict(c) for c in (curves or [])]
        self.sections, self.variables, self._db_read = [], list(DEFAULT_VARIABLES), None
        self.result = None
        root = self.root = tk.Tk()
        root.title("Curves for the image export")
        pad = {"padx": 4, "pady": 3}
        frm = ttk.Frame(root, padding=10)
        frm.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        # variables belong to THIS window (master=root), not to an older Tk of the session
        self.v = dict((k, tk.StringVar(master=root)) for k in ("db", "db_info", "name", "jobs", "excl", "status",
                                                               "y_text", "x_text"))
        for ax in ("y", "x"):
            for f in self.FIELDS:
                self.v[ax + "_" + f] = tk.StringVar(master=root)
        self.enabled = tk.BooleanVar(master=root, value=bool(enabled))

        r = 0
        if info:
            ttk.Label(frm, text=_txt(info), foreground="gray", wraplength=820, justify="left").grid(
                row=r, column=0, columnspan=8, sticky="w", **pad)
            r += 1
        ttk.Label(frm, text="Results database").grid(row=r, column=0, sticky="w", **pad)
        entry = ttk.Entry(frm, textvariable=self.v["db"], width=80)
        entry.grid(row=r, column=1, columnspan=6, sticky="ew", **pad)
        entry.bind("<Return>", lambda ev: self.read_database())
        entry.bind("<FocusOut>", lambda ev: self.read_database())
        ttk.Button(frm, text="Browse...", command=self.browse).grid(row=r, column=7, **pad)
        r += 1
        ttk.Label(frm, textvariable=self.v["db_info"], foreground="gray").grid(
            row=r, column=1, columnspan=7, sticky="w", **pad)
        r += 1
        ttk.Label(frm, text="Curve").grid(row=r, column=0, sticky="w", **pad)
        self.name_box = ttk.Combobox(frm, textvariable=self.v["name"], width=26)
        self.name_box.grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        self.name_box.bind("<<ComboboxSelected>>", lambda ev: self.load(_nat(self.v["name"].get())))
        ttk.Label(frm, text="choose a saved curve, or type a new name to add one", foreground="gray").grid(
            row=r, column=3, columnspan=5, sticky="w", **pad)
        r += 1
        ttk.Label(frm, text="Jobs containing").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.v["jobs"], width=28).grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        ttk.Label(frm, text="empty = every job; e.g. SHEAR  or  BEND, CYCLIC", foreground="gray").grid(
            row=r, column=3, columnspan=5, sticky="w", **pad)
        r += 1
        ttk.Label(frm, text="Jobs not containing").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.v["excl"], width=28).grid(row=r, column=1, columnspan=2, sticky="w", **pad)
        ttk.Label(frm, text="e.g. SHEAR (every other job)", foreground="gray").grid(
            row=r, column=3, columnspan=5, sticky="w", **pad)
        r += 1
        for c, text in enumerate(("", "Section A", "Variable A", "Operation", "Section B", "Variable B",
                                  "Factor", "Axis label (optional)")):
            ttk.Label(frm, text=text).grid(row=r, column=c, sticky="w", **pad)
        self.widgets = {}
        for ax, title in (("y", "Y axis (vertical)"), ("x", "X axis (horizontal)")):
            r += 1
            ttk.Label(frm, text=title).grid(row=r, column=0, sticky="w", **pad)
            w = {"a_sec": ttk.Combobox(frm, textvariable=self.v[ax + "_a_sec"], width=24),
                 "a_var": ttk.Combobox(frm, textvariable=self.v[ax + "_a_var"], width=8),
                 "op": ttk.Combobox(frm, textvariable=self.v[ax + "_op"], width=7, state="readonly",
                                    values=[o[0] for o in OPERATIONS]),
                 "b_sec": ttk.Combobox(frm, textvariable=self.v[ax + "_b_sec"], width=24),
                 "b_var": ttk.Combobox(frm, textvariable=self.v[ax + "_b_var"], width=8),
                 "factor": ttk.Entry(frm, textvariable=self.v[ax + "_factor"], width=8),
                 "label": ttk.Entry(frm, textvariable=self.v[ax + "_label"], width=22)}
            for c, f in enumerate(self.FIELDS):
                w[f].grid(row=r, column=c + 1, sticky="w", **pad)
            self.widgets[ax] = w
        for ax in ("y", "x"):
            r += 1
            ttk.Label(frm, textvariable=self.v[ax + "_text"]).grid(row=r, column=1, columnspan=7, sticky="w", **pad)
        r += 1
        ttk.Checkbutton(frm, variable=self.enabled,
                        text="Plot the curves in the export (one PNG per job and curve, image frames marked)").grid(
            row=r, column=0, columnspan=8, sticky="w", **pad)
        r += 1
        ttk.Label(frm, textvariable=self.v["status"], foreground="#b03030").grid(
            row=r, column=0, columnspan=8, sticky="w", **pad)
        r += 1
        buttons = ttk.Frame(frm)
        buttons.grid(row=r, column=0, columnspan=8, sticky="ew", **pad)
        ttk.Button(buttons, text="Delete this curve", command=self.on_delete).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=root.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Save", command=self.on_save).pack(side="right", padx=4)

        # formula lines follow every change. Widget events, not variable traces: a trace keeps
        # the window (and its Tcl interpreter) alive after it is closed - in the Abaqus kernel.
        for ax in ("y", "x"):
            for f, w in self.widgets[ax].items():
                w.bind("<KeyRelease>", lambda ev: self.update_texts(), add="+")
                w.bind("<<ComboboxSelected>>", lambda ev: self.update_texts(), add="+")
        self.v["db"].set(_txt(db or ""))
        self.read_database()
        self.load(current or (self.curves[0]["name"] if self.curves else "Pushover"))

    # -- helpers -----------------------------------------------------------------
    def get(self, key):
        return _nat(self.v[key].get()).strip()

    def find(self, name):
        for c in self.curves:
            if c.get("name") == name:
                return c
        return None

    def browse(self):
        d = self.fd.askdirectory(initialdir=self.get("db") or os.getcwd(), parent=self.root,
                                 title="Results database of A_1_Export_Auto.py")
        if d:
            self.v["db"].set(_txt(os.path.normpath(_nat(d))))
            self.read_database()

    def read_database(self):
        db = self.get("db")
        if db == self._db_read:
            return
        self._db_read = db
        self.sections = list_sections(db)
        self.variables = list_variables(db) if self.sections else list(DEFAULT_VARIABLES)
        for w in self.widgets.values():
            for f in ("a_sec", "b_sec"):
                w[f].configure(values=[_txt(s) for s in self.sections])
            for f in ("a_var", "b_var"):
                w[f].configure(values=[_txt(s) for s in self.variables])
        self.v["db_info"].set(_txt(
            "%d sections found" % len(self.sections) if self.sections else
            "no sections found - choose the results database of A_1_Export_Auto.py (Browse...)"))

    def load(self, name):
        curve = self.find(name) or {"name": name or "Pushover"}
        self.v["name"].set(_txt(curve.get("name", "")))
        self.v["jobs"].set(_txt(curve.get("jobs_containing") or ""))
        self.v["excl"].set(_txt(curve.get("jobs_excluding") or ""))
        for ax in ("y", "x"):
            spec = axis_spec(curve.get(ax) or {})
            try:
                factor = "%g" % float(spec["factor"])
            except (TypeError, ValueError):
                factor = str(spec["factor"])   # shown as it is; Save reports it
            vals = {"op": _op_label(spec["op"]), "factor": factor, "label": spec["label"]}
            for part in ("a", "b"):
                try:
                    vals[part + "_sec"], vals[part + "_var"] = split_term(spec[part])
                except ValueError:
                    vals[part + "_sec"], vals[part + "_var"] = "", ""
            for f in self.FIELDS:
                self.v[ax + "_" + f].set(_txt(vals[f]))
        self.name_box.configure(values=[_txt(c.get("name", "")) for c in self.curves])
        self.v["status"].set("")
        self.update_texts()

    def axis_from_fields(self, ax):
        g = lambda f: self.get(ax + "_" + f)
        axis = {"a": "%s:%s" % (g("a_sec"), g("a_var"))}
        op = _op_code(g("op"))
        if op:
            axis["op"], axis["b"] = op, "%s:%s" % (g("b_sec"), g("b_var"))
        try:
            factor = float(g("factor") or "1")
        except ValueError:
            raise ValueError("factor %r is no number" % g("factor"))
        if factor != 1.0:
            axis["factor"] = factor
        if g("label"):
            axis["label"] = g("label")
        return axis

    def update_texts(self):
        for ax, title in (("y", "Y"), ("x", "X")):
            state = "normal" if _op_code(self.get(ax + "_op")) else "disabled"
            for f in ("b_sec", "b_var"):
                self.widgets[ax][f].configure(state=state)
            try:
                axis = self.axis_from_fields(ax)
                check_axis(axis, title)
                text = "%s = %s" % (title, axis_text(axis))
            except ValueError as e:
                text = "%s: %s" % (title, e)
            self.v[ax + "_text"].set(_txt(text))

    def database_problems(self, curve):
        """Sections / variables that are not in the database (only if it was found)."""
        if not self.sections:
            return []
        out = []
        for ax in ("y", "x"):
            spec = axis_spec(curve[ax])
            for term in [spec["a"]] + ([spec["b"]] if spec["op"] else []):
                section, variable = split_term(term)
                if resolve_section(self.sections, section)[0] is None:
                    out.append("section '%s' is not in the database" % section)
                if variable not in self.variables:
                    out.append("variable '%s' is not in the database (%s)" % (variable, ", ".join(self.variables)))
        return out

    # -- buttons -----------------------------------------------------------------
    def finish(self, selected, deleted=None):
        self.result = {"curves": _nat(self.curves), "db": self.get("db"),
                       "enabled": bool(self.enabled.get()), "selected": selected, "deleted": deleted}
        self.root.destroy()

    def on_save(self):
        name = re.sub(r"[^\w\-]+", "_", self.get("name")).strip("_")
        if not name:
            self.v["status"].set("Not saved: give the curve a name")
            return
        try:
            curve = dict(self.find(name) or {})
            curve.update({"name": name, "jobs_containing": self.get("jobs"), "jobs_excluding": self.get("excl"),
                          "y": self.axis_from_fields("y"), "x": self.axis_from_fields("x")})
            if not curve["jobs_excluding"]:
                del curve["jobs_excluding"]
            check_curve(curve)
            problems = self.database_problems(curve)
            if problems:
                raise ValueError("; ".join(problems))
        except ValueError as e:
            self.v["status"].set(_txt("Not saved: %s" % e))
            return
        if self.find(name):
            self.curves = [(_nat(curve) if c.get("name") == name else c) for c in self.curves]
        else:
            self.curves.append(_nat(curve))
        self.finish(name)

    def on_delete(self):
        name = self.get("name")
        if not self.find(name):
            self.v["status"].set(_txt("'%s' is not a saved curve" % name))
            return
        self.curves = [c for c in self.curves if c.get("name") != name]
        self.finish(None, deleted=name)

    def run(self):
        root = self.root
        try:
            root.lift()                      # in front of the Abaqus window
            root.attributes("-topmost", True)
            root.update()
            root.attributes("-topmost", False)
            root.focus_force()
        except Exception:                    # closed while it opened
            return self.result
        root.mainloop()
        return self.result


def edit_curves(curves, db, enabled=True, current=None, info=""):
    """Show the dialog. Returns {"curves", "db", "enabled", "selected" (saved curve),
    "deleted" (deleted curve)} or None (cancelled)."""
    try:
        return CurveDialog(curves, db, enabled, current, info).run()
    finally:
        gc.collect()   # the Tk interpreter must not outlive the dialog in the Abaqus kernel


if __name__ == "__main__":
    import tempfile
    args = odb_tools.script_args()
    db = args[0] if args else os.path.join(os.path.dirname(_HERE), "Panel_results")
    demo = [{"name": "Pushover", "x": {"a": "PIER&RU&2&0:Ux"}, "y": {"a": "PIER&RU&2&0:Fx", "factor": 0.001,
                                                                      "label": "Fx [kN]"}}]
    out = edit_curves(demo, db, info="Demo of pushover_curve.py: choose a curve - a preview PNG is written "
                                     "for one job of the database (nothing is saved).")
    if not out or not out["selected"]:
        raise SystemExit("Cancelled")
    curve = [c for c in out["curves"] if c["name"] == out["selected"]][0]
    db = out["db"]
    sections = list_sections(db)
    job = args[1] if len(args) > 1 else (list_jobs(db, sections[0])[0] if sections and list_jobs(db, sections[0]) else "")
    print(describe(curve))
    print("job:", job)
    png, msg = plot_job(db, job, curve, [], tempfile.gettempdir(), title="%s (preview)" % job)
    print(msg)
