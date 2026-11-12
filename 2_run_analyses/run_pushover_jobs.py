# -*- coding: utf-8 -*-
"""
run_pushover_jobs.py - pushover analyses in Abaqus/CAE: the chosen models of the open .cae
are run at every vertical force (pre-compression), a chosen number of analyses at the same
time, each analysis on a chosen number of cores.

Cleaned-up version of Automatic_job_running_generalEXPLICIT.py (same Abaqus commands).

HOW TO RUN
    1. Open the model database (.cae) in Abaqus/CAE. The ODB files are written to the work
       directory (File > Set Work Directory...).
    2. File > Run Script... > run_pushover_jobs.py
    3. The first dialog shows the INPUT below - change it if needed:
           Models              names separated by commas, * and ? as wildcards (* = all models)
           Vertical forces     separated by commas, in the force unit of the model;
                               empty = the models are run with the force they have
           Analyses at a time  number of analyses running at the same time
           Cores per analysis  cores of every analysis (numCpus = numDomains)
       The second dialog lists the analyses and asks before anything is changed or submitted.
    Abaqus/CAE stays busy until the last analysis has been submitted (the script waits for
    free places). Analyses whose <job>.odb already exists in the work directory are skipped,
    so an interrupted run is continued by running the script again (delete the .odb of a
    failed analysis to repeat it). Progress: run_pushover_jobs_log.txt in the work directory.

WHAT IS CHANGED IN THE MODEL
    The concentrated force LOAD_NAME gets cf3 = -force (pointing down) in the steps LOAD_STEPS,
    then the job is created and submitted. The model keeps the force of the last analysis.

JOB NAMES
    JOB_NAME with {model} and {force}, e.g. BEND_NOkey_S_FR07_EX_360000; without vertical
    forces "_{force}" is left out (BEND_NOkey_S_FR07_EX).

Parameter studies (contact, CDP material) are run with run_parameter_study.py.
Written for Abaqus 2021 (Python 2.7); also runs with Python 3.
"""
from __future__ import print_function

import os
import re
import sys
import time
import fnmatch

from abaqus import mdb
from abaqusConstants import *

# =============================================================================
# INPUT (the first dialog starts with these values)
# =============================================================================
MODELS = ["BEND_NOkey_S_FR07"]      # INPUT: models of the open .cae; "*" = all, wildcards * and ?
VERTICAL_FORCES = [34272, 172699, 360000, 720000, 1080000, 1440000, 1800000, 2160000, 2520000]
                                    # INPUT: one analysis per force; [] = the models as they are
JOBS_AT_ONCE = 2                    # INPUT: analyses running at the same time
CORES_PER_JOB = 4                   # INPUT: cores per analysis (numCpus = numDomains)

LOAD_NAME = "VERT_FORCE"            # concentrated force of the models (cf3 = -force)
LOAD_STEPS = ("VERT", "HOR")        # steps in which the force is set
JOB_NAME = "{model}_EX_{force}"     # job name

JOB_SETTINGS = dict(                # further arguments of mdb.Job (here: Abaqus/Explicit, double precision)
    memory=90, memoryUnits=PERCENTAGE, explicitPrecision=DOUBLE_PLUS_PACK, nodalOutputPrecision=FULL,
    parallelizationMethodExplicit=DOMAIN, activateLoadBalancing=False, multiprocessingMode=DEFAULT)

ASK = True          # INPUT: False = no dialogs, the INPUT is used as it is (e.g. abaqus cae noGUI=...)
SUBMIT = True       # INPUT: False = only write the input files <job>.inp (to run them later)
WAIT_AT_END = False # INPUT: True = the script also waits until the last analyses have finished
# =============================================================================

LOG = os.path.join(os.getcwd(), "run_pushover_jobs_log.txt")
FORBIDDEN = ' ,.$&*~!()[]{}|;:"\'`<>?/\\'
FIELDS = ("Models (separated by commas; * and ? as wildcards, * = all):",
          "Vertical forces (separated by commas; empty = as in the model):",
          "Analyses at the same time:",
          "Cores per analysis:")


def log(message=""):
    """print() that is also written to run_pushover_jobs_log.txt (with the time)."""
    print(message)
    try:
        sys.stdout.flush()
        with open(LOG, "a") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Input
