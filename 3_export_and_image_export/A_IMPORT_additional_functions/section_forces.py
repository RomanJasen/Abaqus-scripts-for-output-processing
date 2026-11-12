"""
section_forces.py - section forces Fx, Fy, Fz, Mx, My, Mz of a cut.

A SET needs a node set (nodes on the cut) and an element set (elements on one
side of the cut) with the same name; both_sides_warning() reports SETs whose
element set has elements of both sides (their forces cancel). Forces are resolved
in the section csys given by SectionSet.force_csys_points(). Two methods
(DEFAULT_FORCE_OPTIONS):

  "freebody"  Abaqus free-body cut (session.FreeBodyFromNodesElements) read with
              ONE XYDataFromFreeBody call for all frames. Needs the CAE kernel.
  "nforc"     sums the element nodal forces NFORC of the element set at the cut
              nodes directly from the ODB (needs NFORC in the field output):
                  F = -sum F_i           M = -sum (x_i - C) x F_i  (+ NFORC4-6 for shells)
              (minus: NFORC act on the nodes, the cut gives the forces on the element set)
              C = AREA-WEIGHTED centroid of the element faces on the cut (length
              weighted edges for shells), so the centre does not shift towards
              finer parts of the mesh as a plain node average does. Works under
              plain  abaqus python  too (no session needed).

Frame sync: results are keyed by FrameRecord.index. For "freebody" the frames are
activated by position and every returned point is checked against the frame time
(FrameSyncError on mismatch).

STAND-ALONE RUN: edit DEMO_SETTINGS (METHOD "compare" runs both methods and
prints the differences), then File > Run Script... in Abaqus/CAE or Viewer.
"""
from __future__ import print_function

import os
import sys
import copy
import inspect

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np

import odb_tools
import section_geometry as geo
import section_definitions as sdefs
from odb_tools import FrameSyncError

# =============================================================================
# DEFAULT FORCE OPTIONS - main script can override with CONFIG["FORCES"]
# =============================================================================
DEFAULT_FORCE_OPTIONS = {
    "METHOD": "freebody",      # "freebody" | "nforc"
    "NFORC_DEFORMED": True,    # moment arms from deformed coordinates (large displacements)
    "NFORC_CENTRE": "area",    # "area" (area-weighted cut centroid) | "nodes" (plain node average)
    "NFORC_SIGN": -1.0,        # NFORC = forces of the elements ON the nodes; the free-body cut gives the
                               # forces acting on the element set -> -1 (checked with "compare" on the
                               # benchmark wall: both methods agree within 0.01 % in all 6 components)
}

# =============================================================================
# DEMO SETTINGS - only used when THIS file is run on its own
# =============================================================================
DEMO_SETTINGS = {
    "ODB": None,            # full path, None -> ODB open in viewport / last export / dialog
    "STEP": None,           # None -> step of the last export / last step
    "SET": None,            # e.g. "V_PIER&DPARC&1&0", None -> prompt / first set with forces
    "MIN_DT": None,         # min. step time between frames, None = every frame
    "FRAME_INDICES": None,  # e.g. [0, 25, -1] for a quick test, None = all frames
    "METHOD": "compare",    # "freebody" | "nforc" | "compare" (both + differences)
}
# =============================================================================

CUT_NAME = "AUTOMATIC_CUT_DELETE_IT_IF_YOU_SEE_IT"
CSYS_NAME = "AUTOMATIC_EXPORT_CSYS"
COMPONENTS = ("force component 1", "force component 2", "force component 3",
              "moment component 1", "moment component 2", "moment component 3")
LABELS = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")


def merged_options(overrides=None):
    opt = copy.deepcopy(DEFAULT_FORCE_OPTIONS)
    opt.update(overrides or {})
    if opt["METHOD"] not in ("freebody", "nforc"):
        raise ValueError("FORCES METHOD must be freebody or nforc, not %r" % opt["METHOD"])
    return opt


