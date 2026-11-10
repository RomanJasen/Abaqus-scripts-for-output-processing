"""
section_geometry.py - pure numpy geometry used to turn a cloud of node
coordinates into cross-section values (centre, rotations, dimensions) and
to compute cut-face centroids.

No Abaqus import: this module runs in any Python with numpy.
Merges the former Field_of_displ_into_section_displ.py and
Section_displacement_manipulation.py.

Sign convention for rotations: right-hand rule about the section axes
(fix about X, fiy about Y, fiz about Z).

Run on its own (plain python or abaqus python) for a self-test:
    python section_geometry.py
"""
from __future__ import print_function

import math
import numpy as np

AXES = {"X": 0, "Y": 1, "Z": 2}


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------
def as_points(points):
    """Return points as a float64 (N,3) numpy array."""
    arr = np.asarray(points, dtype=np.float64)
    if arr.ndim == 1 and arr.shape[0] == 3:
        arr = arr.reshape(1, 3)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("Expected an (N,3) array of points, got shape %s" % (arr.shape,))
    if arr.shape[0] == 0:
        raise ValueError("A set with no nodes was provided")
    return arr


def rotate_to_local(points, angle_deg):
    """Rotate points (or vectors) about global Z by angle_deg so local X runs along the wall.
    x' =  cos(a)*x + sin(a)*y
    y' = -sin(a)*x + cos(a)*y
    z' =  z
    """
    p = as_points(points)
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    out = p.copy()
    out[:, 0] = c * p[:, 0] + s * p[:, 1]
    out[:, 1] = -s * p[:, 0] + c * p[:, 1]
    return out


def calibrate_axes(points, orientation):
    """Re-orient local axes for the element type (a proper rotation, det = +1).
    PIER: unchanged.  SPANDREL: (x, y, z) -> (-z, y, x)."""
    p = as_points(points)
    if orientation in ("PIER", None):
        return p
    if orientation == "SPANDREL":
        return np.column_stack((-p[:, 2], p[:, 1], p[:, 0]))
    raise ValueError("Unknown orientation: %r" % (orientation,))


def to_section_axes(points, angle_deg, orientation):
    """Global coordinates (or vectors) -> section (local + calibrated) axes."""
    return calibrate_axes(rotate_to_local(points, angle_deg), orientation)


def regression_plane(points):
    """Least-squares plane z = A*x + B*y + D.
    Returns ([A, B, D], [xc, yc, zc]) where xc, yc is the bounding-box centre
    in X/Y and zc is the plane height at that point."""
    p = as_points(points)
    X = np.column_stack((p[:, 0], p[:, 1], np.ones(len(p))))
    Q, R = np.linalg.qr(X)
    coef = np.linalg.solve(R, Q.T.dot(p[:, 2]))
    xc = (p[:, 0].min() + p[:, 0].max()) / 2.0
    yc = (p[:, 1].min() + p[:, 1].max()) / 2.0
    zc = coef[0] * xc + coef[1] * yc + coef[2]
    return [float(coef[0]), float(coef[1]), float(coef[2])], [float(xc), float(yc), float(zc)]


def regression_line(points, axis_1, axis_2):
    """Least-squares line axis_2 = k*axis_1 + n. Returns [k, n]."""
    p = as_points(points)
    k, n = np.polyfit(p[:, AXES[axis_1]], p[:, AXES[axis_2]], 1)
    return [float(k), float(n)]


def centroid(points):
    """Arithmetic mean of the points."""
    return [float(v) for v in as_points(points).mean(axis=0)]


def extents(points):
    """[dX, dY, dZ] size of the bounding box."""
    p = as_points(points)
    return [float(v) for v in (p.max(axis=0) - p.min(axis=0))]


# ---------------------------------------------------------------------------
# Rigid-body fit (large rotations)
# ---------------------------------------------------------------------------
def rigid_fit(p0, p):
    """Best-fit rigid motion p ~ R (p0 - m0) + m  (Kabsch / SVD).
    Exact for any rotation size; needs >= 3 non-collinear points
    (coplanar is fine, e.g. the nodes of one cross-section).
    Returns (R 3x3, m0, m)."""
    p0 = as_points(p0)
    p = as_points(p)
    m0 = p0.mean(axis=0)
    m = p.mean(axis=0)
    H = (p0 - m0).T.dot(p - m)
    U, S, Vt = np.linalg.svd(H)
    d = 1.0 if np.linalg.det(Vt.T.dot(U.T)) > 0 else -1.0
    R = Vt.T.dot(np.diag([1.0, 1.0, d])).dot(U.T)
    return R, m0, m


