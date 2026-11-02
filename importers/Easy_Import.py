"""
Easy_Import.py  -  part of HoovyTools (3.0.2)

EASY IMPORT for Import Animation (.dmx), the user (2026-10-30): "when we turn on EASY IMPORT at the bottom, some new
variables will appear. FIX REST POSE ... MAKE UPRIGHT ... IMPORT WITH MODEL ... it will import them with the eye fix
through our importer at default, we can use Source IO though. Make sure this does not mess up the session import, and
that this will make it easy for me to load animations for fixing, to quickly apply whichever character i want."

Used only by the Import Animation operator (Import_DMX_Animation.HT_OT_ImportDmxAnimation) when Easy Import is on. The
session import calls import_dmx_animation() directly and never reaches this module.

    dmx_models(path)              the models/... .mdl paths the .dmx names (SFM's own exports carry one, an Export
                                  Helper file its template's and its own)
    pick_model(dmx, chosen, ...)  the .mdl to import: yours, else the one the file names whose skeleton matches it best
    import_model(path, engine,    the character, through Import Model (.mdl) - the eye fix on, the rest pose fixed when
                 fix_rest)        asked - with the Embedded importer (default) or SourceIO; its new armature
    make_upright(arm, frame)      the character turned to stand up (pelvis -> head along +Z) by a static empty above
                                  its hierarchy, so the root motion's keys never fight the turn
"""
import math
import os
import re
import struct
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

UPRIGHT = "_upright"                      # the empty's name suffix and its tag
UPRIGHT_TOL_DEG = 20.0                    # off up by less than this: already standing, nothing added
HEADS = ("bip_head", "valvebiped.bip01_head1", "head", "head1", "mixamorig:head")
PELVES = ("bip_pelvis", "valvebiped.bip01_pelvis", "pelvis", "hips", "mixamorig:hips")
_MDL_RE = re.compile(rb"models[/\\][\w ./\\\-]+?\.mdl", re.IGNORECASE)


def dmx_models(dmx_path):
    """the models/... .mdl paths a .dmx names, in the order they appear, each once (text or binary - read raw)"""
    try:
        data = Path(dmx_path).read_bytes()
    except OSError:
        return []
    out = []
    for m in _MDL_RE.finditer(data):
        rel = m.group(0).decode("latin-1").replace("\\", "/")
        if rel.lower() not in [x.lower() for x in out]:
            out.append(rel)
    return out


def mdl_bone_names(path):
    """the bone names of a .mdl (studiohdr: count @156, offset @160, 216-byte bones, name offset first)"""
    try:
        b = Path(path).read_bytes()
        n, idx = struct.unpack_from("<ii", b, 156)
        names = []
        for i in range(max(0, min(n, 4096))):
            o = idx + i * 216
            p = o + struct.unpack_from("<i", b, o)[0]
            e = b.index(b"\0", p)
            names.append(b[p:e].decode("latin-1"))
        return names
    except Exception:                                          # noqa: BLE001
        return []


def _file_bones(dmx_path):
    try:
        from .Import_DMX_Animation import _get_datamodel, animated_bone_names
        return {n.lower() for n in animated_bone_names(_get_datamodel().load(str(dmx_path)))}
    except Exception:                                          # noqa: BLE001
        return set()


def pick_model(dmx_path, chosen="", log=print):
    """(absolute .mdl path or None, how it was found)"""
    if chosen:
        p = Path(bpy.path.abspath(chosen))
        return (str(p), "yours") if p.is_file() else (None, "your model was not found: %s" % p)
    from ..session import Import_Session
    dirs = Import_Session._build_search_paths()
    found = []
    for rel in dmx_models(dmx_path):
        hit = Import_Session._resolve_model(rel, dirs)
        if hit is not None:
            found.append((rel, str(hit)))
    if not found:
        return None, "the .dmx names no model that is on disk - choose one in Model"
    if len(found) == 1:
        return found[0][1], "the file's own (%s)" % found[0][0]
    want = _file_bones(dmx_path)
    scored = sorted(found, key=lambda rp: -len(want & {n.lower() for n in mdl_bone_names(rp[1])}))
    log("[DMX_ANIM]  easy import: the file names %d models - %s matches its bones best" % (len(found), scored[0][0]))
    return scored[0][1], "the file's own, best skeleton match (%s)" % scored[0][0]


