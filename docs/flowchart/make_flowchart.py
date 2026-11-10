# -*- coding: utf-8 -*-
"""Flowcharts of the A_ post-processing scripts, from ONE model:
SVG (vector), PNG (2x), single-figure PDFs (vector), HTML report, A4 PDF report, draw.io (editable).

Run:  python make_flowchart.py      (needs Python 3 with Pillow, and Microsoft Edge for PNG / PDF)
Edit the texts and positions in overview() and detailed(); every file is regenerated from them."""
import os
import sys
import html
import math
import shutil
import datetime
import subprocess
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import ImageFont

OUT = Path(__file__).resolve().parent          # this folder: all versions are written here
MAIN = OUT.parent                                # the folder with the A_ scripts
SCRATCH = Path(__import__("tempfile").gettempdir()) / "flowchart_postprocessing_work"
SCRATCH.mkdir(exist_ok=True)
BASE = "Flowchart_postprocessing"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TODAY = datetime.date.today()

SANS = "'Segoe UI', Arial, Helvetica, sans-serif"
MONO = "Consolas, 'Courier New', monospace"
FONT_FILES = {("sans", False): r"C:\Windows\Fonts\segoeui.ttf", ("sans", True): r"C:\Windows\Fonts\segoeuib.ttf",
              ("mono", False): r"C:\Windows\Fonts\consola.ttf", ("mono", True): r"C:\Windows\Fonts\consolab.ttf"}
_fonts = {}


def text_width(text, family, bold, size):
    key = (family, bold, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_FILES[(family, bold)], size=int(round(size * 8)))
    return _fonts[key].getlength(text) / 8.0


# text styles: family, bold, size, colour (None = accent of the box), line height
ST = {
    "script": ("mono", True, 12.0, None, 17),
    "title": ("sans", True, 13.0, "#0f172a", 17),
    "body": ("sans", False, 11.5, "#334155", 15),
    "mono": ("mono", False, 10.5, "#334155", 14),
    "small": ("sans", False, 10.5, "#64748b", 14),
    "tag": ("sans", True, 11.0, "#475569", 16),
    "gap": ("sans", False, 6.0, "#334155", 6),
}

PAL = {
    "1": dict(stroke="#1d4ed8", fill="#eff6ff", lane_fill="#f6f9ff", lane_stroke="#bfd3fb"),
    "2a": dict(stroke="#b45309", fill="#fff8eb", lane_fill="#fffcf5", lane_stroke="#f5d29a"),
    "2b": dict(stroke="#047857", fill="#ecfdf5", lane_fill="#f6fdf9", lane_stroke="#a3e6c9"),
    "store": dict(stroke="#475569", fill="#f1f5f9"),
    "doc": dict(stroke="#475569", fill="#ffffff"),
    "ext": dict(stroke="#94a3b8", fill="#f8fafc"),
}
FLOW = "#334155"
GRAY = "#94a3b8"


def esc(t):
    return html.escape(t, quote=False)


class Node(object):
    def __init__(self, id, kind, x, y, w, h, lines, group=None, badge=None, lane=None, dashed=False):
        self.id, self.kind, self.x, self.y, self.w, self.h = id, kind, x, y, w, h
        self.lines, self.group, self.badge, self.lane, self.dashed = lines, group, badge, lane, dashed

    @property
    def accent(self):
        if self.group in ("1", "2a", "2b"):
            return PAL[self.group]["stroke"]
        return PAL.get(self.kind, PAL["doc"])["stroke"]

    def colors(self):
        if self.kind in ("process", "manual"):
            return PAL[self.group]["fill"], PAL[self.group]["stroke"]
        if self.kind == "lane":
            return PAL[self.group]["lane_fill"], PAL[self.group]["lane_stroke"]
        p = PAL[self.kind]
        return p["fill"], p["stroke"]


class Edge(object):
    def __init__(self, src, s_side, s_t, dst, d_side, d_t, via=(), label=None, label_at=None, color=FLOW,
                 dashed=False, label_anchor="middle"):
        self.src, self.s_side, self.s_t, self.dst, self.d_side, self.d_t = src, s_side, s_t, dst, d_side, d_t
        self.via, self.label, self.label_at, self.color = list(via), label, label_at, color
        self.dashed, self.label_anchor = dashed, label_anchor


class Diagram(object):
    def __init__(self, key, W, H, title, subtitle, claim):
        self.key, self.W, self.H, self.title, self.subtitle, self.claim = key, W, H, title, subtitle, claim
        self.nodes, self.edges, self.dots, self.notes, self.legend_y = [], [], [], [], None
        self.dashed_meaning = "link to the rest of the seismic analysis"

    def node(self, *a, **k):
        n = Node(*a, **k)
        self.nodes.append(n)
        return n

    def get(self, id):
        return [n for n in self.nodes if n.id == id][0]

    def edge(self, *a, **k):
        self.edges.append(Edge(*a, **k))


def anchor(n, side, t):
    if side == "left":
        return (n.x, n.y + t * n.h)
    if side == "right":
        return (n.x + n.w, n.y + t * n.h)
    if side == "top":
        return (n.x + t * n.w, n.y)
    return (n.x + t * n.w, n.y + n.h - (6 if n.kind == "doc" else 0))


# =============================================================================
# The two diagrams
# =============================================================================
def overview():
    d = Diagram("overview", 1610, 650, "Post-processing module: Abaqus ODB files \u2192 section histories, images, pushover curves",
                "A_1_Export_Auto.py  \u00b7  A_2_Image_save_view.py  \u00b7  A_2_Image_export_Auto.py   (Abaqus/CAE or Viewer 2021)",
                "ODB files from the Abaqus analyses go in; A_1 writes the results database, A_2_Image_save_view stores "
                "the picture definitions, and A_2_Image_export_Auto turns both into images per frame and pushover curves.")
    R1, R2, R3, H = 110, 270, 430, 100
    d.node("from", "ext", 30, R1, 110, 420, [("tag", "FROM"), ("small", "previous steps"), ("gap", ""),
                                             ("body", "model with"), ("body", "cross-section"), ("body", "SETs"),
                                             ("gap", ""), ("body", "Abaqus/"), ("body", "Standard or"),
                                             ("body", "Explicit"), ("body", "analyses")])
    d.node("to", "ext", 1470, R1, 110, 420, [("tag", "TO"), ("small", "next steps"), ("gap", ""),
                                             ("body", "damage-state"), ("body", "identification"), ("gap", ""),
                                             ("body", "capacity"), ("body", "curves"), ("gap", ""),
                                             ("body", "drift, section"), ("body", "forces")])
    d.node("viewer", "manual", 180, R1, 170, H, [("title", "Abaqus/Viewer"), ("body", "the engineer sets up"),
                                                ("body", "each picture"), ("small", "(one ODB open)")], group="2a")
    d.node("odb", "doc", 180, R2, 170, H, [("title", "ODB files"), ("body", "one per job"),
                                          ("mono", "SHEAR_\u2026, BEND_\u2026")])
    d.node("s2a", "process", 400, R1, 260, H, [("script", "A_2_Image_save_view.py"), ("title", "Define the pictures"),
                                              ("body", "view, variable, frames,"), ("body", "contour limits, curves")],
           group="2a", badge="2a")
    d.node("s1", "process", 400, R3, 260, H, [("script", "A_1_Export_Auto.py"), ("title", "Section export"),
                                             ("body", "displacements, rotations and"),
                                             ("body", "forces of every SET and frame")], group="1", badge="1")
    d.node("cfg", "doc", 710, R1, 200, H, [("title", "Image settings"), ("mono", "2_Image_export_settings.json"),
                                          ("body", "views, variables, frames,"), ("body", "contour limits, curves")])
    d.node("db", "store", 710, R3, 200, H, [("title", "Results database"), ("mono", "Panel_results/<SET>/<JOB>/"),
                                           ("mono", "Section_data\u2026.txt")])
    d.node("s2b", "process", 960, R1, 220, R2 + H - R1,
           [("script", "A_2_Image_export_Auto.py"), ("title", "Image & curve export"), ("gap", ""),
            ("body", "every job \u00d7 view \u00d7"), ("body", "variable \u00d7 frame"), ("gap", ""),
            ("body", "curves from the results"), ("body", "database, image frames"), ("body", "marked on them")],
           group="2b", badge="2b")
    d.node("images", "doc", 1230, R1, 200, H, [("title", "Images per frame"), ("mono", "Panel_images/<JOB>/"),
                                              ("mono", "<variable>/<view>/"), ("mono", "f0012_t1.2.png")])
    d.node("curves", "doc", 1230, R2, 200, H, [("title", "Pushover curves"), ("mono", "_curve_<name>.png, .csv"),
                                              ("body", "image frames marked")])
    g = d.get
    ft = lambda n, y: (y - n.y) / float(n.h)
    d.edge("from", "right", ft(g("from"), 320), "odb", "left", 0.5)
    d.edge("viewer", "right", 0.5, "s2a", "left", 0.5, label="live view", label_at=(375, 151), color=PAL["2a"]["stroke"])
    d.edge("odb", "right", 0.5, "s1", "left", 0.5, via=[(375, 320), (375, 480)], label="reads",
           label_at=(381, 404), label_anchor="start")
    d.edge("odb", "right", 0.5, "s2b", "left", ft(g("s2b"), 320), label="reads every ODB file", label_at=(590, 311))
    d.edge("s2a", "right", 0.5, "cfg", "left", 0.5, label="writes", label_at=(685, 151))
    d.edge("s1", "right", 0.5, "db", "left", 0.5, label="writes", label_at=(685, 471))
    d.edge("cfg", "right", 0.5, "s2b", "left", ft(g("s2b"), 160), label="reads", label_at=(935, 151))
    d.edge("db", "top", 0.5, "s2b", "bottom", 0.5, via=[(810, 400), (1070, 400)], label="reads (curves)",
           label_at=(940, 391))
    d.edge("db", "right", 0.5, "to", "left", ft(g("to"), 480), label="section histories: Ux \u2026 Mz vs time",
           label_at=(1190, 471))
    d.edge("s2b", "right", ft(g("s2b"), 160), "images", "left", 0.5, label="PNG", label_at=(1205, 151))
    d.edge("s2b", "right", ft(g("s2b"), 320), "curves", "left", 0.5)
    d.edge("images", "right", 0.5, "to", "left", ft(g("to"), 160))
    d.edge("curves", "right", 0.5, "to", "left", ft(g("to"), 320))
    d.dots.append((375, 320))
    d.legend_y = 572
    d.notes.append("Order: 1 and 2a in any order (the curve lists of 2a come from the results database of 1), then 2b.")
    return d


