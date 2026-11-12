# Tutorial

**[Tutorial_Abaqus_scripts_for_output_processing.pdf](Tutorial_Abaqus_scripts_for_output_processing.pdf)**
(22 pages) - how to use the scripts, step by step, with pictures of the benchmark model, the dialogs
and the outputs.

| chapter | contents |
|---|---|
| 0. Overview and conventions | the four steps, INPUT blocks, remembered settings, log files, the example |
| 1. Preparing the model | cross-section SETs (node set on the cut + element set on one side), naming `TYPE&LABEL&INDEX&ANGLE`, section axes and signs, correct and wrong cuts, creating the SETs in Abaqus/CAE, field output |
| 2. Running the analyses | workflow A `run_pushover_jobs.py` (dialog: models, vertical forces, analyses at a time, cores), workflow B `run_parameter_study.py`, CDP materials |
| 3. Section export | `A_1_Export_Auto.py`: settings dialog, what is computed, results database, checking the results (free-body cut vs. NFORC) |
| 4. Defining pictures | `A_2_Image_save_view.py`: Save view dialog, curve dialog |
| 5. Images and curves | `A_2_Image_export_Auto.py`: exported images and folders, contour limits, pushover curves with the image frames marked |
| 6. Changing the scripts | a new parameter study, a new section type, own post-processing of the results database |
| A, B | troubleshooting; video tutorials |

The pictures of chapters 1, 3 and 5 come from the benchmark model of the videos: section geometry,
results database, images and curves were produced by the scripts of this repository on one of its
analyses. The screenshots of the export and curve dialogs show the scripts' own dialogs; the
dialogs that Abaqus itself draws (Save view, run_pushover_jobs) are shown as drawn replicas with
the texts of the scripts.

The videos listed in the main [README](../../README.md) were recorded with the earlier version of
the scripts (same modelling, different script input).

## Changing the tutorial

`source/tutorial.html` is the text (open it in a browser to read it as a web page),
`source/figures/` the pictures. After a change rebuild the PDF:

    cd source
    python build_pdf.py

(Python 3 with PyMuPDF, `pip install pymupdf`; Microsoft Edge prints the HTML.)
