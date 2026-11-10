"""
section_displacements.py - cross-section displacements / rotations from the
nodal displacement field.

Output per frame (6 values, section axes, right-hand rule):
    Ux, Uy, Uz   displacement of the section centre
    fix, fiy, fiz rotation about section X, Y, Z   (empty for 'point' sets)

How rotations are measured is set in DEFAULT_KINEMATICS (below); the main
script can override it with CONFIG["KINEMATICS"].

  METHOD "rigid"  best-fit rigid-body motion of the section nodes (Kabsch/SVD).
                  Exact for LARGE rotations and displacements, insensitive to
                  mesh density; the centre displacement is the rigid motion of
                  the initial centre point. Rotations are then decomposed as a
                  rotation vector (default) or XYZ Euler angles.
  METHOD "angle"  atan of the regression plane / line slopes (legacy geometry,
                  valid to moderate rotations about ONE axis at a time).
  METHOD "slope"  the slopes themselves (small-rotation assumption, like the
                  original script; note the original also had fiy with the
                  opposite sign and fix/fiy mixed up - both fixed here).

  ROTATIONS  per component "relative" (change from the undeformed state) or
             "absolute" (orientation relative to the section axes, i.e. an
             initially tilted section starts with a non-zero value).

Shell sections are a LINE of nodes: rotations about the line (twist, fix) can't
be derived from translations, so it is read from the UR output (mean of the
nodes) when available, else 0.

Works for IMPLICIT and EXPLICIT ODBs. Results are keyed by FrameRecord.index
(see odb_tools) so they line up with section_forces.

STAND-ALONE RUN: edit DEMO_SETTINGS, then File > Run Script... in Abaqus/CAE or Viewer.
"""
from __future__ import print_function

import os
import sys
import math
import time
import copy
import inspect

_HERE = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np

import odb_tools
import section_geometry as geo
import section_definitions as sdefs

# =============================================================================
# DEFAULT KINEMATICS - how section rotations/displacements are measured
# =============================================================================
DEFAULT_KINEMATICS = {
    "METHOD": "rigid",                   # "rigid" | "angle" | "slope"
    "ROTATIONS": {"fix": "relative",     # "relative" | "absolute", per component
                  "fiy": "relative",
                  "fiz": "relative"},
    "DECOMPOSITION": "rotation_vector",  # rigid only: "rotation_vector" | "euler_xyz"
    "SIGN": {"fix": 1.0, "fiy": 1.0, "fiz": 1.0},   # e.g. fiy -1.0 to match old databases
    "SHELL_TWIST_FROM_UR": True,         # shells: fix from mean UR if UR is in the ODB
}

# =============================================================================
# DEMO SETTINGS - only used when THIS file is run on its own
# =============================================================================
DEMO_SETTINGS = {
    "ODB": None,            # full path, None -> ODB open in viewport / last export / dialog
    "STEP": None,           # None -> step of the last export / last step
    "SET": None,            # e.g. "V_PIER&DPARC&1&0", None -> prompt / first suitable set
    "MIN_DT": None,         # min. step time between frames, None = every frame
    "FRAME_INDICES": None,  # e.g. [0, 25, -1] for a quick test, None = all frames
    "COMPARE_METHODS": True,  # also print rigid / angle / slope side by side
}
# =============================================================================

COMPONENTS = ("fix", "fiy", "fiz")


def merged_kinematics(overrides=None):
    kin = copy.deepcopy(DEFAULT_KINEMATICS)
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(kin.get(k), dict):
            kin[k].update(v)
        else:
            kin[k] = v
    if kin["METHOD"] not in ("rigid", "angle", "slope"):
        raise ValueError("KINEMATICS METHOD must be rigid, angle or slope, not %r" % kin["METHOD"])
    return kin


