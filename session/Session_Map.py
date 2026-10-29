"""
Session_Map.py  -  part of SFM Session Importer (3.0.0)
=======================================================

The shot's map, as the session import's last step - in ONE collection, lined up with the session.

WHICH MAP. Every shot (DmeFilmClip) names the map it plays on in `mapname` ("maps/stage_simple.bsp"). One shot:
its map. The whole session: the map most of its shots use (a session usually plays on one).

WHERE. The same search folders the models come from (gameinfo + every mount). A map that only exists inside a
VPK (SFM's own stock maps) cannot be handed to SourceIO by path - the step says so instead of failing the import.

HOW. SourceIO's BSP importer at the session's scale (1 Hammer unit = 1 Blender unit, like the models), then every
object it made is moved into one `Map - <name>` collection under the scene, and the collections SourceIO made - now
empty - are removed. A second run finds that collection and leaves the map alone.

LINED UP. Every session element goes through ONE world map, SFM (x, y, z) -> Blender (y, -x, z), which is Rz(-90)
about the origin (importers/Import_DMX_Animation.py, the AXIS note - proved by the angle two objects subtend at the
camera). SourceIO brings a map in raw Source coordinates, so without the same turn the map sits 90 degrees off
everything the session put in it. The map's ROOT objects get Rz(-90); their children follow. The collection is
marked `ht_world_map`, so a map imported before this fix is turned into place on the next run, and never twice.
"""

import math
from pathlib import Path

import bpy
from bpy.types import Operator
from mathutils import Matrix

from ..core import Progress

COLLECTION_PREFIX = "Map - "
WORLD_MARK = "ht_world_map"
#  The session's world map: (x, y, z) -> (y, -x, z).
WORLD = Matrix.Rotation(-math.pi / 2.0, 4, 'Z')
#  No SourceIO: the map is left out, everything else imports - the models come in with HoovyTools' own importer.
SKIPPED_NO_SOURCEIO = {"map": None, "skipped": "sourceio",
                       "note": "left out - SourceIO is not installed, and maps import through it (the models do not "
                               "need it)"}


def map_names(session_path, shot_index=-1, shot_name=""):
    """The .bsp paths the chosen shot (or the whole session) plays on, most used first."""
    from . import Session_Reader, Session_Paths
    model = Session_Reader.load_session_model(session_path)
    fps = Session_Reader.session_fps(model.root) or 24.0
    shots = Session_Reader.shots(model, fps)
    chosen, _note = Session_Paths.resolve_shot(shots, shot_index, shot_name)
    counts = {}
    for s in ([chosen] if chosen is not None else shots):
        el = s.get("element")
        name = el.get("mapname") if el is not None else None
        if name:
            counts[str(name)] = counts.get(str(name), 0) + 1
    if not counts:
        clip = model.root.get("activeClip")
        name = clip.get("mapname") if clip is not None else None
        if name:
            counts[str(name)] = 1
    return sorted(counts, key=lambda n: -counts[n])


def find_map(rel):
    """The loose .bsp for a mapname, searched like the models are. (path or None, folders searched)."""
    from .Import_Session import _build_search_paths
    rel = str(rel).replace("\\", "/").lstrip("/")
    if not rel.lower().endswith(".bsp"):
        rel += ".bsp"
    if not rel.lower().startswith("maps/"):
        rel = "maps/" + rel
    dirs = _build_search_paths()
    for d in dirs:
        p = Path(d) / rel
        if p.is_file():
            return p, len(dirs)
    return None, len(dirs)


def _depth(coll, parents):
    n, c = 0, coll
    while c in parents:
        c = parents[c]
        n += 1
    return n


def line_up(context, coll):
    """Turn the map in `coll` onto the session's world map - its root objects only, once. Returns how many."""
    if coll.get(WORLD_MARK):
        return 0
    Progress.note("lining the map up with the session")
    context.view_layer.update()
    objs = set(coll.objects)
    roots = [o for o in objs if o.parent is None or o.parent not in objs]
    for o in roots:
        o.matrix_world = WORLD @ o.matrix_world
    coll[WORLD_MARK] = "(x, y, z) -> (y, -x, z)"
    return len(roots)


