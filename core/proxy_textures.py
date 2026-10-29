"""
proxy_textures.py  -  part of SFM to Blender (Session Importer)    [1.21.0, 1.23.0, 1.25.0]
====================================================================

PROXY TEXTURES: each material of a model imported WITHOUT textures gets a
small copy of its own base texture - the look survives, the import stays quick
and a saved .blend stays small (a full FNAF session's textures made a 935 MB
.blend; proxies are kilobytes).

WHERE THE PICTURE COMES FROM
----------------------------
A VTF already carries every size of its picture (its mip chain, smallest
first). The proxy is the largest mip that is still MAX_SIZE px or less, read
straight out of the file - nothing is resized, nothing full-size is decoded
(a VTF with no mip that small: ONE MIP below).

    material name (the .mdl's texture table)  +  the .mdl's $cdmaterials
      -> materials/<cd>/<name>.vmt in the same mounts the session import
         searches for models (usermod, gameinfo's SearchPaths, every mod
         folder under game/)
      -> its $basetexture -> materials/<basetexture>.vtf -> one small mip

A material whose VMT or VTF is not loose on disk (inside a game's VPK) gets a
flat grey and is counted, never guessed at.

ONE MIP (1.25.0)
----------------
A VTF made without mips has nothing that small: your tettris Glamrock
textures are one 4096 px picture each (freddy_spurk_a's 2048). Before 1.25.0
the whole picture was decoded and packed at full size - Glamrock Freddy and
freddy_spurk_a: 20 images, 96 MB in the .blend, 1.3 - 2.4 s per texture. Now
the smallest mip there is gets SAMPLED down to MAX_SIZE: each proxy pixel
averages SAMPLES x SAMPLES of the 4x4 blocks spread over the area it covers
(all 16 texels of each; pixels, for an uncompressed format) - only those
blocks are decoded, never the whole picture.

ONE IMAGE PER VTF (1.25.0)
--------------------------
Two VMTs on one $basetexture (Glamrock Freddy's Body and Body_MTL, Hour1 and
Hour1_MTL ...; freddy_spurk_a's four on one basecolor) made two images of it.
An image now remembers its VTF (ht_proxy_vtf) and is made once per .blend:
every material, of this model or another, that uses that VTF shares it.

Formats read: DXT1 / DXT3 / DXT5, the 8-bit RGBA orders, RGB888 / BGR888,
I8, IA88, A8. Anything else: grey, counted.

    V1        the first time that VMT comes in this .blend
    shared    the same VMT again (its full path) in the same mode: the
              material made the first time is used - six copies of a model,
              one set of materials, no second set of proxy images
    V2, V3 .. a material of that name that is another VMT's, the other
              mode's, or not made here (yours, edited) is never taken and
              never renamed over; an eye's own material (one per model copy,
              its full path carries an id) is never shared - the next V

so a full-texture import of the same model later never meets a proxy
material of its own name. Each keeps its VMT's name (ht_proxy_vmt) and full
path (full_path, ht_proxy_of) - a skin swap still finds it.
"""

import math
import os
import re
import struct

import bpy

MAX_SIZE = 64                       # px - the proxy is the largest mip at or under this
SAMPLES = 4                         # 1.25.0: blocks (pixels) a side averaged into a proxy pixel when no mip is that small
IMAGE_KEY = "ht_proxy_vtf"          # 1.25.0: the VTF (and size) an image was made from - one image per VTF
GREY = (0.5, 0.5, 0.5, 1.0)
_BPP = {0: 4, 1: 4, 2: 3, 3: 3, 5: 1, 6: 2, 8: 1, 11: 4, 12: 4, 16: 4}
_DXT = {13: 8, 14: 16, 15: 16, 20: 8}


# ------------------------------------------------------------------ the .mdl
def mdl_materials(mdl_path):
    """(texture names, cdmaterials folders) from a Source 1 .mdl - its texture table and $cdmaterials"""
    with open(mdl_path, "rb") as f:
        d = f.read()
    if d[:4] != b"IDST":
        return [], []

    def cstr(o):
        return d[o:d.index(b"\0", o)].decode("latin-1")

    n_tex, tex_at, n_cd, cd_at = struct.unpack_from("<iiii", d, 204)
    names = [cstr(tex_at + i * 64 + struct.unpack_from("<i", d, tex_at + i * 64)[0]) for i in range(max(0, n_tex))]
    cds = [cstr(struct.unpack_from("<i", d, cd_at + i * 4)[0]) for i in range(max(0, n_cd))]
    return names, cds


