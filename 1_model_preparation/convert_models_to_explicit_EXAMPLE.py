# -*- coding: utf-8 -*-
"""
convert_models_to_explicit_EXAMPLE.py - EXAMPLE of turning Abaqus/Standard models into
Abaqus/Explicit models with a script (replaces automated_conversion_to_explicit.py).

The commands were RECORDED in Abaqus/CAE (abaqus.rpy) on the masonry panel models of
the Zaprudje benchmark: part names (SER_vol, panel_S, mozdanik, ...), the edge / cell
masks and the step, load and amplitude names belong to that model. For another model
record the same actions once in Abaqus/CAE and replace the recorded lines below.

HOW TO RUN
    Abaqus/CAE: File > Run Script...  with the model database open (or set CAE_FILE).
    Choose the parts to run with the switches in INPUT.
"""
from __future__ import print_function

from abaqus import mdb, openMdb
from abaqusConstants import *
import mesh

# =============================================================================
# INPUT
# =============================================================================
CAE_FILE = None        # INPUT: None = the open model database; or e.g. "Zaprudje_panel_2_explicit.cae"
MODELS = ["BEND_key_S_COH", "BEND_key_S_FR05", "BEND_key_S_TIE",
          "SHEAR_key_S_COH", "SHEAR_key_S_FR05", "SHEAR_key_S_TIE"]   # INPUT

CONVERT_STEPS = False          # static steps -> explicit steps VERT (10 s) and HOR (60 s)
SET_EXPLICIT_ELEMENTS = False  # explicit element types (element deletion, max. degradation 0.8)
SET_OUTPUT_REQUESTS = False    # field output every 0.1 s, history output every 0.01 s (step HOR)
SET_RAMPS_AND_TIMES = True     # field output every 0.1 s, ramps 0 -> 1 in 5 s, step times 5 s
# =============================================================================


def convert_steps(m):
    """As recorded (it was switched off in the original script) - check it in Abaqus/CAE first."""
    m.StaticStep(name='VERT', previous='Initial', maintainAttributes=True)
    del m.steps['HOR']
    m.ExplicitDynamicsStep(name='VERT', previous='Initial', maintainAttributes=True, timePeriod=10.0,
                           improvedDtMethod=ON)
    m.ExplicitDynamicsStep(name='HOR', previous='VERT', timePeriod=60.0, improvedDtMethod=ON)


def solid_types():
    return (mesh.ElemType(elemCode=C3D8, elemLibrary=EXPLICIT, secondOrderAccuracy=ON, distortionControl=DEFAULT,
                          elemDeletion=ON, maxDegradation=0.8),
            mesh.ElemType(elemCode=C3D6, elemLibrary=EXPLICIT),
            mesh.ElemType(elemCode=C3D4, elemLibrary=EXPLICIT))


def set_explicit_elements(m):
    """Recorded on the panel model: (part, cell mask) for solids, (part, edge mask) for beams."""
    for part, mask in (('SER_vol', '[#1 ]'), ('panel_S', '[#ffffff ]'), ('mozdanik', '[#3 ]')):
        p = m.parts[part]
        p.setElementType(regions=(p.cells.getSequenceFromMask(mask=(mask, ), ), ), elemTypes=solid_types())
    beam = (mesh.ElemType(elemCode=B31, elemLibrary=EXPLICIT), )
    for part, mask in (('fi6_S_panel', '[#ffffffff:4 #fffffff ]'), ('fi6_mozdanik', '[#1fffff ]'),
                       ('fi8_S_panel', '[#3 ]'), ('fi6_serklaz', '[#3fffffff ]'), ('fi12_serklaz', '[#3f ]'),
                       ('ser_fi8', '[#3f ]'), ('ser_fi6', '[#3ffff ]')):
        p = m.parts[part]
        p.setElementType(regions=(p.edges.getSequenceFromMask(mask=(mask, ), ), ), elemTypes=beam)
    m.rootAssembly.regenerate()


def set_output_requests(m):
    m.fieldOutputRequests['F-Output-1'].setValuesInStep(
        stepName='HOR', variables=('S', 'MISES', 'E', 'PE', 'PEEQ', 'U', 'V', 'RF', 'NFORC', 'CSTRESS', 'CDISP',
                                   'CFORCE', 'CSTATUS', 'DAMAGEC', 'DAMAGET', 'SDEG', 'CFAILURE'), timeInterval=0.1)
    m.historyOutputRequests['H-Output-1'].setValuesInStep(
        stepName='HOR', variables=('ALLAE', 'ALLCD', 'ALLDC', 'ALLDMD', 'ALLFD', 'ALLIE', 'ALLKE', 'ALLPD', 'ALLSE',
                                   'ALLVD', 'ALLWK', 'ALLCW', 'ALLMW', 'ALLPW', 'ETOTAL', 'DT'), timeInterval=0.01)


def set_ramps_and_times(m):
    m.fieldOutputRequests['F-Output-1'].setValuesInStep(stepName='HOR', timeInterval=0.1)
    m.amplitudes['HOR_ramp'].setValues(timeSpan=STEP, smooth=SOLVER_DEFAULT, data=((0.0, 0.0), (5.0, 1.0)))
    m.amplitudes['VERT_ramp'].setValues(timeSpan=STEP, smooth=SOLVER_DEFAULT, data=((0.0, 0.0), (5.0, 1.0)))
    m.steps['VERT'].setValues(timePeriod=5.0, improvedDtMethod=ON)
    m.steps['HOR'].setValues(timePeriod=5.0, improvedDtMethod=ON)


def main():
    if CAE_FILE:
        openMdb(CAE_FILE)
    for name in MODELS:
        m = mdb.models[name]
        if CONVERT_STEPS:
            convert_steps(m)
        if SET_EXPLICIT_ELEMENTS:
            set_explicit_elements(m)
        if SET_OUTPUT_REQUESTS:
            set_output_requests(m)
        if SET_RAMPS_AND_TIMES:
            set_ramps_and_times(m)
        print("converted: %s" % name)


if __name__ == "__main__":
    main()
