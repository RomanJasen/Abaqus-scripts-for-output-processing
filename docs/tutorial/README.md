# Tutorial (planned)

A written tutorial with pictures (PDF) will be added here. Until then: the README of every step
folder, the flowchart in [`../flowchart`](../flowchart) and the videos listed in the main
[README](../../README.md) (recorded with the earlier version of the scripts).

## Planned content

| chapter | pictures | replaces / complements |
|---|---|---|
| 1. Preparing the model: cross-section SETs (node set on the cut + element set on one side), naming `TYPE&LABEL&INDEX&ANGLE`, local axes, field output (U, UR, NFORC) | Abaqus/CAE: creating a SET, a correct and a wrong cut, the axes for ANGLE 0 and 90 | videos "Creation of the benchmark model", "Cross-section naming and local axes" |
| 2. Running a parameter study with `run_jobs.py` (vertical force, contact, material; CDP material input) | INPUT block, job list in Abaqus/CAE, log file | video "Automated job running" |
| 3. Section export with `A_1_Export_Auto.py` | settings dialog, results database folders, one section file, a check against a free-body cut | video "Export script" |
| 4. Defining pictures with `A_2_Image_save_view.py` | a picture set up in Abaqus/Viewer, the Save view dialog, the curve dialog | new |
| 5. Images and curves with `A_2_Image_export_Auto.py` | image folders, a pushover curve with the image frames marked | new |
| 6. Changing the scripts: adding a study, a section type or a post-processing function | code snippets | videos "Displacement and force conversion modification demo", "Adding custom postprocessing function" |
