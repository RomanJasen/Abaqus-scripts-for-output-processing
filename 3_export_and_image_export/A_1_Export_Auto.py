"""
A_1_Export_Auto.py - export cross-section displacements and forces from Abaqus
ODB files (IMPLICIT and EXPLICIT) into the results database.

Replaces  1_Export_Auto_optimised EXPLICIT.py  and the implicit copy in
"implicit odbs and export functions". The analysis type is detected per ODB.

TO USE THE SCRIPTS IN ANOTHER FOLDER copy everything whose name starts with A_:
    A_1_Export_Auto.py, A_2_Image_export_Auto.py, A_2_Image_save_view.py and the
    folder A_IMPORT_additional_functions (it must stay next to the scripts).
    (Optional: the *_settings.json files, to take the saved settings along.)

Run (free-body cuts need the CAE kernel, so use "abaqus cae", not "abaqus python"):
    abaqus cae noGUI=A_1_Export_Auto.py
or in Abaqus/CAE or Viewer: File > Run Script...

SETTINGS ARE REMEMBERED
    The settings of each export are saved in 1_Export_Auto_settings.json next to
    this script (just before the export starts) and are loaded again next time.
    CONFIG below only gives the defaults for the first run in a folder.
    Change a setting in the dialog (USE_GUI = True) or edit it here in the
    script - the latest change wins. Delete 1_Export_Auto_settings.json to start
    again from the defaults below.

PROGRESS
    Abaqus/CAE and Viewer often show script messages only when the script ends.
    Every message is therefore also written to 1_Export_Auto_log.txt next to this
    script - open it at any time to see how far the export is.
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
import section_definitions as sdefs
import section_displacements
import section_forces
import database_io
import export_settings
from odb_tools import log

LOG_FILE_NAME = "1_Export_Auto_log.txt"

# =============================================================================
# CONFIGURATION  (edit the lines marked INPUT)
# =============================================================================
DEFAULT_DATABASE_NAME = "Panel_results"   # INPUT: name of the results database folder (created next to this script)

USE_GUI = True           # INPUT: True -> settings dialog before the export
GUI_BACKEND = "tk"       # INPUT: "tk" (works everywhere) or "abaqus" (getInputs, only from the CAE GUI)

# Defaults for the first run in a folder (afterwards the saved settings are used,
# except for values you change here - see "SETTINGS ARE REMEMBERED" above).
# Paths may be absolute or relative to the folder of this script ("." = that folder).
CONFIG = {
    "ODB_FOLDER": ".",                        # folder with the .odb files
    "ODB_NAMES": None,                        # None = every .odb in ODB_FOLDER; or ["a.odb", "b.odb"]
    "STEP": None,                             # None = the last step of each ODB; or e.g. "HOR"
    "DATABASE_PATH": DEFAULT_DATABASE_NAME,   # results database folder
    "SET_FILTER": [""],      # only SETs containing one of these strings ("" = all)
    "ANALYSIS_TYPE": "AUTO", # "AUTO", "IMPLICIT" or "EXPLICIT"
    # Keep a frame only if it is >= this much step time after the last kept one.
    # None = every frame. (The old implicit script used dT=1 with a strict '>' test,
    # which on 1 s frames kept every 2nd frame; use 2.0 here to reproduce that.)
    "MIN_FRAME_TIME_INCREMENT": {"IMPLICIT": 1.0, "EXPLICIT": None},
    # "index"     -> frameId column = frame number as in Abaqus/CAE (position in step)
    # "increment" -> frameId column = frame.frameId (increment number in Explicit)
    "FRAME_ID_COLUMN": "index",
    # Section rotations/displacements - see DEFAULT_KINEMATICS in section_displacements.py.
    # Only the keys given here override the defaults there.
    "KINEMATICS": {
        "METHOD": "rigid",                   # "rigid" (large rotations) | "angle" | "slope"
        "ROTATIONS": {"fix": "relative", "fiy": "relative", "fiz": "relative"},  # or "absolute"
    },
    # Section forces - see DEFAULT_FORCE_OPTIONS in section_forces.py.
    "FORCES": {
        "METHOD": "freebody",                # "freebody" (Abaqus cut) | "nforc" (needs NFORC output)
    },
    "OVERWRITE": False,          # re-export sections that already have a result file
    "CONTINUE_ON_ERROR": False,  # log a failing SET and go on with the next one
    "COPY_INP": True,            # copy <job>.inp next to the results
}
# =============================================================================


def prepare_config(cfg):
    """Plain-str text (Abaqus 2021 / Python 2 rejects 'unicode'), absolute paths,
    and a valid ODB folder. The ODB list is not filled in yet."""
    cfg = export_settings.to_absolute(odb_tools.native(dict(cfg)), SCRIPT_DIR)
    if not cfg.get("ODB_FOLDER"):
        cfg["ODB_FOLDER"] = SCRIPT_DIR
    if not os.path.isdir(cfg["ODB_FOLDER"]):
        log("WARNING: ODB folder %s does not exist - using the script folder" % cfg["ODB_FOLDER"])
        cfg["ODB_FOLDER"] = SCRIPT_DIR
    if not cfg.get("DATABASE_PATH"):
        cfg["DATABASE_PATH"] = os.path.join(SCRIPT_DIR, DEFAULT_DATABASE_NAME)
    return cfg


def resolve_config(cfg):
    """prepare_config() + the list of ODB files to export + checks."""
    cfg = prepare_config(cfg)
    available = odb_tools.list_odbs(cfg["ODB_FOLDER"])
    names = cfg.get("ODB_NAMES")
    if names:
        missing = [n for n in names if n not in available]
        names = [n for n in names if n in available]
        if missing:
            log("NOTE: %d selected ODB file(s) are not in %s any more: %s"
                  % (len(missing), cfg["ODB_FOLDER"], ", ".join(missing)))
        if not names:
            log("NOTE: none of the selected ODB files exist here - using all ODB files of the folder")
    cfg["ODB_NAMES"] = names or available
    if not cfg["ODB_NAMES"]:
        raise ValueError("No .odb files found in %s" % cfg["ODB_FOLDER"])
    if os.path.normcase(cfg["DATABASE_PATH"]) == os.path.normcase(os.path.normpath(SCRIPT_DIR)):
        raise ValueError("DATABASE_PATH must not be the script folder itself")
    return cfg


def remember(cfg):
    """Save the settings of this export for the next run. If every ODB of the folder
    is selected, 'all' is saved, so ODB files added later are included next time."""
    to_save = dict(cfg)
    if set(cfg["ODB_NAMES"]) == set(odb_tools.list_odbs(cfg["ODB_FOLDER"])):
        to_save["ODB_NAMES"] = None
    try:
        log("Settings saved to %s" % export_settings.save(to_save, CONFIG, SCRIPT_DIR, script_name=SCRIPT_NAME))
    except (IOError, OSError) as e:
        log("WARNING: settings could not be saved: %s" % e)


def frame_id_value(rec, mode):
    return rec.index if mode == "index" else rec.frame_id


def build_rows(frames, displacement_rows, force_rows, frame_id_mode):
    """Merge per-frame data; every frame must be present in every source."""
    rows = []
    for rec in frames:
        if rec.index not in displacement_rows:
            raise odb_tools.FrameSyncError("Frame index %d missing from displacements" % rec.index)
        if force_rows is not None and rec.index not in force_rows:
            raise odb_tools.FrameSyncError("Frame index %d missing from forces" % rec.index)
        forces = force_rows[rec.index] if force_rows is not None else [None] * 6
        rows.append([round(rec.step_time, 6), frame_id_value(rec, frame_id_mode)]
                    + list(displacement_rows[rec.index]) + list(forces))
    return rows


def export_odb(odb_path, cfg, report):
    job = odb_tools.job_name(odb_path)
    db = cfg["DATABASE_PATH"]
    # an ODB already open in the viewer is reused and left open
    log("  opening ODB ...")
    odb, opened_here = odb_tools.open_or_reuse(odb_path)
    log("  ODB %s" % ("opened" if opened_here else "already open in the viewer - reused"))
    try:
        step = cfg["STEP"] or list(odb.steps.keys())[-1]
        analysis = cfg["ANALYSIS_TYPE"]
        if analysis == "AUTO":
            analysis = odb_tools.detect_analysis_type(odb, step)
        min_dt = cfg["MIN_FRAME_TIME_INCREMENT"].get(analysis)
        frames = odb_tools.select_frames(odb, step, min_time_increment=min_dt)
        log("  %s analysis, step %s%s: %d frames selected (min dT = %s)" % (
            analysis, step, "" if cfg["STEP"] else " (last step)", len(frames), min_dt))

        set_names = sdefs.select_sets(odb.rootAssembly.nodeSets.keys(), cfg["SET_FILTER"])
        database_io.ensure_database(db, set_names)
        todo = [s for s in set_names if cfg["OVERWRITE"] or not database_io.section_exported(db, s, job)]

        """
        for s in set_names:
            print(cfg)
            print(cfg["OVERWRITE"])
            print(database_io)
            print(not database_io.section_exported(db, s, job))
        asd=dsa
        """

        for s in set_names:
            if s not in todo:
                log("  already exported, skipped: %s" % s)
        if not todo:
            return

        sections = []
        for s in todo:
            try:
                sections.append(sdefs.parse(s))
            except ValueError as e:
                log("  SKIPPED SET: %s" % e)

        # 1) displacements of all sections in one pass over the frames
        log("  displacements of %d section(s) ..." % len(sections))
        t0 = time.time()
        displacements = section_displacements.extract_section_displacements(
            odb, sections, frames, kinematics=cfg["KINEMATICS"], skip_errors=cfg["CONTINUE_ON_ERROR"])
        log("  displacements of %d sections done in %.1fs" % (len(sections), time.time() - t0))

        # 2) forces section by section (one free-body cut each), 3) write
        for k, section in enumerate(sections):
            name = section.set_name
            try:
                if name not in displacements:
                    raise ValueError("no displacement data (see message above)")
                ref, disp_rows = displacements[name]
                force_rows = None
                if section.type.forces:
                    log("  forces %s (%s) ..." % (name, cfg["FORCES"]["METHOD"]))
                    t1 = time.time()
                    force_rows = section_forces.extract_section_forces(
                        odb, step, section, frames, cfg["FORCES"])
                    log("  forces %s (%s) done in %.1fs" % (name, cfg["FORCES"]["METHOD"], time.time() - t1))
                rows = build_rows(frames, disp_rows, force_rows, cfg["FRAME_ID_COLUMN"])
                database_io.write_section_file(db, name, job, rows)
                database_io.write_attributes(db, name, ref.centre0, ref.dimensions)
                if cfg["COPY_INP"]:
                    database_io.copy_inp(odb_path, db, name, job)
                report["exported"].append((job, name))
                log("  [%d/%d] exported %s" % (k + 1, len(sections), name))
            except Exception as e:
                report["failed"].append((job, name, str(e)))
                if not cfg["CONTINUE_ON_ERROR"]:
                    raise
                log("  [%d/%d] FAILED %s: %s" % (k + 1, len(sections), name, e))
                log(traceback.format_exc())
        database_io.register_job(db, job)
    finally:
        if opened_here:
            odb.close()


def run(cfg):
    cfg = resolve_config(cfg)
    log("=" * 78)
    log("ODB folder : %s   (%d ODB files)" % (cfg["ODB_FOLDER"], len(cfg["ODB_NAMES"])))
    log("Database   : %s" % cfg["DATABASE_PATH"])
    log("Step       : %s" % (cfg["STEP"] or "last step of each ODB"))
    log("Kinematics : %s   |   Forces: %s" % (cfg["KINEMATICS"], cfg["FORCES"]))
    log("=" * 78)

    report = {"exported": [], "failed": []}
    t0 = time.time()
    for i, name in enumerate(cfg["ODB_NAMES"]):
        path = os.path.join(cfg["ODB_FOLDER"], name)
        log("\n[%d/%d] %s" % (i + 1, len(cfg["ODB_NAMES"]), path))
        odb_tools.progress("Exporting", i + 1, len(cfg["ODB_NAMES"]), "ODB files")
        try:
            export_odb(path, cfg, report)
        except Exception as e:
            report["failed"].append((odb_tools.job_name(path), "*", str(e)))
            if not cfg["CONTINUE_ON_ERROR"]:
                raise
            log(traceback.format_exc())

    log("\n" + "=" * 78)
    log("DONE in %.1f min: %d sections exported, %d failures" % (
        (time.time() - t0) / 60.0, len(report["exported"]), len(report["failed"])))
    for f in report["failed"]:
        log("  FAILED %s / %s: %s" % f)
    return report


def known_steps():
    """Step names of the ODB shown in the viewport. It is already open, so nothing
    has to be opened (the dialog itself must not call Abaqus - see export_gui)."""
    odb = odb_tools.viewport_odb()
    try:
        return list(odb.steps.keys()) if odb is not None else []
    except Exception:
        return []


def main():
    odb_tools.set_log_file(os.path.join(SCRIPT_DIR, LOG_FILE_NAME), "%s started" % SCRIPT_NAME)
    try:
        cfg, info = export_settings.load(CONFIG, SCRIPT_DIR)
        log(info)
        cfg = prepare_config(cfg)
        if USE_GUI:
            import export_gui
            log("Settings dialog open - waiting for 'Run export' or 'Cancel' ...")
            cfg = export_gui.edit_config(cfg, GUI_BACKEND, defaults=prepare_config(CONFIG), info=info,
                                         steps=known_steps())
            if cfg is None:
                log("Export cancelled - saved settings unchanged.")
                return
            log("Settings dialog closed.")
        cfg = resolve_config(cfg)
        remember(cfg)  # before the export, so an interrupted export is remembered too
        run(cfg)
    except Exception:
        log("EXPORT STOPPED BY AN ERROR:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