def import_model(path, engine="EMBEDDED", fix_rest=True):
    """the model through Import Model (.mdl): eye fix on, rest pose fixed when asked, scale 1. Returns its new
    armature (or raises)"""
    before = set(bpy.data.objects)
    kw = dict(filepath=str(path), apply_eye_fix=True, fix_rig=bool(fix_rest), scale=1.0)
    if "engine" in bpy.ops.ht.import_mdl.get_rna_type().properties:
        kw["engine"] = engine
    r = bpy.ops.ht.import_mdl(**kw)
    if "FINISHED" not in r:
        raise RuntimeError("Import Model did not finish for %s" % Path(path).name)
    arms = [o for o in bpy.data.objects if o not in before and o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError("%s came in without an armature" % Path(path).name)
    arm = max(arms, key=lambda o: len(o.data.bones))
    for o in bpy.context.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    return arm


# ------------------------------------------------------------------ 3.0.3 YOUR MODELS
#the user: "Cannot activate a file selector dialog, one already open" (Model's folder button inside Import
#Animation's own file browser) / "in config, let's write down which models we imported and how many times and add +1
#every time we import and we will get 10 most imported models there + option to add path"
#counted in _config/usage.json (core/usage.py): every Import Model +1, every animation onto a model +1
DMX_ID, PATH_ID = "DMX", "PATH"
TOP = 10
_ITEMS = []                                   # Blender reads enum items lazily: they must outlive the call


def _id(path):
    import hashlib
    from ..core import usage
    return "M" + hashlib.md5(usage.key(path).encode("utf-8")).hexdigest()[:12]


def model_items(self=None, _context=None):
    """Model's list: the .dmx's own model; the models this animation went onto before; your 10 most imported; a path
    typed below"""
    from ..core import usage
    _ITEMS.clear()
    _ITEMS.append((DMX_ID, "From the .dmx", "The model the .dmx names (of several, the one whose skeleton matches)"))
    seen = set()
    dmx = getattr(self, "filepath", "") if self is not None else ""
    for path, count in usage.models_for(dmx) if dmx and str(dmx).lower().endswith(".dmx") else []:
        seen.add(path)
        _ITEMS.append((_id(path), "%s  - with this animation (%d)" % (Path(path).stem, count),
                       "%s - this animation went onto it %d time(s)" % (path, count)))
    for path, count in usage.top_models(TOP):
        if path in seen:
            continue
        _ITEMS.append((_id(path), "%s  (%d)" % (Path(path).stem, count), "%s - imported %d time(s)" % (path, count)))
    _ITEMS.append((PATH_ID, "Path below", "The .mdl typed or pasted into Model Path"))
    return _ITEMS


def path_of(choice, typed=""):
    """the .mdl a Model choice stands for: '' for From the .dmx; the typed path for Path below (or when typed and the
    choice is From the .dmx)"""
    if choice == PATH_ID or (typed and choice == DMX_ID):
        return typed
    from ..core import usage
    d = usage._load()
    for path in list((d.get("models") or {})) + [m for a in (d.get("animations") or {}).values() for m in a]:
        if _id(path) == choice:
            return path
    return ""


class HT_OT_EasyAddModel(bpy.types.Operator):
    """Add a model to Easy Import's Model list (your 10 most imported): a file browser here, outside Import
    Animation's own - Blender opens one file browser at a time. The model is then chosen in the list.
THIS FEATURE WAS ADDED IN VERSION 3.0.3 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.easy_add_model"
    bl_label = "Add Model"
    bl_options = {"REGISTER"}
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore
    filter_glob: bpy.props.StringProperty(default="*.mdl", options={"HIDDEN"})  # type: ignore

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        p = Path(bpy.path.abspath(self.filepath))
        if not p.is_file() or p.suffix.lower() != ".mdl":
            self.report({"ERROR"}, "Not a .mdl: %s" % p)
            return {"CANCELLED"}
        from ..core import usage
        usage.model_added(p)
        mid = _id(p)
        try:                                                   # chosen in Import Animation's next press
            last = context.window_manager.operator_properties_last("ht.import_dmx_animation")
            last.easy_import = last.import_with_model = True
            last.model_pick = mid
        except Exception:                                      # noqa: BLE001
            pass
        self.report({"INFO"}, "%s is on the Model list" % p.name)
        return {"FINISHED"}


def _find(arm, names):
    low = {b.name.lower(): b.name for b in arm.data.bones}
    for n in names:
        if n in low:
            return low[n]
    for b in arm.data.bones:
        if any(n in b.name.lower() for n in names[2:]):
            return b.name
    return None


def _top(ob):
    while ob.parent is not None:
        ob = ob.parent
    return ob


def _holder(arm, size=1.0):
    """the static empty above the character's hierarchy that Easy Import turns and moves ('<armature>_upright') -
    made once, the hierarchy hung under it as it stands"""
    top = _top(arm)
    if top.get(UPRIGHT):
        return top
    sc = bpy.context.scene
    holder = bpy.data.objects.new(arm.name + UPRIGHT, None)
    holder[UPRIGHT] = arm.name
    holder.empty_display_type = "ARROWS"
    holder.empty_display_size = max(0.1, size)
    (top.users_collection[0] if top.users_collection else sc.collection).objects.link(holder)
    mw = top.matrix_world.copy()
    top.parent = holder
    top.matrix_parent_inverse = Matrix.Identity(4)
    top.matrix_world = mw
    return holder


def _ground_of(arm, root=None):
    """the character's place: the root empty (SFM's root transform) if there is one, else the armature's origin"""
    return (root if root is not None else arm).matrix_world.translation.copy()