# -----------------------------------------------------------------------------
def split_list(text):
    return [t for t in re.split(r"[,;\s]+", text.strip()) if t]


def number(text, what):
    try:
        value = float(text)
    except ValueError:
        raise ValueError("%s: %r is not a number" % (what, text))
    return int(value) if value == int(value) else value


def whole_number(text, what):
    value = number(text, what)
    if value != int(value) or value < 1:
        raise ValueError("%s must be a whole number of at least 1, not %r" % (what, text))
    return int(value)


def choose_models(patterns, available):
    """Model names matching the patterns (* and ?, not case sensitive), in the given order."""
    if not patterns:
        raise ValueError("no model given")
    chosen = []
    for pattern in patterns:
        hits = [m for m in available if fnmatch.fnmatchcase(m.upper(), pattern.upper())]
        if not hits:
            raise ValueError("no model %r in the open .cae (models: %s)" % (pattern, ", ".join(available)))
        chosen += [m for m in hits if m not in chosen]
    return chosen


def parse(texts):
    """[models, forces, at once, cores] as text -> settings dict (ValueError on a mistake)."""
    models = choose_models(split_list(texts[0]), sorted(mdb.models.keys()))
    forces = [number(t, "vertical forces") for t in split_list(texts[1])]
    settings = dict(models=models, forces=forces,
                    at_once=whole_number(texts[2], "analyses at the same time"),
                    cores=whole_number(texts[3], "cores per analysis"))
    check_models(models, forces)
    return settings


def input_texts():
    return [", ".join(MODELS), ", ".join("%s" % f for f in VERTICAL_FORCES), str(JOBS_AT_ONCE), str(CORES_PER_JOB)]


def check_models(models, forces):
    if not forces:
        return
    for name in models:
        model = mdb.models[name]
        if LOAD_NAME not in model.loads.keys():
            raise ValueError("model %s has no load %s (loads: %s)" % (name, LOAD_NAME, ", ".join(model.loads.keys())))
        missing = [s for s in LOAD_STEPS if s not in model.steps.keys()]
        if missing:
            raise ValueError("model %s has no step %s (steps: %s)" % (name, ", ".join(missing),
                                                                       ", ".join(model.steps.keys())))


# -----------------------------------------------------------------------------
# Jobs
# -----------------------------------------------------------------------------
def force_text(force):
    return ("%s" % force).replace(".", "_")


def job_name(model, force):
    if force is None:
        return JOB_NAME.replace("_{force}", "").replace("{force}", "").format(model=model)
    return JOB_NAME.format(model=model, force=force_text(force))


def make_plan(models, forces):
    """[(model, force or None, job name), ...] in the order of submission."""
    plan = [(m, f, job_name(m, f)) for m in models for f in (forces or [None])]
    names = [p[2] for p in plan]
    bad = [n for n in names if len(n) > 80 or any(c in n for c in FORBIDDEN)]
    if bad:
        raise ValueError("invalid job name(s) (max. 80 characters, none of %s): %s" % (FORBIDDEN, ", ".join(bad)))
    twice = sorted(set(n for n in names if names.count(n) > 1))
    if twice:
        raise ValueError("job name(s) used twice - JOB_NAME needs {model} and {force}: %s" % ", ".join(twice))
    return plan


def already_there(job):
    """'<job>.odb' / '<job>.lck' if the analysis is done or running, else None."""
    for ending in (".odb", ".lck"):
        if os.path.exists(os.path.join(os.getcwd(), job + ending)):
            return job + ending
    return None


def finished(job):
    return mdb.jobs[job].status in (COMPLETED, ABORTED, TERMINATED)


def wait_for(job):
    log("waiting for %s" % job)
    mdb.jobs[job].waitForCompletion()
    log("finished: %s (%s)" % (job, mdb.jobs[job].status))


