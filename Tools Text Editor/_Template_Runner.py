# =============================================================================
#  HoovyTools - Text Editor Runner  (TEMPLATE)
# =============================================================================
#  A generic pattern for hot-reloading ONE HoovyTools tool from the Text
#  Editor while iterating on it. Copy this, set MODULE_NAME to the tool You
#  are working on, press Run Script (Alt+P).
#
#  MODULE_NAME is the file stem inside the HoovyTools folder, e.g.:
#       "Import_Session_Sounds"      -> ht.import_session_sounds
#       "Import_Animations"          -> ht.import_animations
#       "Import_DMX_Animation"       -> ht.import_dmx_animation
#       "Panel"                      -> the N-panel sidebar
#
#  Every tool module in HoovyTools exposes register(icon_id_fn=None) and
#  unregister(), so this runner works for all of them uniformly. Custom icons
#  are skipped here (stock Blender icons are used) - that only affects looks,
#  not function.
# =============================================================================

import bpy
import sys
import os
import importlib

MODULE_NAME = "Import_Session_Sounds"   # <-- change to the tool You are editing


def _find_installed(module_name):
    for key in list(sys.modules.keys()):
        if key.endswith(module_name) and "HoovyTools" in key:
            return importlib.reload(sys.modules[key])
    return None


def _load_from_disk(module_name):
    # EDIT if the addon is not installed:
    addon_dir = r"C:\Users\You\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\HoovyTools"
    if not os.path.isdir(addon_dir):
        raise RuntimeError(
            f"HoovyTools not found. Enable the addon or point addon_dir at it.")
    parent = os.path.dirname(addon_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    pkg = os.path.basename(addon_dir)
    mod = importlib.import_module(f"{pkg}.{module_name}")
    return importlib.reload(mod)


mod = _find_installed(MODULE_NAME) or _load_from_disk(MODULE_NAME)

try:
    mod.unregister()
except Exception:
    pass
mod.register()

print(f"[HoovyTools] {MODULE_NAME} registered from Text Editor.")
