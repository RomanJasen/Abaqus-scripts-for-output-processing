# Step 2 - run the analyses (Abaqus/CAE)

Two workflows, both run in Abaqus/CAE with the model database (.cae) open
(File > Run Script...). The ODB files are written to the work directory
(File > Set Work Directory...).

| workflow | script | runs |
|---|---|---|
| **A - pushover analyses** | `run_pushover_jobs.py` | the chosen models at every vertical force |
| **B - parameter study** | `run_parameter_study.py` (+ `material_CDP`) | the models with every value of a contact or CDP-material parameter |

Common to both:
* analyses whose `<job>.odb` (or `<job>.lck`) already exists in the work directory are skipped,
  so an interrupted run continues where it stopped (delete the .odb of a failed analysis to
  repeat it);
* *analyses at a time*: the script submits that many analyses, then waits for the oldest one
  before the next is submitted (analyses that finished meanwhile also free their place) -
  Abaqus/CAE stays busy until the last analysis has been submitted;
* *cores per analysis*: `numCpus` and `numDomains` of every job; the other job settings
  (`JOB_SETTINGS`: memory, explicit precision ...) are in the INPUT block;
* `SUBMIT = False` only writes the input files `<job>.inp`, e.g. to run them later or on another
  computer;
* progress in a log file in the work directory (`run_pushover_jobs_log.txt`,
  `run_parameter_study_log.txt`).

Video: [automated job running](https://youtu.be/iR5NVptAlkw) (earlier version of the scripts).

## A - pushover analyses: `run_pushover_jobs.py`

Cleaned-up version of `Automatic_job_running_generalEXPLICIT.py`. A dialog shows the INPUT and
lets you change it before anything is done:

| field | meaning |
|---|---|
| Models | model names separated by commas; `*` and `?` as wildcards (`*` = all models, `BEND_*` = all bending models) |
| Vertical forces | one analysis per force, separated by commas, in the force unit of the model; empty = run the models with the force they have |
| Analyses at the same time | e.g. `2` |
| Cores per analysis | e.g. `4` |

A second dialog lists the analyses (and the ones skipped) and asks before submitting.
For every analysis the concentrated force `VERT_FORCE` gets `cf3 = -force` in the steps `VERT` and
`HOR`, then the job `<model>_EX_<force>` (e.g. `BEND_NOkey_S_FR07_EX_360000`) is created and
submitted. Load name, steps and the job name pattern are in the INPUT block; `ASK = False` runs
without dialogs (e.g. `abaqus cae noGUI=run_pushover_jobs.py`), `WAIT_AT_END = True` also waits
for the last analyses.

## B - parameter study: `run_parameter_study.py`

For every model and every value of the studied parameter the model is changed, a job is created
and submitted (`STUDY` in the INPUT block):

| STUDY | changed in the model | job name |
|---|---|---|
| `contact` | interaction property `Simple_contact`: friction, exponential pressure-overclosure, damping | `<prefix>_Damping_<d>pressure<p>` |
| `material` | material `BETON`: elasticity and the CDP tables (compression, tension, damage) | `<model>_MAT_<material>` |

Other INPUT: the models, the values, `JOBS_AT_ONCE`, `CORES_PER_JOB`, `JOB_SETTINGS`, `SUBMIT`.
A new kind of study: write `change_<name>(model, value)` and `cases_<name>()` like the existing
ones and add them to `STUDIES`.

### CDP materials (`material_CDP`)

Used by `STUDY = "material"`. Two ways to give a concrete damaged plasticity material:

| folder | script | input |
|---|---|---|
| `A_Material_input_indirect` | `Material_CDP_ECformula_to_tuple_preparation.py` + `Material_CDP_ECformula_to_tuple.py` | one line per material: `name E v s_max e_smax e_u (not used) Sigma_T GFI` - the compression curve follows the Eurocode formula, tension softens linearly |
| `A_material_input_direct` | `Material_CDP_direct_to_tuple.py` | one file per material with the tables themselves (layout: `Example_direct.txt`) |

The example files contain made-up values. Run a material script on its own (python) to check
the input: the EC scripts print the tables, `Material_CDP_direct_to_tuple.py` plots the
compression curves.

See also chapter 2 of the [tutorial](../docs/tutorial).
