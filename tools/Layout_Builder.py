"""
Layout_Builder.py  -  part of HoovyTools

the user'S CAPTURED WORKSPACE LAYOUTS, REBUILT ON DEMAND.

Two layouts, captured from the user's own auto-generated layout scripts
(2026-08-27) and kept VERBATIM as data:

    TWO     the two-screen-window arrangement
    THREE   the three-monitor arrangement

The rebuild machinery is the user's proven algorithm, unchanged in
approach: duplicate the current workspace, collapse it to one area by
joining rectangular neighbours, then replay the captured split tree -
one screen operation per timer tick, because Blender only re-validates
area geometry between UI pulses. Areas are re-found SPATIALLY each tick
(by normalized centre point), never held across a topology change - a
held Area reference dies the moment a join or split runs.

Reachable two ways:
    - the two buttons in the Developer tab's Layouts box (Developer Mode)
    - automatically after IMPORT WHOLE SESSION, when the Layouts box's
      "after session import" option names a layout (default Off)

NEVER in background mode: joins and splits need a real window, so a
headless call reports and returns instead of raising.
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

TOLERANCE = 5
STEP_DELAY = 0.05
SHOW_STATUSBAR = True


_TREE_TWO = {'kind': 'SPLIT', 'center': (0.5, 0.5), 'direction': 'VERTICAL', 'factor': 0.49921752738654146,
 'first': {'kind': 'SPLIT', 'center': (0.24973917579551383, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.13113113113113112,
           'first': {'kind': 'AREA', 'center': (0.24973917579551383, 0.06556556556556556), 'type': 'DOPESHEET_EDITOR', 'ui_type': 'TIMELINE',
                     'settings': {'show_region_ui': False, 'show_region_header': True, 'show_region_footer': False, 'show_region_channels': False, 'mode': 'TIMELINE'}},
           'second': {'kind': 'AREA', 'center': (0.24960876369327073, 0.5670670670670671), 'type': 'VIEW_3D', 'ui_type': 'VIEW_3D',
                      'settings': {'show_region_ui': True, 'show_region_toolbar': True, 'show_region_header': True}}},
 'second': {'kind': 'SPLIT', 'center': (0.75, 0.5), 'direction': 'VERTICAL', 'factor': 0.7699530516431925,
            'first': {'kind': 'SPLIT', 'center': (0.6924882629107981, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.13113113113113112,
                      'first': {'kind': 'AREA', 'center': (0.6926186750130412, 0.06556556556556556), 'type': 'GRAPH_EDITOR', 'ui_type': 'FCURVES',
                                'settings': {'show_region_ui': True, 'show_region_header': True, 'show_region_footer': False, 'show_region_channels': True, 'mode': 'FCURVES'}},
                      'second': {'kind': 'SPLIT', 'center': (0.6924882629107981, 0.5670670670670671), 'direction': 'VERTICAL', 'factor': 0.4159891598915989,
                                 'first': {'kind': 'SPLIT', 'center': (0.5800730307772561, 0.5670670670670671), 'direction': 'HORIZONTAL', 'factor': 0.4982658959537572,
                                           'first': {'kind': 'AREA', 'center': (0.5800730307772561, 0.34984984984984985), 'type': 'NODE_EDITOR', 'ui_type': 'ShaderNodeTree',
                                                     'settings': {'show_region_ui': True, 'show_region_toolbar': False, 'show_region_header': True, 'tree_type': 'ShaderNodeTree', 'shader_type': 'WORLD'}},
                                           'second': {'kind': 'AREA', 'center': (0.5800730307772561, 0.7842842842842843), 'type': 'NODE_EDITOR', 'ui_type': 'ShaderNodeTree',
                                                      'settings': {'show_region_ui': True, 'show_region_toolbar': False, 'show_region_header': True, 'tree_type': 'ShaderNodeTree', 'shader_type': 'OBJECT'}}},
                                 'second': {'kind': 'SPLIT', 'center': (0.7729525299947835, 0.5670670670670671), 'direction': 'HORIZONTAL', 'factor': 0.44508670520231214,
                                            'first': {'kind': 'AREA', 'center': (0.7729525299947835, 0.32682682682682684), 'type': 'TEXT_EDITOR', 'ui_type': 'TEXT_EDITOR',
                                                      'settings': {'show_region_ui': False, 'show_region_header': True, 'show_region_footer': True, '_text_name': 'Text'}},
                                            'second': {'kind': 'AREA', 'center': (0.7729525299947835, 0.7612612612612613), 'type': 'VIEW_3D', 'ui_type': 'VIEW_3D',
                                                       'settings': {'show_region_ui': False, 'show_region_toolbar': True, 'show_region_header': True}}}}},
            'second': {'kind': 'SPLIT', 'center': (0.9428794992175273, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.8128128128128128,
                       'first': {'kind': 'AREA', 'center': (0.9428794992175273, 0.4064064064064064), 'type': 'PROPERTIES', 'ui_type': 'PROPERTIES',
                                 'settings': {'show_region_header': True, 'context': 'SCENE'}},
                       'second': {'kind': 'AREA', 'center': (0.9428794992175273, 0.9079079079079079), 'type': 'OUTLINER', 'ui_type': 'OUTLINER',
                                  'settings': {'show_region_header': True, 'display_mode': 'VIEW_LAYER'}}}}}

_TREE_THREE = {'kind': 'SPLIT', 'center': (0.5, 0.5), 'direction': 'VERTICAL', 'factor': 0.3323478260869565,
 'first': {'kind': 'SPLIT', 'center': (0.16626086956521738, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.0920920920920921,
           'first': {'kind': 'AREA', 'center': (0.16617391304347826, 0.04604604604604605), 'type': 'DOPESHEET_EDITOR', 'ui_type': 'DOPESHEET',
                     'settings': {'show_region_ui': False, 'show_region_header': True, 'show_region_footer': False, 'show_region_channels': False, 'mode': 'DOPESHEET'}},
           'second': {'kind': 'SPLIT', 'center': (0.16626086956521738, 0.5475475475475475), 'direction': 'VERTICAL', 'factor': 0.47751046025104604,
                      'first': {'kind': 'SPLIT', 'center': (0.07939130434782608, 0.5475475475475475), 'direction': 'HORIZONTAL', 'factor': 0.37610619469026546,
                                'first': {'kind': 'SPLIT', 'center': (0.07939130434782608, 0.2652652652652653), 'direction': 'VERTICAL', 'factor': 0.5542168674698795,
                                          'first': {'kind': 'AREA', 'center': (0.044, 0.2652652652652653), 'type': 'NODE_EDITOR', 'ui_type': 'ShaderNodeTree',
                                                    'settings': {'show_region_ui': True, 'show_region_toolbar': False, 'show_region_header': True, 'tree_type': 'ShaderNodeTree', 'shader_type': 'OBJECT'}},
                                          'second': {'kind': 'AREA', 'center': (0.12365217391304348, 0.2652652652652653), 'type': 'NODE_EDITOR', 'ui_type': 'ShaderNodeTree',
                                                     'settings': {'show_region_ui': True, 'show_region_toolbar': False, 'show_region_header': True, 'tree_type': 'ShaderNodeTree', 'shader_type': 'WORLD'}}},
                                'second': {'kind': 'SPLIT', 'center': (0.07939130434782608, 0.7192192192192193), 'direction': 'VERTICAL', 'factor': 0.47316538882803943,
                                           'first': {'kind': 'AREA', 'center': (0.03756521739130435, 0.7192192192192193), 'type': 'IMAGE_EDITOR', 'ui_type': 'UV',
                                                     'settings': {'show_region_ui': False, 'show_region_toolbar': False, 'show_region_header': True, 'ui_mode': ''}},
                                           'second': {'kind': 'AREA', 'center': (0.11721739130434783, 0.7192192192192193), 'type': 'NODE_EDITOR', 'ui_type': 'CompositorNodeTree',
                                                      'settings': {'show_region_ui': True, 'show_region_toolbar': False, 'show_region_header': True, 'tree_type': 'CompositorNodeTree', 'shader_type': 'OBJECT'}}}},
                      'second': {'kind': 'AREA', 'center': (0.24591304347826087, 0.5475475475475475), 'type': 'VIEW_3D', 'ui_type': 'VIEW_3D',
                                 'settings': {'show_region_ui': False, 'show_region_toolbar': True, 'show_region_header': True}}}},
 'second': {'kind': 'SPLIT', 'center': (0.6664347826086956, 0.5), 'direction': 'VERTICAL', 'factor': 0.5002606882168926,
            'first': {'kind': 'SPLIT', 'center': (0.49973913043478263, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.0920920920920921,
                      'first': {'kind': 'AREA', 'center': (0.49973913043478263, 0.04604604604604605), 'type': 'GRAPH_EDITOR', 'ui_type': 'FCURVES',
                                'settings': {'show_region_ui': True, 'show_region_header': True, 'show_region_footer': False, 'show_region_channels': True, 'mode': 'FCURVES'}},
                      'second': {'kind': 'AREA', 'center': (0.49982608695652175, 0.5475475475475475), 'type': 'VIEW_3D', 'ui_type': 'VIEW_3D',
                                 'settings': {'show_region_ui': False, 'show_region_toolbar': True, 'show_region_header': True}}},
            'second': {'kind': 'SPLIT', 'center': (0.8335652173913044, 0.5), 'direction': 'VERTICAL', 'factor': 0.6650992685475444,
                       'first': {'kind': 'SPLIT', 'center': (0.7778260869565218, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.0920920920920921,
                                 'first': {'kind': 'AREA', 'center': (0.7778260869565218, 0.04604604604604605), 'type': 'SEQUENCE_EDITOR', 'ui_type': 'SEQUENCE_EDITOR',
                                           'settings': {'show_region_ui': False, 'show_region_toolbar': True, 'show_region_header': True, 'show_region_footer': True, 'show_region_channels': True, 'view_type': 'SEQUENCER'}},
                                 'second': {'kind': 'SPLIT', 'center': (0.7778260869565218, 0.5475475475475475), 'direction': 'HORIZONTAL', 'factor': 0.12831858407079647,
                                            'first': {'kind': 'AREA', 'center': (0.7778260869565218, 0.15315315315315314), 'type': 'INFO', 'ui_type': 'INFO',
                                                      'settings': {'show_region_header': True}},
                                            'second': {'kind': 'SPLIT', 'center': (0.7778260869565218, 0.6071071071071071), 'direction': 'HORIZONTAL', 'factor': 0.15286624203821655,
                                                       'first': {'kind': 'AREA', 'center': (0.7778260869565218, 0.27427427427427425), 'type': 'CONSOLE', 'ui_type': 'CONSOLE',
                                                                 'settings': {'show_region_header': True}},
                                                       'second': {'kind': 'SPLIT', 'center': (0.7778260869565218, 0.6686686686686687), 'direction': 'HORIZONTAL', 'factor': 0.2084592145015106,
                                                                  'first': {'kind': 'AREA', 'center': (0.7778260869565218, 0.4064064064064064), 'type': 'CLIP_EDITOR', 'ui_type': 'CLIP_EDITOR',
                                                                            'settings': {'show_region_ui': True, 'show_region_toolbar': True, 'show_region_header': True, 'show_region_channels': True}},
                                                                  'second': {'kind': 'SPLIT', 'center': (0.7778260869565218, 0.7392392392392393), 'direction': 'VERTICAL', 'factor': 0.33935585231736054,
                                                                             'first': {'kind': 'AREA', 'center': (0.7046956521739131, 0.7392392392392393), 'type': 'TEXT_EDITOR', 'ui_type': 'TEXT_EDITOR',
                                                                                       'settings': {'show_region_ui': False, 'show_region_header': True, 'show_region_footer': True, '_text_name': 'Text'}},
                                                                             'second': {'kind': 'SPLIT', 'center': (0.8156521739130435, 0.7392392392392393), 'direction': 'VERTICAL', 'factor': 0.45346062052505964,
                                                                                        'first': {'kind': 'AREA', 'center': (0.7758260869565218, 0.7392392392392393), 'type': 'TEXT_EDITOR', 'ui_type': 'TEXT_EDITOR',
                                                                                                  'settings': {'show_region_ui': False, 'show_region_header': True, 'show_region_footer': True, '_text_name': 'Text'}},
                                                                                        'second': {'kind': 'AREA', 'center': (0.8489565217391304, 0.7392392392392393), 'type': 'TEXT_EDITOR', 'ui_type': 'TEXT_EDITOR',
                                                                                                   'settings': {'show_region_ui': False, 'show_region_header': True, 'show_region_footer': True, '_text_name': 'Text'}}}}}}}},
                       'second': {'kind': 'SPLIT', 'center': (0.9445217391304348, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.8138138138138138,
                                  'first': {'kind': 'AREA', 'center': (0.9445217391304348, 0.4069069069069069), 'type': 'PROPERTIES', 'ui_type': 'PROPERTIES',
                                            'settings': {'show_region_header': True, 'context': 'SCENE'}},
                                  'second': {'kind': 'AREA', 'center': (0.9445217391304348, 0.9084084084084084), 'type': 'OUTLINER', 'ui_type': 'OUTLINER',
                                             'settings': {'show_region_header': True, 'display_mode': 'VIEW_LAYER'}}}}}}

_TREE_DEFAULT = {'kind': 'SPLIT', 'center': (0.5, 0.5), 'direction': 'VERTICAL', 'factor': 0.78,
 'first': {'kind': 'SPLIT', 'center': (0.39, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.08,
           'first': {'kind': 'AREA', 'center': (0.39, 0.04), 'type': 'DOPESHEET_EDITOR', 'ui_type': 'TIMELINE',
                     'settings': {'show_region_ui': False, 'show_region_header': True, 'mode': 'TIMELINE'}},
           'second': {'kind': 'AREA', 'center': (0.39, 0.54), 'type': 'VIEW_3D', 'ui_type': 'VIEW_3D',
                      'settings': {'show_region_ui': False, 'show_region_toolbar': True, 'show_region_header': True}}},
 'second': {'kind': 'SPLIT', 'center': (0.89, 0.5), 'direction': 'HORIZONTAL', 'factor': 0.5,
            'first': {'kind': 'AREA', 'center': (0.89, 0.25), 'type': 'PROPERTIES', 'ui_type': 'PROPERTIES',
                      'settings': {'show_region_header': True}},
            'second': {'kind': 'AREA', 'center': (0.89, 0.75), 'type': 'OUTLINER', 'ui_type': 'OUTLINER',
                       'settings': {'show_region_header': True, 'display_mode': 'VIEW_LAYER'}}}}

LAYOUTS = {
    "DEFAULT": ("HT Default",      _TREE_DEFAULT),
    "TWO":     ("HT Two Screen",   _TREE_TWO),
    "THREE":   ("HT Three Monitor", _TREE_THREE),
}



def existing_workspace(base):
    """The workspace this layout already built, or None.

    1.18.1. A second press SWITCHES to
    the one that is there. The exact name first, then the copies older
    versions made ("HT Two Screen_2", "HT Two Screen.002")."""
    ws = bpy.data.workspaces.get(base)
    if ws is not None:
        return ws
    copies = sorted(w.name for w in bpy.data.workspaces
                    if w.name.startswith(base + "_") or w.name.startswith(base + "."))
    return bpy.data.workspaces.get(copies[0]) if copies else None


#  The sidebar tab the add-on lives in (Panel.HT_PT_sidebar.bl_category).
SIDEBAR_CATEGORY = "HoovyTools"                    # 3.0.0: the HoovyTools tab (1.20.0-1.26: "SFM to Blender")


def show_hoovytools(screen):
    """Open the sidebar of the screen's biggest 3D view on the HoovyTools tab.

    1.18.1. The captured layouts
    keep the sidebar shut on most 3D views and none of them picks a tab, so
    the add-on vanished the moment a layout was built. The main viewport gets
    it back; the smaller 3D views keep what the layout says. Returns the area
    name it opened, or None."""
    if screen is None:
        return None
    views = [a for a in screen.areas if a.type == 'VIEW_3D']
    if not views:
        return None
    main = max(views, key=lambda a: a.width * a.height)
    try:
        main.spaces.active.show_region_ui = True
    except Exception:                                         # noqa: BLE001
        return None
    for region in main.regions:
        if region.type == 'UI':
            try:
                region.active_panel_category = SIDEBAR_CATEGORY
            except Exception:                                 # noqa: BLE001
                pass                  # the tab list is filled on first draw
    try:
        main.tag_redraw()
    except Exception:                                         # noqa: BLE001
        pass
    return f"{main.width}x{main.height} 3D view"


def _show_hoovytools_later(window, tries=10):
    """After a workspace switch the window's screen changes on the next
    redraw, and a sidebar's tab list only exists once it has been drawn -
    so keep trying for a second."""
    state = {"n": tries}

    def _tick():
        try:
            screen = window.screen
            show_hoovytools(screen)
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if (region.type == 'UI' and area.spaces.active.show_region_ui
                                and getattr(region, "active_panel_category", "")
                                == SIDEBAR_CATEGORY):
                            return None
        except Exception:                                     # noqa: BLE001
            return None
        state["n"] -= 1
        return 0.1 if state["n"] > 0 else None

    bpy.app.timers.register(_tick, first_interval=0.05)


def _center_of(area):
    return (int(area.x + area.width * 0.5), int(area.y + area.height * 0.5))


def _screen_bounds(screen):
    areas = list(screen.areas)
    return (min(a.x for a in areas), min(a.y for a in areas),
            max(a.x + a.width for a in areas),
            max(a.y + a.height for a in areas))


def _joinable_pair(screen):
    areas = list(screen.areas)
    for i, a in enumerate(areas):
        for b in areas[i + 1:]:
            same_y = abs(a.y - b.y) <= TOLERANCE
            same_h = abs(a.height - b.height) <= TOLERANCE
            touching_x = (abs((a.x + a.width) - b.x) <= TOLERANCE
                          or abs((b.x + b.width) - a.x) <= TOLERANCE)
            if same_y and same_h and touching_x:
                return a, b
            same_x = abs(a.x - b.x) <= TOLERANCE
            same_w = abs(a.width - b.width) <= TOLERANCE
            touching_y = (abs((a.y + a.height) - b.y) <= TOLERANCE
                          or abs((b.y + b.height) - a.y) <= TOLERANCE)
            if same_x and same_w and touching_y:
                return a, b
    return None


def _area_from_normalized_point(screen, normalized):
    x0, y0, x1, y1 = _screen_bounds(screen)
    px = x0 + normalized[0] * (x1 - x0)
    py = y0 + normalized[1] * (y1 - y0)
    candidates = [a for a in screen.areas
                  if a.x <= px <= a.x + a.width
                  and a.y <= py <= a.y + a.height]
    if not candidates:
        return None
    return min(candidates, key=lambda a: a.width * a.height)


def _apply_leaf(area, node):
    try:
        area.type = node["type"]
    except Exception as exc:                                  # noqa: BLE001
        print(f"[LAYOUT]  could not set editor {node['type']}: {exc}")
    ui_type = node.get("ui_type")
    if ui_type:
        try:
            area.ui_type = ui_type
        except Exception:                                     # noqa: BLE001
            pass
    try:
        space = area.spaces.active
    except Exception:                                         # noqa: BLE001
        return
    settings = node.get("settings", {})
    for prop, value in settings.items():
        if prop.startswith("_") or not hasattr(space, prop):
            continue
        try:
            setattr(space, prop, value)
        except Exception:                                     # noqa: BLE001
            pass
    text_name = settings.get("_text_name")
    if text_name and area.type == "TEXT_EDITOR":
        text = bpy.data.texts.get(text_name)
        if text:
            try:
                space.text = text
            except Exception:                                 # noqa: BLE001
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  The timer state machine
# ─────────────────────────────────────────────────────────────────────────────

_STATE = {"window": None, "workspace": None, "stage": "START", "queue": [],
          "tree": None}


def _rebuild_step():
    window = _STATE["window"]
    if window is None:
        print("[LAYOUT]  window disappeared")
        return None
    screen = window.screen

    if _STATE["stage"] == "COLLAPSE":
        if len(screen.areas) <= 1:
            _STATE["stage"] = "BUILD"
            _STATE["queue"] = [_STATE["tree"]]
            return STEP_DELAY
        pair = _joinable_pair(screen)
        if pair is None:
            print("[LAYOUT]  ERROR: no rectangular pair to join")
            return None
        source, target = pair
        source_xy = _center_of(source)
        target_xy = _center_of(target)
        try:
            with bpy.context.temp_override(window=window, screen=screen,
                                           area=source):
                result = bpy.ops.screen.area_join(source_xy=source_xy,
                                                  target_xy=target_xy)
            if "FINISHED" not in result:
                with bpy.context.temp_override(window=window, screen=screen,
                                               area=target):
                    bpy.ops.screen.area_join(source_xy=target_xy,
                                             target_xy=source_xy)
        except Exception as exc:                              # noqa: BLE001
            print(f"[LAYOUT]  join failed: {exc}")
            return None
        return STEP_DELAY

    if _STATE["stage"] == "BUILD":
        if not _STATE["queue"]:
            _STATE["stage"] = "DONE"
            try:
                screen.show_statusbar = SHOW_STATUSBAR
            except Exception:                                 # noqa: BLE001
                pass
            #  LOOK THROUGH THE SCENE CAMERA, if there is one. A freshly
            #  built layout full of 3D views showing the world origin is a
            #  wall of grey; through the session's camera it is the film.
            try:
                if bpy.context.scene.camera is not None:
                    set_viewports_to_camera(window=window)
            except Exception:                                 # noqa: BLE001
                pass
            _show_hoovytools_later(window)
            print(f"[LAYOUT]  rebuild complete - workspace "
                  f"'{_STATE['workspace'].name}', {len(screen.areas)} areas")
            return None
        node = _STATE["queue"].pop(0)
        area = _area_from_normalized_point(screen, node["center"])
        if area is None:
            print("[LAYOUT]  could not locate target area")
            return None
        if node["kind"] == "AREA":
            _apply_leaf(area, node)
            return STEP_DELAY
        direction = node["direction"]
        factor = max(0.01, min(0.99, float(node["factor"])))
        try:
            with bpy.context.temp_override(window=window, screen=screen,
                                           area=area):
                result = bpy.ops.screen.area_split(direction=direction,
                                                   factor=factor)
        except Exception as exc:                              # noqa: BLE001
            print(f"[LAYOUT]  split failed: {direction} {factor} {exc}")
            return None
        if "FINISHED" not in result:
            print(f"[LAYOUT]  split cancelled: {direction} {factor}")
            return None
        #  Children are found spatially on later ticks - a held Area
        #  reference dies the moment the topology changes.
        _STATE["queue"].insert(0, node["second"])
        _STATE["queue"].insert(0, node["first"])
        return STEP_DELAY

    return None


def rebuild_layout(layout_key, window=None):
    """Duplicate the current workspace and rebuild it as *layout_key*.
    Returns (ok, message). Never raises; refuses in background mode."""
    if layout_key not in LAYOUTS:
        return False, f"unknown layout '{layout_key}'"
    if bpy.app.background:
        return False, "no UI in background mode - layouts need a window"
    window = window or bpy.context.window
    if window is None:
        return False, "no active Blender window"
    if _STATE["stage"] in ("COLLAPSE", "BUILD"):
        return False, "a layout rebuild is already running"

    base_name, tree = LAYOUTS[layout_key]
    have = existing_workspace(base_name)
    if have is not None:
        #  ONE PER LAYOUT: a second press goes to it, never builds a copy.
        window.workspace = have
        _show_hoovytools_later(window)
        return True, f"switched to '{have.name}' (already built)"
    target_name = base_name
    try:
        with bpy.context.temp_override(window=window):
            bpy.ops.workspace.duplicate()
    except Exception as exc:                                  # noqa: BLE001
        return False, f"could not duplicate the workspace: {exc}"
    workspace = window.workspace
    workspace.name = target_name

    _STATE.update(window=window, workspace=workspace, stage="COLLAPSE",
                  queue=[], tree=tree)
    print(f"[LAYOUT]  rebuilding '{target_name}' "
          f"({len(tree_leaves(tree))} editors)")
    bpy.app.timers.register(_rebuild_step, first_interval=STEP_DELAY)
    return True, f"building workspace '{target_name}'"


def tree_leaves(node):
    """Every AREA leaf of a tree - the count a report can print."""
    if node["kind"] == "AREA":
        return [node]
    return tree_leaves(node["first"]) + tree_leaves(node["second"])


# ─────────────────────────────────────────────────────────────────────────────
#  Persistence - the choice survives the .blend
# ─────────────────────────────────────────────────────────────────────────────
#
#  layout_after_import is a SCENE property, and a scene property lasts
#  exactly one .blend - "I picked Two Screen" would silently reset to Off
#  in every new file, which reads as a broken setting (the popup switches
#  taught this lesson first). Same doctrine as core/popups.py: the scene
#  block is the live value Blender's UI binds to, the JSON in _config is
#  what SURVIVES - written whenever the choice changes, applied back onto
#  each scene the first time anything asks.

STORE_NAME = "_layoutvariables.json"

#  Scenes already synced from the file this session - one apply per scene,
#  so an in-session change to Off is respected until the next file.
_synced = set()


def _store_path():
    from ..core import paths as _paths
    return _paths.data_dir("config") / STORE_NAME


def save_choice(layout=None, render=None):
    """Write the choice(s) out - only the keys given change. Never raises."""
    try:
        import json
        p = _store_path()
        data = {}
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            except Exception:                                 # noqa: BLE001
                data = {}
        data["version"] = 1
        data["note"] = ("What Import Whole Session does when it finishes: "
                        "which workspace layout it builds, and which render "
                        "engine preset it applies. Set from the Developer "
                        "tab's Layouts box; OFF disables each.")
        if layout is not None:
            data["layout_after_import"] = str(layout)
        if render is not None:
            data["render_after_import"] = str(render)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:                                  # noqa: BLE001
        print(f"[LAYOUT]  could not save the choice: {exc}")


def _load_key(key, allowed):
    try:
        import json
        p = _store_path()
        if not p.is_file():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        v = raw.get(key)
        return v if v in allowed else None
    except Exception:                                         # noqa: BLE001
        return None


def load_choice():
    """The stored layout choice, or None. Missing or mangled means None -
    the property's own default (OFF) then stands, the safe direction."""
    return _load_key("layout_after_import", (*LAYOUTS, 'OFF'))


