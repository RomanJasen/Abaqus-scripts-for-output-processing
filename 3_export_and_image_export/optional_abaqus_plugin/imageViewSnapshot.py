# -*- coding: mbcs -*-
"""Kernel part of the Plug-ins button (see imageViewSnapshot_plugin.py)."""
import os
import runpy

# newest name first; folders set up before the A_ prefix still work
SCRIPT_NAMES = ("A_2_Image_save_view.py", "2_Image_save_view.py")


def save_view():
    from abaqus import session
    vp = session.viewports[session.currentViewportName]
    odb = vp.displayedObject
    folders = [os.getcwd()]
    if odb is not None and hasattr(odb, "steps"):
        folders.insert(0, os.path.dirname(os.path.abspath(odb.name)))
    for folder in folders:
        for name in SCRIPT_NAMES:
            script = os.path.join(folder, name)
            if os.path.isfile(script):
                runpy.run_path(script, run_name="__main__")
                return
    from abaqus import getWarningReply
    from abaqusConstants import YES
    getWarningReply("%s was not found next to the displayed ODB or in the work folder:\n%s\n\n"
                    "Copy the A_ files of the image export into that folder first." % (
                        SCRIPT_NAMES[0], "\n".join(folders)), (YES,))
