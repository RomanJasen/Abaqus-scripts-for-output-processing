"""
export_gui.py - optional settings dialog for A_1_Export_Auto.py.

edit_config(config, backend, defaults, info, steps) shows a dialog pre-filled
with config (the remembered settings) and returns the edited copy, or None if
the user cancelled. "Reset to defaults" loads defaults (the values written in
the script) into the dialog.

IMPORTANT: the dialog runs inside the Abaqus kernel. Never call Abaqus (open an
ODB, read steps, ...) from a button of this dialog - Abaqus/Viewer and its
kernel deadlock (seen with the former "Read steps" button).

backend "tk"      Tkinter window. Works with  abaqus cae noGUI=...  and plain python.
backend "abaqus"  Abaqus getInputs dialog. Only when the script is started from
                  the Abaqus/CAE GUI (File > Run Script), not with noGUI.

Run on its own to try the dialog (prints the resulting settings):
    python export_gui.py            (or: abaqus cae noGUI=export_gui.py)
"""
from __future__ import print_function

import gc
import os
import sys
import copy
import inspect

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import odb_tools

ANALYSIS_TYPES = ("AUTO", "IMPLICIT", "EXPLICIT")
ROTATION_METHODS = ("rigid", "angle", "slope")
FORCE_METHODS = ("freebody", "nforc")
COMPONENTS = ("fix", "fiy", "fiz")


def _fmt_dt(v):
    return "" if v in (None, 0, "") else str(v)


def _parse_dt(text):
    text = text.strip()
    return float(text) if text else None


def _split(text):
    return [s.strip() for s in text.split(",") if s.strip()]


# Text handed to Tk is converted with odb_tools.to_text(); everything read back
# from Tk goes through odb_tools.native() - Tk returns 'unicode' in Python 2, and
# Abaqus 2021 refuses unicode ("found 'unicode', expecting a recognized type ...").
_txt = odb_tools.to_text
_nat = odb_tools.native


