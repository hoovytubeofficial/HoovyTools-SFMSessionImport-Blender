"""
core/mdl_flex.py  -  a model's face rules, read out of its .mdl and written as the .qc lines the HWM bake reads

3.0.0.

WHY
---
The HWM face bake (importers/Import_Shape_Keys.bake_hwm_localvars) needs four things from a model's QC: its flex
controllers and their ranges, its %rules, which flexes are stereo PAIRS, and the eyelid heights. Twelve TF2 / HL2
QCs ship in _QC Face Data, so every other face got no bake at all. All four are also compiled INTO the .mdl -
studiomdl turns each QC rule into a small stack program - so this reads them back out and writes the same lines:

    flexcontroller phoneme range 0 1 jaw_drop
    %AU26 = jaw_drop
    flexpair "AU12" 1 frame 0
    eyelid upper_right "scout.vta" lowerer 1 -0.24 neutral 0 0.15 raiser 2 0.22 split 0.1 eyeball "eye_right"

Pure Python (struct + pathlib), no bpy: it reads a file and returns text, so it can be checked outside Blender.

THE MDL LAYOUT (studiohdr_t, versions 44-49 - every SFM / TF2 / HL2 model)
-------------------------------------------------------------------------
    232 numbodyparts   236 bodypartindex
    260 numflexdesc    264 flexdescindex          mstudioflexdesc_t        4 bytes  name offset
    268 numflexcontrollers 272 flexcontrollerindex mstudioflexcontroller_t 20 bytes  type, name, global, min, max
    276 numflexrules   280 flexruleindex          mstudioflexrule_t       12 bytes  flex, numops, opindex
                                                  mstudioflexop_t          8 bytes  op, index | value
    bodypart 16 -> model 148 (eyeballs @100/104, meshes @72/76) -> mesh 116 (flexes @16/20) -> flex 60 (flexpair @28)
    eyeball 172: upperflexdesc @68, lowerflexdesc @80, uppertarget @92, lowertarget @104, lid flexdescs @116/@120
Every string offset is relative to the struct that holds it.
"""

import re
import struct
from pathlib import Path

GENERATOR = "mdl_flex 1"            # bump when the output changes: older generated files are then rewritten
SOURCE_TAG = "// source:"

#  studio.h's flex ops
CONST, FETCH1, FETCH2, ADD, SUB, MUL, DIV, NEG, EXP = 1, 2, 3, 4, 5, 6, 7, 8, 9
OPEN, CLOSE, COMMA, MAX, MIN = 10, 11, 12, 13, 14
TWOWAY_0, TWOWAY_1, NWAY, COMBO, DOMINATE = 15, 16, 17, 18, 19
DME_LOWER_EYELID, DME_UPPER_EYELID = 20, 21

_IDENT = re.compile(r"^[A-Za-z_]\w*$")


class MdlFlexError(Exception):
    """The file is not a model this reader understands - the message says why."""


def _num(x):
    """A number the bake's parsers read: plain decimals, never an exponent."""
    x = float(x)
    if abs(x) < 5e-7:
        return "0"
    s = ("%.6f" % x).rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def _cstr(data, off):
    if off <= 0 or off >= len(data):
        return ""
    end = data.find(b"\0", off)
    return data[off:end if end >= 0 else len(data)].decode("latin-1", "replace")


