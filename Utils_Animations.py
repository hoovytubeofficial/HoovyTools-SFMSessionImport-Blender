"""
Utils_Animations.py  —  part of HoovyTools
===========================================
Adds:  File ▸ Import ▸ Source Engine (HoovyTools) ▸ Source Engine Utils ▸ Animation ▸
           Import SMD / DMX

A direct surface to the SST import_smd operator (ht.import_smd).
Unlike Import_DMX_Animation, this applies NO root transform correction,
NO scale patching, and NO axis empties — it is the raw importer, now
fixed for Blender 5.0 via anim_compat.

Use this when you want exactly what the original Blender Source Tools
importer gave you: the action goes straight onto the selected armature
with whatever up-axis and rotation mode you choose.
"""

bl_info = {
    "name":        "HoovyTools: Utils — Animations",
    "description": "Raw SMD / DMX importer utility for the HoovyTools pipeline",
    "author":      "HoovyTools",
    "version":     (1, 0, 0),
    "blender":     (4, 0, 0),
    "location":    "File > Import > Source Engine (HoovyTools) > Source Engine Utils > Animation",
    "category":    "Import-Export",
}

import bpy
from bpy.types import Menu


# ──────────────────────────────────────────────────────────────────────────────
#  ICON HELPER
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}


# ──────────────────────────────────────────────────────────────────────────────
#  MENU
# ──────────────────────────────────────────────────────────────────────────────

class MT_HT_utils_anim_submenu(Menu):
    bl_idname = "MT_HT_utils_anim_submenu"
    bl_label  = "Animation"

    def draw(self, context):
        self.layout.operator(
            "ht.import_smd",
            text="Import SMD / DMX",
            **_icon_id("import_dmx_anim", "ACTION"),
        )


def draw_utils_anim_entry(layout):
    """Called from MT_HT_utils_submenu in __init__.py."""
    layout.menu(
        MT_HT_utils_anim_submenu.bl_idname,
        text="Animation",
        **_icon_id("import_animations", "ANIM"),
    )


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER / UNREGISTER
# ──────────────────────────────────────────────────────────────────────────────

_CLASSES = (MT_HT_utils_anim_submenu,)


def register(icon_id_fn=None):
    global _ht_icon_id
    _ht_icon_id = icon_id_fn
    for cls in _CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