# ------------------------------------------------------------------ VMT / VTF on disk
def _norm(p):
    return str(p).replace("\\", "/").strip("/").lower()


def find_file(rel, search_dirs):
    """materials/... relative path -> the first loose file in the mounts (case-insensitive on Windows anyway)"""
    rel = rel.replace("\\", "/").lstrip("/")
    for d in search_dirs:
        p = os.path.join(str(d), rel)
        if os.path.isfile(p):
            return p
    return None


def vmt_basetexture(vmt_path, search_dirs, depth=0):
    """(basetexture, translucent) from a VMT; a patch VMT is followed to its include once"""
    try:
        txt = open(vmt_path, encoding="latin-1").read()
    except OSError:
        return None, False
    low = txt.lower()

    def val(key):
        m = re.search(r'"?\$' + key + r'"?\s+"?([^"\n\r}]+)"?', low)
        return m.group(1).strip() if m else None

    base = val("basetexture")
    trans = (val("translucent") or "0").startswith("1") or (val("alphatest") or "0").startswith("1")
    if base is None and depth == 0:
        m = re.search(r'"?include"?\s+"([^"]+)"', low)
        if m:
            inc = find_file(m.group(1), search_dirs)
            if inc:
                b2, t2 = vmt_basetexture(inc, search_dirs, depth + 1)
                return b2, trans or t2
    return base, trans


