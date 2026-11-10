"""
export_settings.py - remembers the settings of the last export.

Method: a JSON text file, 1_Export_Auto_settings.json, next to A_1_Export_Auto.py
  * written just BEFORE each export starts (an interrupted export is remembered too)
  * read at the next start, so nothing has to be entered again
  * plain text: open it in any editor; delete it to go back to the defaults
    written in A_1_Export_Auto.py

Which value is used, per setting ("latest change wins"):
  the saved value - unless that setting's default in A_1_Export_Auto.py was edited
  after the file was written; then the new value from the script is used.
  To detect this the file also stores the script defaults it was written with.
  So a setting can be changed in the dialog OR in the script, and it sticks.

Paths inside the script folder are stored relative to it ("." and "Panel_results"),
so a copy of the script folder points at its own ODBs and database.

No Abaqus import: runs in any Python.  Demo (works in a temp folder):
    python export_settings.py
"""
from __future__ import print_function

import os
import sys
import copy
import json
import time
import inspect

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import odb_tools

# Defaults for A_1_Export_Auto.py; other scripts (e.g. A_2_Image_export_Auto.py) pass
# their own file_name / path_keys / script_name to the functions below. (The settings
# files keep their names without A_: they are written by the scripts, not copied.)
SETTINGS_FILE_NAME = "1_Export_Auto_settings.json"
PATH_KEYS = ("ODB_FOLDER", "DATABASE_PATH")
_MISSING = object()


def settings_file(script_dir, file_name=SETTINGS_FILE_NAME):
    """file_name may also be an absolute path (a shared settings file)."""
    return os.path.join(script_dir, file_name)


# ---------------------------------------------------------------------------
# Paths: absolute <-> relative to the script folder
# ---------------------------------------------------------------------------
def absolute_path(path, script_dir):
    """Relative paths are taken relative to the script folder."""
    if not path:
        return path
    path = odb_tools.native(path)
    if not os.path.isabs(path):
        path = os.path.join(script_dir, path)
    return os.path.normpath(os.path.abspath(path))


def portable_path(path, script_dir):
    """Relative to the script folder if inside it ("." = the folder itself), else absolute."""
    if not path:
        return path
    p = absolute_path(path, script_dir)
    try:
        rel = os.path.relpath(p, os.path.normpath(os.path.abspath(script_dir)))
    except ValueError:  # on another drive
        return p
    if rel == os.curdir:
        return "."
    if rel.split(os.sep)[0] == os.pardir:
        return p
    return rel


def _convert_paths(cfg, script_dir, func, path_keys):
    out = copy.deepcopy(cfg)
    for k in path_keys:
        if out.get(k):
            out[k] = func(out[k], script_dir)
    return out


def to_absolute(cfg, script_dir, path_keys=PATH_KEYS):
    return _convert_paths(cfg, script_dir, absolute_path, path_keys)


def to_portable(cfg, script_dir, path_keys=PATH_KEYS):
    return _convert_paths(cfg, script_dir, portable_path, path_keys)


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def _merge(code, saved, snap):
    """Latest change wins, per key and recursively for nested settings:
    saved value, unless the script value differs from the script value at save time."""
    if isinstance(code, dict) and (saved is _MISSING or isinstance(saved, dict)):
        # (a saved value of another type - e.g. FRAMES as text "5" - is compared as a whole below)
        saved = saved if isinstance(saved, dict) else {}
        snap = snap if isinstance(snap, dict) else {}
        out = dict((k, _merge(v, saved.get(k, _MISSING), snap.get(k, _MISSING)))
                   for k, v in code.items())
        # keys only in the saved file were added there by the user (e.g. FRAMES "INDICES")
        # and are kept; a key that was in the script before (in snap) but is not any more
        # was removed from the script on purpose and is dropped
        for k, v in saved.items():
            if k not in code and k not in snap:
                out[k] = copy.deepcopy(v)
        return out
    if saved is _MISSING:
        return copy.deepcopy(code)
    if snap is not _MISSING and snap != code:
        return copy.deepcopy(code)  # edited in the script after the last export
    return copy.deepcopy(saved)