def load_render_choice():
    """The stored render-engine choice, or None. Same doctrine as above."""
    return _load_key("render_after_import", ('OFF', 'EEVEE', 'CYCLES'))


def ensure_synced(scene):
    """Pull the stored choices onto *scene*'s block, once per scene."""
    st = getattr(scene, "ht_panel", None)
    if st is None or id(scene) in _synced:
        return
    _synced.add(id(scene))
    for prop, stored in (("layout_after_import", load_choice()),
                         ("render_after_import", load_render_choice())):
        if stored is not None and getattr(st, prop, None) != stored:
            try:
                setattr(st, prop, stored)
            except Exception:                                 # noqa: BLE001
                pass


def _on_load(_dummy):
    """load_post: a freshly opened .blend gets the stored choice, so the
    Layouts box shows the truth instead of the scene's stale default."""
    _synced.clear()
    try:
        ensure_synced(bpy.context.scene)
    except Exception:                                         # noqa: BLE001
        pass


def launch_after_import(context):
    """Called by Import Whole Session when the Layouts box asked for it.
    Returns a report line, or None when the option is Off / unavailable."""
    ensure_synced(context.scene)
    st = getattr(context.scene, "ht_panel", None)
    choice = getattr(st, "layout_after_import", 'OFF') if st else 'OFF'
    if choice == 'OFF':
        return None
    ok, msg = rebuild_layout(choice)
    return f"Layout : {msg}" + ("" if ok else "  (skipped)")


