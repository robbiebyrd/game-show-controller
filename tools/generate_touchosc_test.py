#!/usr/bin/env python3
"""Generate minimal diagnostic .tosc files to isolate TouchOSC crash."""

import uuid, zlib, sys, os
import xml.etree.ElementTree as ET

W, H = 640, 860

def _node(parent, typ):
    return ET.SubElement(parent, "node", attrib={"ID": str(uuid.uuid4()), "type": typ})

def _ch(n):
    e = n.find("children")
    return e if e is not None else ET.SubElement(n, "children")

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
    v = val
    ET.SubElement(p, "value").text = str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

def pc(pr, key, r, g, b, a=1):
    p = ET.SubElement(pr, "property", attrib={"type": "c"})
    ET.SubElement(p, "key").text = key
    v = ET.SubElement(p, "value")
    for k, val in [("r",r),("g",g),("b",b),("a",a)]:
        ET.SubElement(v, k).text = str(int(val)) if isinstance(val, float) and val == int(val) else str(val)

def ps(pr, key, val):
    p = ET.SubElement(pr, "property", attrib={"type": "s"})
    ET.SubElement(p, "key").text = key
    ET.SubElement(p, "value").text = str(val)

def pframe(pr, x, y, w, h):
    p = ET.SubElement(pr, "property", attrib={"type": "r"})
    ET.SubElement(p, "key").text = "frame"
    v = ET.SubElement(p, "value")
    for k, val in [("x",x),("y",y),("w",w),("h",h)]:
        ET.SubElement(v, k).text = str(val)

def touch(n):
    va = ET.SubElement(n, "values")
    ve = ET.SubElement(va, "value")
    ET.SubElement(ve, "key").text = "touch"
    ET.SubElement(ve, "locked").text = "0"
    ET.SubElement(ve, "lockedDefaultCurrent").text = "0"
    ET.SubElement(ve, "default").text = "false"
    ET.SubElement(ve, "defaultPull").text = "0"

def base_props(pr, x, y, w, h, r, g, b, *, interactive=True, outline=True,
               grab_focus=False, shape=0, corner_radius=0):
    pb(pr, "background", True)
    pc(pr, "color", r, g, b)
    pf(pr, "cornerRadius", corner_radius)
    pframe(pr, x, y, w, h)
    pb(pr, "grabFocus", grab_focus)
    pb(pr, "interactive", interactive)
    pb(pr, "locked", False)
    pi(pr, "orientation", 0)
    pb(pr, "outline", outline)
    pi(pr, "outlineStyle", 0)
    pi(pr, "pointerPriority", 0)
    pi(pr, "shape", shape)
    pb(pr, "visible", True)

def root_group():
    root = ET.Element("lexml", attrib={"version": "5"})
    grp = _node(root, "GROUP")
    pr = ET.SubElement(grp, "properties")
    # Exactly match the blank file's property order and types
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
    touch(grp)
    return root, grp


def add_pager(grp):
    pager = _node(_ch(grp), "PAGER")
    pr = ET.SubElement(pager, "properties")
    ps(pr, "name", "Gameshow")
    base_props(pr, 0, 0, W, H, 0, 0, 0, interactive=True, outline=False)
    pb(pr, "tabLabels", True)
    pb(pr, "tabbar", True)
    pb(pr, "tabbarDoubleTap", False)
    pi(pr, "tabbarSize", 40)
    pi(pr, "textSizeOff", 14)
    pi(pr, "textSizeOn", 14)
    touch(pager)
    return pager


def add_page(pager, label):
    page = _node(_ch(pager), "PAGE")
    pr = ET.SubElement(page, "properties")
    ps(pr, "name", label)
    base_props(pr, 0, 0, W, H - 40, 0.05, 0.05, 0.05,
               interactive=True, outline=False)
    ps(pr, "tabLabel", label)
    pc(pr, "tabColorOn", 0.2, 0.5, 0.2)
    pc(pr, "tabColorOff", 0.2, 0.2, 0.2)
    pc(pr, "textColorOn", 1, 1, 1)
    pc(pr, "textColorOff", 0.6, 0.6, 0.6)
    touch(page)
    return page


