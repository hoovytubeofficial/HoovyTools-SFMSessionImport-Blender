"""
Import_Materials.py  -  part of SFM Session Importer (3.0.0)
============================================================

Import VMT and Import VTF without SourceIO installed.

HOW. The embedded MDL importer (importers/Standalone_MDL.py) carries SourceIO's own code and its texture decoder,
unpacked into a private package. Its texture and material loaders are the same functions SourceIO's own "Import
VTF" / "Import VMT" call, so these two buttons call them there - SourceIO itself is never touched and does not have
to be installed. This module is where a HoovyTools VMT importer grows from: today it hands the parsed VMT to the
carried shader builders, tomorrow it can build its own nodes and keep the same buttons.

The browsers open in usermod/materials and learn the folder you use (core/start_folders.py).
"""

from pathlib import Path

import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper

from ..core import start_folders

_ht_icon_id = None


def _carried():
    """The embedded SourceIO package, unpacked and loaded."""
    from . import Standalone_MDL
    cache = Standalone_MDL._bootstrap()
    return Standalone_MDL, cache


def _content_roots():
    try:
        from ..session.Import_Session import usermod_bases
        return [str(b) for b in usermod_bases()]
    except Exception:                                         # noqa: BLE001
        return []


def import_vtf(path):
    """One .vtf as a packed Blender image. Returns the image."""
    S, _cache = _carried()
    path = Path(bpy.path.abspath(str(path)))
    if not path.is_file():
        raise FileNotFoundError("no such file: %s" % path)
    vtf = S._module("blender_bindings.source1.vtf")
    TinyPath = S._module("library.utils.tiny_path").TinyPath
    with path.open("rb") as fh:
        image = vtf.import_texture(TinyPath(path.name), fh, True)
    if image is None:
        raise RuntimeError("%s could not be decoded" % path.name)
    try:
        if not image.packed_file:
            image.pack()
    except Exception:                                         # noqa: BLE001
        pass
    return image


def import_vmt(path, use_bvlg=True, assign_to=None):
    """One .vmt as a Blender material, its textures found through your SFM install and the folders around the
    file. Returns (material, missing textures)."""
    S, cache = _carried()
    path = Path(bpy.path.abspath(str(path))).resolve()
    if not path.is_file():
        raise FileNotFoundError("no such file: %s" % path)
    S._load_shader_assets(cache)
    manager, warnings = S._mounted_content(path, _content_roots())
    #the folder ABOVE materials\ is a game root too - a loose .vmt names its textures from there
    loose = S._module("library.shared.content_manager.providers.loose_files").LooseFilesContentProvider
    TinyPath = S._module("library.utils.tiny_path").TinyPath
    for parent in path.parents:
        if parent.name.lower() == "materials":
            manager.add_child(loose(TinyPath(str(parent.parent))))
            break
    missing = []
    shader_cls = S._module("blender_bindings.material_loader.shaders.source1_shader_base").Source1ShaderBase
    old_load = shader_cls.load_texture

    def tracked(self, name, tex_path):
        image = old_load(self, name, tex_path)
        if image is None:
            missing.append(str(tex_path / name) + ".vtf")
        return image

    shader_cls.load_texture = tracked
    try:
        VMT = S._module("library.source1.vmt").VMT
        FileBuffer = S._module("library.utils").FileBuffer
        registry = S._module("blender_bindings.material_loader.material_loader").ShaderRegistry
        bpy_utils = S._module("blender_bindings.utils.bpy_utils")
        shader_cls.use_bvlg(bool(use_bvlg))
        mat = bpy_utils.get_or_create_material(path.stem, path.as_posix())
        if mat.get("source_loaded"):
            del mat["source_loaded"]
        with FileBuffer(TinyPath(str(path))) as stream:
            vmt = VMT(stream, TinyPath(str(path)), manager)
        registry.source1_create_nodes(manager, mat, vmt, {})
    finally:
        shader_cls.load_texture = old_load
        manager.first_import = None
        manager.priority_list = None
    if assign_to is not None and getattr(assign_to, "type", "") == "MESH":
        if mat.name not in [s.material.name for s in assign_to.material_slots if s.material]:
            assign_to.data.materials.append(mat)
    return mat, missing + [w for w in warnings if "texture" in w.lower()]


class _Picker:
    # filepath comes from ImportHelper; these two make the browser take several files at once
    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})  # type: ignore
    files: CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    def picked(self):
        if self.files and self.directory:
            return [Path(self.directory) / f.name for f in self.files if f.name]
        return [Path(self.filepath)] if self.filepath else []


