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
     and, for sections with forces (PIER, SPEC, SPANDREL), that the element set has elements
     on ONE side of the cut only: elements of both sides cancel each other's forces (the
     export would give about zero). A geometry set of a face inside a part has this problem.
     Needs the meshed model.
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
import math

import numpy as np
from abaqus import mdb, getInput, getWarningReply

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
FORCE_TOKENS = ("PIER", "SPEC", "SPANDREL")                 # sections whose forces are exported
NAME_RULE = re.compile(r"^[^&]+&[^&]+&-?\d+(\.\d+)?&-?\d+(\.\d+)?$")


# -----------------------------------------------------------------------------
# Element set on one side of the cut? (same test as section_forces.cut_sides of the export)
# -----------------------------------------------------------------------------
def section_z(set_name):
    """Section z axis (normal of the cut): vertical for piers, the beam axis for spandrels."""
    try:
        angle = math.radians(float(set_name.split("&")[3]))
    except (IndexError, ValueError):
        angle = 0.0
    if "SPANDREL" in set_name.upper():
        return np.array([math.cos(angle), math.sin(angle), 0.0])
    return np.array([0.0, 0.0, 1.0])


def side_direction(set_name, pts):
    """Normal of the plane through the cut nodes (solid sections), or section z made normal to
    the line of nodes (shell sections); oriented along section z."""
    z = section_z(set_name)
    centred = pts - pts.mean(axis=0)
    if len(pts) >= 3:
        s, vt = np.linalg.svd(centred, full_matrices=False)[1:]
        if s[1] > 1e-9 * max(s[0], 1.0):                 # the nodes span a plane
            return vt[2] if vt[2].dot(z) >= 0 else -vt[2]
    if len(pts) >= 2:                                    # a line of nodes
        d = np.linalg.svd(centred, full_matrices=False)[2][0]
        w = z - z.dot(d) * d
        if np.linalg.norm(w) > 1e-9:
            return w / np.linalg.norm(w)
    return z


def side_check(assembly, set_name):
    """'' if the element set lies on one side of the cut, else a short description of the problem."""
    the_set = assembly.sets[set_name]
    try:
        nodes, elements = the_set.nodes, the_set.elements
        n_nodes, n_elements = len(nodes), len(elements)
    except Exception:
        n_nodes = n_elements = 0
    if not n_nodes or not n_elements:
        return "not checked: the SET has no %s (mesh the parts first)" % ("nodes" if not n_nodes else "elements")
    cut = dict(((n.instanceName, n.label), n.coordinates) for n in nodes)
    pts = np.array([cut[k] for k in cut], dtype=float)
    direction = side_direction(set_name, pts)
    level = pts.mean(axis=0).dot(direction)
    tol = 1e-6 * max(float((pts.max(axis=0) - pts.min(axis=0)).max()), 1.0)
    plus = minus = 0
    for e in elements:
        corner = e.getNodes()
        if not any((n.instanceName, n.label) in cut for n in corner):
            continue
        side = float(np.mean([n.coordinates for n in corner], axis=0).dot(direction)) - level
        if side > tol:
            plus += 1
        elif side < -tol:
            minus += 1
    if plus and minus:
        return ("elements on BOTH sides of the cut (%d / %d) - their forces cancel, the export would give "
                "about zero; use the elements of one side only" % (plus, minus))
    if not plus and not minus:
        return "no element of the element set touches the nodes of the cut"
    return ""


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


def show(message):
    """Message box in the Abaqus/CAE GUI (abaqus cae noGUI=... has no YES: then only printed)."""
    try:
        from abaqusConstants import YES
        getWarningReply(message, (YES, ))
    except Exception:
        pass


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
        problems = {}
        for s in sets:
            if any(t in s.upper() for t in FORCE_TOKENS):
                try:
                    problems[s] = side_check(model.rootAssembly, s)
                except Exception as e:                  # a check must not stop the script
                    problems[s] = "not checked: %s" % e
            print("  %-30s %s%s" % (s, "name OK" if s not in bad_names else "name not TYPE&LABEL&INDEX&ANGLE",
                                    "; " + problems[s] if problems.get(s) else ""))
        both = sorted(s for s, p in problems.items() if p.startswith("elements on BOTH"))
        other = sorted(s for s, p in problems.items() if p and not p.startswith("elements on BOTH"))
        if both:
            report.append("   ELEMENTS ON BOTH SIDES OF THE CUT (forces would be about zero): %s" % ", ".join(both))
        if other:
            report.append("   element sets to check: %s" % "; ".join("%s: %s" % (s, problems[s]) for s in other))
        if problems and not both and not other:
            report.append("   element sets: one side of the cut in every SET with forces")
        if CREATE_SURFACES:
            created = [s for s in sets if any(t in s.upper() for t in SURFACE_TOKENS)
                       and create_surface(model.rootAssembly, s) == "created"]
            report.append("   surfaces created: %d" % len(created))
        if FIELD_OUTPUT:
            model.fieldOutputRequests[FIELD_OUTPUT_REQUEST].setValues(variables=tuple(FIELD_OUTPUT))
            report.append("   %s variables: %s" % (FIELD_OUTPUT_REQUEST, ", ".join(FIELD_OUTPUT)))
    print("\n".join(report))
    show("Model preparation done:\n\n" + "\n".join(report))


if __name__ == "__main__":
    main()
