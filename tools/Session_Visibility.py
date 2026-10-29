# ═════════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# bpy                            the imported objects, the scene camera
# session/Session_Reader.py      the session, its shots and their sets
# session/Session_Paths.py       which shot the .blend holds
# tools/Layout_Builder.py        viewports into camera view
# Called by session/Session_Orchestrator.py (one-click step 11) and by the
# operator HT_OT_match_sfm_visibility. Added in 1.17.0.
# ═════════════════════════════════════════════════════════════════════════════
"""
Session_Visibility - what SFM hides stays hidden, and the shot's own camera is
the one Blender looks through.

HIDDEN - MEASURED ON `gothic tutorial introduction - v2.dmx`
------------------------------------------------------------
A shot's scene is a DAG: `shot.scene` > wrapper DmeDags (one per set, plus
groups such as "Lights" or "group1") > the DmeGameModel, DmeProjectedLight or
DmeCamera itself. SFM's eye toggle writes `visible` on whatever node was
clicked, and a hidden GROUP hides everything under it. In this file:

    light1                 DmeProjectedLight  visible=False   (itself)
    'Light Set Up 2', 'VIEW 1', 'axis1', 'scout1'
                           DmeDag groups      visible=False   (everything under them)

So an element is hidden when it OR ANY ANCESTOR in its shot's tree says
visible=False. It is a static flag here: of the file's 8 animated `visible`
channels all 8 drive particle systems, and the particle importer keys those
itself (Session_Particles.apply_visibility).

In Blender a hidden set gets the bodygroup treatment - hide_viewport and
hide_render on its armature and everything parented under it (or its light,
or its camera), tagged `ht_sfm_hidden` with the node that hid it. Running it
again UNHIDES what it hid once SFM shows it again; nothing it did not tag is
ever touched.

THE CURRENT CAMERA
------------------
A shot (DmeFilmClip) has ONE `camera` - what SFM looks through; "camera5" in
the gothic shot. The import's camera jump took the alphabetically first
camera, and capitals sort first, so "Constrained Camera" - which drives
camera2 - won. The shot's camera is resolved by IDENTITY: the set whose
`camera` IS the shot's camera (never by name - the Gomez film holds thirty
DmeCameras called "camera2"), then the Blender camera named after that set
(the camera importer names its objects after the extracted file, i.e. the
set). The name is stamped on the scene as `ht_shot_camera` so the one-click's
final camera jump picks it.
"""

from pathlib import Path

import bpy

SCENE_CAMERA_KEY = "ht_shot_camera"
HIDDEN_TAG = "ht_sfm_hidden"
KINDS = (("gameModel", "model"), ("light", "light"), ("camera", "camera"))


# ─────────────────────────────────────────────────────────────────────────────
# Reading the session
# ─────────────────────────────────────────────────────────────────────────────

def _scene_parents(shot_element):
    """{id(node): parent node} over the shot's scene DAG."""
    out = {}
    root = None
    try:
        root = shot_element.get("scene") if shot_element is not None else None
    except Exception:                                         # noqa: BLE001
        root = None
    stack = [root] if root is not None else []
    seen = set()
    while stack:
        node = stack.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        try:
            kids = list(node.get("children") or [])
        except Exception:                                     # noqa: BLE001
            kids = []
        for kid in kids:
            if kid is None:
                continue
            out.setdefault(id(kid), node)
            stack.append(kid)
    return out


def hidden_by(elem, parents):
    """None while visible; else the name of the node that hides it (itself or
    the nearest hidden ancestor)."""
    node, hops = elem, 0
    while node is not None and hops < 128:
        try:
            vis = node.get("visible") if "visible" in node.keys() else None
        except Exception:                                     # noqa: BLE001
            vis = None
        if vis is not None and not bool(vis):
            return node.name or node.type or "?"
        node = parents.get(id(node))
        hops += 1
    return None


