"""
Report_UI.py  -  part of HoovyTools
===================================

ONE place where the add-on tells the user what it just did.

THE PROBLEM THIS EXISTS TO FIX
==============================
`IMPORT WHOLE SESSION` runs eight steps. Every step was its own operator and
every operator ended with `window_manager.popup_menu(...)`, so finishing a
session meant clicking through a stack of dialogs before the scene could even
be looked at. Worse, a popup BLOCKS: the next step does not start until the
previous dialog is dismissed, so a one-click import was not one click.

THE RULE NOW
============
Every report goes through `report()`. Each call site names a KEY, and each key
has its own on/off switch (`scene.ht_reports.<key>`). What a call produces:

  * the full text on the CONSOLE, always - that is the record, and it is never
    suppressed by anything here;
  * ONE popup, and only if that key's switch is on. The switch is drawn INSIDE
    the popup, so the popup carries its own off button - untick it and that
    report never interrupts again;
  * `operator.report()` - Blender's OWN status bar and Info editor.

NO CUSTOM MESSAGE UI. DELIBERATE, AND NOT COMING BACK.
======================================================
An earlier version of this module drew its own coloured bar across the bottom
of the 3D viewport with a GPU draw handler, fading out after ten seconds.
the user's verdict, 2026-08-21: remove it, use Blender's own channels.

They were right, and the reasons are worth writing down so nobody re-adds it:

  * Blender already HAS a status bar and an Info editor, and users already
    know where those are. A second, invented message surface means two places
    to look and one of them is unfamiliar.
  * A draw handler that raises does not merely lose its own output - it takes
    the region down with it and floods the console on every redraw. That is a
    real risk taken on for a cosmetic gain.
  * It painted over the viewport - over the thing the user was trying to look
    at, at exactly the moment they wanted to look at it.
  * It could not be checked headlessly, so it needed an offscreen GPU render
    to test. That is a lot of machinery for a status line.

`self.report({'INFO'|'WARNING'|'ERROR'}, msg)` gets the colour, the placement
and the persistence for free, and behaves the way every other add-on does.

BATCH RUNS
==========
`with Report_UI.quiet():` swallows popups for everything inside it, collecting
each report instead. `IMPORT WHOLE SESSION` wraps its whole pipeline in one,
then emits a single report of its own - so eight steps produce exactly one
popup, not eight.

The console output is deliberately NOT suppressed in a quiet scope, and
neither is `operator.report()`. A batch run is exactly when the per-step
detail matters most; what it must not do is stack dialogs.

HEADLESS
========
`blender -b` has no window. Everything here checks `bpy.app.background` first
and degrades to plain printing. The sounds importer crashing Blender with
EXCEPTION_ACCESS_VIOLATION - a `popup_menu` reached in background - is the
reason that check is not optional.
"""

import bpy

from bpy.types import Operator, PropertyGroup
from bpy.props import BoolProperty


#  Blender's own report levels. These three are the only ones used anywhere in
#  the add-on, and Blender already colours them: INFO neutral, WARNING amber,
#  ERROR red. That colouring is the reason this module no longer paints any of
#  its own.
LEVELS = ('INFO', 'WARNING', 'ERROR')

LEVEL_ICONS = {
    'INFO':    'INFO',
    'WARNING': 'ERROR',       # Blender's amber triangle
    'ERROR':   'CANCEL',
}


# ─────────────────────────────────────────────────────────────────────────────
#  The switches
# ─────────────────────────────────────────────────────────────────────────────
#
#  One entry per popup in the add-on. The KEY is what call sites pass; it is
#  also the property name, so it must be a valid Python identifier and it must
#  not change once shipped - a renamed key silently resets a user's choice.
#
#  Anything that reports without a key registered here still works: it prints,
#  it reports, and its popup is shown (unknown keys default to ON). Registering
#  the key is what gives it a switch in the panel.