def run(plan, at_once, cores):
    """Set the force, create the job and submit it - at most at_once analyses at a time."""
    running, done, failed = [], [], []
    for model_name, force, job in plan:
        if SUBMIT:
            while len(running) >= at_once:        # wait for the oldest; drop the ones finished meanwhile
                wait_for(running.pop(0))
                running = [j for j in running if not finished(j)]
        model = mdb.models[model_name]
        try:
            if force is not None:
                for step in LOAD_STEPS:
                    model.loads[LOAD_NAME].setValuesInStep(stepName=step, cf3=-force)
            if job in mdb.jobs.keys():
                del mdb.jobs[job]
            settings = dict(JOB_SETTINGS, numCpus=cores, numDomains=cores)
            mdb.Job(name=job, model=model_name, description="" if force is None else "vertical force %s" % force,
                    type=ANALYSIS, atTime=None, waitMinutes=0, waitHours=0, queue=None, echoPrint=OFF,
                    modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine="", scratch="",
                    resultsFormat=ODB, **settings)
            if SUBMIT:
                mdb.jobs[job].submit()
                running.append(job)
                log("submitted: %s (%d running)" % (job, len(running)))
            else:
                mdb.jobs[job].writeInput(consistencyChecking=OFF)
                log("input file written: %s.inp" % job)
            done.append(job)
        except Exception as error:            # one bad job must not stop the others
            failed.append(job)
            log("ERROR %s: %s" % (job, error))
    if WAIT_AT_END:
        for job in running:
            wait_for(job)
        running = []
    return done, failed, running


# -----------------------------------------------------------------------------
# Dialogs (Abaqus/CAE)
# -----------------------------------------------------------------------------
def ask_settings():
    """First dialog, repeated with the error message until the input is valid. None = cancelled."""
    from abaqus import getInputs
    texts = input_texts()
    label = "Pushover analyses of the open model database\nwork directory: %s" % os.getcwd()
    while True:
        answer = getInputs(fields=list(zip(FIELDS, texts)), label=label, dialogTitle="run_pushover_jobs.py")
        if not answer or answer[0] is None:
            return None
        texts = list(answer)
        try:
            return parse(texts)
        except ValueError as error:
            label = "Please correct the input:\n%s" % error


def summary(settings, plan, skipped):
    todo = [p[2] for p in plan if p[2] not in skipped]
    lines = ["%d analyses: %d model(s) x %s" % (len(plan), len(settings["models"]),
             "%d vertical forces" % len(settings["forces"]) if settings["forces"] else "force as in the model"),
             "%d at the same time, %d cores each" % (settings["at_once"], settings["cores"])]
    if skipped:
        lines.append("skipped (ODB already in the work directory or running): %d" % len(skipped))
    lines.append("")
    lines += todo[:12] + (["... and %d more" % (len(todo) - 12)] if len(todo) > 12 else [])
    return lines, todo


def confirm(lines):
    from abaqus import getWarningReply
    action = "Set the forces, create and submit the jobs?" if SUBMIT else "Write the input files?"
    return getWarningReply(message="\n".join(lines + ["", action]), buttons=(YES, NO)) == YES


# -----------------------------------------------------------------------------
def main():
    if ASK:
        try:
            settings = ask_settings()
        except Exception as error:            # e.g. no dialogs without the GUI: stop, submit nothing
            log("the dialog could not be shown (%s) - nothing submitted; to run without dialogs "
                "(e.g. abaqus cae noGUI=run_pushover_jobs.py) set ASK = False" % error)
            raise
        if settings is None:
            log("cancelled")
            return
    else:
        settings = parse(input_texts())

    plan = make_plan(settings["models"], settings["forces"])
    skipped = {}
    for _, _, job in plan:
        found = already_there(job)
        if found:
            skipped[job] = found
    lines, todo = summary(settings, plan, skipped)
    log("=" * 70)
    for line in lines:
        if line:
            log(line)
    for job in sorted(skipped):
        log("skipped (%s exists): %s" % (skipped[job], job))
    if not todo:
        log("nothing to do: every analysis has its ODB file in %s" % os.getcwd())
        return
    if ASK and not confirm(lines):
        log("cancelled")
        return

    done, failed, running = run([p for p in plan if p[2] not in skipped], settings["at_once"], settings["cores"])
    log("DONE: %d %s, %d skipped, %d failed%s" % (
        len(done), "submitted" if SUBMIT else "input files written", len(skipped), len(failed),
        "" if not running else " - still running: %s (see the Job Manager)" % ", ".join(running)))


if __name__ == "__main__":
    main()