def shot_visibility(shot):
    """[(set name, kind, element, hidden_by or None)] for one shot's sets."""
    parents = _scene_parents(shot.get("element"))
    out = []
    for a in (shot.get("sets") or ()):
        for key, kind in KINDS:
            try:
                v = a.get(key)
            except Exception:                                 # noqa: BLE001
                v = None
            if v is None:
                continue
            out.append((a.name or "", kind, v, hidden_by(v, parents)))
            break
    return out


def hidden_state(shots):
    """{(set name, kind): hidden_by or None} over `shots`.

    A WHOLE-SESSION import holds every cut's copy of a set under one name,
    so a set is hidden only when it is hidden in EVERY cut that has it -
    never hide something another cut shows."""
    state = {}
    for sh in shots:
        for set_name, kind, _elem, why in shot_visibility(sh):
            key = (set_name, kind)
            if key not in state:
                state[key] = why
            elif why is None:
                state[key] = None             # any cut that shows it wins
    return state


def chosen_shots(shot_list, shot_index=None, shot_name=""):
    """(the chosen shot or None, the shots it covers) - one shot when one is
    chosen (or the session has only one), else every shot that has sets."""
    from ..session import Session_Paths
    chosen = None
    if shot_index is not None and int(shot_index) >= 0:
        chosen, _note = Session_Paths.resolve_shot(shot_list, index=int(shot_index),
                                                   name=shot_name or "")
    if chosen is None and len(shot_list) == 1:
        chosen = shot_list[0]
    return chosen, ([chosen] if chosen is not None else [s for s in shot_list if s.get("sets")])


def hidden_set_names(session_path, scene=None, info=None, force=False):
    """1.26.0 SKIP HIDDEN OBJECTS: {set name: what hides it} of the sets the
    import leaves out - empty while the switch (ht_project.skip_hidden) is off,
    so nothing is read then. The chosen shot decides; a whole-session import
    leaves a set out only when every cut that has it hides it (hidden_state).
    Never raises: a session it cannot read skips nothing."""
    from ..session import Session_Paths, Session_Reader
    scene = scene or getattr(bpy.context, "scene", None)
    if not force and not Session_Paths.skip_hidden(scene):
        return {}
    try:
        info = info or Session_Reader.read_session(str(session_path))
        idx, name = Session_Paths.shot_choice(scene)
        _chosen, shots = chosen_shots(info["shots"], idx, name)
        out = {}
        for (set_name, _kind), why in hidden_state(shots).items():
            if why is not None and set_name:
                out[set_name] = why
        if out:
            print(f"[SESSION]  skip hidden: {len(out)} set(s) SFM hides are left out - "
                  + ", ".join(f"{n} (by {w})" if w != n else n for n, w in sorted(out.items())))
        return out
    except Exception as exc:                                  # noqa: BLE001
        print(f"[SESSION]  skip hidden unavailable ({exc}) - importing every set")
        return {}


def shot_camera_set(shot):
    """(set name, camera element name) of the camera THIS shot looks through,
    or (None, element name) when no set of the shot drives it."""
    cam = shot.get("camera_element")
    if cam is None:
        return None, None
    for a in (shot.get("sets") or ()):
        try:
            if a.get("camera") is cam:
                return a.name or "", cam.name or ""
        except Exception:                                     # noqa: BLE001
            continue
    return None, cam.name or ""


# ─────────────────────────────────────────────────────────────────────────────
# Finding the Blender objects
# ─────────────────────────────────────────────────────────────────────────────

def _named(scene, name, types):
    """The object called `name` in this scene (or `name.001` style when the
    exact one is not here), of one of `types`."""
    ob = bpy.data.objects.get(name)
    if ob is not None and ob.type in types and scene.objects.get(ob.name) is not None:
        return ob
    for o in scene.objects:
        if o.type in types and o.name.rsplit(".", 1)[0] == name:
            return o
    return None