def read(mdl_path):
    """Everything face-related in one .mdl, as plain data. Raises MdlFlexError for a file it cannot read."""
    path = Path(mdl_path)
    data = path.read_bytes()
    if len(data) < 400 or data[:4] != b"IDST":
        raise MdlFlexError("%s is not a Source model (no IDST header)" % path.name)
    version = struct.unpack_from("<i", data, 4)[0]
    if not 44 <= version <= 49:
        raise MdlFlexError("%s is MDL version %d - this reader knows 44 to 49" % (path.name, version))

    def i32(off):
        return struct.unpack_from("<i", data, off)[0]

    def inside(off, size=1):
        return 0 < off and off + size <= len(data)

    n_desc, desc_ix = i32(260), i32(264)
    n_ctrl, ctrl_ix = i32(268), i32(272)
    n_rule, rule_ix = i32(276), i32(280)
    n_bp, bp_ix = i32(232), i32(236)
    for n, ix, size, what in ((n_desc, desc_ix, 4, "flexdesc"), (n_ctrl, ctrl_ix, 20, "flexcontroller"),
                              (n_rule, rule_ix, 12, "flexrule"), (n_bp, bp_ix, 16, "bodypart")):
        if n < 0 or n > 100000 or (n and not inside(ix, n * size)):
            raise MdlFlexError("%s: the %s table points outside the file (%d at %d)" % (path.name, what, n, ix))

    descs = []
    for k in range(n_desc):
        o = desc_ix + 4 * k
        descs.append(_cstr(data, o + i32(o)))

    ctrls = []
    for k in range(n_ctrl):
        o = ctrl_ix + 20 * k
        lo, hi = struct.unpack_from("<ff", data, o + 12)
        ctrls.append({"type": _cstr(data, o + i32(o)), "name": _cstr(data, o + i32(o + 4)),
                      "min": lo, "max": hi})

    rules = []
    for k in range(n_rule):
        o = rule_ix + 12 * k
        flex, nops, opix = struct.unpack_from("<iii", data, o)
        if nops < 0 or not inside(o + opix, nops * 8):
            raise MdlFlexError("%s: rule %d's program points outside the file" % (path.name, k))
        ops = []
        for m in range(nops):
            oo = o + opix + 8 * m
            op = i32(oo)
            ops.append((op, struct.unpack_from("<f", data, oo + 4)[0] if op == CONST else i32(oo + 4)))
        rules.append((flex, ops))

    pairs, eyes = [], []
    for b in range(n_bp):
        bo = bp_ix + 16 * b
        n_models, model_ix = i32(bo + 4), i32(bo + 12)
        if n_models < 0 or (n_models and not inside(bo + model_ix, n_models * 148)):
            continue
        for mi in range(n_models):
            mo = bo + model_ix + 148 * mi
            n_mesh, mesh_ix = i32(mo + 72), i32(mo + 76)
            n_eye, eye_ix = i32(mo + 100), i32(mo + 104)
            if 0 < n_mesh < 10000 and inside(mo + mesh_ix, n_mesh * 116):
                for me in range(n_mesh):
                    so = mo + mesh_ix + 116 * me
                    n_flex, flex_ix = i32(so + 16), i32(so + 20)
                    if not (0 < n_flex < 100000 and inside(so + flex_ix, n_flex * 60)):
                        continue
                    for f in range(n_flex):
                        fo = so + flex_ix + 60 * f
                        desc, partner = i32(fo), i32(fo + 28)
                        if partner and (desc, partner) not in pairs:
                            pairs.append((desc, partner))
            if 0 < n_eye < 64 and inside(mo + eye_ix, n_eye * 172):
                for e in range(n_eye):
                    eo = mo + eye_ix + 172 * e
                    eyes.append({"name": _cstr(data, eo + i32(eo)),
                                 "upper": struct.unpack_from("<3f", data, eo + 92),
                                 "lower": struct.unpack_from("<3f", data, eo + 104),
                                 "upper_lid": i32(eo + 116), "lower_lid": i32(eo + 120)})
    return {"path": str(path), "version": version, "descs": descs, "controllers": ctrls,
            "rules": rules, "pairs": pairs, "eyes": eyes}


# ─────────────────────────────────────────────────────────────────────────────
#  Rule programs -> expressions
# ─────────────────────────────────────────────────────────────────────────────
#
#  The engine runs each rule on a stack (CStudioHdr::RunFlexRules). Run the same program on TEXT and the stack ends
#  holding the expression. The bake's evaluator knows + - * /, min, max and names (a controller's value in its
#  range; %name = another flex already computed), so the remapping ops are written out with those:
#      2WAY_0   RemapValClamped(c, -1, 0, 1, 0) = min(1, max(0, -c))
#      2WAY_1   RemapValClamped(c,  0, 1, 0, 1) = min(1, max(0, c))
#      COMBO    the product of the last n
#      DOMINATE value * (1 - product of the last n)
#      NWAY     a trapezoid ramp of one controller times another
#      DME_*_EYELID  the DMX eyelid rule, written with the same pieces
#  A program using anything else (EXP, a ramp built from non-constants) is skipped and named in a comment.

def _remap01(c):
    """RemapValClamped(controller, min, max, 0, 1) - the controller as 0..1 of its own range."""
    span = c["max"] - c["min"]
    if abs(span) < 1e-9:
        return "0"
    return "min(1, max(0, (%s - (%s)) / %s))" % (c["name"], _num(c["min"]), _num(span))


def _ramp(x, a, b, invert):
    """clamp((x-a)/(b-a)) rising, or the falling twin; a step when the edge has no width."""
    w = b - a
    if abs(w) < 1e-9:
        body = "(%s - (%s)) * 1000000" % (x, _num(a))
    else:
        body = "(%s - (%s)) / %s" % (x, _num(a), _num(w))
    if invert:
        body = "1 - (%s)" % body
    return "min(1, max(0, %s))" % body


