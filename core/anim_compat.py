# anim_compat.py
# ──────────────────────────────────────────────────────────────────────────────
# Blender 4.x / 5.0 animation API compatibility shim for HoovyTools
#
# Blender 5.0 removed Action.groups and Action.fcurves. F-curves now live in
# per-slot "channelbags" accessed via:
# action.slots  → action.layers → layer.strips → strip.channelbag(slot)
#
# This module provides three helpers that work on both versions:
#
# make_action(name, target_obj)
# Create a new Action and wire it to target_obj, returning (action, bag)
# bag  is the channelbag (5.0) or an ActionGroups/FCurves proxy (4.x)
#
# get_channelbag(action, target_obj)
# Return the channelbag for an existing action / object pair
#
# fc_find_or_new(bag, data_path, index=0, group_name=None)
# Find or create an FCurve; optionally assign it to a named group
#
# iter_fcurves(action, target_obj=None)
# Yield all FCurves for the action (bag-aware)
#
# count_fcurves(action, target_obj=None)
# Return the num of FCurves for the action.
#
# ──────────────────────────────────────────────────────────────────────────────

import bpy

# true when running on Blender 5.0+
_LAYERED = hasattr(bpy.types, "ActionLayer")


class _LegacyBag:
    """
    Thin wrapper so 4.x code can share the same call sites.
    Wraps action.fcurves / action.groups under a channelbag-like interface.
    """
    __slots__ = ("_action",)

    def __init__(self, action):
        self._action = action

    @property
    def fcurves(self):
        return self._action.fcurves

    @property
    def groups(self):
        return self._action.groups


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def make_action(name: str, target_obj) -> tuple:
    """
    Create a new bpy.data.actions Action named *name*, wire it to
    *target_obj*.animation_data, and return (action, channelbag).

    On 5.0 a Slot is created for the object and a single Keyframe strip is
    added so that channelbag(slot) is immediately available.
    On 4.x the action is assigned normally and a _LegacyBag wrapper is
    returned.
    """
    action = bpy.data.actions.new(name)
    action.use_fake_user = True

    if not target_obj.animation_data:
        target_obj.animation_data_create()
    anim = target_obj.animation_data

    if _LAYERED:
        #Blender 5.0 layered action
        slot = action.slots.new(id_type=target_obj.id_type, name=target_obj.name)
        anim.action            = action
        anim.action_slot_handle = slot.handle

        layer = action.layers.new(name="Layer")
        strip = layer.strips.new(type='KEYFRAME')
        bag   = strip.channelbag(slot, ensure=True)
    else:
        # Blender 4.x
        anim.action = action
        bag = _LegacyBag(action)

    return action, bag


def get_channelbag(action, target_obj):
    """
    Return the channelbag for *action* / *target_obj* pair.
    Creates the slot + layer + strip if missing (5.0 only).
    On 4.x returns a _LegacyBag wrapping the action.
    """
    if not _LAYERED:
        return _LegacyBag(action)

    anim = target_obj.animation_data
    if not anim:
        target_obj.animation_data_create()
        anim = target_obj.animation_data

    anim.action = action

    # ActionSlot has no .name attribute for reading in 5.0
    # Match by handle — if animation_data already points to a slot in this
    # action, reuse it; otherwise create a new one
    slot = None
    if anim.action_slot_handle:
        for s in action.slots:
            if s.handle == anim.action_slot_handle:
                slot = s
                break

    if slot is None:
        slot = action.slots.new(id_type=target_obj.id_type, name=target_obj.name)
        anim.action_slot_handle = slot.handle

    #find or create layer + strip
    if action.layers:
        layer = action.layers[0]
    else:
        layer = action.layers.new(name="Layer")

    if layer.strips:
        strip = layer.strips[0]
    else:
        strip = layer.strips.new(type='KEYFRAME')

    return strip.channelbag(slot, ensure=True)


def fc_find_or_new(bag, data_path: str, index: int = 0, group_name: str = None):
    """
    Find an existing FCurve in *bag* matching *data_path* + *index*, or
    create one.  If *group_name* is given the curve is added to that group
    (creating it if needed).

    Works with both a real channelbag (5.0) and a _LegacyBag (4.x).
    """
    fc = bag.fcurves.find(data_path, index=index)
    if fc is not None:
        return fc

    if _LAYERED:
        # 5.0: no action_group kwarg — assign group after creation
        fc = bag.fcurves.new(data_path=data_path, index=index)
    else:
        # 4.x: action_group kwarg still works
        if group_name:
            fc = bag.fcurves.new(data_path=data_path, index=index,
                                 action_group=group_name)
        else:
            fc = bag.fcurves.new(data_path=data_path, index=index)

    # assign / create group
    if group_name:
        group = (bag.groups.get(group_name) or
                 bag.groups.new(name=group_name))
        fc.group = group

    return fc


def iter_fcurves(action, target_obj=None):
    """
    Yield all FCurves for *action*.
    On 5.0 iterates over all channelbags for all slots.
    On 4.x iterates action.fcurves directly.
    """
    if not _LAYERED:
        yield from action.fcurves
        return

    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                try:
                    bag = strip.channelbag(slot)
                    if bag:
                        yield from bag.fcurves
                except Exception:
                    pass


def count_fcurves(action, target_obj=None) -> int:
    """Return the number of FCurves in *action*."""
    return sum(1 for _ in iter_fcurves(action, target_obj))