REPORTS = (
    # key                     label                     description
    ("session_one_click",     "Import Whole Session",   "The single summary at the end of a whole-session import"),
    ("session_import_all",    "Session Import (batch)", "The batch session importer's summary"),
    ("session_plan",          "Session Plan",           "The dry-run plan listing what a session would import"),
    ("step_models",           "1  Models",              "Step 1 - models imported from the session, rest poses fixed"),
    ("step_animations",       "2  Animations",          "Step 2 - bone animation onto the rigs"),
    ("step_shapekeys",        "3  Shape Keys",          "Step 3 - facial animation"),
    ("step_cameras",          "4  Cameras",             "Step 4 - the session's cameras"),
    ("step_lights",           "6  Lights",              "Step 6 - the session's lights"),
    ("step_particles",        "7  Particles",           "Step 7 - the session's particle effects"),
    ("session_models",        "Session Models",         "The standalone model importer"),
    ("rig_fixer",             "Rig Fixer",              "The standalone Fix Rig Rest Poses report"),
    ("import_dmx_animation",  "DMX Animation",          "The standalone DMX animation importer"),
    ("import_dmx_camera",     "DMX Camera",             "The standalone DMX camera importer"),
    ("import_shape_keys",     "Shape Keys",             "The standalone shape-key importer"),
    ("import_animations",     "Animations (folder)",    "The folder-at-a-time animation importer"),
    ("import_camera_anims",   "Camera Animations",      "The folder-at-a-time camera importer"),
    ("import_shapekey_anims", "Shape Key Animations",   "The folder-at-a-time shape-key importer"),
    ("import_sounds",         "Session Sounds",         "The standalone sound importer"),
    ("import_lights",         "Lights",                 "The standalone light importer"),
    ("session_report",        "Session Report",         "What a session file contains"),
    ("sources",               "Source Files",           "The purple manifest: the session, .mdl and .pcf files this scene was built from"),
    ("session_locks",         "Session Locks",          "What the session attaches to what"),
    ("session_extract",       "Session Extract",        "Writing the anims/ folder out of a session"),
    ("dmx_analyzer",          "DMX Analyzer",           "The DMX file analysis report"),
    #  OFF BY DEFAULT - see DEFAULT_OFF. Blender Source Tools raises its own
    #  blocking dialog for every bone an animation names that the rig lacks,
    #  and a session import runs it once per model.
    ("smd_warnings",          "Source Tools Warnings",  "Blender Source Tools' own error/warning dialog, raised once per imported file"),
    ("camera_tools",          "Camera Tools",           "Camera handles, splitting and extension"),
    ("shapekey_proxy",        "Shape Key Proxy",        "The proxy built when facial data has no rig"),
    ("playground",            "Playground",             "Experimental tools"),
    ("utils_misc",            "Utils - Misc",           "Miscellaneous utility reports"),
    ("utils_organizer",       "Utils - Organizer",      "Scene organiser reports"),
    ("utils_camera_fix",      "Utils - Camera Fix",     "The camera fixer report"),
    ("panel_tools",           "Panel Tools",            "Purge rigs, strip animation and other panel buttons"),
    ("register_skydome",      "Register Skydome",       "Skydome shadow pass-through and the world-shader override"),
    ("vertexlit_fix",         "VertexlitGeneric Fix",   "Retuning SourceIO's flat material values"),
    ("update_rig",            "Update Rig Animation",   "The per-rig refresh button in the Rigs roster"),
)

_KEYS = tuple(k for k, _, _ in REPORTS)

MASTER_KEY = "disable_all"
_PERSIST_KEYS = _KEYS + (MASTER_KEY,)


def _switch_changed(self, context):
    """Write the switches out whenever one is toggled.

    ON THE PROPERTY, NOT ON THE SETTER. The checkbox inside each popup is a
    plain `layout.prop()` - it writes the scene property directly and never
    goes near `set_popup()` - so persisting from there would have caught none
    of what actually happens. An `update` callback catches every route into
    the value, including somebody poking it from the Python console.
    """
    _persist(self)


#  Report keys that ship with their dialog OFF. A report is only in here
#  because it is raised by something OTHER than this add-on and fires per
#  file rather than per action.
DEFAULT_OFF = frozenset({"smd_warnings"})


