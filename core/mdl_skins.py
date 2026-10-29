"""
mdl_skins - a model's skins, read straight from the .mdl, and put on an import.

WHAT A SKIN IS
--------------
A Source model lists its materials once (the texture table) and then a skin
table: one row per skin family, one column per material slot, each cell the
index of the material that slot shows in that skin. Skin 0 is the default;
`$texturegroup` in the QC writes the rest (red / blue team, a damaged
version, the glowing FNAF eyes on skin 1).

THE TABLE IS READ FROM THE FILE, NOT FROM SOURCEIO, because the file browser
has to list the skins BEFORE anything is imported - the moment a .mdl is
clicked. The header fields are the same in every Source 1 version (44-49):
    numtextures  @204   textureindex @208
    numskinref   @220   numskinfamilies @224   skinindex @228
A texture entry is 64 bytes; its first int is the offset of its name,
counted from the start of that entry.

WHY HOOVYTOOLS SWAPS THE MATERIALS ITSELF
-----------------------------------------
SourceIO loads EVERY material of the model (all skins, with textures) and
stamps each mesh with `skin_groups` = {"0": [names], "1": [names], ...} and
`active_skin`. Its own "Change skin" button compares the mesh's material
OBJECTS against those NAMES, so on a Source 1 model it never swaps anything.
`apply_skin` matches by name (and by SourceIO's `full_path` stamp when a name
was shortened or suffixed).
"""

import os
import struct

import bpy

_CACHE = {}          # path -> (mtime, families)
_ITEMS_KEEP = []     # Blender needs dynamic enum items kept alive


def read_skins(path):
    """[[material name per slot] per skin family] for a .mdl, or [] when the
    file is not a readable Source 1 model. Cached by modification time."""
    try:
        path = os.fspath(path)
        mtime = os.path.getmtime(path)
    except (OSError, TypeError):
        return []
    hit = _CACHE.get(path)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    families = []
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data[:4] == b"IDST":
            (n_tex, tex_at) = struct.unpack_from("<ii", data, 204)
            (n_ref, n_fam, skin_at) = struct.unpack_from("<iii", data, 220)
            if 0 < n_tex < 4096 and 0 < n_ref < 4096 and 0 < n_fam < 1024:
                names = []
                for i in range(n_tex):
                    entry = tex_at + i * 64
                    (name_off,) = struct.unpack_from("<i", data, entry)
                    start = entry + name_off
                    end = data.index(b"\0", start)
                    names.append(data[start:end].decode("latin-1"))
                for fam in range(n_fam):
                    row = struct.unpack_from(f"<{n_ref}h", data, skin_at + fam * n_ref * 2)
                    families.append([names[i] if 0 <= i < len(names) else "" for i in row])
    except Exception:                                         # noqa: BLE001
        families = []
    _CACHE[path] = (mtime, families)
    return families


def _short(name):
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def skin_label(families, index):
    """'1 - spy_blue' : the skin number, then what it changes from skin 0."""
    if index == 0:
        return "0 - Default"
    base = families[0]
    changed = [_short(n) for i, n in enumerate(families[index])
               if i < len(base) and n.lower() != base[i].lower()]
    if not changed:
        return f"{index} - same as default"
    more = f" +{len(changed) - 2}" if len(changed) > 2 else ""
    return f"{index} - " + ", ".join(changed[:2]) + more


def enum_items(path):
    """EnumProperty items for the skins of `path` (always at least one)."""
    families = read_skins(path) if path and str(path).lower().endswith(".mdl") else []
    if len(families) <= 1:
        what = ("this model has one skin" if families else
                "select a .mdl to see its skins")
        items = [("0", "0 - Default", what)]
    else:
        items = [(str(i), skin_label(families, i),
                  f"Skin {i} of {len(families)}: " + ", ".join(
                      sorted({_short(n) for n in fam})[:8]))
                 for i, fam in enumerate(families)]
    _ITEMS_KEEP[:] = items
    return items


def _material_for(name, candidates=None):
    """The Blender material SourceIO made for a model material name."""
    want = _short(name).lower()
    pool = list(candidates) if candidates is not None else list(bpy.data.materials)
    for m in pool:
        if m is not None and m.name.lower() == want:
            return m
    for m in pool:
        if m is None:
            continue
        stem = m.name.rsplit(".", 1)[0].lower() if m.name[-4:-3] == "." else m.name.lower()
        fp = str(m.get("full_path", "")).replace("\\", "/").lower()
        if stem == want or fp.endswith("/" + want) or fp == want:
            return m
    return None


def apply_skin(objects, index):
    """Put skin `index` on every mesh SourceIO stamped with `skin_groups`.

    Returns {"meshes": n touched, "slots": n swapped, "missing": [names]}."""
    key = str(int(index))
    out = {"meshes": 0, "slots": 0, "missing": []}
    for ob in objects:
        if ob.type != "MESH":
            continue
        groups = ob.get("skin_groups")
        if not groups or key not in groups.keys():
            continue
        cur_key = str(ob.get("active_skin", "0"))
        if cur_key not in groups.keys():
            cur_key = "0"
        old = [str(x) if not hasattr(x, "name") else x.name for x in groups[cur_key]]
        new = [str(x) if not hasattr(x, "name") else x.name for x in groups[key]]
        slots = ob.data.materials
        #  THE WHOLE MAP FIRST, then each slot once: a skin may swap two
        #  materials (A->B and B->A), and replacing as we go would swap the
        #  first one straight back.
        remap = {}
        for o_name, n_name in zip(old, new):
            if o_name.lower() == n_name.lower():
                continue
            cur = _material_for(o_name, slots)
            if cur is None or cur.name in remap:
                continue
            repl = _material_for(n_name)
            if repl is None:
                if n_name not in out["missing"]:
                    out["missing"].append(n_name)
                continue
            remap[cur.name] = repl
        touched = False
        for i, m in enumerate(list(slots)):
            if m is not None and m.name in remap:
                slots[i] = remap[m.name]
                out["slots"] += 1
                touched = True
        ob["active_skin"] = key
        out["meshes"] += touched
    return out
