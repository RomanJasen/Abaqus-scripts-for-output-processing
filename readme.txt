EARLIER README TEXTS AND VIDEO LINKS
====================================

This file keeps, word for word, the README texts of the two repositories that existed before the
scripts were cleaned up and uploaded here (November 2026):

  A) github.com/RomanJasen/Abaqus-scripts-for-output-processing  (this repository)
  B) github.com/RomanJasen/Abaqus-result-extraction-scripts      (merged into this repository)

The videos show the EARLIER version of the scripts. The model preparation (cross-section SETs,
their names and local axes) is unchanged; the script names and their input are different now -
see README.md and the README.md of every step folder.


----------------------------------------------------------------------------------------------------
A) README of Abaqus-scripts-for-output-processing
   Description: Here python scripts for use with Abaqus CAE are provided, intended for use in civil
   engineering seismic analysis, but applicable in other areas that requireextraction of section
   forces and displacements from Volumetric or Shell finite elements
----------------------------------------------------------------------------------------------------

The content of this repository is a set of scripts (currently being refined for publishing, not yet uploaded), usefull for structural analysis of buildings or associated benchmarks in Abaqus CAE software. Roughly, the scripts allow automation, and extract forces and displacements from numerical models. Main usecases are seismic (or other) analysis of complete buildings (modelled by volumetric or shell elements), or running parametric analysis on benchmarks, IE larger number of analyses on a smaller model like a shear wall etc...

Here, along with the scripts, videos are provided explaining different levels of scripts. Showing how they can be used with almost no coding knowledge and, very basic coding knowledge, and with additional coding ho they can be specialised for different tasks. If you create a notable addaptation of the script, i would love to see it, publishing as a branch of this repository is an option.

These scripts are to be published in a article, which will be linked here. If you use them in research, please reference the provided article. (Link will be here as soon as it is published)

article link is to be provided by 2025 If you have any questions or sudgestions please contact me on the email: romano.jevtic.rundek@grad.unizg.hr

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

How the scripts work - general overview and demonstration -> from new model to extracted results

https://youtu.be/g9gw_EXEesM How the scripts folder is structured - folders, scripts layout and assumptions:
Link to be provided

More detailed overviews: Cross-section naming and local axes: https://youtu.be/6BFI6Eegp64 Export script: https://youtu.be/nRnF_rlyfsg Dispalcement and force conversion modification demo: https://youtu.be/nNw8NbOuac0 Automated job running: https://youtu.be/iR5NVptAlkw Adding custom postprocessing function: https://youtu.be/oXEkcqDdTa8

Creation of the benchmark model: https://youtu.be/stwDfm0-Hc0

Entire playlist: https://www.youtube.com/playlist?list=PLjdnR7Fv3RGjCVFS0ykvkd6-2jo0IHgPl


----------------------------------------------------------------------------------------------------
B) README of Abaqus-result-extraction-scripts (MIT License, Copyright (c) 2026 RomanJasen)
   Description: A set of scripts made for extraction of forces and displacements from volumetric
   and shell elements in implicit and explicit abaqus analysis
----------------------------------------------------------------------------------------------------

Abaqus-result-extraction-scripts

A set of scripts made for extraction of forces and displacements from volumetric and shell elements in implicit and explicit abaqus analysis

IMPORTANT: I recommend a check on any and all results exported, assume an error can happen and exported force or displacement can be wrong.

There is a playlist of tutorials for these scripts. The tutorials are not ideal, but should be sufficient to introduce the entire script structure. It is recommended to read this ReadMe too as there were some additional variants of scripts made for explicit analysis.

General tutorial and overview - https://www.youtube.com/watch?v=g9gw_EXEesM&list=PLjdnR7Fv3RGjCVFS0ykvkd6-2jo0IHgPl&index=2
Making of the model from the General tutorial - https://www.youtube.com/watch?v=stwDfm0-Hc0&list=PLjdnR7Fv3RGjCVFS0ykvkd6-2jo0IHgPl&index=8