def detailed():
    d = Diagram("detailed", 1650, 880, "Post-processing with the A_ scripts \u2014 detailed flow",
                "what each script does, step by step, and which data it reads and writes",
                "Step-by-step flow of the three A_ scripts: A_2_Image_save_view defines the pictures, A_1_Export_Auto "
                "exports section displacements and forces, A_2_Image_export_Auto prints the images and draws the curves.")
    a, b, c = PAL["2a"]["stroke"], PAL["1"]["stroke"], PAL["2b"]["stroke"]
    # lanes
    d.node("lane2a", "lane", 240, 90, 660, 200, [("script", "A_2_Image_save_view.py"), ("title", "define the pictures"),
                                                 ("small", "interactive in Abaqus/Viewer: File > Run Script, or Plug-ins > "
                                                           "Image export > Save current view \u2014 once per picture")],
           group="2a", badge="2a")
    d.node("lane1", "lane", 240, 360, 660, 370, [("script", "A_1_Export_Auto.py"), ("title", "section displacements and forces"),
                                                 ("small", "File > Run Script, or  abaqus cae noGUI=A_1_Export_Auto.py;"
                                                           "  progress in 1_Export_Auto_log.txt")],
           group="1", badge="1")
    d.node("lane2b", "lane", 1170, 90, 250, 705, [("script", "A_2_Image_export_Auto.py"),
                                                  ("small", "images and curves, every job")], group="2b", badge="2b")
    # inputs
    d.node("viewer", "manual", 30, 150, 170, 112, [("title", "Abaqus/Viewer"), ("body", "one ODB open; the"),
                                                  ("body", "engineer sets up"), ("body", "each picture")], group="2a")
    d.node("odb", "doc", 30, 281, 170, 80, [("title", "ODB files"), ("body", "one per job"),
                                           ("small", "(from the analyses)")])
    # lane 2a steps
    xs = [250, 414, 578, 742]
    d.node("a1", "process", xs[0], 150, 148, 112, [("title", "Set up the picture"), ("body", "camera, section cut"),
                                                   ("body", "display group"), ("body", "contour type & limits"),
                                                   ("body", "edges, legend, variable")], group="2a", lane="lane2a")
    d.node("a2", "process", xs[1], 150, 148, 112, [("title", "Run the script"), ("mono", "view__variable"),
                                                   ("body", "frames of the view"), ("body", "contour limits"),
                                                   ("body", "curves: edit / on / off")], group="2a", lane="lane2a")
    d.node("a3", "process", xs[2], 150, 148, 112, [("title", "Snapshot"), ("body", "read from the live"),
                                                   ("body", "session; display group"), ("body", "from abaqus.rpy;"),
                                                   ("body", "checked in Abaqus")], group="2a", lane="lane2a")
    d.node("a4", "process", xs[3], 150, 148, 112, [("title", "Curve dialog"), ("body", "sections, variables"),
                                                   ("small", "(from results database)"),
                                                   ("body", "A\u2212B, A+B, A\u00d7B, A\u00f7B"),
                                                   ("body", "factor, label, jobs")], group="2a", lane="lane2a",
           dashed=True)
    # lane 1 steps (two rows)
    xs = [250, 470, 690]
    d.node("b1", "process", xs[0], 420, 200, 120, [("title", "Settings"), ("body", "dialog, or remembered in"),
                                                   ("mono", "1_Export_Auto_settings.json"),
                                                   ("body", "ODB files, step, database,"), ("body", "SET filter, methods")],
           group="1", lane="lane1")
    d.node("b2", "process", xs[1], 420, 200, 120, [("title", "Each ODB"), ("body", "opened (or reused if open)"),
                                                   ("body", "Implicit / Explicit detected"),
                                                   ("body", "last step (or chosen)"),
                                                   ("body", "frames: all, or \u0394t \u2265 minimum")],
           group="1", lane="lane1")
    d.node("b3", "process", xs[2], 420, 200, 120, [("title", "Each SET"), ("mono", "TYPE&LABEL&INDEX&ANGLE"),
                                                   ("body", "\u2192 volume, shell or point"),
                                                   ("body", "section (V_PIER, S_PIER \u2026)"),
                                                   ("body", "exported before \u2192 skipped")], group="1", lane="lane1")
    d.node("b4", "process", xs[0], 600, 200, 120, [("title", "Displacements, rotations"), ("body", "in section axes:"),
                                                   ("body", "rigid-body fit | angle | slope"),
                                                   ("mono", "Ux Uy Uz   fix fiy fiz"), ("body", "relative or absolute")],
           group="1", lane="lane1")
    d.node("b5", "process", xs[1], 600, 200, 120, [("title", "Forces"), ("body", "in the section csys:"),
                                                   ("body", "free-body cut | NFORC sum"),
                                                   ("mono", "Fx Fy Fz   Mx My Mz"), ("small", "(NFORC: area-weighted centre)")],
           group="1", lane="lane1")
    d.node("b6", "process", xs[2], 600, 200, 120, [("title", "Write the table"), ("body", "rows matched by"),
                                                   ("body", "frame position (index)"),
                                                   ("body", "one table per SET & job"),
                                                   ("body", "centre, size, .inp copy")], group="1", lane="lane1")
    # stores
    d.node("cfg", "doc", 940, 150, 190, 118, [("title", "Image settings"), ("mono", "2_Image_export_settings.json"),
                                             ("body", "views, variables, frames,"), ("body", "contour limits, curves"),
                                             ("small", "+ preview PNGs")])
    d.node("db", "store", 940, 596, 190, 128, [("title", "Results database"), ("mono", "Panel_results/"),
                                              ("mono", "<SET>/<JOB>/"), ("mono", "Section_data\u2026.txt"),
                                              ("small", "+ Attributes.json, .inp")])
    # lane 2b steps
    X = 1185
    d.node("c1", "process", X, 160, 220, 90, [("title", "Load the settings"), ("body", "latest change wins;"),
                                              ("body", "frames & limits checked")], group="2b", lane="lane2b")
    d.node("c2", "process", X, 281, 220, 80, [("title", "Each ODB"), ("body", "frames per view"),
                                              ("small", "(+ frames around the peak)")], group="2b", lane="lane2b")
    d.node("c3", "process", X, 395, 220, 150, [("title", "Each frame \u00d7 variable \u00d7 view"),
                                               ("body", "start values restored"), ("body", "view replayed: camera,"),
                                               ("body", "cuts, display group"), ("body", "variable + contour limits"),
                                               ("body", "PNG printed")], group="2b", lane="lane2b")
    d.node("c4", "process", X, 615, 220, 90, [("title", "Curves"), ("body", "results database read"),
                                              ("body", "X, Y of the sections"), ("body", "image frames marked")],
           group="2b", lane="lane2b")
    d.node("c5", "process", X, 730, 220, 50, [("title", "Finish"), ("body", "optional ZIP per job")],
           group="2b", lane="lane2b")
    # outputs
    d.node("images", "doc", 1460, 418, 160, 104, [("title", "Images"), ("mono", "Panel_images/"),
                                                 ("mono", "<JOB>/<var>/<view>/"), ("mono", "f0012_t1.2.png")])
    d.node("curves", "doc", 1460, 615, 160, 90, [("title", "Curves"), ("mono", "_curve_<name>.png"),
                                                ("mono", "_curve_<name>.csv")])
    d.node("logs", "doc", 1460, 723, 160, 64, [("title", "Log"), ("mono", "2_Image_export_log.txt")])  # centre = Finish
    g = d.get
    ft = lambda n, y: (y - n.y) / float(n.h)
    # lane 2a
    d.edge("viewer", "right", 0.5, "a1", "left", 0.5, label="live view", label_at=(225, 197), color=a)
    for s, t in (("a1", "a2"), ("a2", "a3"), ("a3", "a4")):
        d.edge(s, "right", 0.5, t, "left", 0.5, color=a)
    d.edge("a4", "right", 0.5, "cfg", "left", ft(g("cfg"), 206), label="writes", label_at=(919, 197))
    # lane 1
    d.edge("odb", "right", 0.5, "b1", "left", 0.5, via=[(220, 321), (220, 480)])
    d.edge("b1", "right", 0.5, "b2", "left", 0.5, color=b)
    d.edge("b2", "right", 0.5, "b3", "left", 0.5, color=b)
    d.edge("b3", "bottom", 0.5, "b4", "top", 0.5, via=[(790, 570), (350, 570)], color=b)
    d.edge("b4", "right", 0.5, "b5", "left", 0.5, color=b)
    d.edge("b5", "right", 0.5, "b6", "left", 0.5, color=b)
    d.edge("b6", "right", 0.5, "db", "left", ft(g("db"), 660), label="writes", label_at=(919, 651))
    # lane 2b
    d.edge("cfg", "right", ft(g("cfg"), 205), "c1", "left", 0.5, label="reads", label_at=(1157, 196))
    d.edge("odb", "right", 0.5, "c2", "left", 0.5, label="reads every ODB file", label_at=(580, 312))
    d.edge("db", "right", ft(g("db"), 660), "c4", "left", 0.5, label="reads", label_at=(1157, 651))
    for s, t in (("c1", "c2"), ("c2", "c3"), ("c3", "c4"), ("c4", "c5")):
        d.edge(s, "bottom", 0.5, t, "top", 0.5, color=c)
    d.edge("c3", "right", 0.5, "images", "left", 0.5, label="PNG", label_at=(1432, 461))
    d.edge("c4", "right", 0.5, "curves", "left", 0.5)
    d.edge("c5", "right", 0.5, "logs", "left", 0.5)
    d.dots.append((220, 321))
    d.notes.append("Alternatives to 2a: MODE = \"capture\" in A_2_Image_export_Auto.py (pictures printed in Abaqus, "
                   "read from abaqus.rpy), or VIEWS / VARIABLES edited in the script.")
    d.notes.append("Order: 1 \u2192 2a \u2192 2b.  2a needs 1 only for the curve lists; 2b needs the settings of 2a "
                   "and, for the curves, the results database of 1.")
    d.legend_y = 812
    d.dashed_meaning = "optional step"
    return d