def root_to_origin(arm, root, mode, f0, f1):
    """3.0.3, the user: "allow for forcing the root transform to be at the middle" / "0,0,0". The character put at
    0,0,0 by the static empty above the hierarchy - no key of the file's touched. Where the character is = its pelvis
    over the ground (an SFM export moves the pelvis channel; its root transform often sits still), at the root's
    height:
        START  at 0,0,0 on the first frame; the take travels from there
        LOCK   held at 0,0,0 the whole take (in place) - the travel taken out, smoothed over a second so the hips'
               own sway stays
    Returns a report"""
    if mode not in ("START", "LOCK"):
        return {"moved": 0}
    pel = _find(arm, PELVES)
    sc = bpy.context.scene
    keep = sc.frame_current
    holder = _holder(arm)
    base = holder.location.copy()
    frames = list(range(int(f0), int(f1) + 1))
    pts = []
    for f in frames:
        sc.frame_set(f)
        bpy.context.view_layer.update()
        g = _ground_of(arm, root)
        if pel:
            q = arm.matrix_world @ arm.pose.bones[pel].head
            g = Vector((q.x, q.y, g.z))
        pts.append(g)
    z0 = pts[0].z
    if mode == "START":
        holder.location = base - Vector((pts[0].x, pts[0].y, z0))
        moved = pts[0].length
    else:
        half = max(1, int(round(sc.render.fps / max(sc.render.fps_base, 1e-6))) // 2)
        if holder.animation_data and holder.animation_data.action:
            holder.animation_data_clear()
        moved = 0.0
        for i, f in enumerate(frames):
            win = pts[max(0, i - half):i + half + 1]
            cx = sum(v.x for v in win) / len(win)
            cy = sum(v.y for v in win) / len(win)
            holder.location = base - Vector((cx, cy, z0))
            holder.keyframe_insert("location", frame=f)
            moved = max(moved, math.hypot(cx, cy))
    sc.frame_set(keep)
    bpy.context.view_layer.update()
    return {"moved": round(moved, 3), "mode": mode, "empty": holder.name, "root": pel or (root or arm).name}


UPRIGHT_SNAP_DEG = 35.0                   # this close to a world axis: the file lies along that axis


UPRIGHT_SAMPLES = 60                      # frames measured across the take (evenly spaced)


def make_upright(arm, frame=None, root=None, last=None):
    """the character standing. 3.0.4: pelvis -> head measured over the whole take (`frame` .. `last`, about
    UPRIGHT_SAMPLES frames, each counting the same) - one leaning or crouched frame no longer decides it; the same file
    always gets the same turn. This close to a world axis
    (UPRIGHT_SNAP_DEG) the file lies along that axis and the whole axis is turned (3.0.3: a leaning first pose measured
    78 deg on a file that lies 90 deg off - the lean is the animation's, it stays). The turn is about the root's
    ground point (3.0.3: about the pelvis it left an offset on the character and the feet under the ground), on a
    static empty '<armature>_upright' above its top parent (the root empty carries keyed root motion - turned there,
    the keys would undo it). Returns a report"""
    head, pel = _find(arm, HEADS), _find(arm, PELVES)
    if not head or not pel:
        return {"turned": 0.0, "why": "no pelvis / head bone found"}
    sc = bpy.context.scene
    keep = sc.frame_current
    f0 = int(frame) if frame is not None else sc.frame_current
    f1 = int(last) if last is not None else f0
    step = max(1, (f1 - f0) // UPRIGHT_SAMPLES)
    v = Vector((0.0, 0.0, 0.0))
    piv = None
    for f in range(f0, f1 + 1, step):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        W = arm.matrix_world
        d = W @ arm.pose.bones[head].head - W @ arm.pose.bones[pel].head
        if d.length > 1e-9:
            v += d.normalized()                               # every sampled frame counts the same
        if piv is None:
            piv = _ground_of(arm, root)                       # the turn's pivot: the first frame's
    sc.frame_set(keep)
    bpy.context.view_layer.update()
    if v.length < 1e-9:
        return {"turned": 0.0, "why": "pelvis and head in one place"}
    up = Vector((0.0, 0.0, 1.0))
    axes = [Vector(c) for c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    near = min(axes, key=lambda a: v.normalized().angle(a))
    lie = near if math.degrees(v.normalized().angle(near)) < UPRIGHT_SNAP_DEG else v.normalized()
    off = math.degrees(lie.angle(up))
    if off < UPRIGHT_TOL_DEG:
        return {"turned": 0.0, "off": round(math.degrees(v.normalized().angle(up)), 1), "why": "already standing"}
    holder = _holder(arm, v.length * 0.5)
    if lie.dot(up) < -0.999:                                  # upside down: half a turn about X
        R = Matrix.Rotation(math.pi, 4, "X")
    else:
        R = lie.rotation_difference(up).to_matrix().to_4x4()
    holder.matrix_world = Matrix.Translation(piv) @ R @ Matrix.Translation(-piv) @ holder.matrix_world
    bpy.context.view_layer.update()
    return {"turned": round(off, 1), "empty": holder.name}


def _ours(arm, ob):
    """one of the empties the importer / Easy Import put above this armature"""
    return ob.type == "EMPTY" and (ob.name in (arm.name + "_root", arm.name + "_axis", arm.name + UPRIGHT)
                                   or bool(ob.get(UPRIGHT)))


def bake_root(arm, f0, f1):
    """3.0.4, the user: "allow for baking the ROOT TRANSFORM as animation, so we do not import the upright and axis
    and root". The armature's world placement on every frame - what the _root, _axis and _upright empties above it
    make together - keyed on the armature object itself (location, quaternion, scale), then those empties removed.
    A placement that never changes is set once, without keys. Anything else hung on the empties moves to the
    armature, where it stands. Returns a report"""
    chain = []
    p = arm.parent
    while p is not None and _ours(arm, p):
        chain.append(p)
        p = p.parent
    if not chain:
        return {"keys": 0, "removed": [], "why": "no root / axis / upright empty above the armature"}
    outer = p                                                 # a parent of your own above them stays
    sc = bpy.context.scene
    keep = sc.frame_current
    frames = list(range(int(f0), int(f1) + 1))
    mats = []
    for f in frames:
        sc.frame_set(f)
        bpy.context.view_layer.update()
        m = arm.matrix_world.copy()
        mats.append(outer.matrix_world.inverted() @ m if outer is not None else m)
    sc.frame_set(frames[0])
    bpy.context.view_layer.update()
    others = [c for e in chain for c in e.children if c is not arm and c not in chain]
    held = [(c, c.matrix_world.copy()) for c in others]
    arm.parent = outer
    arm.matrix_parent_inverse = Matrix.Identity(4)
    arm.rotation_mode = "QUATERNION"
    still = all(all(abs(a - b) < 1e-5 for ra, rb in zip(m, mats[0]) for a, b in zip(ra, rb)) for m in mats)
    prev = None
    for f, m in zip(frames, mats):
        loc, rot, scl = m.decompose()
        if prev is not None and rot.dot(prev) < 0.0:          # the short way between neighbouring frames
            rot.negate()
        prev = rot
        arm.location, arm.rotation_quaternion, arm.scale = loc, rot, scl
        if still:
            break
        for path in ("location", "rotation_quaternion", "scale"):
            arm.keyframe_insert(path, frame=f)
    for c, mw in held:
        c.parent = arm
        c.matrix_parent_inverse = Matrix.Identity(4)
        c.matrix_world = mw
    removed = []
    for e in chain:
        act = e.animation_data.action if e.animation_data else None
        removed.append(e.name)
        bpy.data.objects.remove(e)
        if act is not None and act.users == 0:
            bpy.data.actions.remove(act)
    sc.frame_set(keep)
    bpy.context.view_layer.update()
    return {"keys": 0 if still else len(frames), "removed": removed, "still": still}
