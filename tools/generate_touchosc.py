#!/usr/bin/env python3
"""Generate a TouchOSC .tosc control surface for the gameshow (flat layout, no PAGER)."""

import uuid
import xml.etree.ElementTree as ET
import zlib
import sys
import os

W, H = 1024, 768  # landscape tablet
P = 10  # padding


def _fmt(v) -> str:
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def _sub(parent, tag):
    e = parent.find(tag)
    return e if e is not None else ET.SubElement(parent, tag)


def _ch(n): return _sub(n, "children")
def _pr(n): return _sub(n, "properties")
def _va(n): return _sub(n, "values")
def _ms(n): return _sub(n, "messages")


def ps(pr, key, val):
    p = ET.SubElement(pr, "property", attrib={"type": "s"})
    ET.SubElement(p, "key").text = key
    ET.SubElement(p, "value").text = str(val)

def pb(pr, key, val):
    p = ET.SubElement(pr, "property", attrib={"type": "b"})
    ET.SubElement(p, "key").text = key
    ET.SubElement(p, "value").text = "1" if val else "0"

def pi(pr, key, val):
    p = ET.SubElement(pr, "property", attrib={"type": "i"})
    ET.SubElement(p, "key").text = key
    ET.SubElement(p, "value").text = str(int(val))

def pf(pr, key, val):
    p = ET.SubElement(pr, "property", attrib={"type": "f"})
    ET.SubElement(p, "key").text = key
    ET.SubElement(p, "value").text = _fmt(val)

def pc(pr, key, r, g, b, a=1):
    p = ET.SubElement(pr, "property", attrib={"type": "c"})
    ET.SubElement(p, "key").text = key
    v = ET.SubElement(p, "value")
    for k, val in (("r", r), ("g", g), ("b", b), ("a", a)):
        ET.SubElement(v, k).text = _fmt(val)

def pframe(pr, x, y, w, h):
    p = ET.SubElement(pr, "property", attrib={"type": "r"})
    ET.SubElement(p, "key").text = "frame"
    v = ET.SubElement(p, "value")
    for k, val in (("x", x), ("y", y), ("w", w), ("h", h)):
        ET.SubElement(v, k).text = _fmt(val)


def _base(pr, x, y, w, h, color, *,
          interactive=True, outline=True, outline_style=0,
          grab_focus=False, locked=False, orientation=0,
          pointer_priority=0, corner_radius=0, shape=0):
    """Apply the full set of standard properties in the same order as the blank file."""
    pb(pr, "background", True)
    pc(pr, "color", *color)
    pf(pr, "cornerRadius", corner_radius)
    pframe(pr, x, y, w, h)
    pb(pr, "grabFocus", grab_focus)
    pb(pr, "interactive", interactive)
    pb(pr, "locked", locked)
    pi(pr, "orientation", orientation)
    pb(pr, "outline", outline)
    pi(pr, "outlineStyle", outline_style)
    pi(pr, "pointerPriority", pointer_priority)
    pi(pr, "shape", shape)
    pb(pr, "visible", True)


def _touch_value(n):
    va = _va(n)
    ve = ET.SubElement(va, "value")
    ET.SubElement(ve, "key").text = "touch"
    ET.SubElement(ve, "locked").text = "0"
    ET.SubElement(ve, "lockedDefaultCurrent").text = "0"
    ET.SubElement(ve, "default").text = "false"
    ET.SubElement(ve, "defaultPull").text = "0"


def _x_value(n, default="0"):
    va = _va(n)
    ve = ET.SubElement(va, "value")
    ET.SubElement(ve, "key").text = "x"
    ET.SubElement(ve, "locked").text = "0"
    ET.SubElement(ve, "lockedDefaultCurrent").text = "0"
    ET.SubElement(ve, "default").text = str(default)
    ET.SubElement(ve, "defaultPull").text = "0"


def _text_value(n, default, static=True):
    """LABEL controls use 'text' as their value key (not 'x').
    static=True locks to the default so the property text is always shown."""
    va = _va(n)
    ve = ET.SubElement(va, "value")
    ET.SubElement(ve, "key").text = "text"
    ET.SubElement(ve, "locked").text = "0"
    ET.SubElement(ve, "lockedDefaultCurrent").text = "1" if static else "0"
    ET.SubElement(ve, "default").text = str(default)
    ET.SubElement(ve, "defaultPull").text = "0"


def _partial(parent, typ, conversion, val):
    pt = ET.SubElement(parent, "partial")
    ET.SubElement(pt, "type").text = typ
    ET.SubElement(pt, "conversion").text = conversion
    ET.SubElement(pt, "value").text = val
    ET.SubElement(pt, "scaleMin").text = "0"
    ET.SubElement(pt, "scaleMax").text = "1"