def csys_basis(points):
    """3x3 matrix whose ROWS are the unit axes of the csys given by origin, point on X, point in XY."""
    o, p1, p2 = [np.asarray(p, dtype=np.float64) for p in points]
    e1 = p1 - o
    e1 /= np.linalg.norm(e1)
    e3 = np.cross(e1, p2 - o)
    e3 /= np.linalg.norm(e3)
    return np.vstack((e1, np.cross(e3, e1), e3))


# =============================================================================
# Method 1: free-body cut (Abaqus/CAE session)
# =============================================================================
def _abaqus():
    """Import the CAE-only modules lazily so the module can be imported anywhere."""
    from abaqus import session
    import abaqusConstants as C
    dgo = odb_tools.display_group_toolset()     # also loads Visualization under noGUI
    return session, C, dgo


def _odb_data(session, odb):
    for key in (odb.name, getattr(odb, "path", None), os.path.basename(odb.name)):
        if key and key in session.odbData.keys():
            return session.odbData[key]
    raise KeyError("ODB %s not found in session.odbData: %s" % (odb.name, list(session.odbData.keys())))


def _viewport(session):
    return session.viewports[session.currentViewportName]


def create_free_body(odb, set_name, csys_points, shell=False, cut_name=CUT_NAME):
    """Create the free-body cut for set_name resolved in the csys given by 3 points."""
    session, C, dgo = _abaqus()
    vp = _viewport(session)
    vp.setValues(displayedObject=odb)
    # use the ODB's own (plain str, correctly upper-cased) set names
    e_leaf = dgo.LeafFromElementSets(elementSets=(odb_tools.set_key(odb.rootAssembly.elementSets, set_name, "Element"),))
    n_leaf = dgo.LeafFromNodeSets(nodeSets=(odb_tools.set_key(odb.rootAssembly.nodeSets, set_name, "Node"),))
    try:
        scratch = session.scratchOdbs[odb.name]
    except Exception:
        scratch = session.ScratchOdb(odb)
    scratch.rootAssembly.DatumCsysByThreePoints(
        name=CSYS_NAME, coordSysType=C.CARTESIAN,
        origin=csys_points[0], point1=csys_points[1], point2=csys_points[2])
    # shells: centroid cannot be computed -> nodal average (as in the original)
    session.FreeBodyFromNodesElements(
        name=cut_name, elements=e_leaf, nodes=n_leaf,
        summationLoc=C.NODAL_AVERAGE if shell else C.CENTROID,
        componentResolution=C.CSYS, csysName=CSYS_NAME)
    vp.odbDisplay.setValues(freeBodyNames=(cut_name,), freeBody=C.ON)


def delete_free_body(cut_name=CUT_NAME):
    session, C, _ = _abaqus()
    try:
        _viewport(session).odbDisplay.setValues(freeBody=C.OFF)
    except Exception:
        pass
    if cut_name in session.freeBodies.keys():
        del session.freeBodies[cut_name]


def _order_components(xy_list):
    """Return the 6 XYData objects in COMPONENTS order (fall back to returned order)."""
    by_suffix = {}
    for xy in xy_list:
        for comp in COMPONENTS:
            if xy.name.lower().endswith(comp):
                by_suffix[comp] = xy
    if len(by_suffix) == 6:
        return [by_suffix[c] for c in COMPONENTS]
    if len(xy_list) != 6:
        raise RuntimeError("XYDataFromFreeBody returned %d curves, expected 6: %s"
                           % (len(xy_list), [x.name for x in xy_list]))
    return list(xy_list)


def _time_tol(t):
    # XY data are single precision -> relative 1e-6 is ~10x the float32 resolution
    return 1e-6 * max(1.0, abs(t))