def axis_angle_matrix(axis, angle):
    """Rotation matrix for a rotation of angle (rad) about axis (Rodrigues)."""
    a = np.asarray(axis, dtype=np.float64)
    n = np.linalg.norm(a)
    if n < 1e-15 or angle == 0.0:
        return np.eye(3)
    a = a / n
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * K.dot(K)


def rotation_between(u, v):
    """Smallest rotation matrix turning direction u into direction v."""
    u = np.asarray(u, dtype=np.float64) / np.linalg.norm(u)
    v = np.asarray(v, dtype=np.float64) / np.linalg.norm(v)
    axis = np.cross(u, v)
    s = np.linalg.norm(axis)
    c = float(np.clip(u.dot(v), -1.0, 1.0))
    if s < 1e-15:
        if c > 0:
            return np.eye(3)
        perp = np.cross(u, [1.0, 0.0, 0.0])
        if np.linalg.norm(perp) < 1e-8:
            perp = np.cross(u, [0.0, 1.0, 0.0])
        return axis_angle_matrix(perp, math.pi)
    return axis_angle_matrix(axis, math.atan2(s, c))


def rotation_vector(R):
    """Rotation vector (axis * angle, rad) of a rotation matrix.
    For small rotations its components equal the rotations about X, Y, Z."""
    R = np.asarray(R, dtype=np.float64)
    c = float(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))
    angle = math.acos(c)
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if angle < 1e-7:
        return 0.5 * w
    if math.pi - angle > 1e-6:
        return angle / (2.0 * math.sin(angle)) * w
    # ~180 deg: axis from the symmetric part
    B = (R + np.eye(3)) / 2.0
    axis = np.sqrt(np.clip(np.diag(B), 0.0, None))
    k = int(np.argmax(axis))
    axis = B[:, k] / math.sqrt(max(B[k, k], 1e-300))
    return angle * axis / np.linalg.norm(axis)


def euler_xyz(R):
    """Angles (rx, ry, rz) with R = Rz(rz) . Ry(ry) . Rx(rx)  (rotate about X, then Y, then Z,
    fixed axes). For small rotations equal to the rotations about X, Y, Z."""
    R = np.asarray(R, dtype=np.float64)
    rx = math.atan2(R[2, 1], R[2, 2])
    ry = math.atan2(-R[2, 0], math.sqrt(R[2, 1] ** 2 + R[2, 2] ** 2))
    rz = math.atan2(R[1, 0], R[0, 0])
    return np.array([rx, ry, rz])


def decompose_rotation(R, method="rotation_vector"):
    if method == "rotation_vector":
        return rotation_vector(R)
    if method == "euler_xyz":
        return euler_xyz(R)
    raise ValueError("Unknown rotation decomposition %r" % method)


def _principal_axes(points):
    """Rows = principal directions of the point cloud, largest spread first.
    full_matrices=False: without it numpy also builds an unused N x N matrix
    (8*N^2 bytes - several GB for large node sets)."""
    p = as_points(points)
    # with < 3 points the reduced SVD has < 3 rows; the full one is tiny then anyway
    _, _, Vt = np.linalg.svd(p - p.mean(axis=0), full_matrices=p.shape[0] < 3)
    return Vt


def plane_normal(points, hint=(0.0, 0.0, 1.0)):
    """Unit normal of the best-fit plane (smallest principal direction), oriented along hint."""
    n = _principal_axes(points)[2]
    return n if n.dot(hint) >= 0 else -n


def line_direction(points, hint=(1.0, 0.0, 0.0)):
    """Unit direction of the best-fit line (largest principal direction), oriented along hint."""
    d = _principal_axes(points)[0]
    return d if d.dot(hint) >= 0 else -d