def _osc_send(ms, address, arg_type="VALUE", arg_val="x", arg_conv="FLOAT",
              trigger="RISE"):
    osc = ET.SubElement(ms, "osc")
    for k, v in (("enabled","1"),("send","1"),("receive","0"),
                 ("feedback","0"),("connections","00001")):
        ET.SubElement(osc, k).text = v
    t = ET.SubElement(ET.SubElement(osc, "triggers"), "trigger")
    ET.SubElement(t, "var").text = "x"
    ET.SubElement(t, "condition").text = trigger
    _partial(ET.SubElement(osc, "path"), "CONSTANT", "STRING", address)
    _partial(ET.SubElement(osc, "arguments"), arg_type, arg_conv, arg_val)


def _osc_receive(ms, address):
    osc = ET.SubElement(ms, "osc")
    for k, v in (("enabled","1"),("send","0"),("receive","1"),
                 ("feedback","0"),("connections","00001")):
        ET.SubElement(osc, k).text = v
    t = ET.SubElement(ET.SubElement(osc, "triggers"), "trigger")
    ET.SubElement(t, "var").text = "text"
    ET.SubElement(t, "condition").text = "ANY"
    _partial(ET.SubElement(osc, "path"), "CONSTANT", "STRING", address)
    _partial(ET.SubElement(osc, "arguments"), "VALUE", "STRING", "text")


def _node(parent_ch, typ):
    return ET.SubElement(parent_ch, "node",
                         attrib={"ID": str(uuid.uuid4()), "type": typ})


# ----- control factories -----

def button(parent_ch, x, y, w, h, label, address,
           color=(0.3, 0.3, 0.3), arg_val="1"):
    # GROUP wrapper at absolute position; children use relative coords
    grp = _node(parent_ch, "GROUP")
    gpr = _pr(grp)
    pb(gpr, "background", False)
    pc(gpr, "color", 0, 0, 0)
    pf(gpr, "cornerRadius", 0)
    pframe(gpr, x, y, w, h)
    pb(gpr, "grabFocus", False)
    pb(gpr, "interactive", True)
    pb(gpr, "locked", False)
    pi(gpr, "orientation", 0)
    pb(gpr, "outline", False)
    pi(gpr, "outlineStyle", 0)
    pi(gpr, "pointerPriority", 0)
    pi(gpr, "shape", 0)
    pb(gpr, "visible", True)
    _touch_value(grp)

    ch = _ch(grp)

    # LABEL first (underneath): shows button color and text label
    lbl = _node(ch, "LABEL")
    lpr = _pr(lbl)
    ps(lpr, "name", f"{label}_lbl")
    ps(lpr, "text", label)
    pb(lpr, "background", True)
    pc(lpr, "color", *color)
    pf(lpr, "cornerRadius", 1)
    pframe(lpr, 0, 0, w, h)
    pb(lpr, "grabFocus", False)
    pb(lpr, "interactive", False)
    pb(lpr, "locked", False)
    pi(lpr, "orientation", 0)
    pb(lpr, "outline", False)
    pi(lpr, "outlineStyle", 0)
    pi(lpr, "pointerPriority", 0)
    pi(lpr, "shape", 0)
    pb(lpr, "visible", True)
    pi(lpr, "font", 0)
    pc(lpr, "textColor", 1, 1, 1)
    pi(lpr, "textSize", 16)
    pi(lpr, "textAlignH", 2)
    pi(lpr, "textAlignV", 2)
    pi(lpr, "textLength", 0)
    pb(lpr, "textClip", True)
    _text_value(lbl, label, static=True)
    _touch_value(lbl)

    # BUTTON second (on top): transparent background so LABEL shows through,
    # handles touch detection and OSC sending
    n = _node(ch, "BUTTON")
    pr = _pr(n)
    ps(pr, "name", f"{label}_btn")
    pb(pr, "background", False)
    pc(pr, "color", *color)
    pf(pr, "cornerRadius", 1)
    pframe(pr, 0, 0, w, h)
    pb(pr, "grabFocus", True)
    pb(pr, "interactive", True)
    pb(pr, "locked", False)
    pi(pr, "orientation", 0)
    pb(pr, "outline", False)
    pi(pr, "outlineStyle", 0)
    pi(pr, "pointerPriority", 0)
    pi(pr, "shape", 0)
    pb(pr, "visible", True)
    pi(pr, "buttonType", 0)
    pb(pr, "press", True)
    pb(pr, "release", True)
    pb(pr, "valuePosition", False)
    _touch_value(n)
    _x_value(n, "0")
    _osc_send(_ms(n), address, arg_type="CONSTANT", arg_val=arg_val, arg_conv="FLOAT")

    return grp