class HoovyToolsReportSettings(PropertyGroup):
    """One BoolProperty per report key. Built from REPORTS so the list above
    is the only place a new popup has to be declared - plus the master
    switch, disable_all."""
    __annotations__ = {
        MASTER_KEY: BoolProperty(
            name="Disable All Popups",
            description=("No HoovyTools report opens a dialog. Every report "
                         "still prints to the console, still shows in the "
                         "status bar and still lands in the _Logs file. Your "
                         "per-popup choices stay as they are and come back "
                         "when this is off.\n"
                         "THIS FEATURE WAS ADDED IN VERSION 1.18.0 AND IS IN "
                         "EXPERIMENTAL STAGE"),
            default=False,
            update=_switch_changed,
        ),
        **{key: BoolProperty(
            name=label,
            description=(f"{desc}.\n\nOff: this report still prints to the "
                         f"console and still appears in Blender's status bar "
                         f"and Info editor - it just stops opening a dialog "
                         f"you have to click away"),
            default=(key not in DEFAULT_OFF),
            update=_switch_changed,
        )
        for key, label, desc in REPORTS},
    }


def _log_switch_changed(self, context):
    """Persist the log switches whenever one is toggled - same reasoning as
    _switch_changed above: the update callback catches every route into the
    value, including the Python console."""
    try:
        from . import logvars
        logvars.capture_from(self, _KEYS)
    except Exception:                                         # noqa: BLE001
        pass


class HoovyToolsLogSettings(PropertyGroup):
    """One BoolProperty per report key: does that report land in the _Logs
    file. Built from REPORTS, so declaring a popup key is also declaring its
    log switch - the two lists can never drift apart.

    OFF LOSES NOTHING LIVE. A switched-off report still prints to the
    console, still reaches the status bar and Info editor, and still sits in
    the in-memory history behind PRINT ADDON BEHAVIOR. It only stays out of
    the log FILE."""
    __annotations__ = {
        key: BoolProperty(
            name=label,
            description=(f"{desc}.\n\nWrite this report to the _Logs file. "
                         f"Off: the report still prints to the console and "
                         f"still shows in the status bar - it just stays out "
                         f"of the log file"),
            default=True,
            update=_log_switch_changed,
        )
        for key, label, desc in REPORTS
    }


def prefs(context=None):
    """The switch block, or None before registration / without a scene."""
    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    if scene is None:
        return None
    return getattr(scene, "ht_reports", None)


def log_prefs(context=None):
    """The log-switch block, or None before registration / without a scene."""
    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    if scene is None:
        return None
    return getattr(scene, "ht_logs", None)


#  Scenes whose block has already been synced from the file this session.
_synced = set()


def popup_enabled(context, key):
    """Is the dialog for *key* wanted? Unknown keys are ON - a new call site
    that forgot to register its key must not go silent."""
    p = prefs(context)
    if p is None or key is None:
        return True
    #  SYNC ON FIRST ASK, ONCE PER SCENE. Registration can only reach the
    #  scene that exists at the time; open another .blend and its block is
    #  fresh with everything on, which is the setting appearing not to stick.
    try:
        ident = id(p.id_data)
        if ident not in _synced:
            _synced.add(ident)
            from . import popups
            popups.apply_to(p, _PERSIST_KEYS)
    except Exception:                                         # noqa: BLE001
        pass
    if getattr(p, MASTER_KEY, False):
        return False
    return bool(getattr(p, key, True))


def all_popups_off(context=None):
    """True when the master DISABLE ALL POPUPS switch is on."""
    p = prefs(context)
    return bool(getattr(p, MASTER_KEY, False)) if p is not None else False


#  Scenes whose LOG block has been synced from the file this session. Separate
#  from _synced: the two blocks sync from different files, and sharing the set
#  would mean whichever is asked first silently skips the other's sync.
_log_synced = set()


