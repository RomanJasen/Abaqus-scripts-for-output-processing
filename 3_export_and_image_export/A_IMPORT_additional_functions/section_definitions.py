"""
section_definitions.py - what kind of cross-section a node/element SET is,
and how it must be processed.

SET naming convention (unchanged from the original scripts):
    <TYPE>&<LABEL>&<INDEX>&<ANGLE>
    e.g. V_PIER&DPARC&1&0
    TYPE   V_PIER, V_SPEC, S_PIER, V_SPANDREL, S_DRIFT, SRIFT ...
    INDEX  number of the section (no influence on the axes)
    ANGLE  rotation (deg) of the local axes about global Z (displacements and forces)

To support a new set type, add one SectionType to SECTION_TYPES.

No Abaqus import: runs in any Python.   python section_definitions.py
"""
from __future__ import print_function

import math


class SectionType(object):
    """How a family of sets is processed.

    geometry     'volume' -> regression plane of solid-element section
                 'shell'  -> centroid + regression lines of a shell section
                 'point'  -> plain (average) nodal displacement, global axes
    orientation  'PIER' or 'SPANDREL' (local axes calibration), None for 'point'
    forces       True -> free-body cut forces are extracted
    """

    def __init__(self, name, tokens, geometry, orientation, forces):
        self.name = name
        self.tokens = tokens
        self.geometry = geometry
        self.orientation = orientation
        self.forces = forces

    def __repr__(self):
        return "SectionType(%s, geometry=%s, orientation=%s, forces=%s)" % (
            self.name, self.geometry, self.orientation, self.forces)


# Order matters: first match wins.
SECTION_TYPES = [
    SectionType("V_PIER",     ("V_PIER", "V_SPEC"), "volume", "PIER",     True),
    SectionType("S_PIER",     ("S_PIER",),          "shell",  "PIER",     True),
    SectionType("V_SPANDREL", ("V_SPANDREL",),      "volume", "SPANDREL", True),
    # shell spandrel: vertical line of shell nodes; section X = -global Z (along the
    # line), section Z = beam axis. New - check the first results against a hand calc.
    SectionType("S_SPANDREL", ("S_SPANDREL",),      "shell",  "SPANDREL", True),
    SectionType("S_DRIFT",    ("S_DRIFT",),         "point",  None,       False),
    SectionType("SRIFT",      ("SRIFT",),           "volume", "PIER",     False),
]


class SectionSet(object):
    """A parsed SET name plus its SectionType."""

    def __init__(self, set_name, section_type, label, index, angle):
        self.set_name = set_name
        self.type = section_type
        self.label = label
        self.index = index
        self.angle = angle

    def force_csys_points(self):
        """Origin, point on local X, point on local Y for the free-body csys.
        Same orientation for every INDEX (the original scripts turned it by 180 deg
        for odd INDEX, which flipped Fx, Fy, Mx, My against the displacement axes)."""
        a = math.radians(self.angle)
        c, s = math.cos(a), math.sin(a)
        if self.type.orientation == "SPANDREL":
            return ((0.0, 0.0, 0.0), (0.0, 0.0, -1.0), (-s, c, 0.0))
        return ((0.0, 0.0, 0.0), (c, s, 0.0), (-s, c, 0.0))

    def __repr__(self):
        return "SectionSet(%r, type=%s, index=%s, angle=%s)" % (
            self.set_name, self.type.name, self.index, self.angle)


def classify(set_name):
    """Return the SectionType for a set name, or None if it is not exported."""
    upper = set_name.upper()
    for st in SECTION_TYPES:
        for token in st.tokens:
            if token in upper:
                return st
    return None


def parse(set_name):
    """Parse a set name into a SectionSet. Raises ValueError on a bad name."""
    st = classify(set_name)
    if st is None:
        raise ValueError("SET %r does not match any known section type" % set_name)
    parts = set_name.split("&")
    if len(parts) < 4:
        raise ValueError("SET %r must look like TYPE&LABEL&INDEX&ANGLE" % set_name)
    try:
        index = int(float(parts[2]))
        angle = float(parts[3])
    except ValueError:
        raise ValueError("SET %r: INDEX and ANGLE must be numbers" % set_name)
    return SectionSet(set_name, st, parts[1], index, angle)


def select_sets(all_set_names, name_filters=("",)):
    """Keep sets that are a known section type AND contain one of name_filters
    ("" keeps everything). Returns a sorted list of names."""
    selected = []
    for name in all_set_names:
        if classify(name) is None:
            continue
        if any(f.upper() in name.upper() for f in name_filters):
            selected.append(name)
    return sorted(selected)


if __name__ == "__main__":
    samples = ["V_PIER&DPARC&1&0", "V_SPEC&DM&2&0", "S_PIER&W1&1&90", "V_SPANDREL&S1&2&45",
               "S_DRIFT&F1&1&0", "SRIFT&F2&1&0", "S_SPANDREL&X&1&0", "ALL_NODES"]
    print("Classification of example SET names:")
    for n in samples:
        try:
            s = parse(n)
            print("  %-22s -> %-11s geometry=%-6s forces=%-5s csys=%s" % (
                n, s.type.name, s.type.geometry, s.type.forces,
                [tuple(round(v, 3) for v in p) for p in s.force_csys_points()]))
        except ValueError as e:
            print("  %-22s -> skipped (%s)" % (n, e))
    print("select_sets(filter='SPEC') ->", select_sets(samples, ["SPEC"]))
