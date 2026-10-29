# =============================================================================
#  Import VTF (V1)
#  The Text Editor version of  SFM Session Importer > Tools > HoovyTools
#  Importers > 3 Import VTF  (SFM Session Importer 3.0.0).
# =============================================================================
#
#  WHAT IT DOES: decodes each .vtf into a Blender image, packed into the
#  .blend - every format SFM uses, sprite sheets included - with HoovyTools'
#  own reader: SourceIO does not have to be installed. Open the images in an
#  Image Editor or pick them in any Image Texture node.
#
#  HOW: set the value below, press Run Script (Alt+P). Each image's name and
#  size prints to the console (Window > Toggle System Console).
#
#  Needs the SFM Session Importer add-on (3.0.0 or newer) installed.
#
#  THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE.
# =============================================================================

VTF_FILES = [r""]           # one or more .vtf files: [r"C:\...\a.vtf", r"C:\...\b.vtf"]

# -----------------------------------------------------------------------------

import addon_utils
import bpy

NAMES = ("HoovyTools-SFMSessionImport-Blender-Master", "HoovyTools-SFMSessionImport-Blender-master",
         "HoovyTools-SFMSessionImport-Blender-main")


def session_importer():
    """Make sure the add-on is on - enabled here ONLY when it is installed and off (enabling twice re-registers it
    under this running script)."""
    if "import_vtf" in dir(bpy.ops.ht):
        return
    installed = {m.__name__ for m in addon_utils.modules()}
    for name in NAMES:
        if name in installed:
            addon_utils.enable(name, default_set=True)
            break
    if "import_vtf" not in dir(bpy.ops.ht):
        raise RuntimeError("SFM Session Importer 3.0.0+ is not installed - install it, then run this again")


def main():
    files = [f for f in VTF_FILES if f.strip()]
    if not files:
        raise RuntimeError("Set VTF_FILES at the top of this script to one or more .vtf files")
    session_importer()
    for f in files:
        result = bpy.ops.ht.import_vtf(filepath=f)
        print("[SFM Session Importer]  Import VTF %s: %s" % (sorted(result)[0], f))


main()
