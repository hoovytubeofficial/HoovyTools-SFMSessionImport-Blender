# =============================================================================
#  Import VMT (V1)
#  The Text Editor version of  SFM Session Importer > Tools > HoovyTools
#  Importers > 2 Import VMT  (SFM Session Importer 3.0.0).
# =============================================================================
#
#  WHAT IT DOES: builds a Blender material from each .vmt - its shader, its
#  textures (found through your SFM install and the folders around the file)
#  and their settings, packed into the .blend - with HoovyTools' own reader:
#  SourceIO does not have to be installed. With a mesh active, the materials
#  are added to it.
#
#  HOW: set the values below, press Run Script (Alt+P). What it made, and
#  every texture it could not find, prints to the console (Window > Toggle
#  System Console).
#
#  Needs the SFM Session Importer add-on (3.0.0 or newer) installed.
#
#  THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE.
# =============================================================================

VMT_FILES = [r""]           # one or more .vmt files: [r"C:\...\a.vmt", r"C:\...\b.vmt"]
SOURCE_SHADING = True       # True = VertexLitGeneric with the Source look (phong, rim, tint); False = plain Principled
ADD_TO_ACTIVE_MESH = True   # add every material to the active mesh's material slots

# -----------------------------------------------------------------------------

import addon_utils
import bpy

NAMES = ("HoovyTools-SFMSessionImport-Blender-Master", "HoovyTools-SFMSessionImport-Blender-master",
         "HoovyTools-SFMSessionImport-Blender-main")


def session_importer():
    """Make sure the add-on is on - enabled here ONLY when it is installed and off (enabling twice re-registers it
    under this running script)."""
    if "import_vmt" in dir(bpy.ops.ht):
        return
    installed = {m.__name__ for m in addon_utils.modules()}
    for name in NAMES:
        if name in installed:
            addon_utils.enable(name, default_set=True)
            break
    if "import_vmt" not in dir(bpy.ops.ht):
        raise RuntimeError("SFM Session Importer 3.0.0+ is not installed - install it, then run this again")


def main():
    files = [f for f in VMT_FILES if f.strip()]
    if not files:
        raise RuntimeError("Set VMT_FILES at the top of this script to one or more .vmt files")
    session_importer()
    for f in files:
        result = bpy.ops.ht.import_vmt(filepath=f, use_bvlg=SOURCE_SHADING, assign=ADD_TO_ACTIVE_MESH)
        print("[SFM Session Importer]  Import VMT %s: %s" % (sorted(result)[0], f))


main()
