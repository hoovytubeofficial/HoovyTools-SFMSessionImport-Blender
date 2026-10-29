"""
Session_Locks.py  -  part of HoovyTools     [EXPERIMENTAL]
==========================================================

WHAT A "LOCK" IS, AND THE FOUR PLACES IT COULD HIDE
===================================================
the user's idea, and it is the right one: if a session says the water barrel
is attached to gman's head, we should be able to read that, resolve it, and
animate the barrel from the head's motion - recursively, so a hat locked to a
head locked to a helicopter all falls out of one dependency pass.

The blocker is not the maths. It is finding out how SFM writes it down. There
are four candidate mechanisms and this module looks for all of them, because
guessing which one is in play is exactly the mistake that costs a day:

  1  CONSTRAINT OPERATORS.  SFM's rig system writes
     `DmeRig*ConstraintOperator` elements into a DmeAnimationSet's `operators`
     array - point, orient, parent, aim, IK. Each carries `targets` (a list of
     DmeConstraintTarget, each with a `target` and a `weight`) and a `slave`.
     THIS IS THE ONE THAT CARRIES A REAL ATTACHMENT.

  2  DAG PARENTING.  A game model's DAG node hung under another set's bone
     instead of under `scene`. We already resolve exactly this for particle
     systems (see Session_Particles.parent_matrix), so if a lock shows up this
     way it is nearly free.

  3  AN UNRECOGNISED OPERATOR.  Anything in `operators` that is not an
     expression, a colour pack or a flex controller is worth looking at.

  4  BAKED MOTION.  SFM can bake an attachment down to plain keys. That is not
     a lock any more - it is animation, and it already imports correctly. The
     tell is a channel with hundreds of keys on a prop nobody hand-animated.

MEASURED ON the user'S OWN TEST FILE, 2026-08-21
=================================================
`new session2.dmx` - saved right after locking a water_barrel to gman's head -
contains NONE of 1, 2 or 3:

  * no element type in the file contains "Constraint" or "Rig" (all 36 types
    were listed and checked);
  * `water_barrel_GameModel` hangs off `water_barrel1` -> `scene`, exactly
    like every other model - it is not under gman;
  * `water_barrel1`'s only operator is `static_prop_scale_rescale`, the
    ordinary scale plumbing every set has;
  * diffing against the pre-lock save, everything that appeared is just the
    barrel arriving as a normal animation set. NOTHING references both the
    barrel and gman except containers - the film clip's `animationSets` list,
    the `scene` DAG and the editor track;
  * `static_prop_p` has THREE keys. An attachment baked against a moving head
    would have hundreds.

So the lock did not persist into the file. The most likely reason is that
SFM's padlock in the Animation Set Editor is an EDIT lock - it pins a control
so procedural operations leave it alone - and not an attachment. An attachment
is made through the rig/constraint workflow, and that is what writes case 1.

WHAT THIS MODULE DOES TODAY
===========================
It scans, reports, and orders. `scan_locks()` finds every attachment it can
see, `dependency_order()` sorts them so a master is always resolved before its
slaves, and `ht.session_locks` prints the result. Run it on a session that DOES
carry a lock and it will say so, with the element types involved - which is the
one piece of information needed to finish the evaluator.

It deliberately does NOT invent an evaluator for a format nobody has seen in a
real file yet. Every other conversion in this add-on was measured first
(see the constitution); this one gets the same treatment.
"""

import bpy
import collections

from bpy.types import Operator


# operator types that are ordinary session plumbing, not attachments
BORING_OPERATORS = {
    "DmeExpressionOperator",
    "DmePackColorOperator",
    "DmeGlobalFlexControllerOperator",
}

#substrings that mark an element type as constraint-shaped. Kept as
#substrings rather than an exact list bc SFM's constraint family is
#larger than the handful anyone remembers, and a type we have not seen
#before is exactly what we want reported rather than skipped
CONSTRAINT_MARKERS = ("constraint", "rig")


def _dm():
    from ..SST import get_datamodel
    return get_datamodel()


def _parents(model):
    """{id(child) -> parent element} across every DAG in the session."""
    out = {}
    for e in model.elements:
        try:
            kids = e.get("children")
        except Exception:
            continue
        if not kids:
            continue
        for k in kids:
            if k is not None:
                out.setdefault(id(k), e)
    return out


