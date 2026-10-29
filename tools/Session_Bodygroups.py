# ═════════════════════════════════════════════════════════════════════════════
#  DEPENDENCIES
#    bpy                      hide flags on the imported mesh objects
#    struct                   the .mdl bodypart table
#  Called by session/Import_Session.py after each SourceIO model import.
#  Added in 1.16.0.
# ═════════════════════════════════════════════════════════════════════════════
"""
Session_Bodygroups - show only the bodygroup options the SESSION has on.

WHY
---
SourceIO imports EVERY option of EVERY bodygroup: a soldier comes in wearing
his default helmet and every alternative hat at once, a prop with an "open"
and a "closed" bodygroup shows both. SFM shows one option per bodygroup, and
which one is stored per model in the session as a single integer -
DmeGameModel's `body`.

HOW `body` ENCODES THE CHOICE
-----------------------------
Every bodypart in the .mdl carries a `base`. The option shown for a bodypart
is

        (body // base) % nummodels

so one integer holds every choice at once, mixed-radix. body = 0 is option 0
everywhere - which still hides things on any model whose bodyparts have more
than one option, because option 0 is ONE option, not all of them.

THE .MDL TABLE (studiohdr_t, v44-v49, read directly)
------------------------------------------------------
    232  int  numbodyparts
    236  int  bodypartindex
    mstudiobodyparts_t, 16 bytes each:
         +0  int sznameindex   (relative to this struct)
         +4  int nummodels
         +8  int base
        +12  int modelindex    (relative to this struct)
    mstudiomodel_t, 148 bytes each:
         +0  char name[64]
        +80  int  numvertices  (0 = a "blank" option: SourceIO makes no object)

MATCHING A BLENDER OBJECT TO ITS OPTION
---------------------------------------
SourceIO names the MESH DATA after the bodypart AND the model, which is what
pins an object to exactly one option:
    v49+   "<header name>_<bodypart>_<model>_MESH"
    v44    "<bodypart>_<model>_MESH"
Blender caps names at 63 characters, so a long one arrives cut short; a cut
name is matched as a prefix of the full one. The object name (the model name,
or "<bodypart>_<model>") and the bodypart collection SourceIO groups meshes
into are the fallbacks, in that order. ".001" suffixes from importing the same
model twice are stripped first.

NOTHING IS DELETED. A hidden option is hidden in the viewport and the render
and tagged `ht_bodygroup_hidden` with the reason, so un-hiding it in the
outliner is the whole undo.
"""

import re
import struct

import bpy

_SUFFIX = re.compile(r"\.\d{3}$")
NAME_MAX = 63          # Blender's ID name limit - longer names arrive cut


def _plain(name):
    return _SUFFIX.sub("", name or "")


def _cstr(b, at):
    end = b.find(b"\0", at)
    return b[at:end if end >= 0 else at + 64].decode("latin-1", "replace")


def read_bodyparts(mdl_path):
    """[{name, base, models: [{name, verts}]}] straight from the .mdl.

    Returns [] for anything that is not a v44-v49 studio model, rather than
    guessing at a layout it does not know."""
    with open(mdl_path, "rb") as fh:
        b = fh.read()
    if len(b) < 240 or b[:4] != b"IDST":
        return []
    version, = struct.unpack_from("<i", b, 4)
    if not 44 <= version <= 49:
        return []
    header_name = _cstr(b, 12)
    count, index = struct.unpack_from("<ii", b, 232)
    if count <= 0 or count > 256 or index <= 0 or index + count * 16 > len(b):
        return []
    parts = []
    for i in range(count):
        o = index + i * 16
        nameidx, nummodels, base, modelidx = struct.unpack_from("<iiii", b, o)
        models = []
        for k in range(max(0, nummodels)):
            m = o + modelidx + k * 148
            if m + 84 > len(b):
                break
            verts, = struct.unpack_from("<i", b, m + 80)
            models.append({"name": _cstr(b, m), "verts": verts})
        parts.append({"name": _cstr(b, o + nameidx), "base": max(1, base),
                      "models": models, "header": header_name,
                      "version": version})
    return parts