# ---------------------------------------------------------------------------
# Tk backend
# ---------------------------------------------------------------------------
def _edit_tk(cfg, defaults=None, info="", steps=None):
    try:
        import Tkinter as tk
        import ttk
        import tkFileDialog as fd
    except ImportError:
        import tkinter as tk
        from tkinter import ttk
        from tkinter import filedialog as fd

    result = {"cfg": None}
    state = {"selection": None}  # ODB names to pre-select, None = all
    root = tk.Tk()
    root.title("Abaqus section export")
    pad = {"padx": 6, "pady": 3}
    frm = ttk.Frame(root, padding=10)
    frm.grid(sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frm.columnconfigure(1, weight=1)

    # variables belong to THIS window (master=root), not to an older Tk of the session
    sv = dict((k, tk.StringVar(master=root)) for k in ("folder", "step", "db", "filter", "type",
                                                       "dt_imp", "dt_exp", "rot", "force"))
    bv = dict((k, tk.BooleanVar(master=root)) for k in ("overwrite", "continue", "inp") + COMPONENTS)
    v_status = tk.StringVar(master=root, value="")

    r = 0
    ttk.Label(frm, text=_txt(info), foreground="gray", wraplength=640, justify="left").grid(
        row=r, column=0, columnspan=3, sticky="w", **pad)

    r += 1
    ttk.Label(frm, text="ODB folder").grid(row=r, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=sv["folder"], width=60).grid(row=r, column=1, sticky="ew", **pad)

    def browse_odb():
        d = fd.askdirectory(initialdir=sv["folder"].get() or os.getcwd())
        if d:
            sv["folder"].set(os.path.normpath(d))
            state["selection"] = None  # new folder -> select all
            refresh()
    ttk.Button(frm, text="Browse...", command=browse_odb).grid(row=r, column=2, **pad)

    r += 1
    ttk.Label(frm, text="ODB files\n(multi-select)").grid(row=r, column=0, sticky="nw", **pad)
    lb_frame = ttk.Frame(frm)
    lb_frame.grid(row=r, column=1, sticky="nsew", **pad)
    frm.rowconfigure(r, weight=1)
    lb = tk.Listbox(lb_frame, selectmode=tk.EXTENDED, height=12, exportselection=False)
    sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=sb.set)
    lb.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    btns = ttk.Frame(frm)
    btns.grid(row=r, column=2, sticky="n", **pad)

    def selected_odbs():
        return [_nat(lb.get(i)) for i in lb.curselection()]

    def refresh():
        lb.delete(0, tk.END)
        folder = _nat(sv["folder"].get().strip())
        try:
            names = odb_tools.list_odbs(folder) if folder else []
        except OSError:
            names = []
        wanted = state["selection"]
        if not wanted or not any(n in names for n in wanted):
            wanted = names
        for i, n in enumerate(names):
            lb.insert(tk.END, _txt(n))
            if n in wanted:
                lb.selection_set(i)
        v_status.set("%d ODB files found, %d selected" % (len(names), len(lb.curselection())))

    def refresh_keep():
        state["selection"] = selected_odbs() or state["selection"]
        refresh()
    ttk.Button(btns, text="Refresh", command=refresh_keep).pack(fill="x", pady=2)
    ttk.Button(btns, text="Select all", command=lambda: lb.selection_set(0, tk.END)).pack(fill="x", pady=2)
    ttk.Button(btns, text="Select none", command=lambda: lb.selection_clear(0, tk.END)).pack(fill="x", pady=2)

    r += 1
    ttk.Label(frm, text="Step\n(empty = last step)").grid(row=r, column=0, sticky="w", **pad)
    # No Abaqus calls may be made while this dialog is open (e.g. opening an ODB to
    # read its steps): Abaqus/Viewer and its kernel deadlock. Known step names are
    # passed in by the caller instead.
    ttk.Combobox(frm, textvariable=sv["step"], width=30,
                 values=[_txt(s) for s in (steps or [])]).grid(row=r, column=1, sticky="w", **pad)

    r += 1
    ttk.Label(frm, text="Results database").grid(row=r, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=sv["db"], width=60).grid(row=r, column=1, sticky="ew", **pad)

    def browse_db():
        d = fd.askdirectory(initialdir=sv["db"].get() or os.getcwd())
        if d:
            sv["db"].set(os.path.normpath(d))
    ttk.Button(frm, text="Browse...", command=browse_db).grid(row=r, column=2, **pad)

    r += 1
    ttk.Label(frm, text="SET name filter\n(comma separated,\nempty = all)").grid(row=r, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=sv["filter"], width=40).grid(row=r, column=1, sticky="w", **pad)

    r += 1
    ttk.Label(frm, text="Analysis type").grid(row=r, column=0, sticky="w", **pad)
    tf = ttk.Frame(frm)
    tf.grid(row=r, column=1, sticky="w", **pad)
    for t in ANALYSIS_TYPES:
        ttk.Radiobutton(tf, text=t.title(), value=t, variable=sv["type"]).pack(side="left", padx=4)

    r += 1
    ttk.Label(frm, text="Rotation method").grid(row=r, column=0, sticky="w", **pad)
    rf = ttk.Frame(frm)
    rf.grid(row=r, column=1, sticky="w", **pad)
    for t in ROTATION_METHODS:
        ttk.Radiobutton(rf, text=t, value=t, variable=sv["rot"]).pack(side="left", padx=4)
    for comp in COMPONENTS:
        ttk.Checkbutton(rf, text="%s absolute" % comp, variable=bv[comp]).pack(side="left", padx=4)

    r += 1
    ttk.Label(frm, text="Force method").grid(row=r, column=0, sticky="w", **pad)
    ff = ttk.Frame(frm)
    ff.grid(row=r, column=1, sticky="w", **pad)
    for t in FORCE_METHODS:
        ttk.Radiobutton(ff, text=t, value=t, variable=sv["force"]).pack(side="left", padx=4)

    r += 1
    ttk.Label(frm, text="Min. frame time step\n(empty = every frame)").grid(row=r, column=0, sticky="w", **pad)
    df = ttk.Frame(frm)
    df.grid(row=r, column=1, sticky="w", **pad)
    ttk.Label(df, text="Implicit").pack(side="left")
    ttk.Entry(df, textvariable=sv["dt_imp"], width=8).pack(side="left", padx=(2, 12))
    ttk.Label(df, text="Explicit").pack(side="left")
    ttk.Entry(df, textvariable=sv["dt_exp"], width=8).pack(side="left", padx=2)

    r += 1
    of = ttk.Frame(frm)
    of.grid(row=r, column=1, sticky="w", **pad)
    ttk.Checkbutton(of, text="Overwrite existing results", variable=bv["overwrite"]).pack(anchor="w")
    ttk.Checkbutton(of, text="Continue with next SET on error", variable=bv["continue"]).pack(anchor="w")
    ttk.Checkbutton(of, text="Copy .inp files into database", variable=bv["inp"]).pack(anchor="w")

    r += 1
    ttk.Label(frm, textvariable=v_status, foreground="gray").grid(row=r, column=0, columnspan=3, sticky="w", **pad)

    def fill(c):
        """Put the values of config c into the widgets."""
        sv["folder"].set(_txt(c.get("ODB_FOLDER") or ""))
        sv["step"].set(_txt(c.get("STEP") or ""))
        sv["db"].set(_txt(c.get("DATABASE_PATH") or ""))
        sv["filter"].set(_txt(",".join(f for f in c.get("SET_FILTER", [""]) if f)))
        sv["type"].set(c.get("ANALYSIS_TYPE", "AUTO"))
        dt = c.get("MIN_FRAME_TIME_INCREMENT", {})
        sv["dt_imp"].set(_fmt_dt(dt.get("IMPLICIT")))
        sv["dt_exp"].set(_fmt_dt(dt.get("EXPLICIT")))
        kin = c.get("KINEMATICS", {})
        sv["rot"].set(kin.get("METHOD", "rigid"))
        for comp in COMPONENTS:
            bv[comp].set(kin.get("ROTATIONS", {}).get(comp) == "absolute")
        sv["force"].set(c.get("FORCES", {}).get("METHOD", "freebody"))
        bv["overwrite"].set(bool(c.get("OVERWRITE")))
        bv["continue"].set(bool(c.get("CONTINUE_ON_ERROR")))
        bv["inp"].set(bool(c.get("COPY_INP", True)))
        state["selection"] = _nat(c.get("ODB_NAMES"))
        refresh()

    def on_reset():
        fill(defaults)
        v_status.set("Defaults from the script loaded - press 'Run export' to use them")

    def on_run():
        try:
            new = copy.deepcopy(cfg)
            new["ODB_FOLDER"] = sv["folder"].get().strip() or None
            new["ODB_NAMES"] = selected_odbs()
            if not new["ODB_NAMES"]:
                v_status.set("Select at least one ODB file")
                return
            new["STEP"] = sv["step"].get().strip() or None
            new["DATABASE_PATH"] = sv["db"].get().strip() or None
            new["SET_FILTER"] = _split(sv["filter"].get()) or [""]
            new["ANALYSIS_TYPE"] = sv["type"].get()
            new["MIN_FRAME_TIME_INCREMENT"] = {"IMPLICIT": _parse_dt(sv["dt_imp"].get()),
                                               "EXPLICIT": _parse_dt(sv["dt_exp"].get())}
            new["OVERWRITE"] = bool(bv["overwrite"].get())
            new["CONTINUE_ON_ERROR"] = bool(bv["continue"].get())
            new["COPY_INP"] = bool(bv["inp"].get())
            new.setdefault("KINEMATICS", {})["METHOD"] = sv["rot"].get()
            new["KINEMATICS"]["ROTATIONS"] = dict(
                (c, "absolute" if bv[c].get() else "relative") for c in COMPONENTS)
            new.setdefault("FORCES", {})["METHOD"] = sv["force"].get()
        except ValueError as e:
            v_status.set("Invalid input: %s" % e)
            return
        result["cfg"] = _nat(new)
        root.destroy()

    r += 1
    bf = ttk.Frame(frm)
    bf.grid(row=r, column=0, columnspan=3, sticky="ew", **pad)
    if defaults is not None:
        ttk.Button(bf, text="Reset to defaults", command=on_reset).pack(side="left", padx=4)
    ttk.Button(bf, text="Cancel", command=root.destroy).pack(side="right", padx=4)
    ttk.Button(bf, text="Run export", command=on_run).pack(side="right", padx=4)

    fill(cfg)
    # open in front of the Abaqus window (Windows may otherwise put it behind)
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    root.attributes("-topmost", False)
    root.focus_force()
    root.mainloop()
    return result["cfg"]