def log_enabled(context, key):
    """Should this report be written to the log FILE? Unknown keys are ON -
    a call site that forgot to register its key must not vanish from logs."""
    p = log_prefs(context)
    if p is None or key is None:
        return True
    try:
        ident = id(p.id_data)
        if ident not in _log_synced:
            _log_synced.add(ident)
            from . import logvars
            logvars.apply_to(p, _KEYS)
    except Exception:                                         # noqa: BLE001
        pass
    return bool(getattr(p, key, True))


def set_popup(context, key, value):
    p = prefs(context)
    if p is not None and key and hasattr(p, key):
        setattr(p, key, bool(value))
        _persist(p)


def _persist(block):
    """Write the switches out so they outlive this .blend.

    BEING A SCENE PROPERTY MEANT THE SETTING DID NOT STICK. "I turned that
    dialog off" lasted until you opened another file, which reads as a broken
    switch rather than as a per-scene one. The scene block is still the live
    value because that is what Blender's UI binds to; the file is the part
    that survives.
    """
    try:
        from . import popups
        popups.capture_from(block, _PERSIST_KEYS)
    except Exception:                                         # noqa: BLE001
        pass


def load_switches(scene=None):
    """Pull `_popupvariables.json` onto a scene's block. Called on register."""
    try:
        from . import popups
        scene = scene or bpy.context.scene
        return popups.apply_to(getattr(scene, "ht_reports", None), _PERSIST_KEYS)
    except Exception:                                         # noqa: BLE001
        return 0


# ─────────────────────────────────────────────────────────────────────────────
#  Quiet scope
# ─────────────────────────────────────────────────────────────────────────────

_quiet_depth = 0
_collected = []

#  EVERY REPORT THE ADD-ON EMITS, LAST 80, IN MEMORY ONLY.
#
#  This exists for one thing: `Print Addon Behavior` writes a troubleshooting
#  file, and a file listing only the CONFIGURATION answers "what is installed"
#  when the question is always "what happened". A user who can say "it printed
#  55 models then errored on step 3" is describing the bug; a user who can say
#  "SourceIO is enabled" is not.
#
#  A RING, NOT A LOG. Nothing is written to disk until someone asks for it, so
#  an add-on that is merely running costs no I/O and leaves nothing behind. 80
#  is about two full session imports, which is as far back as anyone has ever
#  needed to look.
#
#  Cleared on unregister, so re-enabling the add-on starts a clean history and
#  a stale entry can never outlive the code that wrote it.
from collections import deque
_HISTORY = deque(maxlen=80)


def history():
    """The reports emitted so far, oldest first. Read-only snapshot."""
    return list(_HISTORY)


def clear_history():
    _HISTORY.clear()


class _Quiet:
    """Context manager. Popups are collected, not shown.

    Re-entrant on purpose: a step operator called from the one-click may itself
    call something that reports, and only the OUTERMOST scope releases."""

    def __enter__(self):
        global _quiet_depth
        _quiet_depth += 1
        if _quiet_depth == 1:
            _collected.clear()
        return _collected

    def __exit__(self, *exc):
        global _quiet_depth
        _quiet_depth = max(0, _quiet_depth - 1)
        return False


def quiet():
    return _Quiet()


def is_quiet():
    return _quiet_depth > 0


# ─────────────────────────────────────────────────────────────────────────────
#  The one entry point
# ─────────────────────────────────────────────────────────────────────────────

def _summarise(title, lines, limit=140):
    """One line for the status bar. The popup and the console get the whole
    thing; the status bar gets what fits in a strip."""
    bits = [ln.strip() for ln in lines if ln and ln.strip()]
    text = f"{title} - " + "  |  ".join(bits) if bits else title
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "..."
    return text