def choices(parts, body):
    """{bodypart index: chosen option index} for one `body` value."""
    body = max(0, int(body or 0))
    return {i: (body // p["base"]) % len(p["models"])
            for i, p in enumerate(parts) if p["models"]}


def _expected_names(part, model):
    bp, mn, hd = part["name"], model["name"], part["header"]
    return [f"{hd}_{bp}_{mn}_MESH", f"{bp}_{mn}_MESH"]


def _match(ob, parts):
    """(bodypart index, option index) for one SourceIO mesh object, or None."""
    data_name = _plain(getattr(ob.data, "name", ""))
    obj_name = _plain(ob.name)
    cols = {_plain(c.name) for c in ob.users_collection}
    best, best_len = None, -1
    for i, part in enumerate(parts):
        for k, model in enumerate(part["models"]):
            if model["verts"] <= 0:
                continue
            for full in _expected_names(part, model):
                #  a cut name: Blender keeps 63 characters, and a ".001"
                #  copy keeps only 59 of the base before its suffix
                hit = (data_name == full
                       or (len(data_name) >= NAME_MAX - 5
                           and full.startswith(data_name)))
                if hit and len(full) > best_len:
                    best, best_len = (i, k), len(full)
    if best is not None:
        return best
    #  fallback: object named after the model, inside the bodypart collection
    for i, part in enumerate(parts):
        for k, model in enumerate(part["models"]):
            if model["verts"] <= 0:
                continue
            if obj_name in (model["name"], f"{part['name']}_{model['name']}") \
                    and (part["name"] in cols or len(parts) == 1):
                return (i, k)
    return None


def apply_session_bodygroups(objs, mdl_path, body, label=""):
    """Hide every mesh whose bodygroup option is not the one `body` picks.

    Returns a report dict: parts, chosen, hidden (names), unmatched (names)."""
    out = {"parts": 0, "chosen": {}, "hidden": [], "unmatched": [],
           "body": int(body or 0)}
    try:
        parts = read_bodyparts(str(mdl_path))
    except OSError:
        return out
    multi = [p for p in parts if len(p["models"]) > 1]
    out["parts"] = len(parts)
    if not multi:
        return out                      # nothing to choose between
    pick = choices(parts, body)
    out["chosen"] = {parts[i]["name"]: (k, parts[i]["models"][k]["name"]
                                        or "blank")
                     for i, k in pick.items() if len(parts[i]["models"]) > 1}
    for ob in objs:
        if ob.type != "MESH":
            continue
        m = _match(ob, parts)
        if m is None:
            out["unmatched"].append(ob.name)
            continue
        i, k = m
        if len(parts[i]["models"]) < 2 or pick.get(i) == k:
            continue
        chosen = pick.get(i, 0)
        why = (f"{parts[i]['name']}: option {k} '{parts[i]['models'][k]['name']}'"
               f" is off - the session shows option {chosen} "
               f"'{parts[i]['models'][chosen]['name'] or 'blank'}' (body={out['body']})")
        ob.hide_viewport = True
        ob.hide_render = True
        ob["ht_bodygroup_hidden"] = why
        out["hidden"].append(ob.name)
    if out["hidden"] or out["chosen"]:
        print(f"[BODYGROUPS]  {label or mdl_path}: body={out['body']}, "
              f"{len(out['hidden'])} option mesh(es) hidden"
              + ("".join(f"\n[BODYGROUPS]      {bp} -> {k} '{nm}'"
                         for bp, (k, nm) in out["chosen"].items())))
    if out["unmatched"]:
        print(f"[BODYGROUPS]  {label}: {len(out['unmatched'])} mesh(es) not "
              f"matched to a bodygroup, left as they were: "
              f"{', '.join(out['unmatched'][:6])}")
    return out
