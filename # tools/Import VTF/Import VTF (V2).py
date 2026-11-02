# =============================================================================
# Import VTF (V2)
# The Text Editor version of  SFM Session Importer > Tools > HoovyTools
# Importers > 3 Import VTF  (SFM Session Importer 3.0.10)
# =============================================================================
#
# what IT DOES: decodes each .vtf into a Blender image, packed into the
# .blend - every format SFM uses, sprite sheets included - with HoovyTools'
# own reader: SourceIO doesn't have to be installed. Each image is shown on
# a preview sphere at the 3D cursor (collection "HT · Material Previews",
# on a material made for it), so you see it at once; it is also in every
# Image Editor and Image Texture node.
#
# HOW: set the values below, press Run Script (Alt+P). Each image's name and
# size prints to the console (Window > Toggle System Console).
#
# Needs the SFM Session Importer add-on (3.0.10 or newer) installed
#
# this feature was added in version 3.0.0 and is in experimental stage.
# (V2: SPAWN_PREVIEW_SPHERE - ADDED IN VERSION 3.0.10.)
# =============================================================================

VTF_FILES = [r""]           #one or more .vtf files: [r"C:\...\a.vtf", r"C:\...\b.vtf"]
SPAWN_PREVIEW_SPHERE = True  # put each texture on a UV sphere at the 3D cursor, one next to the other

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
        raise RuntimeError("SFM Session Importer 3.0.10+ is not installed - install it, then run this again")


def main():
    files = [f for f in VTF_FILES if f.strip()]
    if not files:
        raise RuntimeError("Set VTF_FILES at the top of this script to one or more .vtf files")
    session_importer()
    for f in files:
        result = bpy.ops.ht.import_vtf(filepath=f, spawn_sphere=SPAWN_PREVIEW_SPHERE)
        print("[SFM Session Importer]  Import VTF %s: %s" % (sorted(result)[0], f))


main()