def frame_from_axes(e1_hint, e3_hint):
    """Orthonormal frame (columns e1, e2, e3): e3 along e3_hint, e1 = e1_hint made normal to e3."""
    e3 = np.asarray(e3_hint, dtype=np.float64)
    e3 = e3 / np.linalg.norm(e3)
    e1 = np.asarray(e1_hint, dtype=np.float64)
    e1 = e1 - e1.dot(e3) * e3
    if np.linalg.norm(e1) < 1e-12:
        raise ValueError("Frame hints are parallel")
    e1 = e1 / np.linalg.norm(e1)
    return np.column_stack((e1, np.cross(e3, e1), e3))


def section_frame_volume(points):
    """Own frame of a planar section: e3 = plane normal (~+Z), e1 = X projected onto the plane."""
    return frame_from_axes([1.0, 0.0, 0.0], plane_normal(points))


def section_frame_line(direction):
    """Own frame of a line section (shell): e1 = line direction, e3 = Z made normal to it."""
    d = np.asarray(direction, dtype=np.float64)
    e3_hint = [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 * np.linalg.norm(d) else [0.0, -1.0, 0.0]
    e3 = np.asarray(e3_hint) - np.dot(e3_hint, d) / d.dot(d) * d
    return frame_from_axes(d, e3)


# ---------------------------------------------------------------------------
# Cut-face centroid (area weighted)
# ---------------------------------------------------------------------------
def polygon_area_centroid(points, normal):
    """Area and centroid of a planar polygon whose vertices may be unordered
    (they are sorted by angle around their mean in the plane given by normal)."""
    p = as_points(points)
    c = p.mean(axis=0)
    n = np.asarray(normal, dtype=np.float64)
    n = n / np.linalg.norm(n)
    u = p[0] - c
    u = u - u.dot(n) * n
    if np.linalg.norm(u) < 1e-15:
        u = np.cross(n, [1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.cross(n, [0.0, 1.0, 0.0])
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    ang = np.arctan2((p - c).dot(v), (p - c).dot(u))
    q = p[np.argsort(ang)]
    area, acc = 0.0, np.zeros(3)
    for i in range(len(q)):  # fan of triangles around c
        a, b = q[i], q[(i + 1) % len(q)]
        t = 0.5 * np.linalg.norm(np.cross(a - c, b - c))
        area += t
        acc += t * (a + b + c) / 3.0
    if area <= 0.0:
        return 0.0, c
    return area, acc / area


def cut_centroid(faces, normal=None):
    """Area-weighted centroid of the cut.
    faces : list of (k,3) arrays - the nodes of each element that lie on the cut.
            k >= 3 -> polygon (solid elements), k == 2 -> segment (shell edge, length weighted).
    Falls back to the plain node average if no face has a size."""
    polys = [as_points(f) for f in faces if len(f) >= 3]
    if polys:
        if normal is None:
            normal = plane_normal(np.vstack(polys))
        total, acc = 0.0, np.zeros(3)
        for f in polys:
            a, c = polygon_area_centroid(f, normal)
            total += a
            acc += a * c
        if total > 0:
            return acc / total
    segs = [as_points(f) for f in faces if len(f) == 2]
    if segs:
        total, acc = 0.0, np.zeros(3)
        for s in segs:
            L = np.linalg.norm(s[1] - s[0])
            total += L
            acc += L * s.mean(axis=0)
        if total > 0:
            return acc / total
    allp = [as_points(f) for f in faces if len(f)]
    return np.vstack(allp).mean(axis=0)


def plot_section(points, centre=None, plane_coef=None):
    """Debug helper: 3D scatter of a section with optional centre and plane.
    For plain python only: it opens a plot window, which can block the Abaqus kernel."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3d projection)
    p = as_points(points)
    ax = plt.figure().add_subplot(111, projection="3d")
    ax.scatter(p[:, 0], p[:, 1], p[:, 2], c="red")
    if centre is not None:
        ax.scatter([centre[0]], [centre[1]], [centre[2]], c="blue", s=60)
    if plane_coef is not None:
        xx, yy = np.meshgrid(np.linspace(p[:, 0].min(), p[:, 0].max(), 10),
                             np.linspace(p[:, 1].min(), p[:, 1].max(), 10))
        ax.plot_surface(xx, yy, plane_coef[0] * xx + plane_coef[1] * yy + plane_coef[2], alpha=0.4)
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    plt.show()


# ---------------------------------------------------------------------------
# Self-test / demonstration
# ---------------------------------------------------------------------------
def _self_test():
    rng = np.random.RandomState(0)
    ok = True

    def check(name, got, expected, tol=1e-9):
        passed = bool(np.allclose(got, expected, atol=tol))
        print("  %-44s %s   got=%s expected=%s" % (name, "OK  " if passed else "FAIL",
                                                  np.round(got, 6).tolist(), np.round(expected, 6).tolist()))
        return passed

    print("section_geometry self-test")
    # plane z = 0.02x - 0.01y + 5 over a 1200 x 150 wall section
    xy = np.column_stack((rng.uniform(0, 1200, 400), rng.uniform(0, 150, 400)))
    pts = np.column_stack((xy, 0.02 * xy[:, 0] - 0.01 * xy[:, 1] + 5.0))
    coef, centre = regression_plane(pts)
    ok &= check("regression_plane coefficients", coef, [0.02, -0.01, 5.0], 1e-8)
    ok &= check("regression_plane centre z", centre[2], 0.02 * centre[0] - 0.01 * centre[1] + 5.0)

    xs = np.linspace(0, 1200, 25)
    line = regression_line(np.column_stack((xs, np.zeros(25), 0.3 * xs + 2.0)), "X", "Z")
    ok &= check("regression_line z = 0.3x + 2", line, [0.3, 2.0], 1e-8)

    ok &= check("rotate_to_local 90 deg", rotate_to_local([[1.0, 0.0, 3.0]], 90)[0], [0.0, -1.0, 3.0])
    ok &= check("calibrate_axes SPANDREL", calibrate_axes([[1.0, 2.0, 3.0]], "SPANDREL")[0], [-3.0, 2.0, 1.0])
    ok &= check("extents", extents([[0, 0, 0], [2, 3, 4]]), [2, 3, 4])
    ok &= check("centroid", centroid([[0, 0, 0], [2, 4, 6]]), [1, 2, 3])

    # rigid fit of a flat (coplanar) section rotated by LARGE angles
    flat = np.column_stack((xy - [600, 75], np.zeros(len(xy))))
    for rv in ([0.9, 0.0, 0.0], [0.0, -1.2, 0.0], [0.3, 0.5, -2.0]):
        R_true = axis_angle_matrix(rv, np.linalg.norm(rv))
        moved = (R_true.dot(flat.T)).T + [10.0, -5.0, 2.0]
        R, m0, m = rigid_fit(flat, moved)
        ok &= check("rigid_fit + rotation_vector %s" % rv, rotation_vector(R), rv, 1e-8)
    R = axis_angle_matrix([1, 0, 0], 0.7)
    ok &= check("euler_xyz pure X rotation 0.7", euler_xyz(R), [0.7, 0, 0])
    ok &= check("rotation_between X -> Z", rotation_between([1, 0, 0], [0, 0, 1]).dot([1, 0, 0]), [0, 0, 1])

    # small tilt: plane slope B -> rotation about X = atan(B) (right-hand rule)
    tilt = axis_angle_matrix([1, 0, 0], 0.01)
    ok &= check("small tilt about X: rotvec vs slope", rotation_vector(rigid_fit(flat, flat.dot(tilt.T))[0])[0],
                math.atan(regression_plane(flat.dot(tilt.T))[0][1]), 1e-9)

    # area-weighted centroid: coarse + fine mesh halves of a 2 x 1 rectangle
    faces = [np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)]
    for i in range(4):
        for j in range(4):
            x0, y0 = 1 + i * 0.25, j * 0.25
            faces.append(np.array([[x0, y0, 0], [x0 + .25, y0 + .25, 0], [x0 + .25, y0, 0], [x0, y0 + .25, 0]]))
    ok &= check("cut_centroid (mixed mesh density)", cut_centroid(faces), [1.0, 0.5, 0.0])
    print("  (plain node average of the same cut would give x = %.3f)" % np.vstack(faces).mean(axis=0)[0])

    print("RESULT:", "ALL PASSED" if ok else "SOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    _self_test()
