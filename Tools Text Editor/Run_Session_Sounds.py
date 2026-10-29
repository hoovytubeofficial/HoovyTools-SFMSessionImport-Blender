# =============================================================================
#  HoovyTools - Session Sounds  (Text Editor edition)
# =============================================================================
#  Paste into Blender's Text Editor and press Run Script (Alt+P) to (re)register
#  the "6 Session Sounds" operator WITHOUT reinstalling the whole addon. Handy
#  while iterating on the tool - edit, Alt+P, test, repeat.
#
#  It reuses the installed addon's module if HoovyTools is enabled (so You get
#  the bundled SST datamodel and the usermod path from preferences). If the
#  addon is not installed it falls back to loading the module file directly -
#  set ADDON_DIR below to Your HoovyTools folder in that case.
#
#  After running, launch it from the Text Editor console with:
#       import bpy; bpy.ops.ht.import_session_sounds('INVOKE_DEFAULT')
#  or bind it, or just call the File > Import entry it registers.
# =============================================================================

import bpy
import sys
import os
import importlib

# ---- 1. Try the installed addon first -------------------------------------
_MOD = None
for _key in list(sys.modules.keys()):
    if _key.endswith("Import_Session_Sounds") and "HoovyTools" in _key:
        _MOD = importlib.reload(sys.modules[_key])
        break

# ---- 2. Fall back to loading the file directly ----------------------------
if _MOD is None:
    # EDIT THIS if the addon is not installed as an extension:
    ADDON_DIR = r"C:\Users\You\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\HoovyTools"
    if os.path.isdir(ADDON_DIR):
        parent = os.path.dirname(ADDON_DIR)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        pkg = os.path.basename(ADDON_DIR)
        _MOD = importlib.import_module(f"{pkg}.Import_Session_Sounds")
        importlib.reload(_MOD)
    else:
        raise RuntimeError(
            "HoovyTools not found. Enable the addon, or set ADDON_DIR in this "
            "script to Your HoovyTools folder."
        )

# ---- 3. Register just this operator ---------------------------------------
try:
    _MOD.unregister()
except Exception:
    pass
_MOD.register()  # icon_id_fn stays None here - falls back to the stock SOUND icon

print("[HoovyTools] Session Sounds (Text Editor) registered.")
print("             Run:  bpy.ops.ht.import_session_sounds('INVOKE_DEFAULT')")