# ──────────────────────────────────────────────────────────────────────────────
#  THE LOG FILE
# ──────────────────────────────────────────────────────────────────────────────
#
#  Everything this add-on says goes through `report()`, which is the reason it
#  is worth being the only reporting call an operator makes - one function to
#  change and every step, every importer and every check starts writing itself
#  down. The console already has all of it; the console is also gone the
#  moment Blender closes, and a user reporting a problem cannot paste it.
#
#  ONE FILE PER BLENDER RUN, named at import time. Appending to a single
#  rolling file means two Blenders open at once interleave their lines into
#  something neither of them did, and the timestamp is what makes "the run
#  where it broke" findable at all.
#
#  IT NEVER RAISES AND IT NEVER BLOCKS A REPORT. Opened per write rather than
#  held open, because a handle kept across a crash is a truncated file, and
#  because Blender can be killed at any point in a long import. The cost is a
#  file open per report, which against a session import measured in minutes is
#  not worth optimising away.

LOG_KEEP = 20            # runs to keep; older files are pruned on startup

_LOG_PATH = None
_LOG_FAILED = False


def _log_stamp():
    import time
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def log_path():
    """The file this run writes to, or None if logging is unavailable."""
    global _LOG_PATH, _LOG_FAILED
    if _LOG_FAILED:
        return None
    if _LOG_PATH is not None:
        return _LOG_PATH
    try:
        from . import paths
        d = paths.logs_dir()
        if d is None:
            _LOG_FAILED = True
            return None
        _LOG_PATH = d / f"HoovyTools_{_log_stamp()}.log"
        header = [
            "=" * 78,
            f"  HoovyTools log - {_log_stamp()}",
            "=" * 78,
            "",
        ]
        _LOG_PATH.write_text("\n".join(header), encoding="utf-8")
        #  PRUNE AFTER CREATING, NOT BEFORE. Pruning first keeps LOG_KEEP old
        #  files and THEN adds this one, so the folder settles at LOG_KEEP + 1
        #  and stays there for ever. Caught by the suite asserting the COUNT
        #  rather than the constant, which is the only version of that test
        #  worth having - and it took twenty runs to trip.
        _prune_logs(d)
        return _LOG_PATH
    except Exception as exc:                                   # noqa: BLE001
        #  Said ONCE. A read-only add-on folder would otherwise print this
        #  line on every report for the rest of the session, which is worse
        #  than the missing log.
        print(f"[REPORT_UI]  log file unavailable, console only: {exc}")
        _LOG_FAILED = True
        return None


def _prune_logs(d):
    """Keep the newest LOG_KEEP files. Never fatal."""
    try:
        old = sorted(d.glob("HoovyTools_*.log"),
                     key=lambda f: f.stat().st_mtime, reverse=True)
        for f in old[LOG_KEEP:]:
            try:
                f.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _log_write(level, title, lines, prefix="HT"):
    """Append one report. Silent on failure - see the note above."""
    path = log_path()
    if path is None:
        return
    try:
        from . import marks
        import time
        stamp = time.strftime("%H:%M:%S")
        out = [f"[{stamp}]  {marks.mark(level, pad=True)}{title}"]
        out.extend(f"           {ln}" for ln in lines)
        out.append("")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
    except Exception:
        pass


