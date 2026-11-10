"""
A_2_Image_save_view.py - save the picture currently set up in Abaqus as a view for
A_2_Image_export_Auto.py (live-session snapshot), and choose the curves of the export.
Needs A_2_Image_export_Auto.py and the A_IMPORT_additional_functions folder next to it.

HOW TO USE
  1. In Abaqus/Viewer (or CAE) open an ODB and set up the picture: camera, section
     cut, display group, contour type and limits, visible edges, legend / title,
     background, deformation scale, variable ...
  2. File > Run Script... > A_2_Image_save_view.py and type a name:
        "Front"            -> view "Front", variable = the one currently shown
        "Front__DAMAGET"   -> view "Front", variable named "DAMAGET"
     Saving the same view name again with another variable adds that variable
     to the view (the camera etc. are updated to the current state).
     The second field sets the frames of THIS view:
        empty      -> unchanged (a new view uses FRAMES of the settings)
        5 | all | last | every 3 | 0, 25, -1 | times 1.5, 3.0
        default    -> back to FRAMES of the settings
     The third field sets the contour limits of THIS picture (view + variable):
        empty      -> as shown in Abaqus (read from the session: fixed values or automatic)
        auto | 0, 0.5 | auto, 1 | max 0.1 | min 0
     The fourth field is for the curves of the export (e.g. a pushover curve per job
     with the frames of the exported images marked):
        empty      -> unchanged
        edit       -> dialog with drop-down lists: for each axis a section and variable,
                      or two of them and an operation (A - B, A + B, A * B, A / B),
                      e.g. Y = Fx of one section, X = Ux(section 2) - Ux(section 1).
                      A preview is drawn for the ODB shown in Abaqus.
        on | off   -> curves in the export on / off
     Empty picture name + a curve field -> only the curves are changed.
  3. Repeat for every picture, then run A_2_Image_export_Auto.py (MODE = "export").
  Instead of File > Run Script you can install the Plug-ins menu button from the
  abaqus_plugins folder (see the notes in abaqus_plugins/imageViewSnapshot_plugin.py).

WHAT IS STORED (in the settings file of A_2_Image_export_Auto.py)
  read from the session: camera, section cuts, edges, render style, deformation
  scale, contour type / intervals / spectrum, legend / title / triad, background,
  averaging / mirroring, plot state, primary variable, contour limits
  (the limits are stored with the VIEW for this variable, so two views of the same
  variable can have different limits)
  from this session's abaqus.rpy: the display group (Abaqus cannot report its
  content) - so hide / show parts with the Display Group tools as usual.
  Previews: <IMAGE_FOLDER>/_view_previews/<view>__<variable>.png and _curve_<name>.png
"""
from __future__ import print_function

import os
import sys
import inspect

SCRIPT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
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
import rpy_views
import image_export
import pushover_curve
from odb_tools import log

# =============================================================================
# INPUT
# =============================================================================
VIEW_NAME = None                # INPUT: None = ask for the name (and the frames); or e.g. "Front" / "Front__DAMAGET"
VIEW_FRAMES = None              # INPUT: frames of this view: None = unchanged (new view: FRAMES of the settings),
                                #        or "5", "all", "last", "every 3", "0, 25, -1", "times 1.5, 3.0", "default"
                                #        (when the dialog is used, this is the pre-filled value of its frames field)
VIEW_LIMITS = None              # INPUT: contour limits of this picture: None = as shown in Abaqus (read from the session),
                                #        or "auto", "0, 0.5", "auto, 1", "max 0.1", "min 0"
                                #        (when the dialog is used, this is the pre-filled value of its limits field)
CURVE = None                    # INPUT: curves of the export: None = unchanged, "edit" = dialog with drop-down lists
                                #        (section(s), variables, operation per axis), "on" / "off"
                                #        (when the dialog is used, this is the pre-filled value of its curve field)
VIEW_VARIABLES = "current"      # INPUT: "current" = export this view with the saved variable(s) only
                                #        "all"     = export this view with ALL variables of the settings
