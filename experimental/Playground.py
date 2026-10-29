"""
Playground.py  -  part of HoovyTools           [roadmap #16, #17]
================================================================

Tools that exploit the Source Engine but are NOT part of the Session Import
workflow.

The roadmap keeps a separate mental basket for these on purpose: experiments
stay alive without contaminating the product. Main Menu is the path we want
users on; Developer is the workshop; Playground is where things live that
exist because they are interesting.

Nothing in the Session Import path imports this module.


MDL SEQUENCE RESEARCH                                       [roadmap #16]
=========================================================================
Findings from parsing real files, 2026-08-20.

**How a sequence is represented.** `studiohdr_t` holds two separate arrays:

    numlocalanim  / localanimindex   ->  mstudioanimdesc_t[]   raw animation
    numlocalseq   / localseqindex    ->  mstudioseqdesc_t[]    sequences

A SEQUENCE is not animation data. It is a playback definition: a label, an
activity name, flags, and `animindexindex` - an array of shorts indexing INTO
the animation list. `numblends` with `groupsize[2]` describes a blend grid,
so a 1x1 sequence points at exactly one animation and a 3x3 sequence points
at nine and interpolates between them by pose parameter.

**Where the animation data actually sits - the important part.** Usually NOT
in the model you opened. Measured:

    tf/models/player/heavy.mdl              265 sequences,   2 animations
    tf/models/player/heavy_animations.mdl   268 sequences, 710 animations

`heavy.mdl` declares `numincludemodels = 3` and names them:

    models/player/heavy_user_animations.mdl
    models/player/heavy_animations.mdl
    models/workshop/player/animations/heavy_workshop_animations.mdl

That is `$includemodel`. The base model carries the mesh and the sequence
LIST; the animation payload lives in sibling MDLs that must be found on disk
and parsed as well. A sequence whose `numblends` is 0 in the base file is one
of these - its animation is somewhere else.

A second mechanism exists and is rarer: `numanimblocks` with
`szanimblocknameindex` points at an external `.ani` file. Neither TF2 player
model on this machine uses it (`numanimblocks = 0`, no `.ani` sidecars), but
a parser has to expect it.

**What MDL / VVD / VTX each contribute.** Only the MDL matters for animation.
VVD is vertex data, VTX is per-renderer strip/index data, PHY is collision.
Confirmed by sizes: `festive_tree.mdl` is 2 KB while its VVD is 470 KB.

**How bones map.** `mstudiobone_t` is 216 bytes in v44-49, starting with
`sznameindex` then `parent`. Names are plain and match the DMX channel
targets exactly - `bip_pelvis`, `bip_spine_0`, ... - so an MDL animation and
an SFM DMX animation address the SAME skeleton by the same names. That is the
encouraging part: a sequence extracted here could drive a rig imported by any
of the existing importers with no name mapping at all.

**What is NOT solved.** The per-frame animation payload is compressed
(`mstudioanim_t` / `mstudioanimvalue_t` RLE, with per-bone rotation and
position tracks, optionally delta-encoded against the reference pose). This
module reads the DIRECTORY, not the payload. Decoding the payload is the next
piece of work, and SourceIO already contains a working implementation worth
reading before writing another.
"""

import bpy
import os
import struct
from pathlib import Path

from bpy.types import Operator

# ──────────────────────────────────────────────────────────────────────────────
# Icon bridge (wired by __init__.register)
# ──────────────────────────────────────────────────────────────────────────────

_ht_icon_id = None


def _icon_id(key, fallback="NONE"):
    if _ht_icon_id is not None:
        return _ht_icon_id(key, fallback)
    return {"icon": fallback}

from bpy.props import StringProperty, BoolProperty, IntProperty
from bpy_extras.io_utils import ImportHelper


# studiohdr_t field offsets, v44-49. These are stable across the range.
OFF = {
    "version": 4, "checksum": 8, "name": 12, "length": 76, "flags": 152,
    "numbones": 156, "boneindex": 160,
    "numlocalanim": 180, "localanimindex": 184,
    "numlocalseq": 188, "localseqindex": 192,
    "numtextures": 204,
    "numbodyparts": 232, "bodypartindex": 236,
    "numincludemodels": 336, "includemodelindex": 340,
    "szanimblocknameindex": 348, "numanimblocks": 352, "animblockindex": 356,
}

SIZEOF_BONE = 216
SIZEOF_ANIMDESC = 100
SIZEOF_SEQDESC = 212
SIZEOF_MODELGROUP = 8