# =============================================================================
# SVG
# =============================================================================
def marker_id(color):
    return "ah" + color.lstrip("#")


def text_lines_height(lines):
    return sum(ST[s][4] for s, _ in lines)


def svg_text(x, y, text, style, color=None, anchor="middle", extra=""):
    fam, bold, size, col, _ = ST[style]
    return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f"%s fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, SANS if fam == "sans" else MONO, size, ' font-weight="bold"' if bold else "",
               color or col or "#0f172a", anchor, extra, esc(text)))


def badge_svg(x, y, text, color):
    """Pill with white text; (x, y) = top-left. Returns (svg, width)."""
    w = text_width(text, "sans", True, 11.0) + 14
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="19" rx="9.5" fill="%s"/>' % (x, y, w, color) +
            svg_text(x + w / 2, y + 13.6, text, "tag", color="#ffffff")), w


WARN = []


def check_width(diag, node, text, style, avail):
    fam, bold, size, _, _ = ST[style]
    w = text_width(text, fam, bold, size)
    if w > avail + 0.5:
        WARN.append("%s/%s: '%s' is %.0f px, %.0f px available" % (diag.key, node.id, text, w, avail))
    return w


def node_svg(diag, n):
    out = []
    fill, stroke = n.colors()
    dash = ' stroke-dasharray="6 4"' if (n.kind == "ext" or n.dashed) else ""
    x, y, w, h = n.x, n.y, n.w, n.h
    if n.kind in ("process", "manual"):
        out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="9" fill="%s" stroke="%s" stroke-width="1.6"%s/>'
                   % (x, y, w, h, fill, stroke, dash))
    elif n.kind == "ext":
        out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="%s" stroke="%s" stroke-width="1.5"%s/>'
                   % (x, y, w, h, fill, stroke, dash))
    elif n.kind == "lane":
        out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="%s" stroke="%s" stroke-width="1.3"/>'
                   % (x, y, w, h, fill, stroke))
    elif n.kind == "doc":
        dd = 7.0
        out.append('<path d="M %d %d H %d V %.1f Q %.1f %.1f %.1f %.1f T %d %.1f Z" fill="%s" stroke="%s" '
                   'stroke-width="1.5"/>' % (x, y, x + w, y + h - dd, x + 0.75 * w, y + h - 2.6 * dd, x + 0.5 * w,
                                             y + h - dd, x, y + h - dd, fill, stroke))
    elif n.kind == "store":
        ry = 9.0
        out.append('<path d="M %d %.1f A %.1f %.1f 0 0 1 %d %.1f V %.1f A %.1f %.1f 0 0 1 %d %.1f Z" fill="%s" '
                   'stroke="%s" stroke-width="1.5"/>' % (x, y + ry, w / 2.0, ry, x + w, y + ry, y + h - ry,
                                                         w / 2.0, ry, x, y + h - ry, fill, stroke))
        out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" stroke="%s" stroke-width="1.5"/>'
                   % (x + w / 2.0, y + ry, w / 2.0, ry, "#e2e8f0", stroke))
    if n.kind == "manual":   # person glyph = a manual step
        cx, cy = x + 15, y + 14
        out.append('<circle cx="%.1f" cy="%.1f" r="4.2" fill="%s"/>' % (cx, cy, stroke))
        out.append('<path d="M %.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f Z" fill="%s"/>'
                   % (cx - 7.5, cy + 15, cx - 7.5, cy + 4.5, cx + 7.5, cy + 4.5, cx + 7.5, cy + 15, stroke))

    if n.kind == "lane":
        bx, by = x + 14, y + 12
        bsvg, bw = badge_svg(bx, by, n.badge, PAL[n.group]["stroke"])
        out.append(bsvg)
        tx = bx + bw + 9
        sc = [l for l in n.lines if l[0] == "script"][0][1]
        ti = [l for l in n.lines if l[0] == "title"]
        avail = w - (tx - x) - 14
        sw = check_width(diag, n, sc, "script", avail)
        parts = svg_text(tx, by + 14.5, sc, "script", color=PAL[n.group]["stroke"], anchor="start")
        out.append(parts)
        if ti:
            t = "\u2014  " + ti[0][1]
            check_width(diag, n, sc + "   " + t, "title", avail)
            out.append(svg_text(tx + sw + 10, by + 14.5, t, "title", anchor="start"))
        ly = by + 38
        for s, t in n.lines:
            if s == "small":
                check_width(diag, n, t, "small", w - 28)
                out.append(svg_text(x + 14, ly, t, "small", anchor="start"))
                ly += ST["small"][4]
        return "\n".join(out)

    # text block
    lines = n.lines
    top, bottom = y + 6, y + h - 6
    if n.kind == "doc":
        bottom = y + h - 10
    if n.kind == "store":
        top = y + 18
    if n.kind == "manual":
        top = y + 4
    total = text_lines_height(lines)
    cy = top + (bottom - top - total) / 2.0
    cx = x + w / 2.0
    avail = w - 16
    for i, (s, t) in enumerate(lines):
        lh = ST[s][4]
        base = cy + lh * 0.78
        if s == "gap":
            cy += lh
            continue
        if i == 0 and n.badge and s == "script":
            sw = text_width(t, "mono", True, ST["script"][2])
            bw = text_width(n.badge, "sans", True, 11.0) + 14
            total_w = bw + 7 + sw
            if total_w > avail:
                WARN.append("%s/%s: badge + '%s' is %.0f px, %.0f available" % (diag.key, n.id, t, total_w, avail))
            sx = cx - total_w / 2.0
            bsvg, _ = badge_svg(sx, base - 13.8, n.badge, n.accent)
            out.append(bsvg)
            out.append(svg_text(sx + bw + 7, base, t, s, color=n.accent, anchor="start"))
        else:
            check_width(diag, n, t, s, avail)
            out.append(svg_text(cx, base, t, s, color=(n.accent if s == "script" else None)))
        cy += lh
    if n.kind == "process" and n.dashed:
        out.append(svg_text(x + w - 8, y + 13, "optional", "small", anchor="end", extra=' font-style="italic"'))
    return "\n".join(out)