def match_points_to_frames(curves, frames):
    """curves: 6 lists of (time, value). Returns {frame.index: [6 floats]}.
    Primary: positional match (k-th point = k-th active frame), verified by time.
    Fallback (point count differs): nearest time within tolerance."""
    n = len(frames)
    lengths = [len(c) for c in curves]
    if len(set(lengths)) != 1:
        raise FrameSyncError("Force components have different lengths: %s" % lengths)
    if n == 0:
        return {}

    # XY x-axis is total time by default; accept step time if that is what matches
    t_first = curves[0][0][0] if lengths[0] else None
    time_of = lambda rec: rec.total_time
    if t_first is not None and abs(t_first - frames[0].total_time) > _time_tol(frames[0].total_time) \
            and abs(t_first - frames[0].step_time) <= _time_tol(frames[0].step_time):
        time_of = lambda rec: rec.step_time

    if lengths[0] == n:
        out = {}
        for k, rec in enumerate(frames):
            times = [c[k][0] for c in curves]
            if max(abs(t - time_of(rec)) for t in times) > _time_tol(time_of(rec)):
                raise FrameSyncError(
                    "Frame index %d (frameId %d): expected time %.9g, XY data has %s"
                    % (rec.index, rec.frame_id, time_of(rec), times))
            out[rec.index] = [float(c[k][1]) for c in curves]
        return out

    # count mismatch -> match by time
    xs = [p[0] for p in curves[0]]
    out = {}
    for rec in frames:
        t = time_of(rec)
        best = min(range(len(xs)), key=lambda j: abs(xs[j] - t)) if xs else None
        if best is None or abs(xs[best] - t) > _time_tol(t):
            raise FrameSyncError("No force point at time %.9g (frame index %d); XY has %d points for %d frames"
                                 % (t, rec.index, len(xs), n))
        out[rec.index] = [float(c[best][1]) for c in curves]
    return out


def extract_forces_freebody(odb, step_name, section, frames, cut_name=CUT_NAME):
    """{frame_index: [Fx, Fy, Fz, Mx, My, Mz]} from an Abaqus free-body cut."""
    session, C, _ = _abaqus()
    step_key = odb_tools.get_step(odb, step_name).name
    shell = section.type.geometry == "shell"
    xy_names = []
    cut_name = odb_tools.native(cut_name)
    create_free_body(odb, section.set_name, section.force_csys_points(), shell, cut_name)
    try:
        # activate exactly the requested frames (by POSITION) of this step only
        _odb_data(session, odb).setValues(
            activeFrames=((step_key, tuple(str(r.index) for r in frames)),))
        xy_list = session.XYDataFromFreeBody(
            odb=odb, force=C.ON, moment=C.ON, heatFlowRate=C.OFF, resultant=C.OFF,
            comp1=C.ON, comp2=C.ON, comp3=C.ON)
        xy_names = [xy.name for xy in xy_list]
        curves = [list(xy) for xy in _order_components(xy_list)]
        return match_points_to_frames(curves, frames)
    finally:
        for name in xy_names:
            if name in session.xyDataObjects.keys():
                del session.xyDataObjects[name]
        delete_free_body(cut_name)


