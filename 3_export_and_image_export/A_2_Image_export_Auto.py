"""
A_2_Image_export_Auto.py - screenshots of Abaqus ODB files, fully automatic.

Replaces 2_Image_export_uniform.py and "2 Image_export.py". Copy everything whose
name starts with A_ (the three A_ scripts and the A_IMPORT_additional_functions
folder) next to the ODB files; the settings file below is optional.
Run in Abaqus/CAE or Viewer: File > Run Script...   (or: abaqus cae noGUI=A_2_Image_export_Auto.py)

WHAT IS EXPORTED
    every ODB  x  every view  x  its variables  x  its frames
    (frames: FRAMES below, or a view's own "frames" - e.g. 5 frames for one view, all for another)
    -> <IMAGE_FOLDER>/<JOB>/<variable>/<view>/f0012_t1.2.png
    Images are stored once per job (not per SET) and outside the results database,
    so the database stays small; optionally one ZIP per job (ZIP_PER_JOB).

HOW TO DEFINE THE PICTURES
  A) In Abaqus (recommended): open an ODB in Abaqus/Viewer, set up the picture -
     camera, section (view) cut, display group, contour type, visible edges,
     legend / annotations, variable and contour limits - and File > Print it to a
     PNG named "<view>__<variable>", e.g. "Front__DAMAGET" or "CutY__PEEQ".
     Repeat for every picture, then run this script with MODE = "capture".
     The newest abaqus.rpy with prints is read and every print becomes a view /
     variable in the settings file (the part before "__" is the view name).
  B) By coding, like before: edit VIEWS / VARIABLES in DEFAULT_SETTINGS below with
     command lines copied from the .rpy file ("vp" = the viewport).
  C) Live snapshot: set up the picture in Abaqus and run A_2_Image_save_view.py (or the
     Plug-ins button from the abaqus_plugins folder); it reads the settings straight
     from the session and adds the view to the same settings file.

CURVES (optional, CURVE_PLOT)
    e.g. a pushover curve per job from the results database of A_1_Export_Auto.py, with
    the frames of the exported images marked: <IMAGE_FOLDER>/<JOB>/_curve_<name>.png.
    Each axis: one variable of one section, or two combined (A - B, A + B, A * B, A / B),
    e.g. Y = Fx of one section, X = Ux of section 2 - Ux of section 1. Choose them with
    A_2_Image_save_view.py ("edit" in its curve field) or edit CURVES below.

CONTOUR LIMITS
    Stored per picture (view + variable) in the view's "limits", e.g.
    "limits": {"DAMAGET": "0, 1", "PEEQ": "max 0.1"} - so two views of the same
    variable can have different limits. A picture without limits is exported with
    automatic limits. The log lists the limits of every picture (fixed or automatic).

SETTINGS FILE (2_Image_export_settings.json next to this script)
    Holds everything (views, variables, frames, folders, image size) and is used
    at every run, so nothing has to be set again. Copy it to another folder to
    export there with identical settings. Latest change wins: a capture, an edit of
    the JSON, or an edit of DEFAULT_SETTINGS in this script.

PROGRESS: 2_Image_export_log.txt next to this script.
"""
from __future__ import print_function

import os
import sys
import time
import inspect
import traceback

SCRIPT_FILE = os.path.abspath(inspect.getfile(inspect.currentframe()))   # (__file__ is not set by Run Script)
SCRIPT_DIR, SCRIPT_NAME = os.path.split(SCRIPT_FILE)
LIB_DIR = os.path.join(SCRIPT_DIR, "A_IMPORT_additional_functions")
if not os.path.isdir(LIB_DIR):
    raise SystemExit("Folder A_IMPORT_additional_functions not found next to this script - "
                     "copy it together with the A_ scripts.")
# Abaqus keeps imported modules between runs: this folder's library goes first, and
# library modules an earlier run loaded from another folder (other project, older copy)
# are dropped so they are loaded again from here
while LIB_DIR in sys.path:
    sys.path.remove(LIB_DIR)
