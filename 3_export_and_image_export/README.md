# Steps 3 and 4 - section export, images and curves (Abaqus/CAE or Viewer)

**Copy everything whose name starts with A_ into the folder with the ODB files**:
`A_1_Export_Auto.py`, `A_2_Image_export_Auto.py`, `A_2_Image_save_view.py` and the folder
`A_IMPORT_additional_functions` (it must stay next to the scripts). Run the scripts with
File > Run Script... Each has an INPUT block at the top; the settings are remembered in
`1_Export_Auto_settings.json` / `2_Image_export_settings.json` (copy those too to use the same
settings in another folder).

Flowchart and short report: [`../docs/flowchart`](../docs/flowchart). Step-by-step guide with
pictures: chapters 3-5 of the [tutorial](../docs/tutorial).

## Step 3 - `A_1_Export_Auto.py`: section export

For every ODB file of the folder (Abaqus/Standard or Explicit, detected) and every cross-section
SET (see `1_model_preparation`):
* displacements and rotations in the section axes (`Ux Uy Uz fix fiy fiz`): rigid-body fit valid
  for large rotations (or the angle / slope of the regression plane), relative or absolute,
* forces in the section coordinate system (`Fx Fy Fz Mx My Mz`): Abaqus free-body cut or the sum of
  NFORC (area-weighted centre of the cut),
* written frame by frame (matched by frame position) to the results database
  `Panel_results/<SET>/<JOB>/Section_dataIIII<SET>IIII<JOB>.txt`.

A settings dialog asks for the ODB files, step, database folder, SET filter and methods.
Sections already in the database are skipped (unless *Overwrite*). Progress: `1_Export_Auto_log.txt`.

Video: [export script](https://youtu.be/nRnF_rlyfsg) (earlier version).

## Step 4 - images and pushover curves

1. **`A_2_Image_save_view.py`** (in Abaqus/Viewer, once per picture): set up the picture - camera,
   section cut, display group, variable, contour type and limits, legend - then run the script and
   give a name (`View` or `View__VARIABLE`), the frames of the view and the contour limits
   (empty = as shown). The 4th field `edit` opens a dialog with drop-down lists to define the
   **curves** (e.g. Y = Fx of one section, X = Ux of section 2 - Ux of section 1).
   Alternative: `MODE = "capture"` in `A_2_Image_export_Auto.py` reads pictures printed in Abaqus
   from `abaqus.rpy`.
2. **`A_2_Image_export_Auto.py`**: prints every picture for every ODB file and chosen frame
   (`Panel_images/<JOB>/<variable>/<view>/f0012_t1.2.png`, frame 12 at step time 1.2) and draws the
   curves of every job with the frames of the images marked (`Panel_images/<JOB>/_curve_<name>.png`
   and `.csv`). Progress: `2_Image_export_log.txt`.

## Library `A_IMPORT_additional_functions`

| module | contents |
|---|---|
| `odb_tools.py` | opening ODBs, frame selection (frame sync), sets, field values, logging |
| `section_definitions.py` | SET name &rarr; section type and axes |
| `section_geometry.py` | geometry: regression plane, rigid-body fit, rotations, cut centroid |
| `section_displacements.py` | displacements and rotations of the sections |
| `section_forces.py` | free-body cut and NFORC forces |
| `database_io.py` | results database |
| `export_settings.py`, `export_gui.py` | remembered settings, settings dialog |
| `image_export.py`, `rpy_views.py`, `view_snapshot.py` | replaying views, reading `abaqus.rpy`, snapshot of the session |
| `pushover_curve.py` | curves from the results database, curve dialog |

Most modules can be run on their own as a demo or test (File > Run Script, or python).

Video: [adding a custom post-processing function](https://youtu.be/oXEkcqDdTa8) (earlier version).

## Optional: Plug-ins button

`optional_abaqus_plugin`: copy both files once into `C:\Users\<name>\abaqus_plugins\` and restart
Abaqus; *Plug-ins > Image export > Save current view...* then runs `A_2_Image_save_view.py` from the
folder of the displayed ODB.