def apply_render_after_import(context):
    """Apply the chosen render-engine preset when Import Whole Session
    finishes (the Layouts box's second "after import" option). Returns a
    report line, or None when the option is Off."""
    ensure_synced(context.scene)
    st = getattr(context.scene, "ht_panel", None)
    choice = getattr(st, "render_after_import", 'OFF') if st else 'OFF'
    if choice == 'OFF':
        return None
    try:
        bpy.ops.ht.engine_preset(preset=choice)
        return f"Engine : {choice} preset applied"
    except Exception as exc:                                  # noqa: BLE001
        return f"Engine : {choice} preset failed ({exc})"


# ─────────────────────────────────────────────────────────────────────────────
#  The camera jump - the session ends looking through its own lens
# ─────────────────────────────────────────────────────────────────────────────

#  Collections searched for the camera to jump into, MOST REFINED FIRST:
#  the splitter's shots are the cut-up, handled cameras; the importer
#  collections hold the raw takes; anything else is a fallback.
_CAMERA_HOMES = ("__HoovyTools Camera Split__",
                 "___HoovyTools Camera___",
                 "__Hoovy Camera Import__")


def pick_session_camera(scene):
    """The camera a fresh import most wants to be seen through, or None.
    THE SHOT'S OWN CAMERA FIRST (1.17.0): Session_Visibility stamps the
    camera SFM looks through as `scene["ht_shot_camera"]`. Then the first
    shot of the split collection, then a raw take, then anything - the
    alphabetical fallback that used to pick "Constrained Camera" over the
    gothic shot's camera5."""
    stamped = scene.get("ht_shot_camera") if scene is not None else None
    if stamped:
        ob = bpy.data.objects.get(str(stamped))
        if ob is not None and ob.type == 'CAMERA' and \
                scene.objects.get(ob.name) is not None:
            return ob
    for col_name in _CAMERA_HOMES:
        col = bpy.data.collections.get(col_name)
        if col is None:
            continue
        cams = sorted((o for o in col.objects if o.type == 'CAMERA'),
                      key=lambda o: o.name)
        if cams:
            return cams[0]
    cams = sorted((o for o in scene.objects if o.type == 'CAMERA'),
                  key=lambda o: o.name)
    return cams[0] if cams else None


