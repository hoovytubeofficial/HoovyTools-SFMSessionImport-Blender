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
        from ..session.Import_Session import search_bases       #3.0.9: + other drives (option)
        return [str(b) for b in search_bases()]
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
    if not _has_output(mat):
        basetexture_fallback(mat, path)
    if assign_to is not None and getattr(assign_to, "type", "") == "MESH":
        if mat.name not in [s.material.name for s in assign_to.material_slots if s.material]:
            assign_to.data.materials.append(mat)
    return mat, missing + [w for w in warnings if "texture" in w.lower()]


PREVIEW_COLLECTION = "HT · Material Previews"
PREVIEW_RADIUS = 0.5
_SPHERE_HELP = ("Put a UV sphere with each imported %s in the scene, in a row from the 3D cursor (collection "
                "\"HT · Material Previews\"), so you see it at once. THIS FEATURE WAS ADDED IN VERSION 3.0.10 AND "
                "IS IN EXPERIMENTAL STAGE")


def spawn_preview_sphere(context, material, index=None, name=None):
    """A smooth UV sphere (UVs on) wearing `material`, `index` places to the right of the 3D cursor - by default the
    next free place in the preview collection, so a second import (or a script importing one file at a time) does
    not stack on the first. Returns it."""
    import bmesh
    scene = context.scene
    coll = bpy.data.collections.get(PREVIEW_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(PREVIEW_COLLECTION)
    if not any(c is coll for c in scene.collection.children_recursive):
        scene.collection.children.link(coll)
    label = name or "%s preview" % material.name
    me = bpy.data.meshes.new(label)
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")                          #calc_uvs fills a layer - it doesn't make one
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=PREVIEW_RADIUS, calc_uvs=True)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(label, me)
    ob.location = scene.cursor.location.copy()
    ob.location.x += (len(coll.objects) if index is None else index) * PREVIEW_RADIUS * 2.5
    ob["ht_preview_of"] = material.name
    coll.objects.link(ob)
    return ob


def texture_material(image):
    """A material that shows one imported image - colour and alpha - for a VTF's preview sphere. One per image."""
    for m in bpy.data.materials:
        if m.get("ht_preview_image") == image.name:
            return m
    mat = bpy.data.materials.new("%s vtf" % image.name.rsplit(".vtf", 1)[0])
    show_image(mat, image)
    mat["ht_preview_image"] = image.name
    return mat


def show_image(mat, image, additive=False):
    """(Re)build `mat` as one image: colour and alpha on a Principled BSDF - or, additive, as light (an Emission
    added over transparency, the way SFM draws an additive sprite)."""
    if mat.node_tree is None:                                 # Material.use_nodes is deprecated (6.0)
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.location = (-420, 0)
    if additive:
        em = nt.nodes.new("ShaderNodeEmission")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        add = nt.nodes.new("ShaderNodeAddShader")
        em.location, tr.location, add.location = (-120, -40), (-120, 120), (100, 0)
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        nt.links.new(tr.outputs[0], add.inputs[0])
        nt.links.new(em.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
    else:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (-80, 0)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):                 # EEVEE Next
        mat.surface_render_method = "BLENDED" if additive else "DITHERED"
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND" if additive else "HASHED"


def _has_output(mat):
    return mat.node_tree is not None and any(n.type == "OUTPUT_MATERIAL" for n in mat.node_tree.nodes)


