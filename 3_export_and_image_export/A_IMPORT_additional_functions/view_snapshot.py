"""
view_snapshot.py - read the display settings of the running Abaqus/CAE or Viewer
session and turn them into view / variable command lists (the same format as
rpy_views, replayed by A_2_Image_export_Auto.py).

Read directly from the session objects:
  camera            vp.view
  section cuts      vp.odbDisplay.viewCut / viewCutNames / viewCuts[...]
  display options   commonOptions (edges, render style, deformation scale, ...),
                    contourOptions (type, style, intervals, spectrum),
                    superimposeOptions, basicOptions (averaging, mirroring)
  annotations       vp.viewportAnnotationOptions (legend, title, state, triad, fonts)
  background        session.graphicsOptions
  variable          primary variable, plot state, contour limits
  print options     session.printOptions / pngOptions
Abaqus does not report the CONTENT of the display group, so that part is taken
from the display group commands in the session's abaqus.rpy (rpy_views).

Values are written as Python text: numbers, strings, tuples and Abaqus constants
(ON, BANDED, ...). Members that do not exist in an Abaqus version are skipped.

Needs Abaqus/CAE or Viewer. Stand-alone (File > Run Script): prints the commands
that describe the picture currently shown.
"""
from __future__ import print_function

import os
import re
import sys
import inspect
from collections import OrderedDict

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import odb_tools
import rpy_views

# members read per object (skipped when an Abaqus version does not have them)
VIEW_OPTIONS = OrderedDict([
    ("session.graphicsOptions", ("backgroundStyle", "backgroundColor", "backgroundBottomColor", "antiAlias")),
    ("vp.viewportAnnotationOptions", (
        "triad", "legend", "title", "state", "annotations", "compass", "legendBox", "legendPosition",
        "legendFont", "legendDecimalPlaces", "legendNumberFormat", "legendMinMax", "legendTextColor",
        "legendBackgroundStyle", "legendBackgroundColor", "titleFont", "statePosition", "stateFont",
        "triadPosition", "triadFont", "triadLabelColor")),
    ("vp.odbDisplay.commonOptions", (
        "renderStyle", "visibleEdges", "edgeColorWireHide", "edgeColorFillShade", "edgeLineStyle",
        "edgeLineThickness", "featureAngle", "deformationScaling", "uniformScaleFactor",
        "nonuniformScaleFactor", "translucency", "translucencyFactor", "elementShrink",
        "elementShrinkFactor", "elemLabels", "nodeLabels", "faceLabels", "nodeSymbols")),
    ("vp.odbDisplay.contourOptions", (
        "contourType", "contourStyle", "numIntervals", "spectrum", "reversedContourLegendRange",
        "contourEdges", "contourEdgeColor")),
    ("vp.odbDisplay.superimposeOptions", (
        "renderStyle", "visibleEdges", "edgeColorWireHide", "edgeColorFillShade", "edgeLineStyle",
        "translucency", "translucencyFactor")),
    ("vp.odbDisplay.basicOptions", (
        "averageElementOutput", "averagingThreshold", "useRegionBoundaries", "regionBoundaries",
        "computeOrder", "mirrorAboutXyPlane", "mirrorAboutXzPlane", "mirrorAboutYzPlane")),
])
# contour limits (stored per view and variable by A_2_Image_save_view.py)
LIMIT_MEMBERS = ("maxAutoCompute", "maxValue", "minAutoCompute", "minValue", "intervalType",
                 "intervalValues", "outsideLimitsMode", "outsideLimitsAboveColor",
                 "outsideLimitsBelowColor", "showMaxLocation", "showMinLocation")
CAMERA_MEMBERS = ("projection", "nearPlane", "farPlane", "width", "height", "cameraPosition",
                  "cameraUpVector", "cameraTarget", "viewOffsetX", "viewOffsetY")
CUT_DEFINITION = ("shape", "origin", "normal", "axis2", "csysName", "cylinderAxis",
                  "followDeformation", "overrideAveraging", "referenceFrame")
PREDEFINED_CUTS = ("X-Plane", "Y-Plane", "Z-Plane", "Isosurface")
# Abaqus reports every cut's location as 'position', but setValues accepts
# position= only for planes: cylinders / spheres take radius=, an isosurface value=
CUT_VALUE_KEY = {"CYLINDER": "radius", "SPHERE": "radius", "ISOSURFACE": "value"}
CUT_SHOW = ("showModelAboveCut", "showModelOnCut", "showModelBelowCut")
# numbers Abaqus uses for the output position in odbDisplay.primaryVariable
# (1 = NODAL and 2 = INTEGRATION_POINT seen in Abaqus 2021; unknown numbers are kept as numbers)
POSITION_CODES = {0: "UNDEFINED_POSITION", 1: "NODAL", 2: "INTEGRATION_POINT", 3: "ELEMENT_FACE",
                  4: "ELEMENT_NODAL", 5: "WHOLE_ELEMENT", 6: "ELEMENT_CENTROID", 7: "WHOLE_REGION",
                  8: "WHOLE_PART_INSTANCE", 9: "WHOLE_MODEL", 10: "GENERAL_PARTICLE"}