class SectionReference(object):
    """Undeformed state of one section set + per-frame evaluation."""

    def __init__(self, odb, section, kinematics=None):
        self.section = section
        self.kin = merged_kinematics(kinematics)
        self.region = odb_tools.get_node_set(odb, section.set_name)
        nodes = odb_tools.set_nodes(self.region)
        if not nodes:
            raise ValueError("NO NODES FOUND IN SET %s" % section.set_name)
        self.keys = [k for k, _ in nodes]
        self.coords0 = np.array([c for _, c in nodes], dtype=np.float64)
        geometry = section.type.geometry

        if geometry == "point":
            self.centre0 = geo.centroid(geo.rotate_to_local(self.coords0, section.angle))
            self.dimensions = [0.0, 0.0, 0.0]
            return

        local0 = geo.rotate_to_local(self.coords0, section.angle)
        self.dimensions = geo.extents(local0)  # before axis calibration, as in the original
        self.sec0 = geo.calibrate_axes(local0, section.type.orientation)
        if geometry == "volume":
            if len(self.keys) < 3:
                raise ValueError("SET %s has %d nodes, a section needs >= 3" % (section.set_name, len(self.keys)))
            _, self.centre0 = geo.regression_plane(self.sec0)
            self.frame0 = geo.section_frame_volume(self.sec0)
        elif geometry == "shell":
            if len(self.keys) < 2:
                raise ValueError("SET %s has %d nodes, a shell section needs >= 2" % (section.set_name, len(self.keys)))
            self.centre0 = geo.centroid(self.sec0)
            self.dir0 = geo.line_direction(self.sec0)
            proj = (self.sec0 - self.sec0.mean(axis=0)).dot(self.dir0)
            self.i_min, self.i_max = int(np.argmin(proj)), int(np.argmax(proj))
            self.frame0 = geo.section_frame_line(self.dir0)
        else:
            raise ValueError("Unknown geometry %r" % geometry)
        self.slope_values0 = self._slope_values(self.sec0, twist=0.0)

    # -- helpers -------------------------------------------------------------
    def _stack(self, by_node, what):
        try:
            return np.array([by_node[k] for k in self.keys], dtype=np.float64)
        except KeyError as e:
            raise KeyError("Node %s of set %s has no %s output in this frame" % (e, self.section.set_name, what))

    def _slope_values(self, sec, twist):
        """Rotations about X, Y, Z from regression slopes, right-hand rule.
        Returns (slopes, angles)."""
        if self.section.type.geometry == "volume":
            (A, B, _), _ = geo.regression_plane(sec)          # z = A x + B y + D
            k = geo.regression_line(sec, "X", "Y")[0]          # y = k x
            slopes = [B, -A, k]
            angles = [math.atan(B), -math.atan(A), math.atan(k)]
        else:
            kxz = geo.regression_line(sec, "X", "Z")[0]        # z = k x
            kxy = geo.regression_line(sec, "X", "Y")[0]
            slopes = [twist, -kxz, kxy]
            angles = [twist, -math.atan(kxz), math.atan(kxy)]
        return slopes, angles

    def _node_rotation(self, ur):
        """Mean nodal rotation vector (UR) in section axes, or None."""
        if ur is None:
            return None
        ur_sec = geo.to_section_axes(self._stack(ur, "UR"), self.section.angle, self.section.type.orientation)
        return ur_sec.mean(axis=0)

    def _twist(self, ur, R_line=None):
        """Shell twist = rotation about the line left after aligning the line direction:
        R_res = R_line^T . exp(UR);  twist = component of R_res about the initial line."""
        rv = self._node_rotation(ur)
        if rv is None:
            return 0.0
        if R_line is None:  # slope / angle methods: small-rotation component about X
            return float(rv[0])
        R_res = R_line.T.dot(geo.axis_angle_matrix(rv, float(np.linalg.norm(rv))))
        return float(geo.rotation_vector(R_res).dot(self.dir0))

    # -- per frame -----------------------------------------------------------
    def displacement_row(self, u_by_node, ur_by_node=None):
        """[Ux, Uy, Uz, fix, fiy, fiz] for one frame."""
        u = self._stack(u_by_node, "U")
        geometry = self.section.type.geometry
        if geometry == "point":
            d = geo.rotate_to_local(u.mean(axis=0), self.section.angle)[0]
            return [float(v) for v in d] + [None, None, None]

        sec = geo.to_section_axes(self.coords0 + u, self.section.angle, self.section.type.orientation)
        kin = self.kin
        if kin["METHOD"] == "rigid":
            if geometry == "volume":
                R, m0, m = geo.rigid_fit(self.sec0, sec)
                centre = R.dot(np.subtract(self.centre0, m0)) + m
            else:
                hint = sec[self.i_max] - sec[self.i_min]
                d = geo.line_direction(sec, hint=hint)
                R_line = geo.rotation_between(self.dir0, d)
                R = geo.axis_angle_matrix(d, self._twist(ur_by_node, R_line)).dot(R_line)
                centre = np.asarray(geo.centroid(sec))
            rel = geo.decompose_rotation(R, kin["DECOMPOSITION"])
            ab = geo.decompose_rotation(R.dot(self.frame0), kin["DECOMPOSITION"])
        else:
            if geometry == "volume":
                _, centre = geo.regression_plane(sec)
            else:
                centre = geo.centroid(sec)
            which = 0 if kin["METHOD"] == "slope" else 1
            cur = self._slope_values(sec, self._twist(ur_by_node))[which]
            ini = self.slope_values0[which]
            ab = np.array(cur)
            rel = np.subtract(cur, ini)

        disp = np.subtract(centre, self.centre0)
        rot = []
        for i, name in enumerate(COMPONENTS):
            v = ab[i] if kin["ROTATIONS"][name] == "absolute" else rel[i]
            rot.append(float(v) * float(kin["SIGN"][name]))
        return [float(v) for v in disp] + rot