# ---------------------------------------------------------------------------
# Abaqus getInputs backend
# ---------------------------------------------------------------------------
def _edit_abaqus(cfg, info=""):
    from abaqus import getInputs
    cfg = _nat(cfg)
    folder = cfg["ODB_FOLDER"] or os.getcwd()
    names = cfg["ODB_NAMES"] or odb_tools.list_odbs(folder)
    fields = _nat((
        ("ODB folder:", folder),
        ("ODB files (comma separated):", ",".join(names)),
        ("Step (empty = last step of each ODB):", cfg["STEP"] or ""),
        ("Results database folder:", cfg["DATABASE_PATH"] or ""),
        ("SET name filter (comma separated, empty = all):", ",".join(f for f in cfg["SET_FILTER"] if f)),
        ("Analysis type (AUTO / IMPLICIT / EXPLICIT):", cfg["ANALYSIS_TYPE"]),
        ("Min. frame time step IMPLICIT (empty = all):", _fmt_dt(cfg["MIN_FRAME_TIME_INCREMENT"].get("IMPLICIT"))),
        ("Min. frame time step EXPLICIT (empty = all):", _fmt_dt(cfg["MIN_FRAME_TIME_INCREMENT"].get("EXPLICIT"))),
        ("Overwrite existing results (y/n):", "y" if cfg["OVERWRITE"] else "n"),
        ("Rotation method (rigid / angle / slope):", cfg.get("KINEMATICS", {}).get("METHOD", "rigid")),
        ("Force method (freebody / nforc):", cfg.get("FORCES", {}).get("METHOD", "freebody")),
    ))
    label = _nat("Section export settings\n" + info if info else "Section export settings")
    vals = getInputs(fields=fields, label=label, dialogTitle="Abaqus section export")
    if vals[0] is None:
        return None
    new = copy.deepcopy(cfg)
    new["ODB_FOLDER"] = vals[0].strip() or None
    new["ODB_NAMES"] = _split(vals[1]) or None
    new["STEP"] = vals[2].strip() or None
    new["DATABASE_PATH"] = vals[3].strip() or None
    new["SET_FILTER"] = _split(vals[4]) or [""]
    new["ANALYSIS_TYPE"] = vals[5].strip().upper() if vals[5].strip().upper() in ANALYSIS_TYPES else "AUTO"
    new["MIN_FRAME_TIME_INCREMENT"] = {"IMPLICIT": _parse_dt(vals[6]), "EXPLICIT": _parse_dt(vals[7])}
    new["OVERWRITE"] = vals[8].strip().lower().startswith("y")
    if vals[9].strip().lower() in ROTATION_METHODS:
        new.setdefault("KINEMATICS", {})["METHOD"] = vals[9].strip().lower()
    if vals[10].strip().lower() in FORCE_METHODS:
        new.setdefault("FORCES", {})["METHOD"] = vals[10].strip().lower()
    return _nat(new)