Essentials: This GitHub contains a number of python scripts with a main goal to automate extraction of force and displacement data from Abaqus models. These are not finished and it is unclear if they will be finished. They are made by myself, an inexpirienced coder that is self taught, while an effort is made to make the code simple and show its structure as clear as possible, due to the fact i did not decide to write it from stratch again, it is somewhat suboptimal. Still, they do work and can be used efficently, after the initial period of testing and familiarisation. The scripts do a bad job in being a completed program for general use, but i was able to easily modify them for different tasks i needed, such as running a large number of pushover analysis with extraction of data from multiple cross sections. Paragraph 0 relates to versions of python and windows. The scripts exist to automate the workflow which happens in two stages, this is described in paragraph 1. There are multiple variants and versions depending on the expected workflow and depending on the model, described in paragraph 2 will explain different workflows present in the repository. There is a variant with GUI, described in paragraph 3.

Paragraph 0: Abaqus version: The original scripts are made for Abaqus 2021 (Python 2.7.15 (default, Jul 25 2019, 08:13:50) [MSC v.1916 64 bit (AMD64)] ) Windows version: Edition Windows 10 Pro ; Version 22H2 ; Installed on 5.11.2021. ; OS Build 19045.6466 For use in later versions, i would expect there arent big changes, there are some changes in library names (Tkinter vs tkinter). I will likely make a new 2024 version of the scripts, but for now, 2021 is available)

Paragraph 1: With regards to script structure, there are 2 main steps conducted, with everything else being done either to support these, or as additional automation. Step 1: extracting data from field output of abaqus and storing it into txt files as displacements and forces of CROSS-SECTIONS. Step 2: taking the data about cross sections and plotting them in what ever way is desired. In case of PIER elements this meant plotting difference of displacement, and one of the forces. In case of story drift it means plotting extreme values against story index, etc...

Additional scripts and steps: -There is a script used to prepare the model for export of data, which creates surfaces used for extraction of forces. This is needed for Step 1 -There is a script used to prepare an input_file.txt, which defines paths, locations, step name and other data -There is a script used to extract images of the analysis, this script adds files to the existing database of cross-section data -Running of analysis can be automated with a separate script, entirely independent from these

Paragraph 2: Relevant to Step 1: With regards to the model, implicit and explicit analysis are different due to a small difference in the command line used to extract displacement of a node. Relevant to Step 2: Since there are many ways to process data, there are multiple variants here. The main difference is in the question of how big is the analysed model. Is it is a benchmark with say about 10 cross sections, where some sort of pushover curve is needed, it is more optimal to use a smaller script, easier to edit and modify. If the model contains a whole building, with a large number of crossections, and aside from sectional hysteresis, extremes need to be plotted separatelly, a more comprehensive structure is needed, which is also more difficult to modify.

Paragraph 3: GUI was used for some attempts...It can work, but is generally not very practical. Essentially once the scripts work without GUI, it can be added to call and trigger the same functions used without GUI. The benefit is not needing to understand python to use it. The problem is another layer of lost flexibility.


----------------------------------------------------------------------------------------------------
WHAT CHANGED SINCE THESE TEXTS (November 2026)
----------------------------------------------------------------------------------------------------
* One script for implicit AND explicit analyses (A_1_Export_Auto.py detects the analysis type).
* No input_file.txt: every script has an INPUT block at the top and remembers its settings.
* Surfaces are not needed any more: the forces are taken from the node and element sets
  (Abaqus free-body cut, or a sum of NFORC); 1_model_preparation/prepare_model_for_export.py
  still creates them if wanted.
* The images are no longer stored inside the cross-section database (Panel_images instead),
  pictures are defined in Abaqus/Viewer (A_2_Image_save_view.py), and pushover curves with the
  frames of the images marked are drawn for every job.
* Large rotations (rigid-body fit), frame synchronisation of forces and displacements, and a
  settings dialog (GUI) of the section export.