sys.path.insert(0, LIB_DIR)
for _f in os.listdir(LIB_DIR):
    _m = sys.modules.get(_f[:-3]) if _f.endswith(".py") else None
    if getattr(_m, "__file__", None) and \
            os.path.normcase(os.path.dirname(os.path.abspath(_m.__file__))) != os.path.normcase(LIB_DIR):
        del sys.modules[_f[:-3]]

import odb_tools
import export_settings
import rpy_views
import image_export
import pushover_curve
from odb_tools import log

# =============================================================================
# INPUT
# =============================================================================
MODE = "export"          # INPUT: "capture"        read views from the newest abaqus.rpy into the settings file
                         #        "export"         export the images with the settings file
                         #        "capture+export" both
SETTINGS_FILE = "2_Image_export_settings.json"   # INPUT: settings file (next to this script, or a full path)
RPY_FILE = None          # INPUT: None = newest abaqus.rpy with prints (this folder / Abaqus start folder)
CAPTURE_ADDS = False     # INPUT: False = captured views REPLACE the views in the settings,
                         #        True  = they are added (same name -> updated)
JSON_ALWAYS_WINS = False # INPUT: True = the settings file overrides DEFAULT_SETTINGS completely
                         #        (use it when the file comes from a folder with a different script version)

LOG_FILE_NAME = "2_Image_export_log.txt"
PATH_KEYS = ("ODB_FOLDER", "IMAGE_FOLDER", "RESULTS_DATABASE")