def rule_expression(ops, descs, ctrls):
    """(expression, None) or (None, why it could not be written)."""
    stack = []                                 # [(text, constant value or None)]

    def ctrl(ix):
        if not 0 <= ix < len(ctrls):
            raise ValueError("controller %d does not exist" % ix)
        c = ctrls[ix]
        if not _IDENT.match(c["name"]):
            raise ValueError("controller name %r is not a plain name" % c["name"])
        return c

    def pop():
        if not stack:
            raise ValueError("the program reads an empty stack")
        return stack.pop()

    def const_index(item):
        if item[1] is None:
            raise ValueError("an index that is not a constant")
        return int(item[1])

    try:
        for op, val in ops:
            if op == CONST:
                stack.append((_num(val) if val >= 0 else "(%s)" % _num(val), float(val)))
            elif op == FETCH1:
                stack.append((ctrl(val)["name"], None))
            elif op == FETCH2:
                if not 0 <= val < len(descs) or not _IDENT.match(descs[val]):
                    raise ValueError("flex %d is not a plain name" % val)
                stack.append(("%" + descs[val], None))
            elif op in (ADD, SUB, MUL, DIV):
                b, a = pop(), pop()
                sym = {ADD: "+", SUB: "-", MUL: "*", DIV: "/"}[op]
                stack.append(("(%s %s %s)" % (a[0], sym, b[0]), None))
            elif op == NEG:
                a = pop()
                stack.append(("(-%s)" % a[0], None))
            elif op in (MAX, MIN):
                b, a = pop(), pop()
                stack.append(("%s(%s, %s)" % ("max" if op == MAX else "min", a[0], b[0]), None))
            elif op == TWOWAY_0:
                stack.append(("min(1, max(0, -%s))" % ctrl(val)["name"], None))
            elif op == TWOWAY_1:
                stack.append(("min(1, max(0, %s))" % ctrl(val)["name"], None))
            elif op == COMBO:
                n = int(val)
                if n < 1 or n > len(stack):
                    raise ValueError("COMBO of %d values" % n)
                items = [pop() for _ in range(n)][::-1]
                stack.append(("(%s)" % " * ".join(t for t, _v in items), None))
            elif op == DOMINATE:
                n = int(val)
                if n < 1 or n + 1 > len(stack):
                    raise ValueError("DOMINATE of %d values" % n)
                dom = [pop() for _ in range(n)][::-1]
                base = pop()
                stack.append(("(%s * (1 - %s))" % (base[0], " * ".join(t for t, _v in dom)), None))
            elif op == NWAY:
                value_ctrl = ctrl(const_index(pop()))
                d_, c_, b_, a_ = pop(), pop(), pop(), pop()
                if None in (a_[1], b_[1], c_[1], d_[1]):
                    raise ValueError("an NWAY ramp that is not constant")
                x = value_ctrl["name"]
                ramp = "min(%s, %s)" % (_ramp(x, a_[1], b_[1], False), _ramp(x, c_[1], d_[1], True))
                stack.append(("(%s * %s)" % (ramp, ctrl(val)["name"]), None))
            elif op in (DME_LOWER_EYELID, DME_UPPER_EYELID):
                #  The stack holds three controller INDICES (close lid, blink, eye up/down); the decompiled TF2 QCs
                #  write the same three-way product, and the blink index is read and left out, as they do.
                close_lid_v = _remap01(ctrl(val))
                close_lid = _remap01(ctrl(const_index(pop())))
                const_index(pop())                                 # blink
                updown_ix = const_index(pop())
                if updown_ix >= 0:
                    updown = "(%s * 2 - 1)" % _remap01(ctrl(updown_ix))     # RemapValClamped(.., -1, 1)
                else:
                    updown = "0"
                if op == DME_LOWER_EYELID:
                    #  looking up opens the lower lid: (1 - max(0, up)) * (1 - closeV) * close
                    expr = "((1 - max(0, %s)) * (1 - %s) * %s)" % (updown, close_lid_v, close_lid)
                else:
                    #  looking down lowers the upper lid: (1 + min(0, up)) * closeV * close
                    expr = "((1 + min(0, %s)) * %s * %s)" % (updown, close_lid_v, close_lid)
                stack.append((expr, None))
            elif op in (OPEN, CLOSE, COMMA):
                continue                           # parser-only tokens, never in a compiled program
            else:
                raise ValueError("op %d is not supported" % op)
    except (ValueError, IndexError) as exc:
        return None, str(exc)
    if len(stack) != 1:
        return None, "the program leaves %d values" % len(stack)
    return stack[0][0], None


# ─────────────────────────────────────────────────────────────────────────────
#  The .qc text
# ─────────────────────────────────────────────────────────────────────────────

def _pair_base(a, b):
    """'AU12R' + 'AU12L' -> 'AU12'. None when the two do not read as one pair."""
    if len(a) > 1 and len(b) == len(a) and a[:-1] == b[:-1] and {a[-1:].upper(), b[-1:].upper()} == {"R", "L"}:
        return a[:-1]
    return None