def objects_for(scene, set_name, kind):
    if kind == "model":
        arm = _named(scene, set_name, {"ARMATURE", "MESH", "EMPTY"})
        if arm is None:
            return []
        return [arm] + [c for c in arm.children_recursive]
    if kind == "light":
        ob = _named(scene, set_name, {"LIGHT"})
        return [ob] if ob is not None else []
    if kind == "camera":
        ob = _named(scene, set_name, {"CAMERA"})
        return [ob] if ob is not None else []
    return []


def camera_object(scene, set_name, element_name=""):
    """The Blender camera for a camera set: named after the set, else the one
    whose source file is the set, else the only one carrying SFM's name."""
    if set_name:
        ob = _named(scene, set_name, {"CAMERA"})
        if ob is not None:
            return ob
        for o in scene.objects:
            if o.type == "CAMERA" and Path(str(o.get("ht_source_file", ""))).stem == set_name:
                return o
    if element_name:
        hits = [o for o in scene.objects
                if o.type == "CAMERA" and str(o.get("ht_sfm_name", "")) == element_name]
        if len(hits) == 1:
            return hits[0]
    return None



MARKER_PREFIX = "HT shot: "


def bind_shot_cameras(scene, shot_list):
    """Marker per shot, bound to its camera. Returns [(frame, shot, camera)]."""
    tm = scene.timeline_markers
    for m in [m for m in tm if m.name.startswith(MARKER_PREFIX)]:
        tm.remove(m)
    taken = {m.frame for m in tm if m.camera is not None}
    out = []
    for sh in sorted(shot_list, key=lambda s: s.get("frame_start", 0)):
        if not sh.get("sets"):
            continue
        set_name, elem_name = shot_camera_set(sh)
        cam = camera_object(scene, set_name, elem_name)
        if cam is None:
            continue
        fr = int(sh.get("frame_start", 0))
        if fr in taken:
            continue                  # a split camera already cuts here
        mk = tm.new(name=f"{MARKER_PREFIX}{sh.get('name') or '?'}", frame=fr)
        mk.camera = cam
        taken.add(fr)
        out.append((fr, sh.get("name") or "?", cam.name))
    return out


def set_shot_camera(context, session_path, shot_index=None, shot_name="", info=None):
    """The camera half of `apply`, hiding nothing - for 4 Import Cameras."""
    return apply(context, session_path, shot_index=shot_index,
                 shot_name=shot_name, info=info, hide=False)


# ─────────────────────────────────────────────────────────────────────────────
# Applying
# ─────────────────────────────────────────────────────────────────────────────

def apply(context, session_path, shot_index=None, shot_name="", info=None,
          set_camera=True, hide=True):
    """Hide what SFM hides, show again what it shows, and make the shot's
    camera the scene camera - or, with no shot chosen, bind every shot's
    camera to a marker at its first frame. Returns a report dict."""
    from ..session import Session_Reader, Session_Paths
    scene = context.scene
    info = info or Session_Reader.read_session(session_path)
    shot_list = info["shots"]
    chosen, shots = chosen_shots(shot_list, shot_index, shot_name)

    state = hidden_state(shots) if hide else {}

    r = {"hidden": [], "shown": [], "missing": [], "camera": None,
         "camera_set": None, "camera_element": None, "markers": [],
         "shot": chosen.get("name") if chosen is not None else None}
    for (set_name, kind), why in sorted(state.items()):
        objs = objects_for(scene, set_name, kind)
        if why is not None:
            if not objs:
                r["missing"].append(f"{set_name} ({kind}, hidden by {why})")
                continue
            for ob in objs:
                ob.hide_viewport = True
                ob.hide_render = True
                ob[HIDDEN_TAG] = (f"hidden in SFM: {why!r}"
                                  + ("" if why == set_name else f" hides {set_name!r}"))
            r["hidden"].append(f"{set_name} ({kind}, by {why}, {len(objs)} object(s))")
        else:
            for ob in objs:
                if HIDDEN_TAG in ob.keys():
                    ob.hide_viewport = False
                    ob.hide_render = False
                    del ob[HIDDEN_TAG]
                    r["shown"].append(ob.name)

    if set_camera and chosen is not None:
        set_name, elem_name = shot_camera_set(chosen)
        r["camera_set"], r["camera_element"] = set_name, elem_name
        cam = camera_object(scene, set_name, elem_name)
        if cam is not None:
            scene.camera = cam
            scene[SCENE_CAMERA_KEY] = cam.name
            r["camera"] = cam.name
        elif SCENE_CAMERA_KEY in scene.keys():
            del scene[SCENE_CAMERA_KEY]       #an older shot's stamp must not win
    elif set_camera:
        # whole SESSION: every shot's camera on a marker, the first one live
        r["markers"] = bind_shot_cameras(scene, shot_list)
        if r["markers"]:
            first = bpy.data.objects.get(r["markers"][0][2])
            if first is not None:
                scene.camera = first
                scene[SCENE_CAMERA_KEY] = first.name
                r["camera"] = first.name
    return r


