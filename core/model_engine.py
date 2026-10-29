"""
model_engine.py  -  part of SFM to Blender (Session Importer)      [1.21.0]
====================================================================

WHICH MODEL IMPORTER, AND WITH WHICH TEXTURES.

ENGINE
------
    SOURCEIO   SourceIO's own MDL operator - when it is installed AND
               DEVELOPER > Model Importer > Use SourceIO is on.
    EMBEDDED   the importer inside this add-on (importers/Standalone_MDL.py,
               SourceIO's code carried in one file since 1.19.0). Used when
               the switch is off, and whenever SourceIO is missing.

Both build the same thing - an armature, its meshes, a collection named after
the model - so everything after the import (rename, bodygroups, eye fix, rig
fixer, animation) does not know or care which one ran.

TEXTURES
--------
    FULL    every texture at its full size (what every version before 1.21.0
            did)
    PROXY   no full textures; each material gets a SMALL copy of its own base
            texture instead (the VTF's mip at 64 px or less, core/
            proxy_textures.py; 1.25.0: a VTF with no mip that small is
            sampled down to it, one image per VTF) - the look survives, the
            import is quick and a saved .blend stays small
    NONE    no images at all - the quickest, for work that needs only the rig
            and the body (transposing animation to send back to SFM)
"""

import addon_utils
from pathlib import Path
import bpy

ENGINES = ("SOURCEIO", "EMBEDDED")
TEXTURES = ("FULL", "PROXY", "NONE")
_SOURCEIO_MODULES = ("SourceIO-master", "SourceIO", "io_import_source", "blender_source_io")


def _prefs():
    try:
        from . import paths
        return paths.addon_prefs()
    except Exception:                                         # noqa: BLE001
        return None


def use_sourceio():
    """DEVELOPER > Model Importer: SourceIO only when picked (3.0.0: HoovyTools by default)"""
    p = _prefs()
    return False if p is None else bool(getattr(p, "use_sourceio", False))


def sourceio_ready(enable=False):
    """SourceIO's MDL operator is registered. enable=True first tries to switch an installed but disabled SourceIO
    on (the session import always did that)."""
    try:
        bpy.ops.sourceio.mdl.get_rna_type()
        return True
    except Exception:                                         # noqa: BLE001
        pass
    if not enable:
        return False
    for name in _SOURCEIO_MODULES:
        try:
            if addon_utils.enable(name, default_set=True) is not None:
                bpy.ops.sourceio.mdl.get_rna_type()
                return True
        except Exception:                                     # noqa: BLE001
            continue
    return False


def engine(enable=True):
    """"SOURCEIO" or "EMBEDDED" - what an import will use right now"""
    if use_sourceio() and sourceio_ready(enable=enable):
        return "SOURCEIO"
    return "EMBEDDED"


def why():
    """one line for the panel: which engine and why"""
    if not use_sourceio():
        return "Embedded importer (SourceIO switched off here)"
    if sourceio_ready(enable=False):
        return "SourceIO (installed and on)"
    return "Embedded importer (SourceIO not installed / not enabled)"


def textures(scene=None):
    """the session import's Textures choice: FULL / PROXY / NONE"""
    scene = scene or getattr(bpy.context, "scene", None)
    pr = getattr(scene, "ht_project", None) if scene is not None else None
    t = str(getattr(pr, "session_textures", "FULL") or "FULL").upper()
    return t if t in TEXTURES else "FULL"


def import_mdl(abs_path, texture_mode="FULL", scale=1.0, eng=None):
    """Import one .mdl with the chosen engine. Returns (ok, engine used, the objects it made, note).
    PROXY and NONE both import without textures; PROXY's small images are added by the caller
    (proxy_textures.apply) once the objects exist."""
    eng = eng or engine()
    before = set(bpy.data.objects)
    full = str(texture_mode).upper() == "FULL"
    note = ""
    if eng == "SOURCEIO":
        kw = dict(filepath=str(abs_path), files=[{"name": abs_path.name}], discover_resources=True,
                  import_textures=full, import_physics=False, import_animations=False, scale=float(scale))
        if bpy.app.version >= (4, 1, 0):
            kw["directory"] = str(abs_path.parent)
        result = bpy.ops.sourceio.mdl(**kw)
        ok = "FINISHED" in result
        if not ok:
            note = "SourceIO returned %s" % (result,)
    else:
        from ..importers import Import_MDL
        try:
            rep = Import_MDL.import_embedded(str(abs_path), scale=float(scale), import_textures=full)
            ok = True
            if rep and rep.get("warnings"):
                note = "%d warning(s)" % len(rep["warnings"])
        except Exception as exc:                              # noqa: BLE001
            ok, note = False, "embedded importer: %s" % exc
    fresh = [o for o in bpy.data.objects if o not in before]
    if ok:
        # 3.0.0: the model's face rules as a .qc, so the HWM bake runs on any model (importers/Import_Shape_Keys)
        try:
            from ..importers import Import_Shape_Keys
            _qc, qnote, qstate = Import_Shape_Keys.ensure_face_qc(abs_path, fresh)
            if qstate in ("wrote", "error"):
                print("[MODEL]  face data, %s: %s" % (Path(abs_path).name, qnote))
        except Exception as exc:                              # noqa: BLE001
            print("[MODEL]  face data skipped for %s: %s" % (Path(abs_path).name, exc))
    return ok, eng, fresh, note
