# -*- coding: mbcs -*-
"""
Plug-ins menu button "Image export > Save current view..." for Abaqus/CAE and Viewer.

INSTALL (once per computer - NOT copied into every ODB folder):
  copy BOTH files of this folder
      imageViewSnapshot_plugin.py
      imageViewSnapshot.py
  into  C:\\Users\\<your name>\\abaqus_plugins\\   (create the folder if it does not exist)
  and restart Abaqus. (Copy them again after an update of this folder.)

USE:
  open an ODB, set up the picture, then  Plug-ins > Image export > Save current view...
  The button runs A_2_Image_save_view.py from the folder of the displayed ODB (or the
  Abaqus work folder), so the view goes into that folder's 2_Image_export_settings.json.
  (Folders with the older name 2_Image_save_view.py work too.)
"""
from abaqusGui import getAFXApp

toolset = getAFXApp().getAFXMainWindow().getPluginToolset()
toolset.registerKernelMenuButton(
    moduleName="imageViewSnapshot",
    functionName="save_view()",
    buttonText="Image export|Save current view...",
    author="A_2_Image_export_Auto",
    version="1.1",
    description="Saves the picture shown in the viewport as a view for A_2_Image_export_Auto.py "
                "(runs A_2_Image_save_view.py next to the displayed ODB).")