# =============================================================================
# Method 2: NFORC summation (ODB only)
# =============================================================================
class NforcCut(object):
    """Cut definition for NFORC summation: cut nodes, faces of the cut, csys."""

    def __init__(self, odb, section, options=None):
        self.section = section
        self.opt = merged_options(options)
        self.node_region = odb_tools.get_node_set(odb, section.set_name)
        self.elem_region = odb_tools.get_element_set(odb, section.set_name)
        nodes = odb_tools.set_nodes(self.node_region)
        self.keys = [k for k, _ in nodes]
        self.coords0 = dict((k, np.asarray(c, dtype=np.float64)) for k, c in nodes)
        on_cut = set(self.keys)
        self.faces = []  # node keys of each element that lie on the cut
        for _, conn in odb_tools.set_elements(self.elem_region):
            f = []
            for k in conn:
                if k in on_cut and k not in f:
                    f.append(k)
            if f:
                self.faces.append(f)
        if not self.faces:
            raise ValueError("No element of element set %s touches node set %s - check the sets"
                             % (section.set_name, section.set_name))
        self.basis = csys_basis(section.force_csys_points())
        pts0 = np.array([self.coords0[k] for k in self.keys])
        self.normal0 = geo.plane_normal(pts0, hint=self.basis[2]) if len(pts0) >= 3 else self.basis[2]

    def centre(self, coords):
        if self.opt["NFORC_CENTRE"] == "nodes":
            return np.mean([coords[k] for k in self.keys], axis=0)
        return geo.cut_centroid([np.array([coords[k] for k in f]) for f in self.faces], self.normal0)

    def evaluate(self, frame):
        """([Fx..Mz] in section csys, centre point) for one frame."""
        for j in (1, 2, 3):
            if not odb_tools.has_field(frame, "NFORC%d" % j):
                raise KeyError("NFORC%d not in the ODB field output - request *ELEMENT OUTPUT, NFORC" % j)
        on_cut = self.coords0
        forces = dict((k, np.zeros(3)) for k in self.keys)
        moments = dict((k, np.zeros(3)) for k in self.keys)
        for j in (1, 2, 3):
            for (_, nk), v in odb_tools.read_element_nodal(frame, self.elem_region, "NFORC%d" % j).items():
                if nk in on_cut:
                    forces[nk][j - 1] += v
        for j in (4, 5, 6):  # nodal moments of shell / beam elements
            if odb_tools.has_field(frame, "NFORC%d" % j):
                for (_, nk), v in odb_tools.read_element_nodal(frame, self.elem_region, "NFORC%d" % j).items():
                    if nk in on_cut:
                        moments[nk][j - 4] += v

        if self.opt["NFORC_DEFORMED"]:
            u = odb_tools.read_nodal_vectors(frame, self.node_region, "U")
            coords = dict((k, self.coords0[k] + np.asarray(u[k], dtype=np.float64)) for k in self.keys)
        else:
            coords = self.coords0
        c = self.centre(coords)
        F = np.zeros(3)
        M = np.zeros(3)
        for k in self.keys:
            F += forces[k]
            M += np.cross(coords[k] - c, forces[k]) + moments[k]
        s = float(self.opt["NFORC_SIGN"])
        return [float(v) for v in s * self.basis.dot(F)] + [float(v) for v in s * self.basis.dot(M)], c


def extract_forces_nforc(odb, section, frames, options=None, return_centres=False):
    """{frame_index: [Fx, Fy, Fz, Mx, My, Mz]} by NFORC summation."""
    cut = NforcCut(odb, section, options)
    out, centres = {}, {}
    for rec in frames:
        out[rec.index], centres[rec.index] = cut.evaluate(rec.frame)
    return (out, centres) if return_centres else out


# =============================================================================
# Check: element set on both sides of the cut
# =============================================================================
def side_direction(section, points):
    """Direction separating the two sides of the cut, oriented along section z: the normal of the
    plane through the cut nodes (solid sections), or section z made normal to the line of nodes
    (shell sections)."""
    z = csys_basis(section.force_csys_points())[2]
    pts = np.asarray(points, dtype=np.float64)
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


def cut_sides(odb, section):
    """(plus, minus): elements of the element set that touch the cut nodes, with their centre on
    the +z / -z side of the cut. Elements of both sides cancel each other's forces at the cut
    nodes: plus > 0 and minus > 0 means wrong (about zero) section forces. Elements that do not
    touch the cut nodes do not count (e.g. the other part at a contact interface)."""
    cut = dict(odb_tools.set_nodes(odb_tools.get_node_set(odb, section.set_name)))
    elements = odb_tools.set_elements(odb_tools.get_element_set(odb, section.set_name))
    if not cut:
        return 0, 0
    coords = dict((k, np.asarray(c, dtype=np.float64)) for k, c in cut.items())
    pts = np.array(list(coords.values()))
    direction = side_direction(section, pts)
    level = pts.mean(axis=0).dot(direction)
    tol = 1e-6 * max(float((pts.max(axis=0) - pts.min(axis=0)).max()), 1.0)
    instances = odb.rootAssembly.instances
    plus = minus = 0
    for _, conn in elements:
        if not any(k in cut for k in conn):
            continue
        xyz = []
        for k in conn:
            if k not in coords:
                coords[k] = np.asarray(instances[k[0]].getNodeFromLabel(k[1]).coordinates, dtype=np.float64)
            xyz.append(coords[k])
        side = float(np.mean(xyz, axis=0).dot(direction)) - level
        if side > tol:
            plus += 1
        elif side < -tol:
            minus += 1
    return plus, minus


