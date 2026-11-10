# Step 1 - model preparation (Abaqus/CAE)

What the model needs for the export and image scripts of step 3, and two helper scripts.

## 1. Cross-section SETs

Every cross-section whose forces and displacements are wanted is an **assembly SET** with
* the **nodes on the cut** (node set) and
* the **elements on one side of the cut** (element set),

both with the same name `TYPE&LABEL&INDEX&ANGLE`, e.g. `V_PIER&RU&2&0`:

| part | meaning |
|---|---|
| `TYPE` | `V_PIER` / `V_SPEC` (solid), `S_PIER` (shell), `V_SPANDREL`, `S_SPANDREL`, `S_DRIFT` (point, displacements only), `SRIFT` (solid, displacements only) |
| `LABEL` | free text, e.g. the position in the wall (`RU`, `DPARC`) |
| `INDEX` | number of the section, e.g. 1 = bottom, 2 = top of a pier |
| `ANGLE` | rotation of the local axes about global Z (degrees), for displacements and forces |

Videos: [creation of the benchmark model](https://youtu.be/stwDfm0-Hc0),
[cross-section naming and local axes](https://youtu.be/6BFI6Eegp64).

## 2. Field output

| variable | needed for |
|---|---|
| `U` | displacements and rotations of the sections |
| `UR` | rotation about a shell section's own axis (shell sections only) |
| `NFORC` | section forces (both the Abaqus free-body cut and the NFORC method) |
| e.g. `DAMAGEC`, `DAMAGET`, `PEEQ`, `S` | the variables you want in the images |

More output frames = more points on the curves and more frames to choose for the images.

## Scripts

| script | what it does |
|---|---|
| `prepare_model_for_export.py` | lists the section SETs of one or all models and checks their names; optionally creates the surfaces `SURF_<SET>` (used by the earlier scripts and videos, **not needed** by the current export) and sets the variables of the field output request `F-Output-1`. Run in Abaqus/CAE with the .cae open. |
| `convert_models_to_explicit_EXAMPLE.py` | **example**, recorded on the Zaprudje panel models: explicit steps, explicit element types with element deletion, output requests, load ramps and step times. Part names and masks belong to that model - record the same actions for your model and replace them. |

Both scripts have an INPUT block at the top.