def extract_section_displacements(odb, sections, frames, kinematics=None, field="U",
                                  verbose=True, skip_errors=False):
    """Displacements of several sections over the selected frames.

    sections    : list of section_definitions.SectionSet
    frames      : list of odb_tools.FrameRecord (use the SAME list for forces)
    kinematics  : overrides of DEFAULT_KINEMATICS (dict), None = defaults
    skip_errors : a section whose set cannot be processed is left out of the
                  result (with a message) instead of stopping everything
    returns     : {set_name: (SectionReference, {frame_index: [6 values]})}

    Frames are the outer loop so every frame's field is loaded once for all sets.
    """
    log = odb_tools.log if verbose else (lambda message="": None)
    refs = []
    for s in sections:
        try:
            refs.append(SectionReference(odb, s, kinematics))
        except Exception as e:
            if not skip_errors:
                raise
            log("    SKIPPED %s: %s" % (s.set_name, e))
    log("    %d section(s) prepared (%s nodes)" % (len(refs), ", ".join(str(len(r.keys)) for r in refs)))
    results = dict((r.section.set_name, (r, {})) for r in refs)
    if not frames:
        return results

    kin = merged_kinematics(kinematics)
    need_ur = kin["SHELL_TWIST_FROM_UR"] and any(r.section.type.geometry == "shell" for r in refs)
    if need_ur and not odb_tools.has_field(frames[0].frame, "UR"):
        log("    NOTE: no UR output in the ODB -> shell twist (fix) is set to 0")
        need_ur = False

    t0 = time.time()
    for k, rec in enumerate(frames):
        for ref in refs:
            u = odb_tools.read_nodal_vectors(rec.frame, ref.region, field)
            ur = None
            if need_ur and ref.section.type.geometry == "shell":
                ur = odb_tools.read_nodal_vectors(rec.frame, ref.region, "UR")
            results[ref.section.set_name][1][rec.index] = ref.displacement_row(u, ur)
        if verbose:
            odb_tools.progress("Section displacements", k + 1, len(frames), "frames")
            if k % 10 == 0 or k == len(frames) - 1:
                log("    displacements: frame %d/%d (index %d)  %.1fs" % (k + 1, len(frames), rec.index, time.time() - t0))
    return results


def extract_one(odb, set_name, frames, kinematics=None, verbose=True):
    """Convenience wrapper for a single set -> (SectionReference, {frame_index: row})."""
    section = sdefs.parse(set_name)
    return extract_section_displacements(odb, [section], frames, kinematics, verbose=verbose)[set_name]


def _fmt(v):
    return "" if v is None else "%.5g" % v


if __name__ == "__main__":
    demo = odb_tools.resolve_demo_inputs(DEMO_SETTINGS, set_filter=lambda n, odb: sdefs.classify(n) is not None)
    try:
        frames = demo.frames
        ref, rows = extract_one(demo.odb, demo.set_name, frames)
        print("\nSection %s (%s): %d nodes, centre0=%s, dimensions=%s" % (
            demo.set_name, ref.section.type.name, len(ref.keys),
            np.round(ref.centre0, 4).tolist(), np.round(ref.dimensions, 4).tolist()))
        print("Kinematics: %s" % ref.kin)
        print("%6s %10s %10s | %12s %12s %12s %12s %12s %12s" % (
            "index", "frameId", "time", "Ux", "Uy", "Uz", "fix", "fiy", "fiz"))
        for rec in frames:
            print("%6d %10d %10.4g | %s" % (rec.index, rec.frame_id, rec.step_time,
                                            " ".join("%12s" % _fmt(v) for v in rows[rec.index])))

        if DEMO_SETTINGS["COMPARE_METHODS"] and ref.section.type.geometry != "point":
            picks = sorted(set([frames[0], frames[len(frames) // 2], frames[-1]]), key=lambda r: r.index)
            print("\nMethod comparison (relative rotations, rad):")
            print("%-8s %6s | %12s %12s %12s %12s %12s %12s" % ("method", "index", "Ux", "Uy", "Uz", "fix", "fiy", "fiz"))
            for method in ("rigid", "angle", "slope"):
                _, r2 = extract_one(demo.odb, demo.set_name, picks, {"METHOD": method}, verbose=False)
                for rec in picks:
                    print("%-8s %6d | %s" % (method, rec.index, " ".join("%12s" % _fmt(v) for v in r2[rec.index])))
            print("rigid is exact for large rotations; angle/slope drift apart from it as rotations grow.")
    finally:
        demo.close()