DISPLAY_GROUP_FROM_RPY = True   # INPUT: take the display group (hidden / shown parts) from this session's abaqus.rpy
SAVE_PRINT_OPTIONS = False      # INPUT: True = also store the current File > Print options (decorations, image size)
SAVE_PREVIEW = True             # INPUT: save a preview PNG of the picture (and of a curve chosen with "edit")
IMAGE_SCRIPT = "A_2_Image_export_Auto.py"   # the export script whose settings file receives the view
# =============================================================================
CURVE_CHOICES = ("", "edit", "on", "off")


def load_image_script():
    """The export script as a module (its settings file, defaults and save function)."""
    path = os.path.join(SCRIPT_DIR, IMAGE_SCRIPT)
    if not os.path.isfile(path):
        raise SystemExit("%s not found next to this script - copy all A_ files together" % IMAGE_SCRIPT)
    try:
        import imp                                   # Python 2 (Abaqus <= 2023)
        return imp.load_source("image_export_script", path)
    except ImportError:
        import importlib.util                        # Python 3
        spec = importlib.util.spec_from_file_location("image_export_script", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def ask_inputs(default_name, prefilled_frames, prefilled_limits, prefilled_curve, global_frames):
    """(name, frames, limits, curve) - from VIEW_NAME / VIEW_FRAMES / VIEW_LIMITS / CURVE or
    from Abaqus' own dialog. name None = cancelled. (Only the curve dialog is a Tk window;
    its buttons call no Abaqus function - that would deadlock Abaqus.)"""
    if VIEW_NAME:
        return VIEW_NAME, VIEW_FRAMES, VIEW_LIMITS, CURVE
    try:
        from abaqus import getInputs
    except ImportError:
        raise SystemExit("Could not ask for a name (no Abaqus GUI?) - set VIEW_NAME at the top of the script.")
    fields = (("Picture name - view, or view__variable:", default_name),
              ("Frames of this view (empty = unchanged; %s; default):" % image_export.FRAMES_HELP,
               prefilled_frames or ""),
              ("Contour limits (empty = as shown in Abaqus; %s):" % image_export.LIMITS_HELP,
               prefilled_limits or ""),
              ("Curves of the export (empty = unchanged; edit = choose sections and variables; on; off):",
               prefilled_curve or ""))
    label = ("Save the current picture for %s\n"
             "(views without own frames use FRAMES of the settings: %s)\n"
             "Empty picture name + curve field = change only the curves" % (IMAGE_SCRIPT, global_frames))
    try:
        name, frames, limits, curve = getInputs(fields=odb_tools.native(fields), label=odb_tools.native(label),
                                                dialogTitle="Save view")
    except Exception as e:
        raise SystemExit("Could not ask for a name (%s) - set VIEW_NAME at the top of the script." % e)
    if name is None:
        return None, None, None, None
    return name, frames, limits, curve


def check_in_session(view_cmds, var_cmds):
    """Apply the saved commands to the session. They describe what is shown now, so
    nothing changes - but whatever Abaqus rejects is reported NOW instead of during an
    export. Display group commands and cut definitions are not repeated (not repeatable)."""
    found = []
    rep = image_export.Replayer(report=found.append)
    rep.run(var_cmds, "variable")
    rep.run([c for c in view_cmds if (rpy_views.parse_call(c) or (None, None))[1] == "setValues"], "view")
    return found


def upsert(items, item):
    """Replace the entry with the same name, or append it. Returns True if it existed."""
    for i, old in enumerate(items):
        if old["name"] == item["name"]:
            items[i] = item
            return True
    items.append(item)
    return False


# -----------------------------------------------------------------------------
# The picture
# -----------------------------------------------------------------------------
def add_view(settings, image, name, frames_text, limits_text):
    """Read the session and put the picture into (a copy of) settings. Returns a dict for
    report_view (incl. the new settings), or None if nothing may be saved (reason logged)."""
    import view_snapshot
    view_part, _, var_part = name.partition("__")
    view_name = rpy_views.sanitize(view_part)
    frames_text = (frames_text or "").strip()
    try:
        if frames_text and frames_text.lower() != "default":
            image_export.parse_frames(frames_text)
        typed_limits = image_export.parse_limits(limits_text)
    except ValueError as e:
        log("NOT SAVED - %s" % e)
        return None

    # read the session (+ display group from this session's replay file)
    snap = view_snapshot.Snapshot()
    rpy_state, rpy_path = {"display_group": [], "primary": None}, None
    if DISPLAY_GROUP_FROM_RPY:
        rpy_path = rpy_views.find_newest_rpy([os.getcwd(), SCRIPT_DIR])
        if rpy_path:
            try:
                rpy_state = rpy_views.state_at_end(rpy_path)
            except (IOError, OSError) as e:
                log("NOTE: %s could not be read (%s) - display group not stored" % (rpy_path, e))
    view_cmds = odb_tools.native(snap.view_commands(rpy_state["display_group"]))
    var_cmds, primary, plot = snap.variable_commands(rpy_state["primary"])
    var_cmds, shown_limits = image_export.split_limits(odb_tools.native(var_cmds))
    var_name = rpy_views.sanitize(var_part) if var_part else rpy_views.variable_name(primary, plot)
    # contour limits of this picture: typed (min / max only - intervals etc. as shown), else as shown
    if typed_limits:
        limits_cmd = odb_tools.native(image_export.merge_limits(shown_limits[0] if shown_limits else None, typed_limits))
        limits_source = "VIEW_LIMITS" if VIEW_NAME else "typed in the dialog"
    elif shown_limits:
        limits_cmd, limits_source = shown_limits[0], "as shown in Abaqus"
    else:
        limits_cmd, limits_source = None, "could not be read - automatic"
    problems = check_in_session(view_cmds, var_cmds + ([limits_cmd] if limits_cmd else []))

    # add to the settings of the export script
    settings = dict(settings)
    if settings["VIEWS"] == odb_tools.native(image.DEFAULT_SETTINGS["VIEWS"]):
        log("The example views of DEFAULT_SETTINGS are replaced by your saved views.")
        settings["VIEWS"] = []
    # limits kept in variables by older versions move to the views first, so saving this
    # picture does not change the other pictures of the same variable
    settings = image_export.normalize_limits(settings)
    views = list(settings["VIEWS"])
    old = [v for v in views if v["name"] == view_name]
    var_list = [] if VIEW_VARIABLES == "all" else list(old[0]["variables"]) if old else []
    if VIEW_VARIABLES != "all" and var_name not in var_list:
        var_list.append(var_name)
    view = {"name": view_name, "jobs_containing": old[0].get("jobs_containing", "") if old else "",
            "variables": var_list, "commands": view_cmds}
    view_frames = old[0].get("frames") if old else None      # empty field: unchanged
    if frames_text:
        view_frames = None if frames_text.lower() == "default" else frames_text
    if view_frames:
        view["frames"] = view_frames
    view_lims = dict(old[0].get("limits") or {}) if old else {}
    if limits_cmd:
        view_lims[var_name] = limits_cmd                        # limits belong to this picture
    else:
        view_lims.pop(var_name, None)
    if view_lims:
        view["limits"] = view_lims
    existed = upsert(views, view)
    variables = list(settings["VARIABLES"])
    upsert(variables, {"name": var_name, "commands": var_cmds})
    settings["VIEWS"], settings["VARIABLES"] = views, variables
    if SAVE_PRINT_OPTIONS:
        settings["PRINT_COMMANDS"] = odb_tools.native(snap.print_commands())
    return {"settings": settings, "snap": snap, "view_name": view_name, "var_name": var_name, "existed": existed,
            "var_list": var_list, "view_frames": view_frames, "view_cmds": view_cmds, "var_cmds": var_cmds,
            "limits_cmd": limits_cmd, "limits_source": limits_source, "rpy_state": rpy_state,
            "rpy_path": rpy_path, "problems": problems}


def report_view(settings, r, global_frames):
    """Preview PNG of the saved picture and the log lines."""
    snap = r["snap"]
    preview = None
    if SAVE_PREVIEW:
        preview = os.path.join(settings["IMAGE_FOLDER"], "_view_previews", "%s__%s.png" % (r["view_name"], r["var_name"]))
        image_export.print_png(snap.session, snap.ns["vp"], preview, snap.constants["PNG"])
    vp = snap.ns["vp"]
    log("=" * 70)
    log("%s view '%s' with variable '%s'  (%d view / %d variable commands)" % (
        "Updated" if r["existed"] else "Saved", r["view_name"], r["var_name"], len(r["view_cmds"]), len(r["var_cmds"])))
    log("  view is exported with: %s" % (", ".join(r["var_list"]) if r["var_list"] else "all variables"))
    log("  frames: %s" % ("%s (this view)" % image_export.describe_frames(r["view_frames"]) if r["view_frames"]
                          else "%s (FRAMES of the settings)" % global_frames))
    log("  contour limits of %s: %s  (%s)" % (
        r["var_name"], image_export.describe_limits([r["limits_cmd"]] if r["limits_cmd"] else []), r["limits_source"]))
    log("  display group: %s" % ("%d command(s) from %s" % (len(r["rpy_state"]["display_group"]), r["rpy_path"])
                                 if r["rpy_state"]["display_group"] else "whole model"))
    try:
        log("  viewport %.0f x %.0f (use the same aspect ratio in IMAGE_SIZE for identical framing)" % (vp.width, vp.height))
    except Exception:
        pass
    if preview:
        log("  preview: %s" % preview)
    for n in snap.notes:
        log("  note: %s" % n)
    if r["problems"]:
        log("!! Abaqus rejected part of the saved settings - the export would fail the same way:")
        for p in r["problems"]:
            log(p)
    else:
        log("  check: Abaqus accepted all saved commands")


# -----------------------------------------------------------------------------
# Curves of the export
# -----------------------------------------------------------------------------
def change_curves(settings, action):
    """'edit' (dialog), 'on' or 'off' for CURVE_PLOT. Returns (settings, result);
    result None = the dialog was cancelled."""
    settings = dict(settings)
    cfg = dict(settings.get("CURVE_PLOT") or {})
    if action in ("on", "off"):
        cfg["ENABLED"] = action == "on"
        settings["CURVE_PLOT"] = cfg
        return settings, {"action": action}
    out = pushover_curve.edit_curves(
        pushover_curve.curves_of(cfg), settings.get("RESULTS_DATABASE"), cfg.get("ENABLED", True),
        info="Curves drawn by %s for every job, with the frames of the exported images marked. "
             "Each axis: a variable of a section, or two of them combined (A - B, A + B, A * B, A / B). "
             "Sections and variables are listed from the results database of A_1_Export_Auto.py." % IMAGE_SCRIPT)
    if out is None:
        return settings, None
    cfg["CURVES"], cfg["ENABLED"] = out["curves"], out["enabled"]
    for key in ("SET_CONTAINS", "X", "Y", "RULES"):          # older form, replaced by CURVES
        cfg.pop(key, None)
    settings["CURVE_PLOT"] = cfg
    if out["db"]:
        settings["RESULTS_DATABASE"] = out["db"]
    return settings, dict(out, action="edit")


def export_frames(settings, odb, job):
    """FrameRecords the export would print for this ODB (all views that apply to the job)."""
    step = settings.get("STEP") or list(odb.steps.keys())[-1]
    records = odb_tools.select_frames(odb, step)
    chosen = set()
    for view in settings["VIEWS"]:
        wanted = [w.strip().upper() for w in str(view.get("jobs_containing", "")).split(",") if w.strip()]
        if wanted and not any(w in job.upper() for w in wanted):
            continue
        spec = image_export.parse_frames(view.get("frames")) or settings["FRAMES"]
        chosen.update(r.index for r in image_export.choose_frames(records, spec))
    return [records[i] for i in sorted(chosen)]


def report_curves(settings, result, odb):
    """Log lines and, for a curve saved in the dialog, a preview for the ODB shown."""
    cfg = settings["CURVE_PLOT"]
    state = "ON" if cfg.get("ENABLED") else "OFF"
    log("=" * 70)
    if result["action"] in ("on", "off"):
        log("Curves in the export: %s" % state)
        return
    if result.get("deleted"):
        log("Curve '%s' deleted (curves in the export: %s)" % (result["deleted"], state))
        return
    curve = [c for c in pushover_curve.curves_of(cfg) if c.get("name") == result["selected"]][0]
    log("Curve saved - %s" % pushover_curve.describe(curve))
    log("  curves in the export: %s;  results database: %s" % (state, settings.get("RESULTS_DATABASE")))
    if not SAVE_PREVIEW:
        return
    db, job = settings.get("RESULTS_DATABASE"), odb_tools.job_name(odb.path)
    folder = os.path.join(settings["IMAGE_FOLDER"], "_view_previews")
    if not pushover_curve.curve_applies(curve, job):
        log("  note: this curve is not drawn for %s (jobs containing / not containing)" % job)
    try:
        png, msg = pushover_curve.plot_job(db, job, curve, export_frames(settings, odb, job), folder,
                                           title="%s  -  %s (preview)" % (job, curve["name"]))
        if png is None and "no data of job" in msg:          # show the curve of another job instead
            others = pushover_curve.jobs_with_data(db, curve)
            if others:
                log("  %s" % msg)
                png, msg = pushover_curve.plot_job(db, others[0], curve, [], folder,
                                                   title="%s  -  %s (preview, no data of %s)" % (others[0], curve["name"], job))
    except Exception as e:
        msg = "curve %s: preview failed (%s)" % (curve["name"], e)
    log("  preview %s" % msg)


# -----------------------------------------------------------------------------
def overview(settings, global_frames):
    log("Views now in the settings:")
    all_vars = dict((v["name"], v) for v in settings["VARIABLES"])
    for v in settings["VIEWS"]:
        log("  %-26s frames: %s" % (v["name"], image_export.describe_frames(v["frames"]) if v.get("frames")
                                    else "default (%s)" % global_frames))
        for n in (v["variables"] or sorted(all_vars)):
            try:
                lims = image_export.limits_for(v, all_vars[n]) if n in all_vars else []
                text = image_export.describe_limits(lims) if lims else "automatic"
            except ValueError as e:                 # e.g. a typing error in the settings file
                text = "INVALID - %s" % e
            log("  %-26s   %-20s limits: %s" % ("", n, text))
    cfg = settings.get("CURVE_PLOT") or {}
    log("Curves of the export (%s):" % ("ON" if cfg.get("ENABLED") else "OFF"))
    for c in pushover_curve.curves_of(cfg):
        log("  %s" % pushover_curve.describe(c))


def main():
    if odb_tools.session is None:
        raise SystemExit("Run this inside Abaqus/CAE or Viewer (File > Run Script) with the picture set up.")
    odb = odb_tools.viewport_odb()
    if odb is None:
        raise SystemExit("No ODB is displayed in the current viewport - open one and set up the picture first.")

    image = load_image_script()
    settings, info = image.load_settings()
    global_frames = image_export.describe_frames(settings["FRAMES"])
    default_name = "View_%d" % (len(settings["VIEWS"]) + 1)
    name, frames_text, limits_text, curve_text = ask_inputs(default_name, VIEW_FRAMES or "", VIEW_LIMITS or "",
                                                            CURVE or "", global_frames)
    if name is None:
        log("Cancelled - nothing saved.")
        return
    name, action = name.strip(), (curve_text or "").strip().lower()
    if action not in CURVE_CHOICES:
        log("NOT SAVED - curve field: %r not understood (empty, edit, on or off)" % curve_text)
        return

    view = None
    if name or not action:                 # empty name + curve field = only the curves
        view = add_view(settings, image, name or default_name, frames_text, limits_text)
        if view is None:
            return
        settings = view["settings"]
    curves = None
    if action:
        settings, curves = change_curves(settings, action)
        if curves is None and view is None:
            log("Cancelled - nothing saved.")
            return
    image.save_settings(settings)
    if view:
        report_view(settings, view, global_frames)
    if curves:
        report_curves(settings, curves, odb)
    elif action == "edit":
        log("Curve dialog cancelled - curves unchanged.")
    overview(settings, global_frames)


if __name__ == "__main__":
    main()