def _dxt_blocks(blk, kind):
    """the 16 texels of each DXT block (RGBA 0..255, row by row): (N, block bytes) -> (N, 16, 4)"""
    import numpy as np
    col = blk[:, -8:]
    c0 = col[:, 0].astype(np.uint32) | (col[:, 1].astype(np.uint32) << 8)
    c1 = col[:, 2].astype(np.uint32) | (col[:, 3].astype(np.uint32) << 8)

    def rgb(c):
        return np.stack([((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31], -1)

    p0, p1 = rgb(c0).astype(np.float32), rgb(c1).astype(np.float32)
    four = (c0 > c1) | (kind != 13 and kind != 20)
    p2 = np.where(four[:, None], (2 * p0 + p1) / 3, (p0 + p1) / 2)
    p3 = np.where(four[:, None], (p0 + 2 * p1) / 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)                                   # (N, 4, 3)
    a_pal = np.full((len(blk), 4), 255.0, np.float32)
    if kind in (13, 20):
        a_pal[:, 3] = np.where(four, 255.0, 0.0)
    bits = col[:, 4].astype(np.uint32) | (col[:, 5].astype(np.uint32) << 8) | \
        (col[:, 6].astype(np.uint32) << 16) | (col[:, 7].astype(np.uint32) << 24)
    idx = np.stack([(bits >> (2 * i)) & 3 for i in range(16)], 1)        # (N, 16)
    rgbv = np.take_along_axis(pal, idx[:, :, None].repeat(3, 2), 1)       # (N, 16, 3)
    alpha = np.take_along_axis(a_pal, idx, 1)
    if kind == 14:                                                       # DXT3: explicit 4-bit alpha
        a = blk[:, :8]
        alpha = np.stack([((a[:, i // 2] >> (4 * (i % 2))) & 15) * 17 for i in range(16)], 1).astype(np.float32)
    elif kind == 15:                                                     # DXT5: interpolated alpha
        a0, a1 = blk[:, 0].astype(np.float32), blk[:, 1].astype(np.float32)
        ab = np.zeros(len(blk), np.uint64)
        for i in range(6):
            ab |= blk[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
        ai = np.stack([((ab >> np.uint64(3 * i)) & np.uint64(7)).astype(np.int64) for i in range(16)], 1)
        eight = a0 > a1
        tbl = [a0, a1] + [np.where(eight, ((7 - k) * a0 + k * a1) / 7, ((5 - k) * a0 + k * a1) / 5) for k in range(1, 5)]
        tbl += [np.where(eight, (2 * a0 + 5 * a1) / 7, 0.0), np.where(eight, (a0 + 6 * a1) / 7, 255.0)]
        alpha = np.take_along_axis(np.stack(tbl, 1), ai, 1)
    return np.concatenate([rgbv, alpha[:, :, None]], 2)


def _decode_dxt(data, w, h, kind):
    import numpy as np
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    bs = _DXT[kind]
    blk = np.frombuffer(data, np.uint8, bw * bh * bs).reshape(-1, bs)
    px = _dxt_blocks(blk, kind).reshape(bh, bw, 4, 4, 4)
    img = px.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return img[:h, :w] / 255.0


def _decode_raw(data, w, h, fmt):
    import numpy as np
    n = w * h
    a = np.frombuffer(data, np.uint8, n * _BPP[fmt]).reshape(h, w, _BPP[fmt]).astype(np.float32) / 255.0
    one = np.ones((h, w), np.float32)
    order = {0: (0, 1, 2, 3), 1: (3, 2, 1, 0), 11: (1, 2, 3, 0), 12: (2, 1, 0, 3), 16: (2, 1, 0, None)}
    if fmt in order:
        r, g, b, al = order[fmt]
        return np.stack([a[..., r], a[..., g], a[..., b], a[..., al] if al is not None else one], -1)
    if fmt == 2:
        return np.stack([a[..., 0], a[..., 1], a[..., 2], one], -1)
    if fmt == 3:
        return np.stack([a[..., 2], a[..., 1], a[..., 0], one], -1)
    if fmt == 5:
        return np.stack([a[..., 0]] * 3 + [one], -1)
    if fmt == 6:
        return np.stack([a[..., 0]] * 3 + [a[..., 1]], -1)
    return np.stack([one * 0.5] * 3 + [a[..., 0]], -1)                   # A8


def _spots(n_src, n_out, k):
    """(n_out, k): k places spread evenly inside each of n_out equal cells of n_src (blocks or pixels)"""
    import numpy as np
    pos = (np.arange(n_out)[:, None] + (np.arange(k)[None, :] + 0.5) / k) * (n_src / float(n_out))
    return np.clip(pos.astype(np.int64), 0, n_src - 1)


def _shrink(data, w, h, fmt, max_size, k=SAMPLES):
    """1.25.0 (ONE MIP above): a mip larger than max_size sampled down, never decoded whole - (w, h, RGBA top row
    first, 0..1). Each proxy pixel averages k x k of the 4x4 blocks (all their texels) spread over the area it covers;
    an uncompressed mip: k x k of its pixels."""
    import numpy as np
    s = max(w, h) / float(max_size)
    ow, oh = min(max_size, max(1, int(round(w / s)))), min(max_size, max(1, int(round(h / s))))
    if fmt in _DXT:
        bw, bh, bs = max(1, (w + 3) // 4), max(1, (h + 3) // 4), _DXT[fmt]
        blk = np.frombuffer(data, np.uint8, bw * bh * bs).reshape(bh, bw, bs)
        sel = blk[_spots(bh, oh, k)[:, :, None, None], _spots(bw, ow, k)[None, None, :, :]]     # (oh, k, ow, k, bs)
        tex = _dxt_blocks(np.ascontiguousarray(sel).reshape(-1, bs), fmt).reshape(oh, k, ow, k, 16, 4)
        return ow, oh, tex.mean(axis=(1, 3, 4)) / 255.0
    bpp = _BPP[fmt]
    src = np.frombuffer(data, np.uint8, w * h * bpp).reshape(h, w, bpp)
    sel = src[_spots(h, oh, k)[:, :, None, None], _spots(w, ow, k)[None, None, :, :]]           # (oh, k, ow, k, bpp)
    px = _decode_raw(np.ascontiguousarray(sel).tobytes(), oh * k * ow * k, 1, fmt)            # (1, N, 4), 0..1
    return ow, oh, px.reshape(oh, k, ow, k, 4).mean(axis=(1, 3))


def read_vtf_proxy(vtf_path, max_size=MAX_SIZE):
    """(w, h, RGBA float array top row first) of the largest mip <= max_size - 1.25.0: or of the smallest mip there
    is, sampled down to max_size (a VTF with one mip) - or None (format not read)"""
    with open(vtf_path, "rb") as f:
        d = f.read()
    if d[:4] != b"VTF\0":
        return None
    vmaj, vmin, hsize = struct.unpack_from("<III", d, 4)
    w, h, flags, frames = struct.unpack_from("<HHIH", d, 16)
    fmt = struct.unpack_from("<i", d, 52)[0]
    mips = d[56]
    lo_fmt = struct.unpack_from("<i", d, 57)[0]
    lo_w, lo_h = d[61], d[62]
    depth = struct.unpack_from("<H", d, 63)[0] if (vmaj, vmin) >= (7, 2) else 1
    depth = max(1, depth)
    faces = (6 if (vmaj, vmin) >= (7, 5) else 7) if flags & 0x4000 else 1
    frames = max(1, frames)

    def size(fm, mw, mh):
        if fm in _DXT:
            return max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * _DXT[fm]
        return mw * mh * _BPP.get(fm, 0)

    if fmt not in _DXT and fmt not in _BPP:
        return None
    if (vmaj, vmin) >= (7, 3):
        n_res = struct.unpack_from("<I", d, 68)[0]
        start = None
        for i in range(n_res):
            tag, rflags, off = struct.unpack_from("<3sBI", d, 80 + i * 8)
            if tag == b"\x30\x00\x00":
                start = off
        if start is None:
            return None
    else:
        start = hsize + (size(lo_fmt, lo_w, lo_h) if lo_fmt >= 0 and lo_w and lo_h else 0)
    want = 0
    while want < mips - 1 and max(w >> want, h >> want) > max_size:
        want += 1
    off = start
    for m in range(mips - 1, want, -1):
        off += size(fmt, max(1, w >> m), max(1, h >> m)) * frames * faces * depth
    mw, mh = max(1, w >> want), max(1, h >> want)
    data = d[off:off + size(fmt, mw, mh)]
    if len(data) < size(fmt, mw, mh):
        return None
    if max(mw, mh) > max_size:
        return _shrink(data, mw, mh, fmt, max_size)                     # 1.25.0: no mip that small - ONE MIP above
    img = _decode_dxt(data, mw, mh, fmt) if fmt in _DXT else _decode_raw(data, mw, mh, fmt)
    return mw, mh, img


# ------------------------------------------------------------------ the materials
def _strip(name):
    return re.sub(r"\.\d{3}$", "", name).lower().replace("\\", "/").split("/")[-1]


def _image(name, w, h, img):
    import numpy as np
    im = bpy.data.images.new(name, w, h, alpha=True)
    im.pixels.foreach_set(np.ascontiguousarray(img[::-1]).astype(np.float32).ravel())   # Blender rows: bottom first
    im.pack()
    return im


def proxy_image(vtf, max_size=MAX_SIZE):
    """1.25.0 (ONE IMAGE PER VTF above): (the proxy image of this VTF, made earlier in this .blend?) - made once per
    VTF and size, then shared; (None, False) when its format is not read"""
    key = "%s|%d" % (os.path.normcase(os.path.abspath(vtf)), max_size)
    for im in bpy.data.images:
        if im.get(IMAGE_KEY) == key:
            return im, True
    got = read_vtf_proxy(vtf, max_size)
    if got is None:
        return None, False
    w, h, pix = got
    im = _image("%s (proxy %d)" % (os.path.splitext(os.path.basename(vtf))[0], max(w, h)), w, h, pix)
    im[IMAGE_KEY] = key
    return im, False


def _build(mat, image, translucent):
    if mat.node_tree is None:                 # Blender 5.x: use_nodes goes in 6.0 - only when it has none
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out.location, bsdf.location = (300, 0), (0, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if image is None:
        bsdf.inputs["Base Color"].default_value = GREY
        return
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location, tex.image, tex.interpolation = (-320, 0), image, "Closest"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if translucent:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:                                     # noqa: BLE001
            pass
    mat["ht_proxy_texture"] = image.name


def _materials_of(objects):
    mats = []
    for o in objects:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            if slot.material is not None and slot.material not in mats:
                mats.append(slot.material)
    return mats


def name_proxies(objects, mode, log=print):
    """1.23.0: every material on these objects named <vmt>_proxy_V<n> (THE NAMES above). Returns (the materials
    made new here - they need building, the number shared with an earlier import)."""
    fresh, shared = [], 0
    for mat in _materials_of(objects):
        if mat.get("ht_proxy_of"):
            continue                                  # already one of ours (taken from an earlier import)
        #  the VMT: its full path (before a '#': an eye's own material per model copy carries an id there), else
        #  the material's name (no .001, no "[...]" note, no folders) - in the VMT's own spelling
        fp = str(mat.get("full_path", "") or "").replace("\\", "/")
        base = fp.split("#", 1)[0] if fp else re.sub(r"\s*\[.*\]$", "", re.sub(r"\.\d{3}$", "", mat.name))
        shown = base.replace("\\", "/").rstrip("/").split("/")[-1] or _strip(mat.name)
        vmt = shown.lower()                           # lower case: the lookups
        key = ((fp or vmt).lower(), str(mode).upper())
        same = next((m for m in bpy.data.materials if m is not mat and m.get("ht_proxy_of") == key[0]
                     and m.get("ht_proxy_mode") == key[1]), None)
        if same is not None:
            mat.user_remap(same)
            if mat.users == 0:
                bpy.data.materials.remove(mat)
            shared += 1
            continue
        n = 1
        while True:
            tail = "_proxy_V%d" % n
            name = shown[:63 - len(tail)] + tail
            if bpy.data.materials.get(name) is None:
                break
            n += 1
        mat.name = name
        mat["ht_proxy_vmt"] = vmt
        mat["ht_proxy_of"] = key[0]
        mat["ht_proxy_mode"] = key[1]
        fresh.append(mat)
    log("  Material names: %d named <vmt>_proxy_V<n>%s" % (
        len(fresh), (", %d shared with an earlier import of the same VMT" % shared) if shared else ""))
    return fresh, shared


def plain(objects, log=print):
    """Textures: None - every material a plain opaque grey. Without its images the importer's shader reads its
    alpha as 0 and the body renders as a see-through ghost (seen 2026-10-15 on scout). 1.23.0: named
    <vmt>_proxy_V<n> first (an earlier import's are shared, not built again)."""
    mats, shared = name_proxies(objects, "NONE", log=log)
    for mat in mats:
        _build(mat, None, False)
    log("  No textures: %d material(s) plain grey" % len(mats))
    return {"materials": len(mats), "proxied": 0, "grey": len(mats), "reasons": {}, "shared": shared}


def apply(objects, mdl_path, search_dirs, max_size=MAX_SIZE, log=print):
    """Give every material on these objects its proxy texture. Returns {"materials", "proxied", "grey", "reasons"}."""
    names, cds = mdl_materials(mdl_path)
    by_name = {n.lower().replace("\\", "/").split("/")[-1]: n for n in names}
    mats, shared = name_proxies(objects, "PROXY", log=log)          # 1.23.0: named first, shared ones not rebuilt
    rep = {"materials": len(mats), "proxied": 0, "grey": 0, "reasons": {}, "shared": shared, "images shared": 0}
    for mat in mats:
        key = mat.get("ht_proxy_vmt") or _strip(mat.name)
        tex_name = by_name.get(key, key)
        why = None
        img = None
        vmt = None
        for cd in (cds or [""]):
            vmt = find_file("materials/%s/%s.vmt" % (_norm(cd), _norm(tex_name)), search_dirs)
            if vmt:
                break
        if vmt is None:
            why = "no loose .vmt"
        else:
            base, translucent = vmt_basetexture(vmt, search_dirs)
            vtf = find_file("materials/%s.vtf" % _norm(base), search_dirs) if base else None
            if vtf is None:
                why = "no loose .vtf" if base else "no $basetexture"
            else:
                try:
                    img, again = proxy_image(vtf, max_size)          # 1.25.0: once per VTF, shared after
                except Exception as exc:                      # noqa: BLE001
                    img, again, why = None, False, "unreadable vtf (%s)" % exc
                if img is None:
                    why = why or "vtf format not read"
                elif again:
                    rep["images shared"] += 1
        _build(mat, img, img is not None and translucent)
        if img is None:
            rep["grey"] += 1
            rep["reasons"][why] = rep["reasons"].get(why, 0) + 1
        else:
            rep["proxied"] += 1
    log("  Proxy textures: %d of %d material(s)%s%s" % (
        rep["proxied"], rep["materials"],
        (", %d on an image another material already uses" % rep["images shared"]) if rep["images shared"] else "",
        (" - grey: " + ", ".join("%d %s" % (n, r) for r, n in rep["reasons"].items())) if rep["grey"] else ""))
    return rep
