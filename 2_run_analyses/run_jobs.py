# -*- coding: utf-8 -*-
"""
run_jobs.py - parameter study in Abaqus/CAE: for every model and every value of the
studied parameter the model is changed, a job is created and submitted.

Replaces Automatic_job_running_generalEXPLICIT.py, Automatic_job_running_contact.py
and "Automatic_job_running - Material testing.py" (same Abaqus commands, one script).

HOW TO RUN
    Open the model database (.cae) in Abaqus/CAE, then File > Run Script... > run_jobs.py
    Jobs whose <job>.odb already exists in the work folder are skipped, so an
    interrupted study is continued by simply running the script again.
    Progress: run_jobs_log.txt in the work folder.

STUDIES (STUDY below)
    "vertical_force"  value = vertical force: load LOAD_NAME gets cf3 = -value in LOAD_STEPS
                      job name  <prefix>_EX_<force>                 e.g. SHEAR_key_S_TIE_EX_720000
    "contact"         value = (damping, pressure-overclosure stiffness) of CONTACT_PROPERTY
                      job name  <prefix>_Damping_<d>pressure<p>       e.g. B_Damping_0_001pressure100
    "material"        value = one CDP material of the folder material_CDP (EC formula or direct
                      input, see material_CDP/README in 2_run_analyses/README.md); it replaces the
                      material MATERIAL_NAME of the model
                      job name  <prefix>_MAT_<material>               e.g. SHEAR_key_S_FR05_MAT_Mat10
    Another study: write a function change_<name>(model, value) and a cases_<name>() list
    like the ones below and add them to STUDIES.

Written for Abaqus 2021 (Python 2.7).
"""
from __future__ import print_function

import os
import sys
import time
import inspect

from abaqus import mdb
from abaqusConstants import *

# =============================================================================
# INPUT
# =============================================================================
STUDY = "vertical_force"            # INPUT: "vertical_force" | "contact" | "material"
MODELS = ["BEND_NOkey_S_FR07"]      # INPUT: models of the open .cae to run
JOB_PREFIXES = None                 # INPUT: None = the model names; or one prefix per model

# -- vertical_force
VERTICAL_FORCES = [34272, 172699, 360000, 720000, 1080000, 1440000, 1800000, 2160000, 2520000]
LOAD_NAME = "VERT_FORCE"            # concentrated force of the model (cf3 = -force)
LOAD_STEPS = ("VERT", "HOR")        # steps in which the force value is set

# -- contact
CONTACT_PROPERTY = "Simple_contact"   # interaction property of the model
CONTACT_FRICTION = 0.5                # friction coefficient (penalty, isotropic)
CONTACT_DAMPING = [0, 0.0001, 0.001, 0.01]
CONTACT_PRESSURE = [1, 5, 10, 100, 1000]   # exponential pressure-overclosure: (pressure, 0.0), (0.0, 1.0)

# -- material
MATERIAL_NAME = "BETON"             # material of the model that gets the CDP data
MATERIAL_DIR = "material_CDP"       # folder with the material scripts and their input folders

MAX_INCREMENTS_HOR = None           # INPUT: e.g. 2000 = maxNumInc of step HOR (Abaqus/Standard); None = unchanged

# -- jobs
SUBMIT = True                       # INPUT: False = only change the models and create the jobs
JOBS_AT_ONCE = 2                    # INPUT: jobs running at the same time (waits for every n-th job)
JOB_SETTINGS = dict(                # INPUT: arguments of mdb.Job (here: Abaqus/Explicit, 4 cores)
    memory=90, memoryUnits=PERCENTAGE, explicitPrecision=DOUBLE_PLUS_PACK, nodalOutputPrecision=FULL,
    parallelizationMethodExplicit=DOMAIN, numDomains=4, activateLoadBalancing=False,
    multiprocessingMode=DEFAULT, numCpus=4)
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
FORBIDDEN = ' ,$&*~!()[]{}|;:"\'`<>?/\\'
LOG = os.path.join(os.getcwd(), "run_jobs_log.txt")


def log(message=""):
    """print() that shows at once and is also written to run_jobs_log.txt."""
    print(message)
    try:
        sys.stdout.flush()
        with open(LOG, "a") as f:
            f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), message))
    except Exception:
        pass


# -----------------------------------------------------------------------------
# What is changed in the model
# -----------------------------------------------------------------------------
def change_vertical_force(model, force):
    for step in LOAD_STEPS:
        model.loads[LOAD_NAME].setValuesInStep(stepName=step, cf3=-force)