def set_viewports_to_camera(window=None):
    """Flip every VIEW_3D area of *window* (or all windows) into camera
    view. Quiet no-op headless. Returns how many views flipped."""
    if bpy.app.background:
        return 0
    windows = ([window] if window is not None
               else list(bpy.context.window_manager.windows))
    flipped = 0
    for win in windows:
        if win is None or win.screen is None:
            continue
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            try:
                space = area.spaces.active
                if space.region_3d.view_perspective != 'CAMERA':
                    space.region_3d.view_perspective = 'CAMERA'
                flipped += 1
            except Exception:                                 # noqa: BLE001
                pass
    return flipped


def jump_to_session_camera(context):
    """Make the scene look through the session's camera - called at the end
    of Import Whole Session. Returns a report line, or None if no camera.

    Elegance is three things done together: the SCENE camera is set (so
    renders and any later layout agree), every open 3D view flips into
    camera view, and the playhead snaps to the frame range start so the
    first thing on screen is the first frame of the film - not a T-posed
    crowd at the origin."""
    cam = pick_session_camera(context.scene)
    if cam is None:
        return None
    context.scene.camera = cam
    try:
        context.scene.frame_set(context.scene.frame_start)
    except Exception:                                         # noqa: BLE001
        pass
    flipped = set_viewports_to_camera()
    return (f"View   : through '{cam.name}'"
            + (f", {flipped} viewport(s)" if flipped else ""))


