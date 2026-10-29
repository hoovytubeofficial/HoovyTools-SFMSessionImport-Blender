"""
Common_Props.py  -  part of HoovyTools     [roadmap #1, #2, #3, #7]
==================================================================

Shared property definitions, so the same knob behaves the same way in every
importer that offers it. Importing this module costs nothing - it is pure
property factories plus one enum callback.

THE SCALE PRECISION BUG                                        [roadmap #1]
===========================================================================
Every scale field in the addon used to be declared like this:

    FloatProperty(default=1.0, min=0.001, soft_min=0.01, soft_max=100.0)

with no `precision` and no `step`. Blender then applies ITS defaults:

    precision = 3      three decimals in the UI
    step      = 3      0.03 per drag increment

Metres to Hammer Units needs far more than three decimals. The factor
0.01905 is displayed and dragged as 0.019, and 52.4934383202 collapses to
52.493. `min=0.001` clamps the small end away entirely, so anything finer
than a thousandth could not even be typed.

The value itself was never rounded - _apply_anim_scale multiplies in full
float. This was always a DECLARATION bug, not an epsilon bug. Epsilon
compares floats; it must never degrade the value it is comparing.

The fix is scale_prop(): precision 6 (Blender's maximum), step 1, and a
floor of 1e-6 so genuinely tiny factors survive. Presets sit alongside so
nobody has to hand-type 52.4934383202 in the first place.

IMPORT PROFILES                                            [roadmap #2, #3]
===========================================================================
A standalone importer was handed one file and knows nothing else. A session
importer knows the context it came from. Those are different jobs and they
deserve different defaults, so the choice is explicit rather than implied:

    BST       behave the way a Blender Source Tools user predicts.
              No root transform - bone channels only, which is also what
              exports cleanly back to SMD.

    SESSION   session-aware. Root transform on, scale and FPS taken from
              what the session reports.

    CUSTOM    the user touched something; nothing is forced.

profile_defaults() is the single source of truth for what each profile
means, so a fix to one importer's understanding of "BST-like" reaches all
of them.

The factories return plain kwargs dicts, not property objects, so call
sites read `FloatProperty(**scale_prop(...))`. That keeps the addon off
Blender's _PropertyDeferred internals, which are not API.
"""



# ─────────────────────────────────────────────────────────────────────────────
# Scale
# ─────────────────────────────────────────────────────────────────────────────

# 1 Hammer Unit = 1 inch = 0.0254 m
# Valve's player-proportion convention treats 1 HU as 0.75 inch = 0.01905 m,
# which is what SFM content is usually authored against
HU_INCH_TO_M = 0.0254
HU_VALVE_TO_M = 0.01905
M_TO_HU_INCH = 1.0 / HU_INCH_TO_M     # 39.370078740157481
M_TO_HU_VALVE = 1.0 / HU_VALVE_TO_M   # 52.493438320209977

SCALE_PRESETS = [
    ('CUSTOM', "Custom", "Type the factor by hand", 0.0),
    ('ONE', "1:1 Native",
     "Import untouched, in Hammer Units. What SFM exported is what you get", 1.0),
    ('HU_TO_M_VALVE', "HU to m (Valve 0.75in)",
     "Hammer Units to metres at Valve's player-proportion scale, "
     "1 HU = 0.75 inch = 0.01905 m. The usual choice for SFM content",
     HU_VALVE_TO_M),
    ('HU_TO_M_INCH', "HU to m (1in)",
     "Hammer Units to metres treating 1 HU as a true inch, 0.0254 m",
     HU_INCH_TO_M),
    ('M_TO_HU_VALVE', "m to HU (Valve 0.75in)",
     "Metres back to Hammer Units at Valve scale, 52.493438320209977",
     M_TO_HU_VALVE),
    ('M_TO_HU_INCH', "m to HU (1in)",
     "Metres back to Hammer Units treating 1 HU as a true inch, "
     "39.370078740157481", M_TO_HU_INCH),
]

_PRESET_VALUE = {k: v for k, _lbl, _d, v in SCALE_PRESETS}


def preset_items(_self=None, _context=None):
    return [(k, lbl, d) for k, lbl, d, _v in SCALE_PRESETS]


def _preset_update(self, context):
    """Setting a preset writes the factor. CUSTOM leaves it alone."""
    key = getattr(self, "scale_preset", 'CUSTOM')
    if key == 'CUSTOM':
        return
    value = _PRESET_VALUE.get(key)
    if value is None:
        return
    for attr in ("anim_scale", "scale"):
        if hasattr(self, attr):
            setattr(self, attr, value)
            break


def scale_prop(name="Animation Scale", description="", default=1.0):
    """
    A scale factor that survives Hammer Unit conversion.       [roadmap #1]

    precision=6 is Blender's maximum for a float field. step=1 makes a drag
    move 0.01 rather than 0.03. min=1e-6 keeps the field open at the small
    end while still refusing zero and negatives, which would silently
    collapse or mirror an animation.
    """
    return dict(
        name=name,
        description=description or (
            "Multiply every location key by this factor. 1.0 imports "
            "untouched. Full precision is kept - Hammer Unit conversion "
            "needs more than three decimals"),
        default=default,
        min=1e-6,
        soft_min=0.0001,
        soft_max=100.0,
        precision=6,
        step=1,
    )


def scale_preset_prop():
    return dict(
        name="Preset",
        description=("Common unit conversions. Picking one writes the factor "
                     "below at full precision"),
        items=preset_items,
        update=_preset_update,
    )


def draw_scale(layout, op, attr="anim_scale"):
    """Preset + value, drawn the same way everywhere."""
    col = layout.column(align=True)
    col.prop(op, "scale_preset")
    col.prop(op, attr)
    value = getattr(op, attr, 1.0)
    if value != 1.0:
        info = col.row()
        info.scale_y = 0.8
        info.label(text=f"1 unit becomes {value:.6g}", icon='INFO')


# ─────────────────────────────────────────────────────────────────────────────
# Import profiles                                          [roadmap #2, #3]
# ─────────────────────────────────────────────────────────────────────────────

PROFILE_BST = 'BST'
PROFILE_SESSION = 'SESSION'
PROFILE_CUSTOM = 'CUSTOM'

PROFILE_ITEMS = [
    (PROFILE_BST, "BST-like",
     "Standalone defaults, matched to Blender Source Tools behaviour.\n"
     "No root transform - bone channels only, the way BST imports a DMX "
     "and the way an SMD export expects the hierarchy"),
    (PROFILE_SESSION, "Session-aware",
     "The importer has session context, so it may assume more.\n"
     "Root transform on, and scale and frame rate taken from what the "
     "session reports"),
    (PROFILE_CUSTOM, "Custom",
     "Nothing is forced. Your settings stand as you left them"),
]

# the single source of truth for what each profile means.
_PROFILE_DEFAULTS = {
    PROFILE_BST:     {"add_root_helpers": False, "anim_scale": 1.0},
    PROFILE_SESSION: {"add_root_helpers": True,  "anim_scale": 1.0},
}


def profile_defaults(profile):
    return dict(_PROFILE_DEFAULTS.get(profile, {}))


def _profile_update(self, context):
    for attr, value in profile_defaults(getattr(self, "import_profile",
                                                PROFILE_CUSTOM)).items():
        if hasattr(self, attr):
            setattr(self, attr, value)


def profile_prop(default=PROFILE_BST):
    return dict(
        name="Profile",
        description=("Which set of defaults this import starts from. "
                     "Standalone imports default to BST-like; the Session "
                     "Importer drives its own preset"),
        items=PROFILE_ITEMS,
        default=default,
        update=_profile_update,
    )