def add_button_no_osc(page, x, y, w, h, label):
    n = _node(_ch(page), "BUTTON")
    pr = ET.SubElement(n, "properties")
    ps(pr, "name", label)
    ps(pr, "text", label)
    base_props(pr, x, y, w, h, 0.3, 0.3, 0.3, grab_focus=True, corner_radius=1)
    pi(pr, "buttonType", 0)
    pb(pr, "press", True)
    pb(pr, "release", True)
    pc(pr, "textColor", 1, 1, 1)
    pi(pr, "textSize", 16)
    pi(pr, "textAlignH", 2)
    va = ET.SubElement(n, "values")
    for k, d in [("touch","false"), ("x","0")]:
        ve = ET.SubElement(va, "value")
        ET.SubElement(ve, "key").text = k
        ET.SubElement(ve, "locked").text = "0"
        ET.SubElement(ve, "lockedDefaultCurrent").text = "0"
        ET.SubElement(ve, "default").text = d
        ET.SubElement(ve, "defaultPull").text = "0"
    return n


def add_osc_to_button(n, address):
    ms = ET.SubElement(n, "messages")
    osc = ET.SubElement(ms, "osc")
    for k, v in [("enabled","1"),("send","1"),("receive","0"),
                 ("feedback","0"),("connections","00001")]:
        ET.SubElement(osc, k).text = v
    t = ET.SubElement(ET.SubElement(osc, "triggers"), "trigger")
    ET.SubElement(t, "var").text = "touch"
    ET.SubElement(t, "condition").text = "RISE"
    pt = ET.SubElement(ET.SubElement(osc, "path"), "partial")
    ET.SubElement(pt, "type").text = "CONSTANT"
    ET.SubElement(pt, "conversion").text = "STRING"
    ET.SubElement(pt, "value").text = address
    ET.SubElement(pt, "scaleMin").text = "0"
    ET.SubElement(pt, "scaleMax").text = "1"
    arg = ET.SubElement(ET.SubElement(osc, "arguments"), "partial")
    ET.SubElement(arg, "type").text = "CONSTANT"
    ET.SubElement(arg, "conversion").text = "FLOAT"
    ET.SubElement(arg, "value").text = "1"
    ET.SubElement(arg, "scaleMin").text = "0"
    ET.SubElement(arg, "scaleMax").text = "1"


def write(root, path):
    xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    with open(path, "wb") as f:
        f.write(zlib.compress(xml_bytes))
    print(f"Written: {path}")


def build_test1_pager_only(out):
    """Test 1: PAGER with 3 empty pages. No controls."""
    root, grp = root_group()
    pager = add_pager(grp)
    add_page(pager, "Game")
    add_page(pager, "Show")
    add_page(pager, "Audio")
    write(root, out)


def build_test2_buttons_no_osc(out):
    """Test 2: PAGER + pages + buttons, but NO OSC messages."""
    root, grp = root_group()
    pager = add_pager(grp)
    page = add_page(pager, "Game")
    add_button_no_osc(page, 8, 8, 200, 80, "CORRECT")
    add_button_no_osc(page, 216, 8, 200, 80, "INCORRECT")
    add_button_no_osc(page, 424, 8, 208, 80, "CLEAR")
    write(root, out)


def build_test3_buttons_with_osc(out):
    """Test 3: PAGER + pages + buttons WITH OSC messages."""
    root, grp = root_group()
    pager = add_pager(grp)
    page = add_page(pager, "Game")
    n = add_button_no_osc(page, 8, 8, 200, 80, "CORRECT")
    add_osc_to_button(n, "/buzzer/correct")
    n = add_button_no_osc(page, 216, 8, 200, 80, "INCORRECT")
    add_osc_to_button(n, "/buzzer/incorrect")
    write(root, out)


if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..")
    build_test1_pager_only(os.path.join(base, "test1-pager-only.tosc"))
    build_test2_buttons_no_osc(os.path.join(base, "test2-buttons-no-osc.tosc"))
    build_test3_buttons_with_osc(os.path.join(base, "test3-buttons-with-osc.tosc"))