def basetexture_fallback(mat, vmt_path):
    """3.0.10: a shader the carried importer cannot build (SpriteCard, UnlitTwoTexture ... - every particle
    material) left an EMPTY material, so its preview sphere showed nothing. Such a material now shows its
    $basetexture - as light when the .vmt is $additive. Returns the shader name, or '' when nothing was done."""
    import re
    try:
        text = Path(vmt_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    shader = (re.match(r'\s*"?([\w.]+)"?', text) or [None, "?"])[1]
    m = re.search(r'"?\$basetexture"?\s+"?([^"\r\n]+?)"?\s*$', text, re.I | re.M)
    if not m:
        return ""
    rel = m.group(1).strip().replace("\\", "/").removesuffix(".vtf") + ".vtf"
    roots = [p.parent for p in Path(vmt_path).resolve().parents if p.name.lower() == "materials"][:1]
    try:
        from ..session.Import_Session import _build_search_paths
        roots += list(_build_search_paths())
    except Exception:                                         # noqa: BLE001
        pass
    vtf = next((r / "materials" / rel for r in roots if (r / "materials" / rel).is_file()), None)
    if vtf is None:
        return ""
    additive = bool(re.search(r'"?\$(additive|addoverblend)"?\s+"?1', text, re.I))
    show_image(mat, import_vtf(vtf), additive)
    mat["ht_basetexture_fallback"] = shader
    return shader


def _select_only(context, objects):
    """Select the spawned spheres (the last one active) - nothing else."""
    try:
        for o in context.selected_objects:
            o.select_set(False)
        for o in objects:
            o.select_set(True)
        context.view_layer.objects.active = objects[-1]
    except Exception:                                         # noqa: BLE001 - hidden collection, no view layer
        pass


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
added to it, and each one gets a preview sphere at the 3D cursor (Spawn
Preview Sphere, on by default). The browser opens in usermod/materials and
learns the folder you use most.

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
    spawn_sphere: BoolProperty(  # type: ignore
        name="Spawn Preview Sphere",
        description=_SPHERE_HELP % "material",
        default=True)

    def execute(self, context):
        files = [f for f in self.picked() if f.suffix.lower() == ".vmt"]
        if not files:
            self.report({"ERROR"}, "Pick one or more .vmt files")
            return {"CANCELLED"}
        target = context.active_object if self.assign else None
        made, missing, failed, spheres = [], [], [], []
        for f in files:
            try:
                mat, miss = import_vmt(f, self.use_bvlg, target)
                made.append(mat.name)
                missing += miss
                if self.spawn_sphere:
                    spheres.append(spawn_preview_sphere(context, mat))
            except Exception as exc:                          # noqa: BLE001
                failed.append("%s: %s" % (f.name, exc))
                print("[MATERIALS]  %s failed - %s: %s  (%s)" % (f.name, type(exc).__name__, exc, f))
        for m in missing:
            print("[MATERIALS]  missing texture: %s" % m)
        if not made:
            self.report({"ERROR"}, "No material imported - " + "; ".join(failed[:3]))
            return {"CANCELLED"}
        msg = "%d material(s): %s" % (len(made), ", ".join(made[:4]))
        plain = [m for m in made if bpy.data.materials.get(m) and bpy.data.materials[m].get("ht_basetexture_fallback")]
        if plain:
            msg += " - %d shown by its base texture (%s is not built yet)" % (
                len(plain), bpy.data.materials[plain[0]]["ht_basetexture_fallback"])
        if spheres:
            _select_only(context, spheres)
            msg += " - on %d preview sphere(s)" % len(spheres)
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
format SFM uses, sprite sheets included), each shown on a preview sphere at
the 3D cursor (Spawn Preview Sphere, on by default). Open it in an Image
Editor or pick it in any Image Texture node. The browser opens in
usermod/materials and learns the folder you use most.

THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.import_vtf"
    bl_label = "Import VTF"
    bl_options = {"UNDO"}

    filename_ext = ".vtf"
    filter_glob: StringProperty(default="*.vtf", options={"HIDDEN"})  # type: ignore
    spawn_sphere: BoolProperty(  # type: ignore
        name="Spawn Preview Sphere",
        description=_SPHERE_HELP % "texture (on a material made for it)",
        default=True)

    def execute(self, context):
        files = [f for f in self.picked() if f.suffix.lower() == ".vtf"]
        if not files:
            self.report({"ERROR"}, "Pick one or more .vtf files")
            return {"CANCELLED"}
        made, failed, spheres = [], [], []
        for f in files:
            try:
                img = import_vtf(f)
                made.append("%s (%dx%d)" % (img.name, img.size[0], img.size[1]))
                if self.spawn_sphere:
                    spheres.append(spawn_preview_sphere(context, texture_material(img)))
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
        if spheres:
            _select_only(context, spheres)
        self.report({"WARNING" if failed else "INFO"},
                    "%d texture(s): %s%s%s" % (len(made), ", ".join(made[:3]),
                                               (" - on %d preview sphere(s)" % len(spheres)) if spheres else "",
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