def report(context, key, title, lines, level='INFO', icon=None,
           operator=None, summary=None, prefix="HT", body_draw=None):
    """
    Say what just happened. The only reporting call an operator should make.

    context   Blender context (may be None in background)
    key       one of REPORTS' keys - the switch this popup obeys
    title     dialog title, and the first thing in the status-bar line
    lines     the body, one string per line
    level     'INFO' | 'WARNING' | 'ERROR' - Blender colours these itself
    operator  pass `self`. `operator.report()` is how the message reaches the
              status bar and the Info editor, and since the custom viewport
              banner was removed that is the ONLY transient surface this
              add-on uses. A call without one still prints and may pop up, but
              says nothing in the status bar
    summary   override the auto-built one-line status text
    body_draw callable(layout, context) drawn INSTEAD of the plain lines.
              For the one popup that is not just text - the analyzer's, which
              carries "route this file to..." buttons. `lines` is still what
              the console and the status bar get, so a report never depends on
              a draw callback having run
    """
    lines = [str(ln) for ln in (lines or [])]
    level = level if level in LEVELS else 'INFO'
    icon = icon or LEVEL_ICONS[level]

    #  THE DOT GOES ON THE HEADER LINE, NOT ON ALL OF THEM. A colour on every
    #  line of a forty-line report is a colour on nothing - the eye needs one
    #  place to land per block, and that place is the title.
    from . import marks
    print(f"[{prefix}]  {marks.mark(level)}{title}")
    for ln in lines:
        print(f"[{prefix}]  {ln}")

    #  AND TO THE FILE. Beside the print, not instead of it, and before
    #  anything that can return early - a report suppressed by a popup switch
    #  or collected inside a quiet scope is exactly the one somebody will want
    #  to read afterwards.
    #  BEHIND ITS OWN SWITCH, separate from the popup one: the Developer
    #  tab's LOGS box decides per key what the FILE receives. The console
    #  print above is unconditional either way.
    if log_enabled(context, key):
        _log_write(level, title, lines, prefix=prefix)

    bar = summary or _summarise(title, lines)

    #  Recorded BEFORE the popup, so a report still lands in the history when
    #  its popup is switched off - which is the case that most needs it.
    import time as _time
    _HISTORY.append({"t": _time.strftime("%H:%M:%S"), "key": key,
                     "level": level, "title": title, "summary": bar,
                     "lines": lines})

    #  Blender's own channel. Deliberately NOT conditional on the quiet scope:
    #  a batch run still wants its steps in the Info editor, and unlike a popup
    #  this costs the user nothing and blocks nothing.
    if operator is not None:
        try:
            operator.report({level}, bar)
        except Exception:
            pass

    if is_quiet():
        _collected.append({"key": key, "title": title, "lines": lines,
                           "level": level, "summary": bar})
        return

    if bpy.app.background:
        return
    ctx = context or bpy.context
    if getattr(ctx, "window", None) is None:
        return
    if not popup_enabled(ctx, key):
        return

    def draw(menu, _ctx):
        layout = menu.layout
        if body_draw is not None:
            body_draw(layout, _ctx)
        else:
            col = layout.column(align=True)
            for ln in lines:
                if ln.strip():
                    col.label(text=ln)
                else:
                    col.separator()
        #  The off switch lives IN the popup. This is the whole point: the
        #  moment a report becomes noise, it can be silenced from the dialog
        #  that is being complained about, without hunting for a preference.
        p = prefs(_ctx)
        if p is not None and hasattr(p, key or ""):
            layout.separator()
            box = layout.box()
            box.prop(p, key, text="Show this popup again", icon='CHECKBOX_HLT')
            box.label(text="Off: console + the status bar only.", icon='INFO')

    try:
        ctx.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception as exc:
        print(f"[REPORT_UI]  popup unavailable: {exc}")


def report_collected(context, key, title, header_lines=None, level=None,
                     operator=None, prefix="HT"):
    """Emit ONE report standing in for everything a quiet scope collected.

    Called by a batch runner just after its `with quiet():` block. The level is
    the worst level any collected report carried, unless one is forced."""
    lines = list(header_lines or [])
    worst = 'INFO'
    order = {'INFO': 0, 'WARNING': 1, 'ERROR': 2}
    for item in _collected:
        if order[item["level"]] > order[worst]:
            worst = item["level"]
    if _collected:
        lines.append("")
        for item in _collected:
            mark = {'INFO': "", 'WARNING': "! ", 'ERROR': "X "}[item["level"]]
            lines.append(f"{mark}{item['summary']}")
    _collected.clear()
    report(context, key, title, lines, level=(level or worst),
           operator=operator, prefix=prefix)