def report_lines(r):
    L = []
    if r.get("shot"):
        L.append(f"Shot     : {r['shot']}")
    if r.get("markers"):
        L.append(f"Cameras  : {len(r['markers'])} shot(s), each switching to its own "
                 "camera at a timeline marker")
        for fr, shot, cam in r["markers"][:12]:
            L.append(f"           f{fr:<6} {shot} -> {cam}")
    elif r.get("camera"):
        L.append(f"Camera   : {r['camera']} - the shot's camera in SFM"
                 + (f" ({r['camera_element']})" if r.get("camera_element") and
                    r["camera_element"] != r["camera"] else ""))
    elif r.get("camera_element"):
        L.append(f"Camera   : SFM looks through {r['camera_element']!r} - no imported camera matches it")
    L.append(f"Hidden   : {len(r['hidden'])} set(s) hidden as in SFM")
    for line in r["hidden"][:12]:
        L.append(f"           {line}")
    if r["shown"]:
        L.append(f"Shown    : {len(r['shown'])} object(s) SFM shows again")
    if r["missing"]:
        L.append(f"Not found: {len(r['missing'])} hidden set(s) with no object here - "
                 + ", ".join(r["missing"][:4]))
    return L


class HT_OT_match_sfm_visibility(bpy.types.Operator):
    """Hide what SFM hides and look through the shot's own camera

Every model, light and camera hidden in the connected session's shot - hidden itself or inside a hidden group - is
hidden here too (viewport and render), and the scene camera becomes the camera SFM looks through in that shot.
Objects it hid earlier come back when SFM shows them again; nothing else is touched.

HOW: connect the session and pick the shot (Main tab), then press it. The one-click import runs it by itself.

THIS FEATURE WAS ADDED IN VERSION 1.17.0 AND IS IN EXPERIMENTAL STAGE"""
    bl_idname = "ht.match_sfm_visibility"
    bl_label = "Match SFM Visibility + Camera"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from ..session import Session_Paths
        session = Session_Paths.session_file(context.scene)
        if session is None:
            self.report({"ERROR"}, "No session connected")
            return {"CANCELLED"}
        idx, nm = Session_Paths.shot_choice(context.scene)
        try:
            r = apply(context, session, shot_index=idx, shot_name=nm)
        except Exception as exc:                              # noqa: BLE001
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}
        for line in report_lines(r):
            print(f"[VISIBILITY]  {line}")
        if r.get("camera"):
            try:
                from . import Layout_Builder
                Layout_Builder.set_viewports_to_camera()
            except Exception:                                 # noqa: BLE001
                pass
        self.report({"INFO"}, f"{len(r['hidden'])} hidden set(s)"
                              + (f", camera {r['camera']}" if r.get("camera") else ""))
        return {"FINISHED"}


def register():
    bpy.utils.register_class(HT_OT_match_sfm_visibility)


def unregister():
    bpy.utils.unregister_class(HT_OT_match_sfm_visibility)