PRINT_OPTIONS = OrderedDict([
    ("session.printOptions", ("rendition", "vpDecorations", "vpBackground", "compass", "reduceColors")),
    ("session.pngOptions", ("imageSize",)),
])

_SKIP = object()
try:
    _NUMBERS = (int, float, long)  # noqa: F821  Python 2
except NameError:
    _NUMBERS = (int, float)


class Snapshot(object):
    """Reads the current viewport; every method returns command lines (text)."""

    def __init__(self):
        from abaqus import session
        import abaqusConstants
        self.session = session
        self.constants = dict((k, getattr(abaqusConstants, k)) for k in dir(abaqusConstants)
                              if not k.startswith("_"))
        self.ns = {"session": session, "vp": session.viewports[session.currentViewportName]}
        self.notes = []

    # -- values -> Python text ---------------------------------------------------
    def text(self, value):
        """Python source for a member value, or _SKIP if it cannot be written."""
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (str, type(u""))):   # text first: csysName='GLOBAL' is text, not the constant
            return repr(odb_tools.native(value))
        name = str(value)
        if re.match(r"^[A-Z][A-Z0-9_]*$", name) and name in self.constants:
            try:
                if self.constants[name] == value:
                    return name            # Abaqus constant: ON, BANDED, FEATURE, ...
            except Exception:
                pass
        if hasattr(value, "item") and not isinstance(value, (tuple, list)):
            try:
                value = value.item()       # numpy scalar
            except Exception:
                pass
        if isinstance(value, _NUMBERS):
            return repr(value)
        if isinstance(value, (tuple, list)):
            parts = [self.text(v) for v in value]
            if any(p is _SKIP for p in parts):
                return _SKIP
            return "(%s, )" % parts[0] if len(parts) == 1 else "(%s)" % ", ".join(parts)
        return _SKIP

    def members(self, target, names):
        """OrderedDict name -> text of the readable members of an object."""
        out = OrderedDict()
        try:
            obj = eval(target, self.ns)
        except Exception:
            return out
        for n in names:
            try:
                value = getattr(obj, n)
            except Exception:
                continue
            t = self.text(value)
            if t is _SKIP:
                self.notes.append("%s.%s not stored (value %r)" % (target, n, value))
                continue
            out[n] = t
        return out

    def setvalues(self, target, names):
        kw = self.members(target, names)
        return [rpy_views.build_call(target, "setValues", (), kw)] if kw else []

    # -- parts of the picture ------------------------------------------------------
    def camera(self):
        return self.setvalues("vp.view", CAMERA_MEMBERS)

    def view_cuts(self):
        od = self.ns["vp"].odbDisplay
        try:
            active = bool(od.viewCut)
            names = [odb_tools.native(n) for n in (od.viewCutNames or ())]
        except Exception:
            return []
        if not active or not names:
            return ["vp.odbDisplay.setValues(viewCut=OFF)"]
        cmds = []
        for n in names:
            target = "vp.odbDisplay.viewCuts[%r]" % n
            shape = self.members(target, ("shape",)).get("shape", "PLANE")
            if n not in PREDEFINED_CUTS:  # custom cut: its definition is needed in a new session
                kw = OrderedDict([("name", repr(n))])
                kw.update((k, v) for k, v in self.members(target, CUT_DEFINITION).items() if v not in ("''", '""'))
                cmds.append(rpy_views.build_call("vp.odbDisplay", "ViewCut", (), kw))
            key = CUT_VALUE_KEY.get(shape, "position")
            value = self.members(target, (key,)).get(key) or self.members(target, ("position",)).get("position")
            kw = OrderedDict([(key, value)] if value is not None else [])
            kw.update(self.members(target, CUT_SHOW))
            if kw:
                cmds.append(rpy_views.build_call(target, "setValues", (), kw))
        cmds.append("vp.odbDisplay.setValues(viewCutNames=%s, viewCut=ON)" % self.text(tuple(names)))
        return cmds

    def component_labels(self, label):
        """Component names of a field in the displayed ODB (e.g. U1, U2, U3), or ()."""
        try:
            odb = self.ns["vp"].displayedObject
            frame = odb.steps[list(odb.steps.keys())[-1]].frames[-1]
            return tuple(odb_tools.native(c) for c in frame.fieldOutputs[label].componentLabels)
        except Exception:
            return ()

    def primary_variable(self, rpy_primary=None):
        """setPrimaryVariable command for the variable shown now, or None.

        Abaqus reports odbDisplay.primaryVariable with NUMBERS for the position and
        the refinement type, e.g. ('U', 1, <type>, 'Magnitude', ...). So:
          1) the last setPrimaryVariable in this session's abaqus.rpy is used when it
             names the same variable (exact constants and refinement),
          2) otherwise the command is rebuilt: position number -> constant, the
             refinement name is the text in the tuple, COMPONENT if it is one of the
             field's component labels (U1, PE11, ...), else INVARIANT (Magnitude, Mises, ...)."""
        try:
            pv = tuple(self.ns["vp"].odbDisplay.primaryVariable)
        except Exception:
            return rpy_primary
        if not pv or not pv[0]:
            return rpy_primary
        label = odb_tools.native(pv[0])
        ref = None
        for x in pv[2:]:
            if isinstance(x, (str, type(u""))) and x.strip():
                ref = odb_tools.native(x)
                break
        if rpy_primary:
            p = rpy_views.parse_call(rpy_primary)
            if (p and rpy_views.literal(p[3].get("variableLabel", "''")) == label
                    and (ref is None or repr(ref) in p[3].get("refinement", "") or '"%s"' % ref in p[3].get("refinement", ""))):
                return rpy_primary
        pos = pv[1] if len(pv) > 1 else None
        pos_text = POSITION_CODES.get(pos, None) if isinstance(pos, _NUMBERS) and not isinstance(pos, bool) else None
        pos_text = pos_text or self.text(pos)
        if pos_text is _SKIP:
            return rpy_primary
        cmd = "vp.odbDisplay.setPrimaryVariable(variableLabel=%r, outputPosition=%s" % (label, pos_text)
        if ref:
            component = ref in self.component_labels(label) or re.match(r"^[A-Z]+[0-9]+$", ref)
            cmd += ", refinement=(%s, %r)" % ("COMPONENT" if component else "INVARIANT", ref)
        self.notes.append("variable rebuilt from %r" % (pv[:5],))
        return cmd + ")"

    def plot_state(self):
        return self.setvalues("vp.odbDisplay.display", ("plotState",))

    def limits(self):
        kw = self.members("vp.odbDisplay.contourOptions", LIMIT_MEMBERS)
        # a max/min value only counts when it is not computed automatically
        for auto, value in (("maxAutoCompute", "maxValue"), ("minAutoCompute", "minValue")):
            if kw.get(auto) in ("ON", "True"):
                kw.pop(value, None)
        if kw.get("intervalType") != "USER_DEFINED":
            kw.pop("intervalValues", None)
        return [rpy_views.build_call("vp.odbDisplay.contourOptions", "setValues", (), kw)] if kw else []

    # -- complete lists --------------------------------------------------------------
    def view_commands(self, display_group=()):
        cmds = []
        for target, names in VIEW_OPTIONS.items():
            cmds += self.setvalues(target, names)
        cmds += list(display_group)
        cmds += self.view_cuts()
        cmds += self.camera()
        return cmds

    def variable_commands(self, rpy_primary=None):
        """(commands, primary command used, plot state text)."""
        primary = self.primary_variable(rpy_primary)
        if primary is None:
            self.notes.append("primary variable could not be read")
        plot = self.plot_state()
        cmds = ([primary] if primary else []) + plot + self.limits()
        plot_text = self.members("vp.odbDisplay.display", ("plotState",)).get("plotState")
        return cmds, primary, plot_text

    def print_commands(self):
        cmds = []
        for target, names in PRINT_OPTIONS.items():
            cmds += self.setvalues(target, names)
        return cmds


if __name__ == "__main__":
    if odb_tools.session is None:
        raise SystemExit("Run this inside Abaqus/CAE or Viewer (File > Run Script).")
    snap = Snapshot()
    print("VIEW:")
    for c in snap.view_commands():
        print("   ", c)
    cmds, primary, plot = snap.variable_commands()
    print("VARIABLE (%s):" % rpy_views.variable_name(primary, plot))
    for c in cmds:
        print("   ", c)
    print("PRINT OPTIONS:")
    for c in snap.print_commands():
        print("   ", c)
    for n in snap.notes:
        print("  note:", n)