# Settings for the first run (afterwards the settings file is used - see above).
# Paths are absolute or relative to this script's folder. "vp" = the viewport.
DEFAULT_SETTINGS = {
    "ODB_FOLDER": ".",                 # folder with the .odb files
    "ODB_NAMES": None,                 # None = all ODBs in the folder; or ["a.odb", "b.odb"]
    "ODB_FILTER": "",                  # only ODBs whose name contains this text
    "STEP": None,                      # None = last step of each ODB
    # frames of every view that has no "frames" of its own. A dict - MODE "uniform" (COUNT) |
    # "every" (EVERY) | "indices" (INDICES) | "times" (TIMES) | "all" | "last" - or short text:
    # "10" (evenly spread), "all", "last", "every 3", "0, 25, -1", "times 1.5, 3.0"
    "FRAMES": {"MODE": "uniform", "COUNT": 10},
    "IMAGE_FOLDER": "Panel_images",    # images: <IMAGE_FOLDER>/<JOB>/<variable>/<view>/...
    "IMAGE_SIZE": None,                # [width, height] in pixels (smaller = smaller files); None = as on screen
    "ZIP_PER_JOB": False,              # True = pack each job's images into <JOB>.zip (much faster to copy)
    "OVERWRITE": False,                # False = existing images are kept (an interrupted export continues)
    "CONTINUE_ON_ERROR": True,         # a failing ODB is logged and the next one is exported
    "STRICT": False,                   # True = stop at the first command that fails
    # applied once per ODB, before the views
    "COMMON_COMMANDS": [
        "session.graphicsOptions.setValues(backgroundStyle=SOLID, backgroundColor='#FFFFFF')",
        "vp.odbDisplay.commonOptions.setValues(deformationScaling=UNIFORM, uniformScaleFactor=1.0)",
        "vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF, ))",
    ],
    "PRINT_COMMANDS": ["session.printOptions.setValues(vpBackground=ON, compass=ON)"],
    # view: camera, cuts, display group, contour type, edges ... ; "variables": [] = all variables
    # optional per view: "frames": "5" / "all" / "every 3" / ... (same forms as FRAMES; missing = FRAMES)
    #                    "limits": {"DAMAGET": "0, 1"} contour limits per variable: "auto", "0, 0.5",
    #                              "auto, 1", "max 0.1", "min 0" or a contourOptions command; missing = automatic
    "VIEWS": [
        {"name": "Front_view", "jobs_containing": "", "variables": [], "commands": [
            "vp.view.setValues(nearPlane=6475.5, farPlane=8892.35, width=5453.53, height=3504.91, "
            "cameraPosition=(1168.02, 7539.02, 2825.53), cameraUpVector=(0.0426004, -0.482979, 0.874595), "
            "cameraTarget=(1814.46, -34.796, 1549.19), viewOffsetX=1327.83, viewOffsetY=-389.165)"]},
        {"name": "Rear_view", "jobs_containing": "", "variables": [], "commands": [
            "vp.view.setValues(nearPlane=6592.75, farPlane=8703, width=5850.8, height=3760.23, "
            "cameraPosition=(-40.0714, -8012.6, 1796.92), cameraUpVector=(-0.0229519, 0.315631, 0.948604), "
            "cameraTarget=(-1194.72, -393.191, 1942.22), viewOffsetX=3882.17, viewOffsetY=-739.34)"]},
    ],
    # variable: primary variable (+ plot state). Contour limits belong to the views ("limits" above);
    # limits kept in a variable (older settings) are used by views without own limits for it
    "VARIABLES": [
        {"name": "DAMAGEC", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='DAMAGEC', outputPosition=INTEGRATION_POINT)"]},
        {"name": "DAMAGET", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='DAMAGET', outputPosition=INTEGRATION_POINT)"]},
        {"name": "S13", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='S', outputPosition=INTEGRATION_POINT, refinement=(COMPONENT, 'S13'))"]},
        {"name": "S33", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='S', outputPosition=INTEGRATION_POINT, refinement=(COMPONENT, 'S33'))"]},
        {"name": "PEEQ", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='PEEQ', outputPosition=INTEGRATION_POINT)"]},
        {"name": "U_Magnitude", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL, refinement=(INVARIANT, 'Magnitude'))"]},
        {"name": "U3", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL, refinement=(COMPONENT, 'U3'))"]},
        {"name": "U1", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL, refinement=(COMPONENT, 'U1'))"]},
        {"name": "CSTATUS", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='CSTATUS', outputPosition=ELEMENT_NODAL)"]},
        {"name": "S_Max_Principal", "commands": ["vp.odbDisplay.setPrimaryVariable(variableLabel='S', outputPosition=INTEGRATION_POINT, refinement=(INVARIANT, 'Max. Principal'))"]},
    ],
    # optional: curves (e.g. pushover) from the results database of A_1_Export_Auto.py with the frames
    # of the exported images marked -> <IMAGE_FOLDER>/<JOB>/_curve_<name>.png (+ .csv with the points).
    # Easiest to define with A_2_Image_save_view.py: "edit" in its curve field opens drop-down lists.
    # Axis: {"a": "<section>:<variable>"} or {"a": ..., "op": "-" | "+" | "*" | "/", "b": ...}, optional
    # "factor" (e.g. -1, 0.001) and "label"; a unique part of the section name is enough.
    # jobs_containing / jobs_excluding: comma separated texts of job names (empty = every job).
    "RESULTS_DATABASE": "Panel_results",
    "CURVE_PLOT": {
        "ENABLED": True,               # needs matplotlib (part of Abaqus 2021)
        "CURVES": [
            {"name": "Fx_vs_Ux", "jobs_containing": "SHEAR",
             "x": {"a": "PIER&RU&2&0:Ux"}, "y": {"a": "PIER&RU&2&0:Fx"}},
            {"name": "My_vs_fiy", "jobs_excluding": "SHEAR",
             "x": {"a": "PIER&RU&2&0:fiy"}, "y": {"a": "PIER&RU&2&0:My"}},
        ],
        "ADD_FRAMES_AROUND_PEAK": False,   # also export the peak and the points at BEFORE/AFTER * peak (first curve)
        "BEFORE_PEAK": 0.75, "AFTER_PEAK": 0.8,
    },
}
# =============================================================================


