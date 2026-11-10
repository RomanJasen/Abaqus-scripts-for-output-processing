# Step 2 - run the analyses (Abaqus/CAE)

`run_jobs.py` runs a parameter study: for every model and every value the model is changed, a
job is created and submitted. Open the model database (.cae) in Abaqus/CAE and run the script
(File > Run Script...). Jobs whose `<job>.odb` already exists in the work folder are skipped, so a
study that was interrupted continues where it stopped. Progress: `run_jobs_log.txt`.

Video: [automated job running](https://youtu.be/iR5NVptAlkw) (earlier version of the script).

## Studies (`STUDY` in the INPUT block)

| STUDY | changed in the model | job name |
|---|---|---|
| `vertical_force` | load `VERT_FORCE`: `cf3 = -force` in steps `VERT` and `HOR` | `<model>_EX_<force>` |
| `contact` | interaction property `Simple_contact`: friction, exponential pressure-overclosure, damping | `<prefix>_Damping_<d>pressure<p>` |
| `material` | material `BETON`: elasticity and the CDP tables (compression, tension, damage) | `<model>_MAT_<material>` |

Other INPUT: the models, the values, `JOBS_AT_ONCE` (jobs running at the same time - the script
waits for every n-th job), `JOB_SETTINGS` (cores, explicit precision ...) and `SUBMIT = False`
to only change the models and create the jobs.

A new kind of study: write `change_<name>(model, value)` and `cases_<name>()` like the existing
ones and add them to `STUDIES`.

## CDP materials (`material_CDP`)

Used by `STUDY = "material"`. Two ways to give a concrete damaged plasticity material:

| folder | script | input |
|---|---|---|
| `A_Material_input_indirect` | `Material_CDP_ECformula_to_tuple_preparation.py` + `Material_CDP_ECformula_to_tuple.py` | one line per material: `name E v s_max e_smax e_u (not used) Sigma_T GFI` - the compression curve follows the Eurocode formula, tension softens linearly |
| `A_material_input_direct` | `Material_CDP_direct_to_tuple.py` | one file per material with the tables themselves (layout: `Example_direct.txt`) |

The example files contain made-up values. Run a material script on its own (python) to check
the input: the EC scripts print the tables, `Material_CDP_direct_to_tuple.py` plots the
compression curves.