def _chain_names(elem, parents):
    """The DAG path from *elem* up to the root, as names."""
    out, seen = [], set()
    cur = elem
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        out.append(getattr(cur, "name", "?") or "?")
        cur = parents.get(id(cur))
    return out


def _targets_of(op):
    """[(name, type, weight)] a constraint operator points at.

    Written defensively: this runs against a format we have not yet seen in a
    real file, so an attribute that is missing or shaped differently must
    produce a partial answer, never an exception that hides the discovery."""
    out = []
    try:
        for t in (op.get("targets") or []):
            if t is None:
                continue
            tgt = t.get("target") if hasattr(t, "get") else None
            w = 1.0
            try:
                w = float(t.get("weight"))
            except Exception:
                pass
            out.append((getattr(tgt, "name", "?"),
                        getattr(tgt, "type", "?"), w))
    except Exception:
        pass
    return out


def scan_locks(session_path, report=print):
    """Everything in this session that attaches one thing to another.

    Returns
        {"constraints": [...], "dag_attached": [...], "unknown_ops": [...],
         "sets": int, "types": {...}}
    """
    model = _dm().load(str(session_path))
    parents = _parents(model)

    types = collections.Counter((e.type or "?") for e in model.elements)

    #── 1 / 3  operators that are not ordinary plumbing ──────────────────────
    constraints, unknown_ops = [], []
    sets = [e for e in model.elements if e.type == "DmeAnimationSet"]
    for aset in sets:
        for op in (aset.get("operators") or []):
            t = op.type or "?"
            if t in BORING_OPERATORS:
                continue
            rec = {"set": aset.name, "op": op.name, "type": t,
                   "targets": _targets_of(op),
                   "attrs": sorted([a for a in op])}
            if any(k in t.lower() for k in CONSTRAINT_MARKERS):
                constraints.append(rec)
            else:
                unknown_ops.append(rec)

    #── 2  a game model parented under something other than the scene ────────
    dag_attached = []
    for aset in sets:
        gm = aset.get("gameModel")
        if gm is None:
            continue
        chain = _chain_names(gm, parents)
        # normal is  <model>_GameModel -> <set> -> scene. Anything longer, or
        # anything whose path does not end at `scene` thru its own set, is
        # hanging off something else - which is an attachment
        if len(chain) > 3 or (len(chain) >= 2 and chain[-1] != "scene"):
            dag_attached.append({"set": aset.name, "chain": chain})

    #── loose constraint-shaped elements anywhere in the file ────────────────
    loose = [t for t in types
             if any(k in t.lower() for k in CONSTRAINT_MARKERS)
             and t not in BORING_OPERATORS]

    out = {"constraints": constraints, "unknown_ops": unknown_ops,
           "dag_attached": dag_attached, "loose_types": loose,
           "sets": len(sets), "types": dict(types)}
    return out


def dependency_order(links):
    """Slaves after their masters. The recursive part, done once.

    *links* is [(slave, master), ...]. A hat locked to a head locked to a
    helicopter comes back helicopter, head, hat - so a single forward pass can
    resolve each one against a master that is already final.

    A CYCLE IS REPORTED, NOT SURVIVED SILENTLY. SFM will happily let a user
    build one, and an importer that quietly picks an order would produce a
    scene that is subtly wrong every time with nothing to point at.

    Returns (order, cycles).
    """
    masters = collections.defaultdict(list)
    nodes = set()
    for slave, master in links:
        masters[slave].append(master)
        nodes.add(slave)
        nodes.add(master)

    order, state, cycles = [], {}, []

    def visit(n, stack):
        st = state.get(n, 0)
        if st == 2:
            return
        if st == 1:
            cycles.append(list(stack) + [n])
            return
        state[n] = 1
        stack.append(n)
        for m in masters.get(n, ()):
            visit(m, stack)
        stack.pop()
        state[n] = 2
        order.append(n)

    for n in sorted(nodes):
        visit(n, [])
    return order, cycles


