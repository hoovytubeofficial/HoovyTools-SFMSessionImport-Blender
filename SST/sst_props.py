"""
HoovyTools/SST/sst_props.py
============================
Minimal Blender property groups that mirror the .vs properties
BST normally registers on Scene, Armature, and Mesh objects.

Only the attributes actually accessed by import_smd.py are defined here:

  bpy.types.Scene.ht_vs
    up_axis         — used in SmdImporter.invoke and QC import
    material_path   — written during DMX material discovery
    dmx_format      — read by State for encoding decision
    dmx_encoding    — read by State for encoding decision

  bpy.types.Armature.ht_vs
    implicit_zero_bone  — read during bone import
    legacy_rotation     — read during bone transform calc

  bpy.types.Mesh.ht_vs
    flex_stereo_mode    — written during flex shape import
    flex_stereo_vg      — written during flex shape import
"""

import bpy
from bpy.props import (StringProperty, BoolProperty, EnumProperty,
                       IntProperty, PointerProperty)
from bpy.types import PropertyGroup

axes = (('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", ""))


class SST_SceneProps(PropertyGroup):
    up_axis: EnumProperty(
        name="Up Axis",
        items=axes,
        default='Z',
    )
    material_path: StringProperty(
        name="Material Path",
        default="",
    )
    # dmx_format / dmx_encoding are written by import_smd when it detects
    # the DMX version.  Stored as strings to match BST behaviour.
    dmx_format: StringProperty(name="DMX Format", default="1_0")
    dmx_encoding: StringProperty(name="DMX Encoding", default="2")


class SST_ArmatureProps(PropertyGroup):
    implicit_zero_bone: BoolProperty(
        name="Implicit Zero Bone",
        default=True,
    )
    legacy_rotation: BoolProperty(
        name="Legacy Rotation",
        default=False,
    )
    # import_smd also reads action_selection in some paths
    action_selection: EnumProperty(
        name="Action Selection",
        items=(
            ('CURRENT',  "Current Action",  ""),
            ('FILTERED', "Action Filter",   ""),
        ),
        default='CURRENT',
    )


class SST_MeshProps(PropertyGroup):
    flex_stereo_mode: EnumProperty(
        name="Stereo Mode",
        items=(
            ('X',      "X Axis",       ""),
            ('Y',      "Y Axis",       ""),
            ('Z',      "Z Axis",       ""),
            ('VGROUP', "Vertex Group", ""),
        ),
        default='X',
    )
    flex_stereo_vg: StringProperty(
        name="Stereo Vertex Group",
        default="",
    )
    # Sharpness is referenced in flex.py stereo logic
    flex_stereo_sharpness: bpy.props.FloatProperty(
        name="Stereo Sharpness",
        default=90.0, min=0.0, max=100.0, subtype='PERCENTAGE',
    )


_PROP_CLASSES = (SST_SceneProps, SST_ArmatureProps, SST_MeshProps)

_registered = False


def register_props():
    global _registered
    for cls in _PROP_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass  # already registered by BST or previous call

    # ht_vs is our own namespace — completely independent of BST's .vs
    # Register unconditionally, no collision possible
    try:
        bpy.types.Scene.ht_vs = PointerProperty(type=SST_SceneProps)
    except Exception:
        pass
    try:
        bpy.types.Armature.ht_vs = PointerProperty(type=SST_ArmatureProps)
    except Exception:
        pass
    try:
        bpy.types.Mesh.ht_vs = PointerProperty(type=SST_MeshProps)
    except Exception:
        pass

    _registered = True
    print("[HoovyTools/SST]  minimal .vs property groups registered")


def unregister_props():
    global _registered
    if not _registered:
        return
    for attr in ("ht_vs",):
        for t in (bpy.types.Scene, bpy.types.Armature, bpy.types.Mesh):
            try:
                delattr(t, attr)
            except Exception:
                pass
    for cls in reversed(_PROP_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _registered = False