# ─────────────────────────────────────────────────────────────────────────────
#  Render presets - EEVEE / Cycles, tuned for a render you can still orbit
# ─────────────────────────────────────────────────────────────────────────────

def _set_all(obj, pairs):
    """setattr the pairs that exist on this build. Returns names set."""
    done = []
    for name, value in pairs:
        if hasattr(obj, name):
            try:
                setattr(obj, name, value)
                done.append(name)
            except Exception:                                 # noqa: BLE001
                pass
    return done


class HT_OT_engine_preset(Operator):
    """NO INPUT - switches the render engine and tunes its settings

        Set the scene up for EEVEE or Cycles in one press

Every value is chosen to be RENDER-appropriate while the viewport stays
interactive: EEVEE gets 64 render / 16 viewport samples with raytracing
and high-quality shadows; Cycles gets 256 render samples with adaptive
sampling and denoising, 32 denoised viewport samples, GPU device and
persistent data so re-renders skip the sync.

Default resets the same knobs back to Blender's factory numbers on
EEVEE. Only settings that exist on this Blender build are touched"""
    #  NOT ht.render_preset: ui/Developer.py owns that name for the four
    #  quality presets, and two classes on one idname means the one
    #  registered last silently replaces the other - this row's buttons
    #  then set a preset the survivor does not have and the panel draw
    #  raised, cutting off everything drawn after it.
    bl_idname = "ht.engine_preset"
    bl_label = "Engine Preset"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(  # type: ignore
        name="Preset",
        items=[('DEFAULT', "Default", "EEVEE at Blender's factory settings"),
               ('EEVEE', "EEVEE", "EEVEE tuned for rendering"),
               ('CYCLES', "Cycles", "Cycles tuned for rendering")],
        default='EEVEE',
    )

    def _volume_reach(self, scene):
        """How far EEVEE's volumetric range must reach to hold the imported
        HT_Volumetrics box, or None when the scene has no box. Camera-to-far-
        corner, over-estimated from the origin - the same arithmetic as
        Light_Import._fit_eevee_volumetrics."""
        box = bpy.data.objects.get("HT_Volumetrics")
        if box is None:
            return None
        try:
            centre = box.matrix_world.translation
            size = box.dimensions
            return float(centre.length + size.length * 0.5)
        except Exception:                                     # noqa: BLE001
            return None

    def execute(self, context):
        scene = context.scene
        touched = []

        tuned = self.preset != 'DEFAULT'
        reach = self._volume_reach(scene)

        cs = getattr(scene, "cycles", None)
        if cs is not None:
            touched += _set_all(cs, (
                ("samples", 256),
                ("preview_samples", 32),
                ("use_adaptive_sampling", True),
                ("adaptive_threshold", 0.01),
                ("preview_adaptive_threshold", 1.0),
                ("use_denoising", True),
                ("use_preview_denoising", True),
                ("preview_denoiser", 'AUTO'),
                ("device", 'GPU'),
                #  Source scenes are huge in Hammer units; short light
                #  paths keep them interactive without visibly dimming.
                ("max_bounces", 8),
                ("volume_bounces", 8),
                ("sample_clamp_direct", 4.2),
                ("caustics_reflective", False),
                ("caustics_refractive", False),
                #  Exposure is Cycles-only film math - anything but 1.0
                #  makes Cycles brighter/darker than EEVEE by a constant
                #  factor nothing else explains.
                ("film_exposure", 1.0),
                #  Volume march quality, matched against EEVEE's numbers
                #  below - a giant box needs the steps.
                ("volume_step_rate", 1.0),
                ("volume_preview_step_rate", 1.0),
                ("volume_max_steps", 1024),
            ))

        ee = getattr(scene, "eevee", None)
        if ee is not None:
            pairs = [
                ("taa_render_samples", 64),
                ("taa_samples", 16),
                ("use_raytracing", tuned),
                ("use_shadows", True),
                ("shadow_ray_count", 2 if tuned else 1),
                ("shadow_step_count", 4 if tuned else 3),
                #  ALWAYS on: fog that ignores shadows in EEVEE and honours
                #  them in Cycles is the single loudest between-engine
                #  difference in a light-shafts scene.
                ("use_volumetric_shadows", True),
                ("volumetric_shadow_samples", 32 if tuned else 16),
                ("volumetric_tile_size", '4' if tuned else '8'),
                ("volumetric_samples", 96 if tuned else 64),
                ("volumetric_start", 0.1),
                ("use_fast_gi", tuned),
                #  Distant strong lights: EEVEE culls a light's influence at
                #  this threshold, and at Hammer-unit distances the default
                #  0.01 amputates beams Cycles happily draws.
                ("light_threshold", 0.001 if tuned else 0.01),
            ]
            #  Volumetric range must contain the imported fog box, or EEVEE
            #  shows fog for exactly volumetric_end units and then air.
            if reach is not None and tuned:
                try:
                    if float(getattr(ee, "volumetric_end", 0.0)) < reach:
                        pairs.append(("volumetric_end", reach))
                except Exception:                             # noqa: BLE001
                    pass
            touched += _set_all(ee, pairs)

        if self.preset == 'CYCLES':
            try:
                scene.render.engine = 'CYCLES'
            except Exception as exc:                          # noqa: BLE001
                self.report({"ERROR"}, f"Cycles unavailable: {exc}")
                return {"CANCELLED"}
            touched += _set_all(scene.render, (
                ("use_persistent_data", True),
            ))
        else:
            #  DEFAULT and EEVEE both land on EEVEE; DEFAULT with factory
            #  numbers, EEVEE with the render-tuned ones.
            try:
                scene.render.engine = 'BLENDER_EEVEE'
            except Exception:                                 # noqa: BLE001
                try:
                    scene.render.engine = 'BLENDER_EEVEE_NEXT'
                except Exception as exc:                      # noqa: BLE001
                    self.report({"ERROR"}, f"EEVEE unavailable: {exc}")
                    return {"CANCELLED"}
            touched += _set_all(scene.render, (
                ("use_persistent_data", False),
            ))

        self.report({"INFO"},
                    f"{self.preset.title()} preset - engine "
                    f"{scene.render.engine}, {len(touched)} setting(s), "
                    f"both engines' blocks written")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