def read(script_dir, file_name=SETTINGS_FILE_NAME):
    """(file content, None) or (None, message)."""
    path = settings_file(script_dir, file_name)
    if not os.path.isfile(path):
        return None, "No saved settings (%s) - using the defaults from the script" % os.path.basename(path)
    try:
        with open(path) as f:
            data = odb_tools.native(json.load(f))  # json returns unicode in Python 2
        if not isinstance(data.get("settings"), dict):
            raise ValueError("no 'settings' section")
        return data, None
    except Exception as e:
        return None, "Could not read %s (%s) - using the defaults from the script" % (os.path.basename(path), e)


def load(defaults, script_dir, file_name=SETTINGS_FILE_NAME, path_keys=PATH_KEYS):
    """Settings for this run and a message saying where they came from.
    defaults : CONFIG of the script.  Returned paths are absolute."""
    code = to_portable(odb_tools.native(defaults), script_dir, path_keys)
    data, msg = read(script_dir, file_name)
    if data is None:
        return to_absolute(code, script_dir, path_keys), msg
    snap = data.get("code_defaults", {})
    merged = _merge(code, data["settings"], snap)
    info = "Settings saved %s loaded from %s" % (data.get("saved", "?"), os.path.basename(file_name))
    changed = sorted(k for k in code if k in snap and code[k] != snap[k])
    if changed:
        info += "; changed in the script since then (script value used): " + ", ".join(changed)
    return to_absolute(merged, script_dir, path_keys), info


def saved_settings(script_dir, file_name=SETTINGS_FILE_NAME, path_keys=PATH_KEYS):
    """Only the last saved settings (paths absolute); {} if there are none."""
    data, _ = read(script_dir, file_name)
    return to_absolute(data["settings"], script_dir, path_keys) if data else {}


def save(settings, defaults, script_dir, file_name=SETTINGS_FILE_NAME, path_keys=PATH_KEYS,
         script_name="A_1_Export_Auto.py"):
    """Write the settings of this run, plus the script defaults (to detect later edits)."""
    data = {
        "_info": ["Settings written by %s and loaded at its next start." % script_name,
                  "Change a setting here or in the script: the latest change wins.",
                  "Delete this file to go back to the defaults written in %s." % script_name,
                  "Paths without a drive letter are relative to the folder of the script."],
        "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
        "settings": to_portable(odb_tools.native(settings), script_dir, path_keys),
        "code_defaults": to_portable(odb_tools.native(defaults), script_dir, path_keys),
    }
    path = settings_file(script_dir, file_name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(odb_tools.to_text(data), f, indent=2, sort_keys=True, separators=(",", ": "))
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp, path)
    return path


if __name__ == "__main__":
    import shutil
    import tempfile
    folder = tempfile.mkdtemp()
    try:
        defaults = {"ODB_FOLDER": ".", "DATABASE_PATH": "Panel_results", "STEP": None,
                    "FORCES": {"METHOD": "freebody"}}
        print("1) first run:", load(defaults, folder)[1])
        cfg, _ = load(defaults, folder)
        print("   ODB folder  ->", cfg["ODB_FOLDER"])
        print("   database    ->", cfg["DATABASE_PATH"])

        cfg["STEP"] = "HOR"
        cfg["FORCES"]["METHOD"] = "nforc"
        save(cfg, defaults, folder)
        cfg2, info = load(defaults, folder)
        print("2) after an export with STEP=HOR, forces=nforc:\n  ", info)
        print("   STEP=%s  FORCES=%s" % (cfg2["STEP"], cfg2["FORCES"]))

        edited = dict(defaults, DATABASE_PATH="Panel_results_v2")
        cfg3, info = load(edited, folder)
        print("3) database name edited in the script:\n  ", info)
        print("   database -> %s   (STEP=%s and FORCES=%s still remembered)" % (
            cfg3["DATABASE_PATH"], cfg3["STEP"], cfg3["FORCES"]))

        print("--- %s ---" % SETTINGS_FILE_NAME)
        with open(settings_file(folder)) as f:
            print(f.read())
    finally:
        shutil.rmtree(folder)