def label(parent_ch, x, y, w, h, text, color=(0.08, 0.08, 0.08), text_size=12):
    n = _node(parent_ch, "LABEL")
    pr = _pr(n)
    ps(pr, "name", text)
    ps(pr, "text", text)
    _base(pr, x, y, w, h, color, interactive=False, outline=False)
    pi(pr, "font", 0)
    pc(pr, "textColor", 0.55, 0.55, 0.55)
    pi(pr, "textSize", text_size)
    pi(pr, "textAlignH", 1)
    pi(pr, "textAlignV", 2)
    pi(pr, "textLength", 0)
    pb(pr, "textClip", True)
    _text_value(n, text, static=True)
    _touch_value(n)
    return n


def feedback_label(parent_ch, x, y, w, h, address, color=(0.1, 0.1, 0.1)):
    n = _node(parent_ch, "LABEL")
    pr = _pr(n)
    ps(pr, "name", address)
    ps(pr, "text", "—")
    _base(pr, x, y, w, h, color, interactive=False, outline=True)
    pi(pr, "font", 0)
    pc(pr, "textColor", 1, 1, 1)
    pi(pr, "textSize", 18)
    pi(pr, "textAlignH", 2)
    pi(pr, "textAlignV", 2)
    pi(pr, "textLength", 0)
    pb(pr, "textClip", True)
    _text_value(n, "—", static=False)
    _touch_value(n)
    _osc_receive(_ms(n), address)
    return n


def fader(parent_ch, x, y, w, h, address, default=0.7, color=(0.2, 0.4, 0.6)):
    n = _node(parent_ch, "FADER")
    pr = _pr(n)
    ps(pr, "name", address)
    _base(pr, x, y, w, h, color, grab_focus=True)
    pb(pr, "bar", True)
    pi(pr, "barDisplay", 0)
    pb(pr, "grid", True)
    pi(pr, "gridSteps", 10)
    pi(pr, "response", 0)
    pi(pr, "responseFactor", 100)
    pb(pr, "cursor", True)
    pi(pr, "cursorDisplay", 0)
    _x_value(n, _fmt(default))
    _touch_value(n)
    _osc_send(_ms(n), address, trigger="ANY")
    return n


def section_label(parent_ch, x, y, w, h, text):
    n = _node(parent_ch, "LABEL")
    pr = _pr(n)
    ps(pr, "name", text)
    ps(pr, "text", text)
    _base(pr, x, y, w, h, (0.05, 0.05, 0.05), interactive=False, outline=False)
    pi(pr, "font", 0)
    pc(pr, "textColor", 0.4, 0.4, 0.4)
    pi(pr, "textSize", 11)
    pi(pr, "textAlignH", 1)
    pi(pr, "textAlignV", 2)
    pi(pr, "textLength", 0)
    pb(pr, "textClip", True)
    _text_value(n, text, static=True)
    _touch_value(n)
    return n


# ----- layout -----
#
# Single flat GROUP. Divided into three columns:
#   Left  (0..439):    Game control (buzzer commands)
#   Mid   (449..719):  Show navigation
#   Right (729..1014): Audio
#
# Column dividers are just visual — no pager needed.

COL1_X = 0
COL1_W = 440
COL2_X = 449
COL2_W = 270
COL3_X = 729
COL3_W = W - COL3_X - P

BH = 72   # standard button height
BH_SM = 56


def build_game_column(ch):
    x0, cw = COL1_X + P, COL1_W - P * 2
    y = P

    section_label(ch, x0, y, cw, 20, "GAME CONTROL")
    y += 26

    # Feedback: state
    label(ch, x0, y, 60, 36, "STATE", text_size=11)
    feedback_label(ch, x0 + 68, y, cw - 68, 36, "/feedback/state")
    y += 44

    # Feedback: player
    label(ch, x0, y, 60, 36, "PLAYER", text_size=11)
    feedback_label(ch, x0 + 68, y, cw - 68, 36, "/feedback/player")
    y += 52

    # Row: Correct / Incorrect / Clear
    bw3 = (cw - P * 2) // 3
    button(ch, x0,           y, bw3, BH, "CORRECT",   "/buzzer/correct",   (0.1, 0.55, 0.1))
    button(ch, x0 + bw3 + P, y, bw3, BH, "INCORRECT", "/buzzer/incorrect", (0.65, 0.1, 0.1))
    button(ch, x0 + (bw3 + P)*2, y, bw3, BH, "CLEAR", "/buzzer/clear",     (0.3, 0.3, 0.3))
    y += BH + P

    # Row: Allow Next / Round Start / Game Over
    button(ch, x0,           y, bw3, BH, "ALLOW\nNEXT",   "/buzzer/allow_next",  (0.1, 0.35, 0.65))
    button(ch, x0 + bw3 + P, y, bw3, BH, "ROUND\nSTART", "/buzzer/round_start", (0.42, 0.22, 0.58))
    button(ch, x0 + (bw3 + P)*2, y, bw3, BH, "GAME\nOVER",  "/buzzer/game_over",   (0.6, 0.18, 0.0))
    y += BH + P + 4

    # Timed lockout presets
    section_label(ch, x0, y, cw, 20, "TIMED LOCKOUT")
    y += 26

    bw4 = (cw - P * 3) // 4
    for i, (secs, lbl) in enumerate([(3,"3s"), (5,"5s"), (10,"10s"), (30,"30s")]):
        bx = x0 + i * (bw4 + P)
        button(ch, bx, y, bw4, BH_SM, f"Lock\n{lbl}", "/buzzer/timed_lockout",
               (0.48, 0.35, 0.06), arg_val=str(float(secs)))