#  Operator
# ─────────────────────────────────────────────────────────────────────────────

class HT_OT_build_layout(Operator):
    """NO INPUT - builds the layout once, then switches to it

        Build one of the user's captured workspace layouts

The first press creates the workspace (the current one is untouched): it
collapses a copy to a single area, then replays the captured split tree one
screen operation at a time - the build visibly assembles over a second or
two, which is normal. Every later press switches to that workspace instead
of building another copy. Either way the main 3D view opens its sidebar on
the HoovyTools tab. To build it fresh, delete the workspace tab first.

Two Screen is the compact arrangement; Three Monitor is the full spread
with sequencer, compositor, clip editor and three text editors. Also
available automatically after IMPORT WHOLE SESSION - pick a layout under
"after session import" in the Layouts box"""
    bl_idname = "ht.build_layout"
    bl_label = "Build Layout"
    bl_options = {"REGISTER"}

    layout_key: EnumProperty(  # type: ignore
        name="Layout",
        items=[('DEFAULT', "Default", "Blender's stock Layout arrangement"),
               ('TWO', "Two Screen", "The two-screen-window arrangement"),
               ('THREE', "Three Monitor", "The three-monitor arrangement")],
        default='TWO',
    )

    def execute(self, context):
        ok, msg = rebuild_layout(self.layout_key, window=context.window)
        self.report({'INFO' if ok else 'WARNING'}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


_CLASSES = (HT_OT_build_layout, HT_OT_engine_preset)


def register(icon_id_fn=None):
    for cls in _CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:                                     # noqa: BLE001
            pass
        bpy.utils.register_class(cls)
    #  The stored choice onto the current scene now, and onto every scene a
    #  file load brings in later.
    try:
        if _on_load not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_on_load)
        ensure_synced(bpy.context.scene)
    except Exception:                                         # noqa: BLE001
        pass


def unregister():
    _synced.clear()
    try:
        if _on_load in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_on_load)
    except Exception:                                         # noqa: BLE001
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:                                     # noqa: BLE001
            pass