def path_d(pts, r=7.0):
    d = "M %.1f %.1f" % pts[0]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1, l2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        rr = min(r, l1 / 2.0, l2 / 2.0)
        ax, ay = x1 - (x1 - x0) / l1 * rr, y1 - (y1 - y0) / l1 * rr
        bx, by = x1 + (x2 - x1) / l2 * rr, y1 + (y2 - y1) / l2 * rr
        d += " L %.1f %.1f Q %.1f %.1f %.1f %.1f" % (ax, ay, x1, y1, bx, by)
    d += " L %.1f %.1f" % pts[-1]
    return d


def edge_points(diag, e):
    s, t = diag.get(e.src), diag.get(e.dst)
    return [anchor(s, e.s_side, e.s_t)] + e.via + [anchor(t, e.d_side, e.d_t)]


def label_svg(x, y, text, anchor="middle"):
    w = text_width(text, "sans", False, 10.5) + 8
    lx = x - w / 2.0 if anchor == "middle" else x - 4
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="15" rx="3" fill="#ffffff" fill-opacity="0.94"/>'
            % (lx, y - 11.5, w)) + svg_text(x if anchor == "middle" else x, y, text, "small",
                                             color="#475569", anchor=anchor)


def legend_svg(diag):
    y = diag.legend_y
    items = []
    x = 30
    out = []

    def add_text(t, xx):
        out.append(svg_text(xx, y + 4, t, "body", color="#475569", anchor="start"))
        return text_width(t, "sans", False, 11.5)

    for grp, txt in (("1", "1  section export"), ("2a", "2a  picture definition"), ("2b", "2b  image & curve export")):
        out.append('<rect x="%d" y="%d" width="26" height="16" rx="5" fill="%s" stroke="%s" stroke-width="1.5"/>'
                   % (x, y - 8, PAL[grp]["fill"], PAL[grp]["stroke"]))
        x += 33 + add_text(txt, x + 33) + 24
    # manual
    out.append('<rect x="%d" y="%d" width="26" height="16" rx="5" fill="%s" stroke="%s" stroke-width="1.5"/>'
               % (x, y - 8, PAL["2a"]["fill"], PAL["2a"]["stroke"]))
    out.append('<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s"/>' % (x + 13, y - 2.5, PAL["2a"]["stroke"]))
    out.append('<path d="M %.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f Z" fill="%s"/>'
               % (x + 8.5, y + 6, x + 8.5, y + 0.5, x + 17.5, y + 0.5, x + 17.5, y + 6, PAL["2a"]["stroke"]))
    x += 33 + add_text("manual step", x + 33) + 24
    # document
    out.append('<path d="M %d %d H %d V %d Q %.1f %.1f %.1f %d T %d %d Z" fill="#fff" stroke="#475569" '
               'stroke-width="1.4"/>' % (x, y - 9, x + 24, y + 5, x + 18, y + 1, x + 12, y + 5, x, y + 5))
    x += 31 + add_text("file / folder", x + 31) + 24
    # store
    out.append('<path d="M %d %d A 12 4 0 0 1 %d %d V %d A 12 4 0 0 1 %d %d Z" fill="#f1f5f9" stroke="#475569" '
               'stroke-width="1.4"/>' % (x, y - 6, x + 24, y - 6, y + 6, x, y + 6))
    out.append('<ellipse cx="%d" cy="%d" rx="12" ry="4" fill="#e2e8f0" stroke="#475569" stroke-width="1.4"/>'
               % (x + 12, y - 6))
    x += 31 + add_text("results database", x + 31) + 24
    # external
    out.append('<rect x="%d" y="%d" width="26" height="16" rx="5" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.4" '
               'stroke-dasharray="4 3"/>' % (x, y - 8))
    x += 33 + add_text(diag.dashed_meaning, x + 33) + 24
    if x > diag.W - 20:
        WARN.append("%s: legend %d px wider than the figure" % (diag.key, x - diag.W))
    ny = y + 26
    for t in diag.notes:
        check_width(diag, Node("note", "x", 0, 0, diag.W - 60, 0, []), t, "small", diag.W - 60)
        out.append(svg_text(30, ny, t, "small", anchor="start"))
        ny += 16
    return "\n".join(out)


