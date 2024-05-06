The content of this repository is a set of scripts (currently being refined for publishing, not yet uploaded), usefull for structural analysis of buildings or associated benchmarks in Abaqus CAE software. 
Roughly, the scripts allow automation, and extract forces and displacements from numerical models.
Main usecases are seismic (or other) analysis of complete buildings (modelled by volumetric or shell elements), or running parametric analysis on benchmarks, IE larger number of analyses on a smaller model like a shear wall etc...

Here, along with the scripts, videos are provided explaining different levels of scripts. One showing how they can be used with almost no coding knowledge, another showing how the ease of conducting analyses can be improved with very basic coding knowledge, and more indepth dive into their structure to allow modification for specialisation in different tasks. If you create a notable addaptation of the script, i would love to see it, publishing as a branch of this repository is an option :)

These scripts are to be published in a article, which will be linked here. If you use them in research, please reference the provided article. (Link will be here as soon as it is published)
 - 
 If you have any questions or sudgestions please contact me on the email: romano.jevtic.rundek@grad.unizg.hr



////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

How the scripts work - general overview -> defining sections and converting field output into section values
 - link to be provided

USE WITHOUT CODING
How the scripts can be used for seismic analysis of a building (Shell or Volumetric finite elements)
 - this includes extracting and storing output data, processing only selected values into a excell sheet for further processing
 - link to be provided

How the scripts can be used for parametric analysis - no coding required (a bit more limited)
 - this includes extracting and storing output data, processing only selected values into a excell sheet for further processing
 - link to be provided



USE WITH CODING
How the scripts can be used for parametric analysis - almost complete automation (here, complete automation will be possible after some fixes)
 - this includes adapting a script to run parametric analysis, extracting results into a database, and plotting graphs from that database. Additionally, pictures of analysis results can be extracted automatically.
 - link to be provided

How the scripts can be used for seismic analysis
 - this includes, essentially a parametric analysis, where the parameter that is changed is the ground motion, and a scripted postprocessing, rather than generation of a excell spreadsheet.
 - link to be provided


Script structure description
 - General layout - what script is where, and what it does (link to be provided)
   - model preparation explanation (link to be provided)
   - data extraction from odb file overview (link to be provided)
     - data extraction from odb file deepdive (link to be provided)
     - Force extraction (link to be provided)
     - displacement extraction (link to be provided)
     - Database creation (link to be provided)
   - data postprocessing - GUI with excell solution deepdive (link to be provided)
   - data postprocessing - parametric analysis automatic graph creation deepdive (link to be provided)
   - image export deepdive (link to be provided)