def load_settings():
    settings, info = export_settings.load(DEFAULT_SETTINGS, SCRIPT_DIR, SETTINGS_FILE, PATH_KEYS)
    if JSON_ALWAYS_WINS:
        data, _ = export_settings.read(SCRIPT_DIR, SETTINGS_FILE)
        if data:
            code = export_settings.to_portable(odb_tools.native(DEFAULT_SETTINGS), SCRIPT_DIR, PATH_KEYS)
            merged = export_settings._merge(code, data["settings"], code)
            settings = export_settings.to_absolute(merged, SCRIPT_DIR, PATH_KEYS)
            info += " (settings file used completely: JSON_ALWAYS_WINS)"
    return settings, info


def save_settings(settings):
    path = export_settings.save(settings, DEFAULT_SETTINGS, SCRIPT_DIR, SETTINGS_FILE, PATH_KEYS,
                                script_name=SCRIPT_NAME)
    log("Settings saved to %s" % path)


# -----------------------------------------------------------------------------
# Capture
# -----------------------------------------------------------------------------
def find_rpy():
    """RPY_FILE, else the newest abaqus.rpy* that contains prints of an ODB."""
    if RPY_FILE:
        return RPY_FILE
    folders = [SCRIPT_DIR, os.getcwd()]
    files = []
    for folder in folders:
        if os.path.isdir(folder):
            files.extend(os.path.join(folder, f) for f in os.listdir(folder)
                         if f.lower().startswith("abaqus.rpy"))
    for path in sorted(set(files), key=os.path.getmtime, reverse=True):
        try:
            if rpy_views.capture_file(path)["prints"]:
                return path
        except (IOError, OSError):
            continue
    return None


def capture_into(settings):
    path = find_rpy()
    if not path:
        log("CAPTURE: no abaqus.rpy with prints found in %s - print your views in Abaqus first "
            "(File > Print, name them <view>__<variable>) or set RPY_FILE." % SCRIPT_DIR)
        return settings, False
    res = odb_tools.native(rpy_views.capture_file(path))  # plain str for Abaqus 2021 (Python 2)
    log(rpy_views.summary(res))
    # a view captured again keeps its own frame setting
    own_frames = dict((v["name"], v["frames"]) for v in settings["VIEWS"] if v.get("frames"))
    for v in res["views"]:
        if v["name"] in own_frames:
            v["frames"] = own_frames[v["name"]]
    settings = dict(settings)
    if CAPTURE_ADDS:
        # limits kept in a variable (older settings) move to the views that are not captured again
        settings = image_export.normalize_limits(settings)
        views = dict((v["name"], v) for v in settings["VIEWS"])
        order = [v["name"] for v in settings["VIEWS"]]
        for v in res["views"]:
            if v["name"] not in views:
                order.append(v["name"])
            views[v["name"]] = v
        settings["VIEWS"] = [views[n] for n in order]
        variables = dict((v["name"], v) for v in settings["VARIABLES"])
        vorder = [v["name"] for v in settings["VARIABLES"]]
        for v in res["variables"]:
            if v["name"] not in variables:
                vorder.append(v["name"])
            variables[v["name"]] = v
        settings["VARIABLES"] = [variables[n] for n in vorder]
    else:
        settings["VIEWS"] = res["views"]
        settings["VARIABLES"] = res["variables"]
    if res["print_commands"]:
        settings["PRINT_COMMANDS"] = res["print_commands"]
    log("CAPTURE: %d view(s) and %d variable(s) are now in the settings" % (
        len(settings["VIEWS"]), len(settings["VARIABLES"])))
    return settings, True


# -----------------------------------------------------------------------------
# Export
# -----------------------------------------------------------------------------
def applies(view, job, variable_name):
    wanted = [w.strip().upper() for w in str(view.get("jobs_containing", "")).split(",") if w.strip()]
    if wanted and not any(w in job.upper() for w in wanted):
        return False
    return not view.get("variables") or variable_name in view["variables"]