@start_folders.browser_at("material")
class HT_OT_import_vmt(_Picker, Operator, ImportHelper):
    """Import Source .vmt materials - without SourceIO

Builds a Blender material from each .vmt: its shader, its textures (found
through your SFM install and the folders around the file) and their
settings, packed into the .blend. With a mesh selected, the materials are
added to it. The browser opens in usermod/materials and learns the folder
you use most.

THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.import_vmt"
    bl_label = "Import VMT"
    bl_options = {"UNDO"}

    filename_ext = ".vmt"
    filter_glob: StringProperty(default="*.vmt", options={"HIDDEN"})  # type: ignore
    use_bvlg: BoolProperty(  # type: ignore
        name="Source Shading (VertexLitGeneric)",
        description="Build VertexLitGeneric materials with the Source look (phong, rim, tint) instead of a plain "
                    "Principled BSDF",
        default=True)
    assign: BoolProperty(  # type: ignore
        name="Add To The Selected Mesh",
        description="Add every imported material to the active mesh's material slots",
        default=True)

    def execute(self, context):
        files = [f for f in self.picked() if f.suffix.lower() == ".vmt"]
        if not files:
            self.report({"ERROR"}, "Pick one or more .vmt files")
            return {"CANCELLED"}
        target = context.active_object if self.assign else None
        made, missing, failed = [], [], []
        for f in files:
            try:
                mat, miss = import_vmt(f, self.use_bvlg, target)
                made.append(mat.name)
                missing += miss
            except Exception as exc:                          # noqa: BLE001
                failed.append("%s: %s" % (f.name, exc))
                print("[MATERIALS]  %s failed - %s: %s  (%s)" % (f.name, type(exc).__name__, exc, f))
        for m in missing:
            print("[MATERIALS]  missing texture: %s" % m)
        if not made:
            self.report({"ERROR"}, "No material imported - " + "; ".join(failed[:3]))
            return {"CANCELLED"}
        msg = "%d material(s): %s" % (len(made), ", ".join(made[:4]))
        if missing:
            msg += " - %d texture(s) not found (console lists them)" % len(missing)
        if failed:
            msg += " - %d failed" % len(failed)
        self.report({"WARNING" if (missing or failed) else "INFO"}, msg)
        return {"FINISHED"}


@start_folders.browser_at("texture")
class HT_OT_import_vtf(_Picker, Operator, ImportHelper):
    """Import Source .vtf textures - without SourceIO

Decodes each .vtf into a Blender image, packed into the .blend (every
format SFM uses, sprite sheets included). Open it in an Image Editor or
pick it in any Image Texture node. The browser opens in usermod/materials
and learns the folder you use most.

THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.import_vtf"
    bl_label = "Import VTF"
    bl_options = {"UNDO"}

    filename_ext = ".vtf"
    filter_glob: StringProperty(default="*.vtf", options={"HIDDEN"})  # type: ignore

    def execute(self, context):
        files = [f for f in self.picked() if f.suffix.lower() == ".vtf"]
        if not files:
            self.report({"ERROR"}, "Pick one or more .vtf files")
            return {"CANCELLED"}
        made, failed = [], []
        for f in files:
            try:
                img = import_vtf(f)
                made.append("%s (%dx%d)" % (img.name, img.size[0], img.size[1]))
            except Exception as exc:                          # noqa: BLE001
                failed.append("%s: %s" % (f.name, exc))
                print("[MATERIALS]  %s failed - %s: %s  (%s)" % (f.name, type(exc).__name__, exc, f))
        if not made:
            self.report({"ERROR"}, "No texture imported - " + "; ".join(failed[:3]))
            return {"CANCELLED"}
        # show the first one where an Image Editor is open
        try:
            img = bpy.data.images.get(made[0].rsplit(" (", 1)[0])
            for area in context.screen.areas if context.screen else ():
                if area.type == "IMAGE_EDITOR" and img is not None:
                    area.spaces.active.image = img
                    break
        except Exception:                                     # noqa: BLE001
            pass
        self.report({"WARNING" if failed else "INFO"},
                    "%d texture(s): %s%s" % (len(made), ", ".join(made[:3]),
                                             (" - %d failed" % len(failed)) if failed else ""))
        return {"FINISHED"}


_CLASSES = (HT_OT_import_vmt, HT_OT_import_vtf)


def register(icon_id_fn=None):
    global _ht_icon_id
    _ht_icon_id = icon_id_fn
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