def build_show_column(ch):
    x0, cw = COL2_X + P, COL2_W - P * 2
    y = P

    section_label(ch, x0, y, cw, 20, "SHOW")
    y += 26

    label(ch, x0, y, 52, 36, "SCENE", text_size=11)
    feedback_label(ch, x0 + 60, y, cw - 60, 36, "/feedback/scene")
    y += 52

    button(ch, x0, y, cw, BH, "PREVIOUS", "/show/previous", (0.22, 0.22, 0.42))
    y += BH + P
    button(ch, x0, y, cw, BH, "CURRENT",  "/show/current",  (0.18, 0.28, 0.38))
    y += BH + P
    button(ch, x0, y, cw, BH, "ADVANCE",  "/show/advance",  (0.12, 0.42, 0.22))


def build_audio_column(ch):
    x0, cw = COL3_X + P, COL3_W - P
    y = P

    section_label(ch, x0, y, cw, 20, "AUDIO")
    y += 26

    section_label(ch, x0, y, cw, 18, "BACKGROUND")
    y += 24
    bw3 = (cw - P * 2) // 3
    button(ch, x0,               y, bw3, BH_SM, "STOP",   "/audio/background/stop",   (0.5, 0.16, 0.06))
    button(ch, x0 + bw3 + P,     y, bw3, BH_SM, "PAUSE",  "/audio/background/pause",  (0.4, 0.3, 0.05))
    button(ch, x0 + (bw3 + P)*2, y, bw3, BH_SM, "RESUME", "/audio/background/resume", (0.08, 0.38, 0.08))
    y += BH_SM + P
    fader(ch, x0, y, cw, BH_SM, "/audio/background/volume", default=0.7)
    y += BH_SM + P * 2

    section_label(ch, x0, y, cw, 18, "EFFECTS")
    y += 24
    button(ch, x0, y, 90, BH_SM, "STOP", "/audio/effect/stop", (0.5, 0.16, 0.06))
    fader(ch, x0 + 98, y, cw - 98, BH_SM, "/audio/effect/volume",
          default=1, color=(0.42, 0.26, 0.06))


def build() -> ET.Element:
    root = ET.Element("lexml", attrib={"version": "5"})

    grp = _node(root, "GROUP")
    pr = _pr(grp)
    # Exactly match blank file property order and types
    pb(pr, "background", True)
    pc(pr, "color", 0, 0, 0)
    pf(pr, "cornerRadius", 1)
    pframe(pr, 0, 0, W, H)
    pb(pr, "grabFocus", False)
    pb(pr, "interactive", False)
    pb(pr, "locked", False)
    pi(pr, "orientation", 0)
    pb(pr, "outline", True)
    pi(pr, "outlineStyle", 0)
    pi(pr, "pointerPriority", 0)
    pi(pr, "shape", 1)
    pb(pr, "visible", True)
    _touch_value(grp)

    ch = _ch(grp)
    build_game_column(ch)
    build_show_column(ch)
    build_audio_column(ch)

    # Column divider boxes (visual only)
    for div_x in (COL2_X - 5, COL3_X - 5):
        d = _node(ch, "BOX")
        dpr = _pr(d)
        ps(dpr, "name", "divider")
        _base(dpr, div_x, 0, 2, H, (0.18, 0.18, 0.18),
              interactive=False, outline=False)
        _touch_value(d)

    return root


def write(root: ET.Element, path: str):
    xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    with open(path, "wb") as f:
        f.write(zlib.compress(xml_bytes))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "gameshow-control.tosc"
    )
    root = build()
    write(root, out)
    print(f"Written: {out}")