def svg(diag, standalone=True):
    colors = sorted(set([e.color for e in diag.edges]))
    defs = ["<defs>"]
    for c in colors:
        defs.append('<marker id="%s" viewBox="0 0 10 10" refX="9.2" refY="5" markerWidth="7.5" markerHeight="7.5" '
                    'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M 0 0.6 L 10 5 L 0 9.4 Z" '
                    'fill="%s"/></marker>' % (marker_id(c), c))
    defs.append("</defs>")
    body = ['<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>' % (diag.W, diag.H)]
    body.append(svg_text(30, 42, diag.title, "title", anchor="start", extra=' font-size="20"').replace(
        'font-size="13.0"', ""))
    body.append(svg_text(30, 66, diag.subtitle, "body", color="#64748b", anchor="start"))
    check_width(diag, Node("title", "x", 0, 0, diag.W, 0, []), diag.title, "title", (diag.W - 60) / (20 / 13.0))
    for n in [n for n in diag.nodes if n.kind == "lane"]:
        body.append(node_svg(diag, n))
    for e in diag.edges:
        pts = edge_points(diag, e)
        dash = ' stroke-dasharray="5 4"' if e.dashed else ""
        body.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.6"%s marker-end="url(#%s)"/>'
                    % (path_d(pts), e.color, dash, marker_id(e.color)))
    for (x, y) in diag.dots:
        body.append('<circle cx="%.1f" cy="%.1f" r="3.6" fill="%s"/>' % (x, y, FLOW))
    for n in [n for n in diag.nodes if n.kind != "lane"]:
        body.append(node_svg(diag, n))
    for e in diag.edges:
        if e.label:
            body.append(label_svg(e.label_at[0], e.label_at[1], e.label, e.label_anchor))
    if diag.legend_y:
        body.append(legend_svg(diag))
    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"%s role="img" aria-label=%s>'
            % (diag.W, diag.H, ' width="%d" height="%d"' % (diag.W, diag.H) if standalone else "",
               quoteattr(diag.claim)))
    meta = "<title>%s</title><desc>%s</desc>" % (esc(diag.title), esc(diag.claim))
    s = head + meta + "\n".join(defs) + "\n" + "\n".join(body) + "\n</svg>\n"
    if standalone:
        s = '<?xml version="1.0" encoding="UTF-8"?>\n' + s
    return s


# =============================================================================
# draw.io (editable)
# =============================================================================
def drawio_html(lines, accent, badge=None):
    parts = []
    for i, (s, t) in enumerate(lines):
        if s == "gap":
            parts.append('<span style="font-size:4px"> </span>')
            continue
        tt = esc(t)
        if s == "script":
            b = ('<span style="background:%s;color:#fff;border-radius:8px;padding:0 5px;font-family:Helvetica;'
                 'font-size:10px">%s</span> ' % (accent, esc(badge))) if badge else ""
            parts.append('%s<b><font face="Consolas" color="%s" style="font-size:12px">%s</font></b>' % (b, accent, tt))
        elif s == "title":
            parts.append('<b><font color="#0f172a" style="font-size:13px">%s</font></b>' % tt)
        elif s == "mono":
            parts.append('<font face="Consolas" style="font-size:10.5px">%s</font>' % tt)
        elif s == "small":
            parts.append('<font color="#64748b" style="font-size:10.5px">%s</font>' % tt)
        elif s == "tag":
            parts.append('<b><font color="#475569">%s</font></b>' % tt)
        else:
            parts.append(tt)
    return "<br>".join(parts)


def drawio_diagram(diag, page_id):
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    nid = {}
    base = "fontFamily=Segoe UI;fontSize=11;fontColor=#334155;html=1;whiteSpace=wrap;"
    cells.append('<mxCell id="%s-title" value=%s style="text;html=1;align=left;verticalAlign=top;fontFamily=Segoe UI;'
                 'fontColor=#0f172a;" vertex="1" parent="1"><mxGeometry x="20" y="18" width="%d" height="56" '
                 'as="geometry"/></mxCell>' % (page_id, quoteattr('<b style="font-size:20px">%s</b><br>'
                                                                  '<font color="#64748b" style="font-size:12px">%s</font>'
                                                                  % (esc(diag.title), esc(diag.subtitle))), diag.W - 40))
    for n in diag.nodes:
        cid = "%s-%s" % (page_id, n.id)
        nid[n.id] = cid
        fill, stroke = n.colors()
        if n.kind == "lane":
            sc = [l for l in n.lines if l[0] == "script"][0][1]
            ti = [l[1] for l in n.lines if l[0] == "title"]
            sm = [l[1] for l in n.lines if l[0] == "small"]
            val = ('<span style="background:%s;color:#fff;border-radius:8px;padding:1px 6px">%s</span>&nbsp; '
                   '<b><font face="Consolas" color="%s">%s</font></b>%s%s'
                   % (PAL[n.group]["stroke"], esc(n.badge), PAL[n.group]["stroke"], esc(sc),
                      (" <b>&mdash; %s</b>" % esc(ti[0])) if ti else "",
                      "".join('<br><font color="#64748b" style="font-size:10.5px">%s</font>' % esc(t) for t in sm)))
            style = (base + "rounded=1;arcSize=3;absoluteArcSize=1;fillColor=%s;strokeColor=%s;verticalAlign=top;"
                     "align=left;spacingLeft=12;spacingTop=6;fontSize=13;container=1;collapsible=0;recursiveResize=0;"
                     % (fill, stroke))
        else:
            val = drawio_html(n.lines, n.accent, n.badge)
            if n.kind in ("process", "manual"):
                style = base + "rounded=1;arcSize=8;fillColor=%s;strokeColor=%s;strokeWidth=1.6;" % (fill, stroke)
                if n.dashed:
                    style += "dashed=1;dashPattern=6 4;"
                if n.kind == "manual":
                    val = '<font color="%s">&#9679;</font> ' % stroke + val
            elif n.kind == "doc":
                style = base + "shape=document;boundedLbl=1;size=0.1;fillColor=%s;strokeColor=%s;strokeWidth=1.5;" % (fill, stroke)
            elif n.kind == "store":
                style = (base + "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=9;fillColor=%s;strokeColor=%s;"
                         "strokeWidth=1.5;" % (fill, stroke))
            else:  # ext
                style = (base + "rounded=1;arcSize=8;dashed=1;dashPattern=6 4;fillColor=%s;strokeColor=%s;"
                         "strokeWidth=1.5;" % (fill, stroke))
        parent, px, py = "1", 0, 0
        if n.lane:
            lane = diag.get(n.lane)
            parent, px, py = nid[n.lane], lane.x, lane.y
        cells.append('<mxCell id="%s" value=%s style=%s vertex="1" parent="%s"><mxGeometry x="%d" y="%d" width="%d" '
                     'height="%d" as="geometry"/></mxCell>' % (cid, quoteattr(val), quoteattr(style), parent,
                                                               n.x - px, n.y - py, n.w, n.h))
    side_xy = {"left": (0, None), "right": (1, None), "top": (None, 0), "bottom": (None, 1)}
    for i, e in enumerate(diag.edges):
        def xy(side, t):
            a, b = side_xy[side]
            return (a if a is not None else t), (b if b is not None else t)
        ex, ey = xy(e.s_side, e.s_t)
        nx, ny = xy(e.d_side, e.d_t)
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;endSize=7;strokeWidth=1.6;"
                 "strokeColor=%s;exitX=%.4f;exitY=%.4f;exitDx=0;exitDy=0;entryX=%.4f;entryY=%.4f;entryDx=0;entryDy=0;"
                 "fontFamily=Segoe UI;fontSize=10.5;fontColor=#475569;labelBackgroundColor=#ffffff;"
                 % (e.color, ex, ey, nx, ny))
        pts = "".join('<mxPoint x="%.1f" y="%.1f"/>' % p for p in e.via)
        cells.append('<mxCell id="%s-e%d" value=%s style=%s edge="1" parent="1" source="%s" target="%s">'
                     '<mxGeometry relative="1" as="geometry">%s</mxGeometry></mxCell>'
                     % (page_id, i, quoteattr(e.label or ""), quoteattr(style), nid[e.src], nid[e.dst],
                        ('<Array as="points">%s</Array>' % pts) if pts else ""))
    if diag.notes or diag.legend_y:
        txt = ("<b>Colours:</b> blue = 1 section export, amber = 2a picture definition (manual steps marked &#9679;), "
               "green = 2b image &amp; curve export; cylinder = results database; wavy box = file / folder; "
               "dashed = link to the rest of the seismic analysis or optional step.<br>" +
               "<br>".join(esc(t) for t in diag.notes))
        cells.append('<mxCell id="%s-legend" value=%s style="text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;'
                     'fontFamily=Segoe UI;fontSize=11;fontColor=#475569;" vertex="1" parent="1"><mxGeometry x="30" '
                     'y="%d" width="%d" height="60" as="geometry"/></mxCell>'
                     % (page_id, quoteattr(txt), diag.legend_y - 10, diag.W - 60))
    return ('<diagram id="%s" name="%s"><mxGraphModel dx="%d" dy="%d" grid="1" gridSize="10" guides="1" tooltips="1" '
            'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="%d" pageHeight="%d" math="0" shadow="0">'
            '<root>%s</root></mxGraphModel></diagram>'
            % (page_id, page_id.capitalize(), diag.W, diag.H, diag.W, diag.H + 40, "".join(cells)))