def qc_text(info, stamp=""):
    """The face part of a QC, in the forms the bake's parsers read. (text, counts)."""
    descs, ctrls = info["descs"], info["controllers"]
    src = Path(info["path"])
    L = ["// Face data for %s, read from the compiled model by SFM Session Importer (%s)." % (src.name, GENERATOR),
         "%s %s" % (SOURCE_TAG, stamp or src),
         "// Written so the HWM face bake can run on any model. Delete it any time - the next import writes it again;",
         "// a hand-made %s.qc in _QC Face Data (or your override folder) always wins over this one." % src.stem,
         ""]
    L.append("// flex controllers (%d)" % len(ctrls))
    for c in ctrls:
        if not _IDENT.match(c["name"]):
            L.append("// skipped controller %r - not a plain name" % c["name"])
            continue
        typ = c["type"] if _IDENT.match(c["type"] or "") else "default"
        L.append("flexcontroller %s range %s %s %s" % (typ, _num(c["min"]), _num(c["max"]), c["name"]))

    pairs = []
    for d, p in info["pairs"]:
        if 0 <= d < len(descs) and 0 <= p < len(descs):
            base = _pair_base(descs[d], descs[p])
            if base and base not in pairs:
                pairs.append(base)
    L += ["", "// stereo flexes (%d) - the bake splits each <name>R into R and L" % len(pairs)]
    L += ['flexpair "%s" 1 frame 0' % base for base in pairs]

    lids = []
    for eye in info["eyes"]:
        for side in ("upper", "lower"):
            ix = eye["%s_lid" % side]
            h = eye[side]
            if 0 <= ix < len(descs) and _IDENT.match(descs[ix]) and any(abs(v) > 1e-6 for v in h):
                lids.append('eyelid %s "%s.vta" lowerer 1 %s neutral 0 %s raiser 2 %s split 0.1 eyeball "%s"'
                            % (descs[ix], src.stem, _num(h[0]), _num(h[1]), _num(h[2]), eye["name"]))
    L += ["", "// eyelids (%d)" % len(lids)] + lids

    written, skipped = 0, []
    body = []
    for flex, ops in info["rules"]:
        name = descs[flex] if 0 <= flex < len(descs) else ""
        if not _IDENT.match(name):
            skipped.append((name or "#%d" % flex, "not a plain name"))
            continue
        expr, why = rule_expression(ops, descs, ctrls)
        if expr is None:
            skipped.append((name, why))
            body.append("// %%%s skipped: %s" % (name, why))
            continue
        body.append("%%%s = %s" % (name, expr))
        written += 1
    L += ["", "// rules (%d of %d)" % (written, len(info["rules"]))] + body + [""]
    return "\n".join(L), {"controllers": len(ctrls), "rules": written, "rules_skipped": len(skipped),
                          "pairs": len(pairs), "eyelids": len(lids), "skipped": skipped}


def has_face(info):
    return bool(info["rules"] or info["pairs"] or any(e["upper_lid"] >= 0 or e["lower_lid"] >= 0
                                                       for e in info["eyes"]))


def stamp_of(mdl_path):
    """What the header records about the source: path, size and time - a change in any of them rewrites the file."""
    p = Path(mdl_path)
    st = p.stat()
    return "%s | %d bytes | mtime %d | %s" % (p, st.st_size, int(st.st_mtime), GENERATOR)


def generated_by_us(qc_path):
    """(ours, the stamp it carries) - only a file this module wrote is ever replaced."""
    try:
        with open(qc_path, encoding="utf-8", errors="replace") as fh:
            head = [fh.readline() for _ in range(3)]
    except OSError:
        return False, ""
    ours = bool(head) and "read from the compiled model by SFM Session Importer" in head[0]
    stamp = next((ln[len(SOURCE_TAG):].strip() for ln in head if ln.startswith(SOURCE_TAG)), "")
    return ours, stamp


def write_qc(mdl_path, folder):
    """Write <folder>/<model>.qc from the model. Returns (path or None, counts or None, note).

    Up to date (same source, size, time and generator) -> nothing is written. A file of that name that this module
    did not write is never touched."""
    mdl_path = Path(mdl_path)
    folder = Path(folder)
    target = folder / (mdl_path.stem + ".qc")
    stamp = stamp_of(mdl_path)
    if target.exists():
        ours, old = generated_by_us(target)
        if not ours:
            return target, None, "kept %s - it was not written by this add-on" % target.name
        if old == stamp:
            return target, None, "%s is up to date" % target.name
    info = read(mdl_path)
    if not has_face(info):
        return None, None, "%s has no face rules" % mdl_path.name
    text, counts = qc_text(info, stamp)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".qc.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)
    return target, counts, "wrote %s: %d rules, %d controllers, %d pairs, %d eyelids" % (
        target.name, counts["rules"], counts["controllers"], counts["pairs"], counts["eyelids"])