MAGIC = (b"IDST", b"IDSQ")


# ─────────────────────────────────────────────────────────────────────────────
# Parser  (bpy-free, so it can be exercised outside Blender)
# ─────────────────────────────────────────────────────────────────────────────

def _cstr(buf, off):
    if off <= 0 or off >= len(buf):
        return ""
    end = buf.find(b"\0", off)
    return buf[off:end if end >= 0 else len(buf)].decode("ascii", "replace")


def parse_mdl(path):
    """
    Read the studiohdr directory of one MDL. Returns a dict, or None when the
    file is not a studio model. Never decodes the animation payload.
    """
    path = Path(path)
    try:
        buf = path.read_bytes()
    except OSError:
        return None
    if len(buf) < 408 or buf[:4] not in MAGIC:
        return None

    def i32(off):
        return struct.unpack_from("<i", buf, off)[0]

    def f32(off):
        return struct.unpack_from("<f", buf, off)[0]

    out = {
        "path": str(path),
        "name": path.name,
        "magic": buf[:4].decode("ascii", "replace"),
        "version": i32(OFF["version"]),
        "internal_name": _cstr(buf, OFF["name"]),
        "size": len(buf),
        "numbones": i32(OFF["numbones"]),
        "numlocalanim": i32(OFF["numlocalanim"]),
        "numlocalseq": i32(OFF["numlocalseq"]),
        "numbodyparts": i32(OFF["numbodyparts"]),
        "numtextures": i32(OFF["numtextures"]),
        "numanimblocks": i32(OFF["numanimblocks"]),
        "animblock_name": _cstr(buf, i32(OFF["szanimblocknameindex"])),
    }

    # bones
    bones = []
    bi = i32(OFF["boneindex"])
    for k in range(out["numbones"]):
        off = bi + k * SIZEOF_BONE
        if off + 8 > len(buf):
            break
        bones.append((_cstr(buf, off + i32(off)), i32(off + 4)))
    out["bones"] = bones

    # animations
    anims = []
    ai = i32(OFF["localanimindex"])
    for k in range(out["numlocalanim"]):
        off = ai + k * SIZEOF_ANIMDESC
        if off + SIZEOF_ANIMDESC > len(buf):
            break
        anims.append({
            "index": k,
            "name": _cstr(buf, off + i32(off + 4)),
            "fps": f32(off + 8),
            "flags": i32(off + 12),
            "frames": i32(off + 16),
        })
    out["anims"] = anims

    #sequences
    seqs = []
    si = i32(OFF["localseqindex"])
    for k in range(out["numlocalseq"]):
        off = si + k * SIZEOF_SEQDESC
        if off + SIZEOF_SEQDESC > len(buf):
            break
        numblends = i32(off + 56)
        animindexindex = i32(off + 60)
        blends = []
        base = off + animindexindex
        for j in range(max(0, min(numblends, 64))):
            p = base + j * 2
            if p + 2 <= len(buf):
                blends.append(struct.unpack_from("<h", buf, p)[0])
        seqs.append({
            "index": k,
            "label": _cstr(buf, off + i32(off + 4)),
            "activity": _cstr(buf, off + i32(off + 8)),
            "flags": i32(off + 12),
            "numblends": numblends,
            "groupsize": (i32(off + 68), i32(off + 72)),
            "blends": blends,
        })
    out["seqs"] = seqs

    # $includemodel
    includes = []
    ii = i32(OFF["includemodelindex"])
    for k in range(i32(OFF["numincludemodels"])):
        off = ii + k * SIZEOF_MODELGROUP
        if off + SIZEOF_MODELGROUP > len(buf):
            break
        includes.append(_cstr(buf, off + i32(off + 4)))
    out["includes"] = includes

    # sidecars, to show what each file actually contributes
    stem = path.with_suffix("")
    side = {}
    for ext in ("vvd", "dx90.vtx", "dx80.vtx", "sw.vtx", "vtx", "phy", "ani"):
        p = Path(f"{stem}.{ext}")
        if p.exists():
            try:
                side[ext] = p.stat().st_size
            except OSError:
                pass
    out["sidecars"] = side
    return out


def search_roots():
    """Every `models` root worth looking in for an $includemodel target."""
    roots = []
    try:
        from ..session import Import_Session
        base = Import_Session.get_gameinfo_base()
        if base and base.exists():
            roots.append(Path(base))
            parent = Path(base).parent
            for name in ("tf", "tf_movies", "platform", "hl2", "sfm"):
                cand = parent / name
                if cand.is_dir():
                    roots.append(cand)
    except Exception:
        pass
    return roots