def drawio_file(diagrams):
    return ('<mxfile host="Electron" modified="%s" agent="flowchart generator" version="24.0.0">%s</mxfile>\n'
            % (TODAY.isoformat(), "".join(drawio_diagram(d, d.key) for d in diagrams)))


# =============================================================================
# HTML report
# =============================================================================
def report_html(ov, de):
    p = lambda name: BASE + name
    css = """
:root{--ink:#0f172a;--text:#334155;--muted:#64748b;--line:#e2e8f0;--soft:#f8fafc;
--c1:#1d4ed8;--c1f:#eff6ff;--c2a:#b45309;--c2af:#fff8eb;--c2b:#047857;--c2bf:#ecfdf5}
*{box-sizing:border-box}
html{background:#eef2f6}
body{margin:0;font-family:'Segoe UI',Arial,Helvetica,sans-serif;color:var(--text);font-size:14px;line-height:1.5;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheet{max-width:1180px;margin:24px auto;background:#fff;border-radius:14px;padding:30px 36px;
box-shadow:0 1px 3px rgba(15,23,42,.08)}
h1{font-size:25px;line-height:1.25;color:var(--ink);margin:0 0 4px}
h2{font-size:18px;color:var(--ink);margin:26px 0 10px}
.sub{font-size:15px;color:var(--muted);margin:0}
.meta{font-size:12px;color:var(--muted);margin:8px 0 0}
figure{margin:16px 0 6px;border:1px solid var(--line);border-radius:10px;padding:10px;background:#fff}
figure svg{display:block;width:100%;height:auto}
figcaption{font-size:12.5px;color:var(--muted);margin:8px 2px 0}
.links{font-size:12px;color:var(--muted);margin:4px 2px 0}
.links a{color:var(--c1)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:16px}
.card{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--soft)}
.card h3{margin:0 0 6px;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.card p{margin:0;font-size:13px}
.b{display:inline-block;min-width:24px;padding:0 7px;border-radius:9px;color:#fff;font-weight:700;font-size:11.5px;
text-align:center;line-height:18px}
.b1{background:var(--c1)}.b2a{background:var(--c2a)}.b2b{background:var(--c2b)}
code,.mono{font-family:Consolas,'Courier New',monospace;font-size:12.5px}
code{background:#f1f5f9;border-radius:4px;padding:0 4px}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
th{background:#f1f5f9;color:var(--ink);font-weight:600}
tr{break-inside:avoid}
.two{display:grid;grid-template-columns:1.25fr 1fr;gap:20px}
pre{font-family:Consolas,'Courier New',monospace;font-size:12px;background:var(--soft);border:1px solid var(--line);
border-radius:8px;padding:10px 12px;margin:0;line-height:1.45;white-space:pre}
.note{border-left:3px solid var(--c1);background:var(--c1f);padding:9px 12px;border-radius:0 8px 8px 0;font-size:13px}
footer{margin-top:22px;font-size:11.5px;color:var(--muted)}
@page{size:A4 landscape;margin:9mm 10mm}
@media print{html{background:#fff}.sheet{margin:0;max-width:none;box-shadow:none;border-radius:0;padding:0}
.page{break-after:page}.links{display:none}h2{margin-top:6px}body{font-size:11.5px}
figure{padding:6px}table{font-size:10.3px;line-height:1.38}th,td{padding:4px 6px}pre{font-size:9.8px;line-height:1.35;
padding:7px 10px}.card p{font-size:11.3px}code,.mono{font-size:10.2px}code{padding:0 3px}
.two{margin-top:10px!important;gap:16px}h2{font-size:15px;margin:2px 0 6px}.note{font-size:11px;padding:6px 10px}
footer{margin-top:8px}.detail figure{margin-top:4px}}
"""
    ov_svg, de_svg = svg(ov, standalone=False), svg(de, standalone=False)
    links = lambda key: ('<p class="links">Open separately: <a href="%s_%s.svg">SVG</a> \u00b7 <a href="%s_%s.png">PNG</a>'
                         ' \u00b7 <a href="%s_%s.pdf">PDF</a> \u00b7 editable: <a href="%s.vsdx">Visio</a>,'
                         ' <a href="%s.drawio">draw.io</a></p>' % (BASE, key, BASE, key, BASE, key, BASE, BASE))
    steps = [
        ("b1", "1", "A_1_Export_Auto.py", "File &gt; Run Script (or <code>abaqus cae noGUI=A_1_Export_Auto.py</code>); "
         "settings dialog first",
         "ODB files of the folder; <code>1_Export_Auto_settings.json</code> (last settings)",
         "Per ODB: Implicit/Explicit detected, last step, frames (all, or a minimum time step). Per cross-section SET: "
         "section type from the name; displacements and rotations in the section axes (rigid-body fit, angle or slope; "
         "relative or absolute); forces in the section csys (Abaqus free-body cut or NFORC summation); rows matched by "
         "frame position.",
         "<code>Panel_results/&lt;SET&gt;/&lt;JOB&gt;/Section_data\u2026.txt</code>, <code>Attributes.json</code>, "
         "<code>.inp</code> copy, job list; settings and log file"),
        ("b2a", "2a", "A_2_Image_save_view.py", "in Abaqus/Viewer with the picture set up: File &gt; Run Script, or "
         "Plug-ins &gt; Image export &gt; Save current view",
         "the live Viewer session; <code>abaqus.rpy</code> (display group); results database (curve lists)",
         "Snapshot of the picture: camera, section cuts, display group, contour type and limits, edges, legend, "
         "variable. Frames and contour limits per view; curve definitions (section variables, A\u2212B, A+B, A\u00d7B, "
         "A\u00f7B, factor) in a dialog with drop-down lists.",
         "<code>2_Image_export_settings.json</code>; previews in <code>Panel_images/_view_previews</code>"),
        ("b2b", "2b", "A_2_Image_export_Auto.py", "File &gt; Run Script (MODE = \"export\")",
         "ODB files; <code>2_Image_export_settings.json</code>; results database (curves)",
         "Per ODB: frames per view (evenly spread, all, every n-th, frame numbers, times; optionally frames around the "
         "peak). Per frame \u00d7 variable \u00d7 view: start values restored, view replayed, variable and contour limits "
         "set, PNG printed. Curves of the job with the image frames marked. Optional ZIP per job.",
         "<code>Panel_images/&lt;JOB&gt;/&lt;variable&gt;/&lt;view&gt;/f0012_t1.2.png</code>, "
         "<code>_curve_&lt;name&gt;.png / .csv</code>; settings and log file"),
    ]
    rows = "".join("<tr><td><span class='b %s'>%s</span></td><td><b class='mono'>%s</b><br>%s</td><td>%s</td><td>%s</td>"
                   "<td>%s</td></tr>" % s for s in steps)
    types = [("V_PIER, V_SPEC", "volume (solid elements)", "pier", "yes"),
             ("S_PIER", "shell (line of nodes)", "pier", "yes"),
             ("V_SPANDREL", "volume", "spandrel", "yes"),
             ("S_SPANDREL", "shell", "spandrel", "yes"),
             ("S_DRIFT", "point (nodal average)", "global axes", "no"),
             ("SRIFT", "volume", "pier", "no")]
    trows = "".join("<tr><td class='mono'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % t for t in types)
    tree = esc("""Panel_results/                         results database  (A_1_Export_Auto.py)
  baza sadzaj liste.txt                SET names and exported jobs
  <SET>/Attributes.json                section centre and dimensions
  <SET>/<JOB>/Section_dataIIII<SET>IIII<JOB>.txt
        Time, frameId, Ux, Uy, Uz, fix, fiy, fiz, Fx, Fy, Fz, Mx, My, Mz
  <SET>/<JOB>/<job>.inp                copy of the input file

Panel_images/                          images  (A_2_Image_export_Auto.py)
  <JOB>/<variable>/<view>/f0012_t1.2.png      frame 12, step time 1.2
  <JOB>/_curve_<name>.png  and  .csv          curve, image frames marked
  _view_previews/                             previews  (A_2_Image_save_view.py)""")
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Post-processing flowchart</title>
<style>%s</style></head>
<body><main class="sheet">
<section class="page">
<h1>Post-processing of Abaqus results with the A_ scripts</h1>
<p class="sub">Section export, image export and pushover curves \u2014 one module of the seismic analysis workflow</p>
<p class="meta">Scripts: <span class="mono">%s</span> \u00b7 Abaqus/CAE or Viewer 2021 (Python 2.7) \u00b7 %s</p>
<figure>%s<figcaption>Figure 1 \u2013 The module in the seismic analysis. ODB files from the analyses go in; the results
database (section histories), images per frame and pushover curves come out. Scripts 1 and 2a can run in either
order; 2b uses what both of them stored.</figcaption></figure>%s
<div class="cards">
<div class="card"><h3>Goes in</h3><p>ODB files from the Abaqus analyses (one per job, Standard or Explicit), with the
cross-sections defined as node and element SETs named <code>TYPE&amp;LABEL&amp;INDEX&amp;ANGLE</code>; for 2a one
ODB opened in Abaqus/Viewer.</p></div>
<div class="card"><h3>Happens</h3><p><span class="b b1">1</span> displacements, rotations and forces of every section
and frame; <span class="b b2a">2a</span> pictures defined once, interactively; <span class="b b2b">2b</span> every
picture printed for every job and frame, curves drawn.</p></div>
<div class="card"><h3>Comes out</h3><p>Section histories (Ux, Uy, Uz, fix, fiy, fiz, Fx, Fy, Fz, Mx, My, Mz vs time)
per SET and job; PNG images per job, variable, view and frame; pushover curves (PNG + CSV) with the image frames
marked.</p></div>
</div>
</section>
<section class="page detail">
<h2>Detailed flow</h2>
<figure>%s<figcaption>Figure 2 \u2013 What each script does. Coloured arrows are the steps inside a script; dark
arrows are data read from or written to files. A dashed box is optional.</figcaption></figure>%s
</section>
<section class="page">
<h2>The three scripts</h2>
<table><thead><tr><th style="width:4%%"></th><th style="width:21%%">Script / how to run</th><th style="width:20%%">Reads</th>
<th style="width:34%%">Does</th><th style="width:21%%">Writes</th></tr></thead><tbody>%s</tbody></table>
<div class="two" style="margin-top:18px">
<div><h2 style="margin-top:0">Output folders</h2><pre>%s</pre></div>
<div><h2 style="margin-top:0">Section types (SET names)</h2>
<table><thead><tr><th>TYPE</th><th>geometry</th><th>axes</th><th>forces</th></tr></thead><tbody>%s</tbody></table>
<p style="font-size:12.5px;margin:8px 0 0">Name: <code>TYPE&amp;LABEL&amp;INDEX&amp;ANGLE</code>, e.g.
<code>V_PIER&amp;RU&amp;2&amp;0</code>. ANGLE turns the section axes about global Z; INDEX only numbers the
section.</p></div></div>
<h2>Using the module in another folder</h2>
<p class="note">Copy everything whose name starts with <b>A_</b>: <code>A_1_Export_Auto.py</code>,
<code>A_2_Image_export_Auto.py</code>, <code>A_2_Image_save_view.py</code> and the folder
<code>A_IMPORT_additional_functions</code>. Optionally the two <code>*_settings.json</code> files, to keep the saved
settings (views, limits, curves). Order: 1 \u2192 2a \u2192 2b; 1 and 2b run unattended over all ODB files of the
folder.</p>
<footer>Generated %s from the scripts in 3_export_and_image_export. Versions of this flowchart: HTML, PDF report, SVG / PNG / PDF per
figure, Visio and draw.io (editable).</footer>
</section>
</main></body></html>
""" % (css, "Abaqus-scripts-for-output-processing / 3_export_and_image_export", TODAY.strftime("%d %B %Y"), ov_svg, links("overview"), de_svg, links("detailed"), rows,
       tree, trows, TODAY.strftime("%d %B %Y"))


# =============================================================================
# rendering with Edge (headless)
# =============================================================================
def edge(args):
    profile = SCRATCH / "edge_profile"
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions", "--hide-scrollbars",
           "--user-data-dir=%s" % profile, "--run-all-compositor-stages-before-draw",
           "--virtual-time-budget=3000"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode


def render_png(diag, svg_text_, png, scale=2):
    wrapper = SCRATCH / ("_wrap_%s.html" % diag.key)
    wrapper.write_text('<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
                       'background:#fff;overflow:hidden}svg{display:block}</style></head><body>%s</body></html>'
                       % svg_text_.split("?>", 1)[1], encoding="utf-8")
    edge(["--force-device-scale-factor=%d" % scale, "--window-size=%d,%d" % (diag.W, diag.H),
          "--default-background-color=FFFFFFFF", "--screenshot=%s" % png, wrapper.as_uri()])


def render_pdf(html_path, pdf, extra=()):
    edge(["--no-pdf-header-footer", "--print-to-pdf-no-header", "--print-to-pdf=%s" % pdf] + list(extra)
         + [html_path.as_uri()])


def figure_pdf(diag, svg_text_, pdf):
    """Single-page vector PDF with the page size of the figure (for LaTeX / Word)."""
    wmm, hmm = diag.W * 25.4 / 96.0, diag.H * 25.4 / 96.0
    wrapper = SCRATCH / ("_wrap_pdf_%s.html" % diag.key)
    wrapper.write_text('<!DOCTYPE html><html><head><meta charset="utf-8"><style>@page{size:%.2fmm %.2fmm;margin:0}'
                       'html,body{margin:0;padding:0;width:%.2fmm;height:%.2fmm;overflow:hidden;'
                       '-webkit-print-color-adjust:exact;print-color-adjust:exact}'
                       'svg{display:block;width:%.2fmm;height:%.2fmm}</style></head><body>%s</body></html>'
                       % (wmm, hmm, wmm, hmm - 0.3, wmm, hmm - 0.3, svg_text_.split("?>", 1)[1]), encoding="utf-8")
    render_pdf(wrapper, pdf)


# =============================================================================
# Visio (editable; drawn by Visio itself through COM automation)
# =============================================================================
def _rgb(hexcol):
    h = hexcol.lstrip("#")
    return "RGB(%d,%d,%d)" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def visio_file(diagrams, path, png_dir=None):
    """Native Visio drawing (.vsdx), one page per diagram: shapes from Visio's own
    stencils, connectors glued to connection points at the same places as in the SVG
    (they follow when a box is moved). Needs Visio and the comtypes package."""
    import comtypes.client as cc
    IN = lambda px: px / 96.0
    PT = lambda px: "%.2f pt" % (px * 0.75)
    app = cc.CreateObject("Visio.InvisibleApp")
    try:
        app.AlertResponse = 1
        doc = app.Documents.Add("")
        flow = app.Documents.OpenEx("BASFLO_M.VSSX", 2 | 64)     # read-only, hidden
        basic = app.Documents.OpenEx("BASIC_M.VSSX", 2 | 64)
        font_id = {"sans": doc.Fonts("Segoe UI").ID, "mono": doc.Fonts("Consolas").ID}

        def set_cells(shape, **cells):
            for k, v in cells.items():
                shape.CellsU(k.replace("_", ".")).FormulaForceU = str(v)

        def write_text(shape, lines):
            """lines: list of lines; each line a list of segments (text, style, colour)."""
            text = "\n".join("".join(s[0] for s in line) for line in lines)
            shape.Text = text
            pos = 0
            for li, line in enumerate(lines):
                for seg_text, style, color in line:
                    if seg_text:
                        fam, bold, size, col, _ = ST[style]
                        ch = shape.Characters
                        ch.Begin, ch.End = pos, pos + len(seg_text)
                        ch.CharProps[0] = font_id[fam]
                        ch.CharProps[2] = 1 if bold else 0
                        row = ch.CharPropsRow(0)
                        shape.CellsSRC(3, row, 7).FormulaForceU = PT(size)
                        shape.CellsSRC(3, row, 1).FormulaForceU = _rgb(color or col or "#0f172a")
                    pos += len(seg_text)
                pos += 1   # the line break

        def node_lines(n):
            out = []
            for s, t in n.lines:
                if s == "gap":
                    continue
                if s == "script" and n.badge:
                    out.append([(n.badge + "  ", "script", n.accent), (t, "script", n.accent)])
                else:
                    out.append([(t, s, n.accent if s == "script" else None)])
            return out

        for k, diag in enumerate(diagrams):
            H = diag.H
            page = doc.Pages(1) if k == 0 else doc.Pages.Add()
            page.NameU = page.Name = diag.key.capitalize()
            set_cells(page.PageSheet, PageWidth="%.3f in" % IN(diag.W), PageHeight="%.3f in" % IN(H),
                      PrintPageOrientation=2, RouteStyle=1, LineJumpStyle=0)
            box = lambda x, y, w, h: page.DrawRectangle(IN(x), IN(H - y - h), IN(x + w), IN(H - y))
            shapes = {}
            # title
            t = box(24, 16, diag.W - 48, 60)
            set_cells(t, LinePattern=0, FillPattern=0, VerticalAlign=0, Para_HorzAlign=0, ShapePermeableX="TRUE",
                      ShapePermeableY="TRUE")
            write_text(t, [[(diag.title, "title", "#0f172a")], [(diag.subtitle, "body", "#64748b")]])
            t.CellsSRC(3, 0, 7).FormulaForceU = PT(20)
            for n in sorted(diag.nodes, key=lambda n: 0 if n.kind == "lane" else 1):   # lanes at the back
                fill, stroke = n.colors()
                if n.kind == "doc":
                    s = page.Drop(flow.Masters.ItemU("Document"), IN(n.x + n.w / 2.0), IN(H - n.y - n.h / 2.0))
                elif n.kind == "store":
                    s = page.Drop(basic.Masters.ItemU("Can"), IN(n.x + n.w / 2.0), IN(H - n.y - n.h / 2.0))
                else:
                    s = box(n.x, n.y, n.w, n.h)
                set_cells(s, Width="%.3f in" % IN(n.w), Height="%.3f in" % IN(n.h), FillForegnd=_rgb(fill),
                          FillPattern=1, LineColor=_rgb(stroke), LineWeight=PT(1.6 if n.kind != "lane" else 1.3),
                          ShdwPattern=0, LinePattern=2 if (n.kind == "ext" or n.dashed) else 1)
                if n.kind in ("process", "manual", "ext", "lane"):
                    set_cells(s, Rounding="%.3f in" % IN({"lane": 14, "ext": 12}.get(n.kind, 9)))
                if n.kind == "lane":
                    sc = [l[1] for l in n.lines if l[0] == "script"][0]
                    ti = [l[1] for l in n.lines if l[0] == "title"]
                    lines = [[(n.badge + "  ", "script", n.accent), (sc, "script", n.accent),
                              (("   —  " + ti[0]) if ti else "", "title", "#0f172a")]]
                    lines += [[(t2, "small", None)] for s2, t2 in n.lines if s2 == "small"]
                    write_text(s, lines)
                    set_cells(s, VerticalAlign=0, Para_HorzAlign=0, LeftMargin="10 pt", TopMargin="7 pt",
                              ShapePermeableX="TRUE", ShapePermeableY="TRUE")
                else:
                    write_text(s, node_lines(n))
                    set_cells(s, VerticalAlign=1, Para_HorzAlign=1, LeftMargin="3 pt", RightMargin="3 pt")
                    if n.kind == "store":   # keep the text below the top ellipse of the cylinder
                        set_cells(s, TopMargin="15 pt", BottomMargin="2 pt")
                s.Name = n.id
                shapes[n.id] = s
            # connectors glued to connection points at the anchors of the model
            points = {}

            def cpoint(nid, side, tt):
                key = (nid, side, round(tt, 4))
                if key in points:
                    return points[key]
                s = shapes[nid]
                if not s.SectionExists(7, 0):
                    s.AddSection(7)
                fx = {"left": 0.0, "right": 1.0}.get(side, tt)
                fy = {"top": 1.0, "bottom": 0.0}.get(side, 1.0 - tt)
                row = s.AddRow(7, -2, 153)
                s.CellsSRC(7, row, 0).FormulaForceU = "Width*%.4f" % fx
                s.CellsSRC(7, row, 1).FormulaForceU = "Height*%.4f" % fy
                points[key] = s.CellsSRC(7, row, 0)
                return points[key]

            for e in diag.edges:
                c = page.Drop(app.ConnectorToolDataObject, 0, 0)
                c.CellsU("BeginX").GlueTo(cpoint(e.src, e.s_side, e.s_t))
                c.CellsU("EndX").GlueTo(cpoint(e.dst, e.d_side, e.d_t))
                set_cells(c, LineColor=_rgb(e.color), LineWeight=PT(1.6), EndArrow=4, EndArrowSize=2,
                          Rounding="0.07 in", ShdwPattern=0, LinePattern=2 if e.dashed else 1)
                if e.label:
                    write_text(c, [[(e.label, "small", "#475569")]])
                    set_cells(c, TextBkgnd=2)
            # legend and notes
            if diag.legend_y:
                lg = box(30, diag.legend_y - 12, diag.W - 60, diag.H - diag.legend_y + 4)
                set_cells(lg, LinePattern=0, FillPattern=0, VerticalAlign=0, Para_HorzAlign=0,
                          ShapePermeableX="TRUE", ShapePermeableY="TRUE")
                key = ("Colours: blue = 1 section export, amber = 2a picture definition, green = 2b image & curve "
                       "export; cylinder = results database; wavy box = file / folder; dashed = %s."
                       % diag.dashed_meaning)
                write_text(lg, [[(key, "body", "#475569")]] + [[(t3, "small", None)] for t3 in diag.notes])
            if png_dir:
                page.Export(str(Path(png_dir) / ("_visio_%s.png" % diag.key)))
        if os.path.exists(path):
            os.remove(path)
        doc.SaveAs(str(path))
    finally:
        for dd in list(app.Documents):
            dd.Saved = True
        app.Quit()


def main():
    OUT.mkdir(exist_ok=True)
    diagrams = [overview(), detailed()]
    for d in diagrams:
        s = svg(d)
        (OUT / ("%s_%s.svg" % (BASE, d.key))).write_text(s, encoding="utf-8")
        if "--no-render" not in sys.argv:
            render_png(d, s, str(OUT / ("%s_%s.png" % (BASE, d.key))))
            figure_pdf(d, s, str(OUT / ("%s_%s.pdf" % (BASE, d.key))))
    (OUT / ("%s.drawio" % BASE)).write_text(drawio_file(diagrams), encoding="utf-8")
    if "--no-visio" not in sys.argv:
        try:
            visio_file(diagrams, OUT / ("%s.vsdx" % BASE), png_dir=SCRATCH)
        except Exception as e:   # no Visio / comtypes on this computer: the other versions are still made
            print("Visio file skipped: %s" % e)
    rep = OUT / ("%s.html" % BASE)
    rep.write_text(report_html(*diagrams), encoding="utf-8")
    if "--no-render" not in sys.argv:
        render_pdf(rep, str(OUT / ("%s.pdf" % BASE)))
    print("text overflow warnings: %d" % len(WARN))
    for w in WARN:
        print("  " + w)
    for f in sorted(OUT.iterdir()):
        print("  %-48s %9d bytes" % (f.name, f.stat().st_size))


if __name__ == "__main__":
    main()
