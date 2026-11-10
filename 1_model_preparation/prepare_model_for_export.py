# -*- coding: utf-8 -*-
"""
prepare_model_for_export.py - checks the cross-section SETs of an Abaqus/CAE model and
optionally adds what older versions of the export needed (replaces
0_model_preparation_multiple_instances.py).

HOW TO RUN
    Open the model database (.cae) in Abaqus/CAE: File > Run Script... > prepare_model_for_export.py

WHAT IT DOES
  1. lists the assembly SETs that are cross-sections (names containing PIER, SPEC,
     SPANDREL, DRIFT or SRIFT) and checks their names: TYPE&LABEL&INDEX&ANGLE,
     e.g. V_PIER&RU&2&0 (INDEX and ANGLE must be numbers)
  2. CREATE_SURFACES = True: creates a surface SURF_<SET> on the faces of every section SET
     (PIER, SPEC, SPANDREL, SRIFT). The current export (A_1_Export_Auto.py) does NOT need
     them - it reads the forces from the node and element sets - they are kept for the
     older scripts and tutorials.
  3. FIELD_OUTPUT: optionally sets the variables of the field output request F-Output-1.
     The export needs U (displacements; UR for shell sections) and NFORC (section forces,
     both the free-body cut and the NFORC method); the images need the plotted variables.

The SETs themselves are made in Abaqus/CAE (see 1_model_preparation/README.md and the
video "Cross-section naming and local axes").
"""
from __future__ import print_function

import re

from abaqus import mdb, getInput, getWarningReply
from abaqusConstants import YES, NO

# =============================================================================
# INPUT
# =============================================================================
MODELS = None              # INPUT: None = ask (one model or "all"); or e.g. ["SHEAR_key_S_TIE"]
CREATE_SURFACES = True     # INPUT: create SURF_<SET> surfaces (not needed by A_1_Export_Auto.py)
FIELD_OUTPUT = None        # INPUT: None = field output unchanged; or the variables of F-Output-1, e.g.
#   ("S", "PE", "PEEQ", "LE", "U", "V", "A", "RF", "CF", "NFORC", "CSTRESS", "CDISP", "DAMAGEC", "DAMAGET")
FIELD_OUTPUT_REQUEST = "F-Output-1"
# =============================================================================

SECTION_TOKENS = ("PIER", "SPEC", "SPANDREL", "DRIFT", "SRIFT")
SURFACE_TOKENS = ("PIER", "SPEC", "SPANDREL", "SRIFT")      # DRIFT sets are points: no surface
NAME_RULE = re.compile(r"^[^&]+&[^&]+&-?\d+(\.\d+)?&-?\d+(\.\d+)?$")


def choose_models():
    names = list(mdb.models.keys())
    if MODELS:
        missing = [m for m in MODELS if m not in names]
        if missing:
            raise ValueError("Model(s) not in the open .cae: %s (available: %s)" % (missing, names))
        return list(MODELS)
    if len(names) == 1:
        return names
    answer = getInput("Model to prepare, or all:\n  %s" % "\n  ".join(names), "all")
    if answer is None:
        return []
    answer = answer.strip()
    if answer.lower() == "all":
        return names
    if answer not in names:
        raise ValueError("Model %r not in the open .cae (available: %s)" % (answer, names))
    return [answer]


def section_sets(model):
    return [s for s in model.rootAssembly.sets.keys() if any(t in s.upper() for t in SECTION_TOKENS)]


def create_surface(assembly, set_name):
    name = "SURF_" + set_name
    if name in assembly.surfaces.keys():
        return "exists"
    the_set = assembly.sets[set_name]
    try:
        assembly.Surface(name=name, side1Faces=the_set.faces)
    except Exception:
        assembly.Surface(name=name, side1Faces=the_set)   # as in the original script
    return "created"


def main():
    models = choose_models()
    if not models:
        print("Cancelled - nothing changed.")
        return
    report = []
    for model_name in models:
        model = mdb.models[model_name]
        sets = section_sets(model)
        bad_names = [s for s in sets if not NAME_RULE.match(s)]
        report.append("%s: %d section SET(s)%s" % (model_name, len(sets),
                      "; NAMES TO CHECK: %s" % ", ".join(bad_names) if bad_names else ""))
        for s in sets:
            print("  %-30s %s" % (s, "name OK" if s not in bad_names else "name not TYPE&LABEL&INDEX&ANGLE"))
        if CREATE_SURFACES:
            created = [s for s in sets if any(t in s.upper() for t in SURFACE_TOKENS)
                       and create_surface(model.rootAssembly, s) == "created"]
            report.append("   surfaces created: %d" % len(created))
        if FIELD_OUTPUT:
            model.fieldOutputRequests[FIELD_OUTPUT_REQUEST].setValues(variables=tuple(FIELD_OUTPUT))
            report.append("   %s variables: %s" % (FIELD_OUTPUT_REQUEST, ", ".join(FIELD_OUTPUT)))
    print("\n".join(report))
    getWarningReply("Model preparation done:\n\n" + "\n".join(report), (YES,))


if __name__ == "__main__":
    main()