def resolve_include(rel, roots, near=None):
    """
    Find an $includemodel target on disk.

    Its recorded path is game-relative ("models/player/heavy_animations.mdl"),
    so try each game root, and the folder of the referring model first since
    a custom model usually ships its animations beside itself.
    """
    rel = rel.replace("\\", "/").lstrip("/")
    tail = rel[len("models/"):] if rel.lower().startswith("models/") else rel
    cands = []
    if near is not None:
        cands.append(Path(near).parent / Path(tail).name)
    for r in roots:
        cands.append(Path(r) / rel)
        cands.append(Path(r) / "models" / tail)
    for c in cands:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def walk_model(path, max_depth=2):
    """
    Parse a model and everything it $includemodel's.

    Returns (list_of_parsed, list_of_unresolved_names). Depth-limited because
    animation models can include each other.
    """
    roots = search_roots()
    seen, out, missing = set(), [], []
    queue = [(Path(path), 0)]
    while queue:
        p, depth = queue.pop(0)
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        parsed = parse_mdl(p)
        if parsed is None:
            continue
        parsed["depth"] = depth
        out.append(parsed)
        if depth >= max_depth:
            continue
        for rel in parsed["includes"]:
            found = resolve_include(rel, roots, near=p)
            if found is None:
                missing.append(rel)
            else:
                queue.append((found, depth + 1))
    return out, missing


def report_lines(parsed_list, missing, max_seqs=40):
    L = []
    total_seq = sum(p["numlocalseq"] for p in parsed_list)
    total_anim = sum(p["numlocalanim"] for p in parsed_list)
    L.append(f"{len(parsed_list)} model file(s): "
             f"{total_seq} sequence(s), {total_anim} animation(s)")
    L.append("")
    for p in parsed_list:
        pad = "  " * p["depth"]
        L.append(f"{pad}{p['name']}  v{p['version']}  {p['size'] // 1024} KB")
        L.append(f"{pad}   bones {p['numbones']}   "
                 f"sequences {p['numlocalseq']}   "
                 f"animations {p['numlocalanim']}")
        if p["sidecars"]:
            L.append(f"{pad}   sidecars: " + ", ".join(
                f"{k} {v // 1024}KB" for k, v in sorted(p["sidecars"].items())))
        if p["includes"]:
            for inc in p["includes"]:
                L.append(f"{pad}   $includemodel {inc}")
        if p["numanimblocks"]:
            L.append(f"{pad}   animblocks {p['numanimblocks']} "
                     f"-> {p['animblock_name'] or '(unnamed)'}")
        # the sequences that actually carry animation here
        local = [s for s in p["seqs"] if s["numblends"]]
        for s in local[:max_seqs]:
            grid = ("" if s["groupsize"] == (1, 1)
                    else f" blend {s['groupsize'][0]}x{s['groupsize'][1]}")
            act = f"  [{s['activity']}]" if s["activity"] else ""
            names = []
            for b in s["blends"][:3]:
                if 0 <= b < len(p["anims"]):
                    a = p["anims"][b]
                    names.append(f"{a['name']}({a['frames']}f@{a['fps']:g})")
            L.append(f"{pad}   SEQ {s['label']}{act}{grid}"
                     + (f" -> {', '.join(names)}" if names else ""))
        if len(local) > max_seqs:
            L.append(f"{pad}   ... {len(local) - max_seqs} more with animation")
        remote = len(p["seqs"]) - len(local)
        if remote:
            L.append(f"{pad}   {remote} sequence(s) reference animation from "
                     f"an included model")
        L.append("")
    if missing:
        L.append(f"UNRESOLVED $includemodel ({len(missing)}) - "
                 f"their animation was not read:")
        for m in missing:
            L.append(f"   {m}")
    return L


