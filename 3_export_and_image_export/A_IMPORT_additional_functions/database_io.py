"""
database_io.py - results database on disk.
Merges the former Database_creation.py and Exporting_into_the_database.py.
(Export settings are remembered by export_settings.py, not here.)

Database layout (unchanged, downstream scripts rely on it):
    <DB>/
        baza sadzaj liste.txt          SET names, '###', exported jobs
        baza sadzaj liste_LOG.txt      every export appended
        <SET>/Attributes.json          section centre + dimensions
        <SET>/<JOB>/Section_dataIIII<SET>IIII<JOB>.txt
        <SET>/<JOB>/<job>.inp

No Abaqus import: runs in any Python.  Demo (writes into a temp folder):
    python database_io.py
"""
from __future__ import print_function

import os
import json
import shutil

try:  # progress messages that show while Abaqus runs (see odb_tools.log)
    from odb_tools import log
except ImportError:
    log = print

HEADER = ["Time", "frameId", "Ux", "Uy", "Uz", "fix", "fiy", "fiz", "Fx", "Fy", "Fz", "Mx", "My", "Mz"]
CONTENT_FILE = "baza sadzaj liste.txt"
CONTENT_LOG = "baza sadzaj liste_LOG.txt"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def section_file_path(db_path, set_name, job):
    name = "Section_dataIIII%sIIII%s.txt" % (set_name.upper(), job.upper())
    return os.path.join(db_path, set_name, job, name)


def section_exported(db_path, set_name, job):
    return os.path.isfile(section_file_path(db_path, set_name, job))


def ensure_database(db_path, set_names):
    """Create the database folder, SET sub-folders and content files if missing."""
    if not os.path.isdir(db_path):
        log("Creating new database: %s" % db_path)
        os.makedirs(db_path)
    for s in set_names:
        p = os.path.join(db_path, s.upper())
        if not os.path.isdir(p):
            os.makedirs(p)
    for name in (CONTENT_FILE, CONTENT_LOG):
        p = os.path.join(db_path, name)
        if not os.path.isfile(p):
            with open(p, "w") as f:
                f.writelines([s.upper() + "\n" for s in sorted(set_names)] + ["###\n"])


def format_value(v):
    """Full-precision text; None -> empty field."""
    if v is None or v == "":
        return ""
    if isinstance(v, str):
        return v
    return repr(float(v)) if not isinstance(v, int) else str(v)


def write_section_file(db_path, set_name, job, rows, header=HEADER):
    """rows: list of 14-value lists. Format kept identical to the original:
    comma after every value, no newline after the last row."""
    path = section_file_path(db_path, set_name, job)
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    lines = [",".join(header) + ","]
    for row in rows:
        lines.append(",".join(format_value(v) for v in row) + ",")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def write_attributes(db_path, set_name, centre, dimensions):
    """Store section centre/dimensions; warn if an existing file disagrees."""
    path = os.path.join(db_path, set_name.upper(), "Attributes.json")
    data = {"CoordX": centre[0], "CoordY": centre[1], "CoordZ": centre[2],
            "DimensionX": dimensions[0], "DimensionY": dimensions[1], "DimensionZ": dimensions[2]}
    if not os.path.isfile(path):
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            json.dump(data, f)
        return
    with open(path) as f:
        old = json.load(f)
    diff = [k for k in data if k not in old or abs(float(old[k]) - float(data[k])) > 1e-3 * max(1.0, abs(float(data[k])))]
    if diff:
        log("WARNING: %s differs from the current model in %s (file kept)" % (path, diff))


def copy_inp(odb_path, db_path, set_name, job):
    src = os.path.splitext(odb_path)[0] + ".inp"
    if not os.path.isfile(src):
        log("  .inp not found, not copied: %s" % src)
        return
    dst_dir = os.path.join(db_path, set_name.upper(), job)
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    shutil.copy(src, os.path.join(dst_dir, os.path.basename(src)))


def register_job(db_path, job):
    """Append job to the LOG and add it to the content list if not already there."""
    with open(os.path.join(db_path, CONTENT_LOG), "a") as f:
        f.write(job + "\n")
    content = os.path.join(db_path, CONTENT_FILE)
    lines = []
    if os.path.isfile(content):
        with open(content) as f:
            lines = [l.rstrip("\n") for l in f]
    if job not in lines:
        with open(content, "a") as f:
            f.write(job + "\n")


if __name__ == "__main__":
    import tempfile
    db = os.path.join(tempfile.mkdtemp(), "Demo_database")
    sets = ["V_PIER&DEMO&1&0"]
    ensure_database(db, sets)
    rows = [[0.0, 0, 0.001, 0.0, -0.03, 1e-6, None, 8.6e-6, 24.7, -252.4, 1067370.5, 3208676.75, -402432.0, 78599.6],
            [0.1, 1, 0.007, 0.0018, -0.031, 4.4e-6, -6.9e-6, 9.0e-6, 25.1, -250.0, 1067000.0, 3208000.0, -402000.0, 78500.0]]
    p = write_section_file(db, sets[0], "DEMO_JOB", rows)
    write_attributes(db, sets[0], [1800.0, 0.0, 120.0], [1200.0, 150.0, 0.0])
    register_job(db, "DEMO_JOB")
    print("Demo database written to:", db)
    for root, _, files in os.walk(db):
        for fn in files:
            print("  ", os.path.relpath(os.path.join(root, fn), db))
    print("--- %s ---" % os.path.basename(p))
    with open(p) as f:
        print(f.read())