def both_sides_warning(odb, section):
    """'' if the element set lies on one side of the cut, else the text of a warning."""
    plus, minus = cut_sides(odb, section)
    if plus and minus:
        return ("the element set has elements on BOTH sides of the cut (%d on the +z side, %d on the -z side, "
                "all touching the cut nodes): their forces cancel and the exported forces are wrong (about "
                "zero); the displacements are correct. Use the elements of one side only - see "
                "1_model_preparation/README.md" % (plus, minus))
    return ""


# =============================================================================
# Dispatcher
# =============================================================================
def extract_section_forces(odb, step_name, section, frames, options=None):
    """Fx, Fy, Fz, Mx, My, Mz of one section for the given frames.

    section : section_definitions.SectionSet
    frames  : list of odb_tools.FrameRecord (the same list used for displacements)
    options : overrides of DEFAULT_FORCE_OPTIONS, e.g. {"METHOD": "nforc"}
    returns : {frame_index: [Fx, Fy, Fz, Mx, My, Mz]}
    """
    opt = merged_options(options)
    if opt["METHOD"] == "nforc":
        return extract_forces_nforc(odb, section, frames, opt)
    return extract_forces_freebody(odb, step_name, section, frames)


def _print_table(title, frames, rows):
    print("\n" + title)
    print("%6s %10s %10s | %s" % ("index", "frameId", "time", " ".join("%13s" % l for l in LABELS)))
    for rec in frames:
        print("%6d %10d %10.4g | %s" % (rec.index, rec.frame_id, rec.step_time,
                                        " ".join("%13.5g" % v for v in rows[rec.index])))


if __name__ == "__main__":
    def _has_forces(n, odb):
        st = sdefs.classify(n)
        return st is not None and st.forces and n in odb.rootAssembly.elementSets.keys()

    demo = odb_tools.resolve_demo_inputs(DEMO_SETTINGS, set_filter=_has_forces)
    try:
        section = sdefs.parse(demo.set_name)
        frames = demo.frames
        print("csys points (origin, X, XY):", section.force_csys_points())
        method = DEMO_SETTINGS["METHOD"]
        results = {}
        if method in ("freebody", "compare"):
            results["freebody"] = extract_forces_freebody(demo.odb, demo.step, section, frames)
            _print_table("FREE-BODY CUT", frames, results["freebody"])
        if method in ("nforc", "compare"):
            results["nforc"], centres = extract_forces_nforc(demo.odb, section, frames, return_centres=True)
            _print_table("NFORC SUMMATION", frames, results["nforc"])
            c0 = centres[frames[0].index]
            print("NFORC summation point (frame index %d): %s" % (frames[0].index, np.round(c0, 4).tolist()))
            node_avg = np.mean([np.asarray(c, float) for _, c in odb_tools.set_nodes(odb_tools.get_node_set(demo.odb, section.set_name))], axis=0)
            print("plain node average for reference     : %s" % np.round(node_avg, 4).tolist())

        if method == "compare":
            fb, nf = results["freebody"], results["nforc"]
            print("\nDIFFERENCE nforc - freebody")
            print("%6s | %s" % ("index", " ".join("%13s" % l for l in LABELS)))
            for rec in frames:
                print("%6d | %s" % (rec.index, " ".join("%13.4g" % (b - a) for a, b in zip(fb[rec.index], nf[rec.index]))))
            print("\nSUMMARY per component over all frames:")
            print("%5s %14s %14s %10s %8s" % ("", "max|freebody|", "max|diff|", "rel.diff", "sign"))
            for i, l in enumerate(LABELS):
                a = np.array([fb[r.index][i] for r in frames])
                b = np.array([nf[r.index][i] for r in frames])
                peak = np.max(np.abs(a))
                dmax = np.max(np.abs(b - a))
                corr = float(np.dot(a, b))
                sign = "same" if corr >= 0 else "FLIPPED"
                rel = "%9.2f%%" % (100.0 * dmax / peak) if peak else "%10s" % "n/a"
                print("%5s %14.5g %14.5g %s %8s" % (l, peak, dmax, rel, sign))
            print("Forces should agree closely. Moment differences come from the summation point: the free body "
                  "uses Abaqus' own centroid, NFORC uses the area-weighted cut centroid printed above.")
    finally:
        demo.close()