def curve_for_job(settings, job, records, frames):
    """Curves of this job (CURVE_PLOT) with the image frames marked, and the extra frames
    around the peak of its first curve. Returns the extra FrameRecords."""
    cfg = settings.get("CURVE_PLOT") or {}
    if not cfg.get("ENABLED") and not cfg.get("ADD_FRAMES_AROUND_PEAK"):
        return []
    curves = pushover_curve.curves_for_job(cfg, job)
    if not curves:
        log("  curves: none for this job (see jobs_containing / jobs_excluding)")
        return []
    db, cache, extra = settings.get("RESULTS_DATABASE"), {}, []
    if cfg.get("ADD_FRAMES_AROUND_PEAK"):
        data = pushover_curve.curve_data(db, job, curves[0], cache)
        if data["error"]:
            log("  frames around the peak: curve %s: %s" % (curves[0]["name"], data["error"]))
        else:
            times = pushover_curve.times_around_peak(data["time"], data["y"], float(cfg.get("BEFORE_PEAK", 0.75)),
                                                     float(cfg.get("AFTER_PEAK", 0.8)))
            extra = image_export.frames_at_times(records, times)
            log("  frames around the peak of curve %s: %s" % (curves[0]["name"], [r.index for r in extra]))
    if cfg.get("ENABLED"):
        folder = os.path.join(settings["IMAGE_FOLDER"], job)
        for curve in curves:
            try:   # a curve problem must not stop the images
                msg = pushover_curve.plot_job(db, job, curve, list(frames) + extra, folder, cache=cache)[1]
            except Exception as e:
                msg = "curve %s failed: %s" % (curve.get("name"), e)
            log("  " + msg)
    return extra