# ─────────────────────────────────────────────────────────────────────────────
#  Panel + operators
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_reports_all(Operator):
    """Turn every HoovyTools popup back on, or silence all of them

Off does not lose anything. A silenced report still prints its full text
to the system console and still appears in Blender's status bar and Info
editor - it only stops opening a dialog you have to click away.

Every report also carries its own switch inside its popup, so the usual
way to silence one is to untick it there. This is the bulk control, and
mostly the way back"""
    bl_idname = "ht.reports_all"
    bl_label = "All Popups"
    bl_options = {"REGISTER", "UNDO"}

    value: BoolProperty(  # type: ignore
        name="On", default=True,
        description="True turns every popup back on, False silences them all",
    )

    def execute(self, context):
        p = prefs(context)
        if p is None:
            self.report({"ERROR"}, "Report settings unavailable")
            return {"CANCELLED"}
        for key in _KEYS:
            setattr(p, key, self.value)
        state = "on" if self.value else "off"
        self.report({"INFO"}, f"{len(_KEYS)} popup(s) turned {state}")
        return {"FINISHED"}


class HT_OT_logs_all(Operator):
    """Turn every log switch on, or keep every report out of the log file

Off loses nothing live. A report whose switch is off still prints its
full text to the system console and still appears in Blender's status
bar and Info editor - it only stays out of the _Logs file.

The per-report switches are in the Developer tab's LOGS box; this is the
bulk control"""
    bl_idname = "ht.logs_all"
    bl_label = "All Log Switches"
    bl_options = {"REGISTER", "UNDO"}

    value: BoolProperty(  # type: ignore
        name="On", default=True,
        description="True logs every report to the file, False logs none",
    )

    def execute(self, context):
        p = log_prefs(context)
        if p is None:
            self.report({"ERROR"}, "Log settings unavailable")
            return {"CANCELLED"}
        for key in _KEYS:
            setattr(p, key, self.value)
        state = "on" if self.value else "off"
        self.report({"INFO"}, f"{len(_KEYS)} log switch(es) turned {state}")
        return {"FINISHED"}


def draw_report_switches(layout, context, compact=False):
    """Every popup with its own switch. NOT DRAWN ANYWHERE - kept on record.

    The Developer tab used to end with this grid, eighteen checkboxes on the
    screen somebody opens when an import has just failed - and not one of them
    helps with that. It went in the 2026-08-22 (l) cleanup.

    Nothing was lost. Every popup still draws its own checkbox inside itself,
    which is where turning one off has always made sense, and the state now
    lives in `_config/_popupvariables.json` where it survives opening another
    .blend. Call this from a panel if the grid is ever wanted back.
    """
    p = prefs(context)
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Popups", icon='INFO')
    on = head.operator("ht.reports_all", text="All On")
    on.value = True
    off = head.operator("ht.reports_all", text="All Off")
    off.value = False
    if p is None:
        box.label(text="Unavailable - re-enable the addon.", icon='ERROR')
        return
    box.label(text="Off = console + status bar, no dialog.")
    if compact:
        return
    col = box.column(align=True)
    grid = col.grid_flow(row_major=True, columns=2, even_columns=True,
                         align=True)
    for key, label, _desc in REPORTS:
        grid.prop(p, key, text=label)


_CLASSES = (
    HoovyToolsReportSettings,
    HoovyToolsLogSettings,
    HT_OT_reports_all,
    HT_OT_logs_all,
)


def register(icon_id_fn=None):
    for cls in _CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.ht_reports = bpy.props.PointerProperty(
        type=HoovyToolsReportSettings)
    bpy.types.Scene.ht_logs = bpy.props.PointerProperty(
        type=HoovyToolsLogSettings)

    #  PULL THE SAVED SWITCHES ONTO THE CURRENT SCENE. A scene opened later
    #  gets its own fresh block, which is why every popup ALSO checks the
    #  file lazily the first time it is asked - see popup_enabled, and the
    #  log switches do the same in log_enabled.
    try:
        load_switches()
    except Exception:                                         # noqa: BLE001
        pass
    try:
        from . import logvars
        logvars.apply_to(log_prefs(), _KEYS)
    except Exception:                                         # noqa: BLE001
        pass


def unregister():
    _HISTORY.clear()
    _synced.clear()
    _log_synced.clear()
    try:
        del bpy.types.Scene.ht_reports
    except Exception:
        pass
    try:
        del bpy.types.Scene.ht_logs
    except Exception:
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