# ─────────────────────────────────────────────────────────────────────────────
# Operator
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_mdl_sequences(Operator, ImportHelper):
    """PICK .mdl (compiled model) - the COMPILED file; $includemodel is
        followed into the models it points at

        List every sequence and animation in an MDL, following $includemodel

A Source sequence is a playback definition, not animation data: a label, an
activity, and indices into the model's animation list. The animation itself
usually lives in a DIFFERENT file - heavy.mdl declares 265 sequences and
holds 2 animations, while the heavy_animations.mdl it includes holds 710.

This follows those includes, resolves them against your SFM install, and
reports the whole picture: which file owns which sequence, how many frames
each animation has, and which blend grid it belongs to.

Reads the directory only - the compressed per-frame payload is not decoded.
Results go to a Text datablock and the system console"""
    bl_idname = "ht.mdl_sequences"
    bl_label = "MDL Sequence Report"
    bl_options = {"REGISTER"}

    filename_ext = ".mdl"
    filter_glob: StringProperty(default="*.mdl", options={"HIDDEN"})  # type: ignore

    follow_includes: BoolProperty(  # type: ignore
        name="Follow $includemodel",
        description=("Also parse the animation models this one includes. "
                     "Without it you see the sequence list but almost no "
                     "animations, because they live in the included files"),
        default=True,
    )
    max_seqs: IntProperty(  # type: ignore
        name="Sequences Per File",
        description="How many sequences to list per file before truncating",
        default=40, min=1, max=2000,
    )
    to_text: BoolProperty(  # type: ignore
        name="Write Text Datablock",
        description=("Put the report in a Blender Text block so you can "
                     "read and search it without the system console"),
        default=True,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "follow_includes")
        col.prop(self, "max_seqs")
        col.prop(self, "to_text")

    def execute(self, context):
        path = Path(self.filepath)
        if not path.is_file():
            self.report({"ERROR"}, "Pick an .mdl file")
            return {"CANCELLED"}

        try:
            if self.follow_includes:
                parsed, missing = walk_model(path)
            else:
                one = parse_mdl(path)
                parsed, missing = ([one] if one else []), []
                if one:
                    one["depth"] = 0
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        if not parsed:
            self.report({"ERROR"},
                        f"{path.name} is not a Source studio model")
            return {"CANCELLED"}

        lines = report_lines(parsed, missing, max_seqs=self.max_seqs)
        print()
        for line in lines:
            print(f"[MDL_SEQ]  {line}")

        if self.to_text:
            name = f"HT_mdl_sequences_{path.stem}"
            txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
            txt.clear()
            txt.write("\n".join(lines))

        total_seq = sum(p["numlocalseq"] for p in parsed)
        total_anim = sum(p["numlocalanim"] for p in parsed)
        head = lines[0]
        level = "WARNING" if missing else "INFO"
        from ..core import Report_UI
        Report_UI.report(context, "playground", "MDL Sequences", lines[:26],
                         level=level, icon='ACTION', operator=self,
                         prefix="PLAYGROUND",
                         summary=f"MDL Sequences - {total_seq} sequence(s), "
                                 f"{total_anim} animation(s)"
                                 + (f", {len(missing)} include(s) not found"
                                    if missing else ""))
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────────────────────────────────────

class HT_MT_playground_submenu(bpy.types.Menu):
    """Source Engine experiments that are not part of session import"""
    bl_idname = "HT_MT_playground_submenu"
    bl_label = "Playground"

    def draw(self, context):
        layout = self.layout
        layout.operator(HT_OT_mdl_sequences.bl_idname,
                        text="MDL Sequence Report",
                        **_icon_id("mdl_sequences", 'ACTION'))


def draw_playground(layout, context):
    """The Playground box. NOT CURRENTLY DRAWN ANYWHERE - kept on the record.

    The Developer tab used to call this, and the box it drew held
    `ht.mdl_sequences`, which the Experimental box directly above it drew too:
    the same operator, twice, on one tab. The 2026-08-22 (c) cleanup took every
    duplicate off that tab and this went with them.

    The Playground SUBMENU is untouched and still on File > Import > Source
    Engine (HoovyTools), which is where experiments have always lived. Call
    this again from a panel if the box is ever wanted back."""
    box = layout.box()
    box.label(text="Playground", **_icon_id("experimental", 'RNDCURVE'))
    sub = box.column(align=True)
    sub.scale_y = 0.8
    sub.label(text="Source experiments, kept out of")
    sub.label(text="the session workflow on purpose.")
    col = box.column(align=True)
    col.operator("ht.mdl_sequences", text="MDL Sequence Report",
                 **_icon_id("mdl_sequences", 'ACTION'))


def draw_menu_item(layout):
    layout.menu(HT_MT_playground_submenu.bl_idname,
                **_icon_id("experimental", 'RNDCURVE'))


_CLASSES = (
    HT_OT_mdl_sequences,
    HT_MT_playground_submenu,
)


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