def import_map(context, session_path, shot_index=-1, shot_name=""):
    """Import the shot's map into one collection. Returns a dict; raises only for a real failure."""
    Progress.note("which map the shot plays on")
    names = map_names(session_path, shot_index, shot_name)
    if not names:
        return {"map": None, "note": "the session names no map"}
    from ..core import model_engine
    if not model_engine.sourceio_ready(enable=True):
        return dict(SKIPPED_NO_SOURCEIO)
    rel = names[0]
    path, n_dirs = find_map(rel)
    if path is None:
        raise FileNotFoundError("%s is not a loose file in any of the %d search folders - a stock map that lives "
                                "inside a VPK cannot be imported by path" % (rel, n_dirs))
    return import_map_file(context, path)


def import_map_file(context, path):
    """One .bsp through SourceIO, everything it makes in ONE collection 'Map - <name>', lined up with the session.
    Returns a dict."""
    path = Path(path)
    coll_name = COLLECTION_PREFIX + path.stem
    existing = bpy.data.collections.get(coll_name)
    if existing is not None and existing.objects:
        turned = line_up(context, existing)
        note = ("lined up with the session (%d root object(s) turned) - it was imported before the fix" % turned
                if turned else "already in the scene (%s)" % coll_name)
        return {"map": str(path), "note": note, "objects": len(existing.objects), "collection": coll_name}
    from ..core import model_engine
    if not model_engine.sourceio_ready(enable=True):
        return dict(SKIPPED_NO_SOURCEIO)

    before_o = set(bpy.data.objects)
    before_c = set(bpy.data.collections)
    kw = dict(filepath=str(path), files=[{"name": path.name}], discover_resources=True, scale=1.0)
    if bpy.app.version >= (4, 1, 0):
        kw["directory"] = str(path.parent)
    Progress.note("%s through SourceIO - one long step, Blender looks busy until it is in" % path.name)
    result = bpy.ops.sourceio.bsp(**kw)
    if "FINISHED" not in result:
        raise RuntimeError("SourceIO returned %s for %s" % (result, path.name))
    new_o = [o for o in bpy.data.objects if o not in before_o]
    new_c = [c for c in bpy.data.collections if c not in before_c]

    target = existing or bpy.data.collections.new(coll_name)
    if target.name not in context.scene.collection.children:
        context.scene.collection.children.link(target)
    for n_obj, o in enumerate(new_o, 1):
        Progress.update(n_obj, len(new_o), "into %s" % coll_name)
        for c in list(o.users_collection):
            c.objects.unlink(o)
        target.objects.link(o)
    #  SourceIO's own collections hold nothing now - deepest first, so a parent empties after its children
    parents = {}
    for c in bpy.data.collections:
        for ch in c.children:
            parents[ch] = c
    for c in sorted(new_c, key=lambda c: _depth(c, parents), reverse=True):
        if c is target or c.objects or c.children:
            continue
        bpy.data.collections.remove(c)
    turned = line_up(context, target)
    return {"map": str(path), "objects": len(new_o), "collection": target.name, "turned": turned,
            "note": "%d object(s) in %s, lined up with the session" % (len(new_o), target.name)}


class HT_OT_step_map(Operator):
    """Import the map the shot plays on - through SourceIO, at the session's scale - into ONE collection,
'Map - <name>', lined up with everything the session put in the scene. The whole session: the map most of
its shots use. A map already imported is left alone; a stock map that only lives inside a VPK is reported,
not imported.

THIS FEATURE WAS ADDED IN VERSION 3.0.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.step_map"
    bl_label = "8  Import Map"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        from . import Session_Paths
        return Session_Paths.session_file(context.scene) is not None

    @Progress.jobbed_execute("SFM Session Importer - 8  Import Map")
    def execute(self, context):
        from . import Session_Paths
        session = Session_Paths.session_file(context.scene)
        idx, name = Session_Paths.shot_choice(context.scene)
        try:
            r = import_map(context, session, shot_index=idx, shot_name=name)
        except Exception as exc:                              # noqa: BLE001
            print("[MAP]  %s: %s" % (type(exc).__name__, exc))
            self.report({"ERROR"}, "Map: %s" % exc)
            return {"CANCELLED"}
        if not r.get("map"):
            self.report({"WARNING"}, "Map: %s" % r.get("note", "the session names no map"))
            return {"CANCELLED"}
        print("[MAP]  %s - %s" % (r["map"], r.get("note", "")))
        self.report({"INFO"}, "Map: %s - %s" % (Path(r["map"]).name, r.get("note", "")))
        return {"FINISHED"}


_CLASSES = (HT_OT_step_map,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
