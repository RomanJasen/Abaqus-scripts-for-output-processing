# Flowchart of steps 3 and 4

Visual summary of the post-processing (`3_export_and_image_export`), as one module of a seismic
analysis workflow.

| file | use |
|---|---|
| `Flowchart_postprocessing.pdf` / `.html` | short report: both flowcharts, the scripts, output folders, section types |
| `Flowchart_postprocessing_overview.*` | the module with its inputs and outputs (PNG, SVG, single-page vector PDF) |
| `Flowchart_postprocessing_detailed.*` | step by step inside each script |
| `Flowchart_postprocessing.vsdx` / `.drawio` | editable (Visio, draw.io), to merge into a larger flowchart |
| `make_flowchart.py` | regenerates all files after a change of the texts (Python 3 with Pillow; Microsoft Edge for PNG/PDF; Visio for the .vsdx) |