def export_job(rep, settings, odb_path, scopes, report):
    job = odb_tools.job_name(odb_path)
    image_root = settings["IMAGE_FOLDER"]
    zip_path = os.path.join(image_root, job + ".zip")
    if settings["ZIP_PER_JOB"] and os.path.isfile(zip_path) and not settings["OVERWRITE"]:
        log("  %s.zip exists - skipped" % job)
        return
    session, C = rep.session, rep.ns
    log("  opening ODB ...")
    odb, opened_here = odb_tools.open_or_reuse(odb_path)
    try:
        vp = rep.vp
        vp.setValues(displayedObject=odb)
        rep.run(["vp.animationController.setValues(animationType=NONE)"], "animation")
        rep.run(settings["COMMON_COMMANDS"], "COMMON_COMMANDS")
        rep.run(settings["PRINT_COMMANDS"], "PRINT_COMMANDS")
        if settings.get("IMAGE_SIZE"):
            rep.run(["session.pngOptions.setValues(imageSize=(%d, %d))" % tuple(settings["IMAGE_SIZE"])], "IMAGE_SIZE")
        if not rep.baseline:  # starting values, taken once before any view is applied
            rep.snapshot(scopes["view"] | scopes["variable"])

        step = settings["STEP"] or list(odb.steps.keys())[-1]
        records = odb_tools.select_frames(odb, step)  # all frames, records[i].index == i
        views, variables = settings["VIEWS"], settings["VARIABLES"]
        # frames per view: the view's own "frames", else the global FRAMES
        default_frames = set(r.index for r in image_export.choose_frames(records, settings["FRAMES"]))
        view_frames = {}
        for view in views:
            spec = image_export.parse_frames(view.get("frames"))
            view_frames[view["name"]] = (set(r.index for r in image_export.choose_frames(records, spec))
                                         if spec else default_frames)
        union = sorted(set().union(*view_frames.values())) if view_frames else []
        extra = curve_for_job(settings, job, records, [records[i] for i in union])  # peak frames: all views
        for s in view_frames.values():
            s.update(r.index for r in extra)
        frames = [records[i] for i in sorted(set().union(*view_frames.values()))] if view_frames else []
        log("  step %s: %d of %d frames -> %s" % (step, len(frames), len(records), [r.index for r in frames]))
        if any(v.get("frames") for v in views):
            log("  frames per view: %s" % ", ".join("%s %d" % (v["name"], len(view_frames[v["name"]])) for v in views))

        new, skipped_vars = 0, set()
        for k, rec in enumerate(frames):
            shots = []
            for var in variables:
                for view in views:
                    if applies(view, job, var["name"]) and rec.index in view_frames[view["name"]]:
                        path = image_export.image_path(image_root, job, var["name"], view["name"], rec)
                        if settings["OVERWRITE"] or not image_export.repair_missing_extension(path):
                            shots.append((var, view, path))
            odb_tools.progress("Images %s" % job, k + 1, len(frames), "frames")
            if not shots:
                continue
            vp.odbDisplay.setFrame(step=odb_tools.get_step(odb, step).name, frame=rec.index)
            current_var, var_ok, printed = None, True, 0
            for var, view, path in shots:
                if var is not current_var:
                    var_cmds = image_export.split_limits(var["commands"])[0]   # limits: per picture below
                    rep.restore(scopes["variable"] - rep.pairs([var_cmds]), "variable")
                    failed = rep.run(var_cmds, "variable %s" % var["name"])
                    # a variable that cannot be set would give pictures of the PREVIOUS variable
                    var_ok = not any("setPrimaryVariable" in c for c in failed)
                    if not var_ok and var["name"] not in skipped_vars:
                        skipped_vars.add(var["name"])
                        log("  variable %s could not be set - its pictures are skipped (see the warning above)" % var["name"])
                    current_var = var
                if not var_ok:
                    continue
                rep.restore(scopes["view"] - rep.pairs([view["commands"]]), "view")
                rep.run([image_export.RESET_DISPLAY_GROUP], "display group reset")
                rep.run(view["commands"], "view %s" % view["name"])
                # contour limits of THIS picture (reset first: nothing carries over from the last one)
                rep.restore(scopes["limits"], "limits")
                rep.run(image_export.limits_for(view, var) or [image_export.AUTO_LIMITS],
                        "limits %s / %s" % (view["name"], var["name"]))
                image_export.print_png(session, vp, path, C["PNG"])
                new += 1
                printed += 1
            log("  frame %d/%d (index %d, t=%g): %d image(s)" % (k + 1, len(frames), rec.index, rec.step_time, printed))
        report["images"] += new
        log("  %d new image(s) for %s" % (new, job))
    finally:
        if opened_here:
            odb.close()
    if settings["ZIP_PER_JOB"] and os.path.isdir(os.path.join(image_root, job)):
        image_export.zip_folder(os.path.join(image_root, job), zip_path)
        log("  packed into %s" % zip_path)


