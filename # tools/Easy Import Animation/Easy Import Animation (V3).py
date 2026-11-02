# =============================================================================
# Easy Import Animation (V3)
# The Text Editor version of  SFM Session Importer > Tools > Main Tools >
# 2 Import Animation (.dmx) with EASY IMPORT on  (SFM Session Importer 3.0.4).
# =============================================================================
#
# WHAT IT does: puts one or more SFM animation .dmx files on a character for
# fixing - with Import With Model, the character itself is imported first
# (the model the .dmx was made for, or the one you name below; the eye fix
# on), its rest pose fixed and the result stood up. With Import With Model
# off, the animation goes on the SELECTED armature. The file's root
# transform is always kept.
#
# V3 (3.0.4): BAKE_ROOT - the placement baked onto the armature, no
# empties left; Make Upright measured over the whole take.
# V2 (3.0.3): MODEL works again (3.0.3 picks the model from a list - your
# 10 most imported, counted in the add-on's _config\usage.json) and
# ROOT_AT_ORIGIN puts the character at 0,0,0
#
# HOW: set the values below, press Run Script (Alt+P). What it did prints to
# the console (Window > Toggle System Console)
#
# Needs the SFM Session Importer add-on (3.0.4 or newer) installed
#
# THIS FEATURE WAS ADDED IN VERSION 3.0.4 AND IS IN EXPERIMENTAL STAGE.
# =============================================================================

DMX_FILES = [r""]           # one or more animation .dmx files: [r"C:\...\walk.dmx", r"C:\...\run.dmx"]
IMPORT_WITH_MODEL = True    # True = import the character too; False = onto the selected armature
MODEL = r""                 # the character's .mdl; "" = the model each .dmx names
IMPORTER = "EMBEDDED"       # "EMBEDDED" (HoovyTools' own importer) or "SOURCEIO"
FIX_REST_POSE = True        # the rig's rest pose from its Faulty Rigs reference
MAKE_UPRIGHT = True         # standing on +Z (a file lying on its side: a whole 90 deg turn)
ROOT_AT_ORIGIN = "OFF"      # "OFF" / "START" = at 0,0,0 on the first frame / "LOCK" = held at 0,0,0 (in place)
BAKE_ROOT = False           # True = root / axis / upright baked onto the armature object, the empties removed

# -----------------------------------------------------------------------------

import addon_utils
import bpy

NAMES = ("HoovyTools-SFMSessionImport-Blender-Master", "HoovyTools-SFMSessionImport-Blender-master",
         "HoovyTools-SFMSessionImport-Blender-main")


def session_importer():
    """the add-on on - enabled here ONLY when it is installed and off"""
    if "import_dmx_animation" in dir(bpy.ops.ht):
        return
    installed = {m.__name__ for m in addon_utils.modules()}
    for name in NAMES:
        if name in installed:
            addon_utils.enable(name, default_set=True)
            return
    raise SystemExit("EASY IMPORT: the SFM Session Importer add-on is not installed")


session_importer()
for path in [p for p in DMX_FILES if p]:
    kw = dict(filepath=path, easy_import=True, import_with_model=IMPORT_WITH_MODEL, model_engine=IMPORTER,
              fix_rest_pose=FIX_REST_POSE, make_upright=MAKE_UPRIGHT, root_origin=ROOT_AT_ORIGIN, bake_root=BAKE_ROOT)
    if MODEL:
        kw.update(model_pick="PATH", model_path=MODEL)
    r = bpy.ops.ht.import_dmx_animation(**kw)
    print("EASY IMPORT:", path, "->", r)