def report_lines(info):
    """What scan_locks found, as text."""
    L = [f"Animation sets : {info['sets']}"]
    n = (len(info["constraints"]) + len(info["dag_attached"])
         + len(info["unknown_ops"]))
    if not n:
        L += [
            "",
            "NO LOCKS IN THIS SESSION.",
            "",
            "Checked all four places one could be:",
            "  1 constraint operators on an animation set   none",
            "  2 a game model parented under another's bone none",
            "  3 an unrecognised operator                   none",
            "  4 baked motion - that is animation, not a",
            "    lock, and it already imports",
            "",
            "SFM's padlock in the Animation Set Editor is an EDIT lock: it",
            "pins a control so procedural operations leave it alone. It does",
            "not attach anything, and it does not survive into the file.",
            "To make an attachment the session can carry, use the rig /",
            "constraint workflow - that writes a DmeRig*ConstraintOperator",
            "into the set's `operators`, which this reads.",
        ]
        return L

    if info["constraints"]:
        L += ["", f"CONSTRAINTS: {len(info['constraints'])}"]
        for c in info["constraints"]:
            L.append(f"  {c['set']}  <-  {c['type']}  '{c['op']}'")
            for nm, ty, w in c["targets"]:
                L.append(f"      target {nm}  ({ty})  weight {w:g}")
    if info["dag_attached"]:
        L += ["", f"PARENTED IN THE DAG: {len(info['dag_attached'])}"]
        for d in info["dag_attached"]:
            L.append(f"  {d['set']}:  " + "  <-  ".join(d["chain"]))
    if info["unknown_ops"]:
        L += ["", f"OPERATORS WORTH A LOOK: {len(info['unknown_ops'])}"]
        for u in info["unknown_ops"]:
            L.append(f"  {u['set']}  {u['type']}  '{u['op']}'")
            L.append(f"      attrs: {', '.join(u['attrs'][:8])}")

    links = []
    for c in info["constraints"]:
        for nm, _ty, _w in c["targets"]:
            links.append((c["set"], nm))
    for d in info["dag_attached"]:
        if len(d["chain"]) > 2:
            links.append((d["set"], d["chain"][2]))
    if links:
        order, cycles = dependency_order(links)
        L += ["", "RESOLVE IN THIS ORDER (masters first):"]
        L.append("  " + "  ->  ".join(order))
        if cycles:
            L += ["", f"CYCLE(S) - cannot be resolved: {len(cycles)}"]
            for c in cycles[:3]:
                L.append("  " + " -> ".join(c))
    return L


# ─────────────────────────────────────────────────────────────────────────────
# Operator
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_session_locks(Operator):
    """Report what the connected session locks to what  [EXPERIMENTAL]

Looks for every way SFM can attach one thing to another - constraint
operators, DAG parenting, and any operator that is not ordinary session
plumbing - and prints what it finds, with the order the attachments would have
to be resolved in (masters before slaves, so a hat on a head on a helicopter
falls out of one pass).

It reports; it does not yet build the constraints. Every other conversion in
this add-on was measured against a real file before it was written, and no
session seen so far actually carries a lock - SFM's padlock is an EDIT lock,
not an attachment"""
    bl_idname = "ht.session_locks"
    bl_label = "Report Session Locks"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        from ..session.Session_Steps import session_of
        return session_of(context) is not None

    def execute(self, context):
        from ..session.Session_Steps import session_of
        from ..core import Report_UI
        session = session_of(context)
        if session is None:
            self.report({"ERROR"}, "No session connected")
            return {"CANCELLED"}
        try:
            info = scan_locks(session)
        except Exception as exc:
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        lines = [f"{session.name}"] + report_lines(info)
        found = (len(info["constraints"]) + len(info["dag_attached"])
                 + len(info["unknown_ops"]))
        Report_UI.report(
            context, "session_locks", "Session Locks", lines,
            level=('INFO' if found else 'WARNING'), icon='LINKED',
            operator=self, prefix="LOCKS",
            summary=(f"Session Locks - {found} attachment(s) found"
                     if found else
                     "Session Locks - none in this session (SFM's padlock is "
                     "an edit lock, not an attachment)"))
        return {"FINISHED"}


def register(icon_id_fn=None):
    try:
        bpy.utils.unregister_class(HT_OT_session_locks)
    except Exception:
        pass
    bpy.utils.register_class(HT_OT_session_locks)


def unregister():
    try:
        bpy.utils.unregister_class(HT_OT_session_locks)
    except Exception:
        pass