def run_export(settings):
    if odb_tools.session is None:
        raise SystemExit("The export needs Abaqus/CAE or Viewer (File > Run Script, or abaqus cae noGUI=...).")
    rep = image_export.Replayer(strict=settings.get("STRICT", False))
    folder = settings["ODB_FOLDER"]
    names = settings["ODB_NAMES"] or odb_tools.list_odbs(folder, settings.get("ODB_FILTER", ""))
    if not settings["VIEWS"] or not settings["VARIABLES"]:
        raise SystemExit("No views or no variables in the settings - capture them (MODE = 'capture') or add them.")
    # every frame and limit setting is checked before the first ODB is opened
    for owner, spec in [("FRAMES", settings["FRAMES"])] + [("view %s" % v["name"], v.get("frames")) for v in settings["VIEWS"]]:
        try:
            image_export.parse_frames(spec)
        except ValueError as e:
            raise SystemExit("%s: %s" % (owner, e))
    limit_cmds = []
    for v in settings["VIEWS"]:
        for var_name, text in (v.get("limits") or {}).items():
            try:
                limit_cmds.append(image_export.parse_limits(text))
            except ValueError as e:
                raise SystemExit("view %s, variable %s: %s" % (v["name"], var_name, e))
    var_scope = rep.pairs([v["commands"] for v in settings["VARIABLES"]] + [[c for c in limit_cmds if c]])
    view_scope = rep.pairs(v["commands"] for v in settings["VIEWS"]) - var_scope
    limit_scope = set(p for p in var_scope if p[0] == image_export.LIMITS_TARGET and p[1] in rpy_views.LIMIT_KEYS)
    limit_scope |= set((image_export.LIMITS_TARGET, k) for k in ("maxAutoCompute", "minAutoCompute"))
    scopes = {"view": view_scope, "variable": var_scope | limit_scope, "limits": limit_scope}
    shown_before = rep.vp.displayedObject

    log("=" * 78)
    log("ODB folder   : %s   (%d ODB files)" % (folder, len(names)))
    log("Image folder : %s" % settings["IMAGE_FOLDER"])
    log("Views        : %s" % ", ".join("%s [%s]" % (v["name"], image_export.describe_frames(v.get("frames")))
                                        for v in settings["VIEWS"]))
    log("Variables    : %s" % ", ".join(v["name"] for v in settings["VARIABLES"]))
    log("Frames       : default = %s   |   image size: %s" % (image_export.describe_frames(settings["FRAMES"]),
                                                              settings.get("IMAGE_SIZE") or "as on screen"))
    # contour limits of every picture: fixed value(s) or automatic
    variables = dict((v["name"], v) for v in settings["VARIABLES"])
    for v in settings["VIEWS"]:
        for var_name in (v["variables"] or [x["name"] for x in settings["VARIABLES"]]):
            if var_name in variables:
                lims = image_export.limits_for(v, variables[var_name])
                log("Limits       : %-26s %-18s %s" % (v["name"], var_name,
                                                        image_export.describe_limits(lims) if lims else "automatic"))
    curve_cfg = settings.get("CURVE_PLOT") or {}
    if curve_cfg.get("ENABLED"):
        db = settings.get("RESULTS_DATABASE")
        for c in pushover_curve.curves_of(curve_cfg) or [{"name": "none"}]:
            log("Curve        : %s" % (pushover_curve.describe(c) if c.get("x") else "no curves defined"))
        log("Curve data   : %s%s" % (db, "" if db and os.path.isdir(db) else "   (NOT FOUND - no curves will be drawn)"))
    else:
        log("Curves       : off")
    log("=" * 78)
    report = {"images": 0, "failed": []}
    t0 = time.time()
    for i, name in enumerate(names):
        log("\n[%d/%d] %s" % (i + 1, len(names), name))
        try:
            export_job(rep, settings, os.path.join(folder, name), scopes, report)
        except Exception as e:
            report["failed"].append((name, str(e)))
            log(traceback.format_exc())
            if not settings.get("CONTINUE_ON_ERROR", True):
                raise
    try:
        rep.vp.setValues(displayedObject=shown_before)
    except Exception:
        pass
    log("\n" + "=" * 78)
    log("DONE in %.1f min: %d new image(s), %d failed ODB(s)" % ((time.time() - t0) / 60.0, report["images"], len(report["failed"])))
    for name, err in report["failed"]:
        log("  FAILED %s: %s" % (name, err))


def main():
    odb_tools.set_log_file(os.path.join(SCRIPT_DIR, LOG_FILE_NAME), "%s started, MODE = %s" % (SCRIPT_NAME, MODE))
    try:
        settings, info = load_settings()
        log(info)
        if "capture" in MODE:
            settings, _ = capture_into(settings)
        save_settings(settings)  # also before an export, so an interrupted run is remembered
        if "export" in MODE:
            run_export(settings)
    except SystemExit as e:
        log(str(e))
        raise
    except Exception:
        log("STOPPED BY AN ERROR:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