def change_contact(model, value):
    damping, pressure = value
    prop = model.interactionProperties[CONTACT_PROPERTY]
    prop.tangentialBehavior.setValues(
        formulation=PENALTY, directionality=ISOTROPIC, slipRateDependency=OFF, pressureDependency=OFF,
        temperatureDependency=OFF, dependencies=0, table=((CONTACT_FRICTION, ), ), shearStressLimit=None,
        maximumElasticSlip=FRACTION, fraction=0.005, elasticSlipStiffness=None)
    prop.normalBehavior.setValues(
        pressureOverclosure=EXPONENTIAL, table=((pressure, 0.0), (0.0, 1.0)), maxStiffness=None,
        constraintEnforcementMethod=DEFAULT)
    prop.damping.setValues(definition=DAMPING_COEFFICIENT, tangentFraction=DEFAULT, clearanceDependence=STEP,
                           table=((damping, ), ))


def change_material(model, material):
    m = model.materials[MATERIAL_NAME]
    cdp = m.concreteDamagedPlasticity
    m.elastic.setValues(table=material["Elastic"])
    cdp.concreteCompressionHardening.setValues(table=material["Compression_input"])
    cdp.concreteTensionStiffening.setValues(table=material["tension_input"])
    cdp.concreteCompressionDamage.setValues(table=material["damageC"])
    cdp.concreteTensionDamage.setValues(table=material["damageT"])


# -----------------------------------------------------------------------------
# The values of a study: [(job name ending, value), ...]
# -----------------------------------------------------------------------------
def cases_vertical_force():
    return [("_EX_%s" % f, f) for f in VERTICAL_FORCES]


def cases_contact():
    return [("_Damping_%spressure%s" % (str(d).replace(".", "_"), p), (d, p))
            for d in CONTACT_DAMPING for p in CONTACT_PRESSURE]


def cases_material():
    folder = os.path.join(SCRIPT_DIR, MATERIAL_DIR)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import Material_CDP_ECformula_to_tuple_preparation as indirect_input
    import Material_CDP_ECformula_to_tuple as ec_formula
    import Material_CDP_direct_to_tuple as direct_input
    materials = ec_formula.CDP_material_definition_ECformula(indirect_input.Generate_material_dictionaries())
    materials.update(direct_input.Generate_material_dictionaries_DIRECT())
    log("materials: %s" % ", ".join(sorted(materials)))
    return [("_MAT_%s" % name, materials[name]) for name in sorted(materials)]


STUDIES = {"vertical_force": (cases_vertical_force, change_vertical_force),
           "contact": (cases_contact, change_contact),
           "material": (cases_material, change_material)}


# -----------------------------------------------------------------------------
def check_job_names(names):
    bad = [n for n in names if len(n) > 80 or any(c in n for c in FORBIDDEN)]
    if bad:
        raise ValueError("Invalid job name(s) (max. 80 characters, none of %s): %s" % (FORBIDDEN, bad))


def main():
    if STUDY not in STUDIES:
        raise ValueError("STUDY must be one of %s, not %r" % (sorted(STUDIES), STUDY))
    prefixes = JOB_PREFIXES or MODELS
    if len(prefixes) != len(MODELS):
        raise ValueError("JOB_PREFIXES needs one prefix per model")
    missing = [m for m in MODELS if m not in mdb.models.keys()]
    if missing:
        raise ValueError("Model(s) not in the open .cae: %s (available: %s)" % (missing, mdb.models.keys()))
    make_cases, change = STUDIES[STUDY]
    cases = make_cases()
    jobs = [(model, prefix + ending, value) for model, prefix in zip(MODELS, prefixes) for ending, value in cases]
    check_job_names([j for _, j, _ in jobs])
    log("=" * 70)
    log("study %s: %d model(s) x %d value(s) = %d jobs, %d at a time%s" % (
        STUDY, len(MODELS), len(cases), len(jobs), JOBS_AT_ONCE, "" if SUBMIT else " (NOT submitted)"))

    running, submitted, skipped = 0, [], []
    for model_name in MODELS:
        if MAX_INCREMENTS_HOR:
            mdb.models[model_name].steps["HOR"].setValues(maxNumInc=MAX_INCREMENTS_HOR)
    for model_name, job, value in jobs:
        model = mdb.models[model_name]
        if os.path.exists(os.path.join(os.getcwd(), job + ".odb")):
            log("skipped (odb exists): %s" % job)
            skipped.append(job)
            continue
        change(model, value)
        mdb.Job(name=job, model=model_name, description="", type=ANALYSIS, atTime=None, waitMinutes=0,
                waitHours=0, queue=None, echoPrint=OFF, modelPrint=OFF, contactPrint=OFF, historyPrint=OFF,
                userSubroutine="", scratch="", resultsFormat=ODB, **JOB_SETTINGS)
        if not SUBMIT:
            log("created (not submitted): %s" % job)
            continue
        mdb.jobs[job].submit()
        submitted.append(job)
        running += 1
        log("submitted: %s" % job)
        if running >= JOBS_AT_ONCE:
            log("waiting for completion: %s" % job)
            mdb.jobs[job].waitForCompletion()
            running = 0
    log("DONE: %d submitted, %d skipped (the last jobs may still be running)" % (len(submitted), len(skipped)))


if __name__ == "__main__":
    main()