def edit_config(config, backend="tk", defaults=None, info="", steps=None):
    """Show the settings dialog. Returns the edited config (all text as plain str)
    or None (cancelled). defaults: values for the 'Reset to defaults' button;
    steps: step names offered in the Step list."""
    if backend == "abaqus":
        return _edit_abaqus(config, info)
    try:
        return _edit_tk(config, defaults, info, steps)
    finally:
        # delete the Tk interpreter now (it is part of reference cycles): it owns
        # hidden windows that must not outlive the dialog in the Abaqus kernel
        gc.collect()


if __name__ == "__main__":
    demo = {
        "ODB_FOLDER": os.path.dirname(_HERE), "ODB_NAMES": None, "STEP": None,
        "DATABASE_PATH": os.path.join(os.path.dirname(_HERE), "Panel_results"),
        "SET_FILTER": [""], "ANALYSIS_TYPE": "AUTO",
        "MIN_FRAME_TIME_INCREMENT": {"IMPLICIT": 1.0, "EXPLICIT": None},
        "KINEMATICS": {"METHOD": "rigid"}, "FORCES": {"METHOD": "freebody"},
        "OVERWRITE": False, "CONTINUE_ON_ERROR": False, "COPY_INP": True,
    }
    backend = "abaqus" if "abaqus" in odb_tools.script_args() else "tk"
    out = edit_config(demo, backend, defaults=demo, info="Demo run of export_gui.py")
    print("Cancelled" if out is None else "Resulting settings:")
    for k in sorted(out or {}):
        print("  %-26s %r" % (k, out[k]))
