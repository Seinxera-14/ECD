"""
dxf_exporter.py
================
Exports the electrical distribution diagram parsed_data to a DXF file
using the ezdxf library.

Layout strategy
---------------
Components are drawn as a vertical single-line diagram (SLD):
  Supply → MainCB → RCD/RCBO → Busbar → OutCB(s) → Loads
  Neutral Bar and Earth Bar hang off the busbar as horizontal branches.

Every component is drawn as a labeled rectangle (block).
Wire connections are LWPOLYLINE entities.
Neutral wires use a dashed linetype; earth wires use a dot-dash linetype.
Fault-path arrows (when present) are drawn as red dashed lines.

All coordinates are in millimetres.
"""

from __future__ import annotations
import io
import re
from dataclasses import dataclass, field
from typing import Optional
import ezdxf
from ezdxf import bbox as ezdxf_bbox
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment


@dataclass
class Node:
    id: str
    label: str
    group: Optional[str] = None
    order: int = 0


@dataclass
class Edge:
    src: str
    dst: str
    msg: str = ""


# ── Drawing constants (all in mm) ────────────────────────────────────────────

BOX_W        = 60       # component box width
BOX_H        = 20       # component box height
V_GAP        = 18       # vertical gap between boxes (centre-to-centre addition)
H_STEP       = V_GAP + BOX_H   # full vertical step between box centres
SIDE_OFFSET  = 90       # horizontal offset for NBar / EBar from centre column
FONT_H_MAIN  = 3.5      # main label font height
FONT_H_SMALL = 2.5      # sub-label font height
WIRE_OFFSET  = 2        # small inset so wires meet box edges cleanly

# Colours (AutoCAD colour index)
COL_PHASE   = colors.RED
COL_NEUTRAL = colors.BLUE
COL_EARTH   = colors.GREEN
COL_FAULT   = colors.MAGENTA
COL_BOX     = colors.WHITE
COL_TEXT    = colors.WHITE
COL_TITLE   = colors.CYAN


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(label: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r'<br\s*/?>', ' | ', label)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _cx(x: float) -> float:
    """Return centre-x of a box whose left edge is at x."""
    return x + BOX_W / 2


def _cy(y: float) -> float:
    """Return centre-y of a box whose bottom edge is at y."""
    return y + BOX_H / 2


def _draw_box(msp, x: float, y: float, label: str,
              sublabel: str = "", layer: str = "COMPONENTS") -> None:
    """Draw a closed rectangle with centred text labels."""
    # FIX 1: close=True ensures the rectangle is properly closed.
    # Without this, web viewers like ShareCAD render an open polygon.
    msp.add_lwpolyline(
        [(x, y), (x + BOX_W, y),
         (x + BOX_W, y + BOX_H), (x, y + BOX_H)],
        close=True,
        dxfattribs={"layer": layer, "color": COL_BOX, "lineweight": 25},
    )

    # Main label (centred)
    cx, cy = _cx(x), _cy(y)
    if sublabel:
        # two lines
        msp.add_text(
            label,
            dxfattribs={
                "layer": layer,
                "height": FONT_H_MAIN,
                "color": COL_TEXT,
            },
        ).set_placement((cx, cy + FONT_H_MAIN * 0.6),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(
            sublabel,
            dxfattribs={
                "layer": layer,
                "height": FONT_H_SMALL,
                "color": COL_TEXT,
            },
        ).set_placement((cx, cy - FONT_H_MAIN * 0.6),
                        align=TextEntityAlignment.MIDDLE_CENTER)
    else:
        msp.add_text(
            label,
            dxfattribs={
                "layer": layer,
                "height": FONT_H_MAIN,
                "color": COL_TEXT,
            },
        ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


def _draw_wire(msp, pts: list[tuple[float, float]],
               color: int = COL_PHASE,
               layer: str = "WIRES_PHASE",
               linetype: str = "CONTINUOUS",
               lineweight: int = 25) -> None:
    """Draw a polyline wire between points."""
    msp.add_lwpolyline(
        pts,
        dxfattribs={
            "layer": layer,
            "color": color,
            "linetype": linetype,
            "lineweight": lineweight,
        },
        close=False,
    )


def _draw_label(msp, x: float, y: float, text: str,
                height: float = FONT_H_SMALL,
                color: int = COL_PHASE,
                layer: str = "WIRE_LABELS") -> None:
    msp.add_text(
        text,
        dxfattribs={"layer": layer, "height": height, "color": color},
    ).set_placement((x, y), align=TextEntityAlignment.MIDDLE_LEFT)


def _add_linetypes(doc) -> None:
    ezdxf.setup_linetypes(doc)


def _add_layers(doc) -> None:
    layers_def = {
        "COMPONENTS":    (colors.WHITE,   "Continuous"),
        "WIRES_PHASE":   (COL_PHASE,      "Continuous"),
        "WIRES_NEUTRAL": (COL_NEUTRAL,    "DASHED"),
        "WIRES_EARTH":   (COL_EARTH,      "DASHDOT"),
        "WIRES_FAULT":   (COL_FAULT,      "DASHED"),
        "WIRE_LABELS":   (colors.YELLOW,  "Continuous"),
        "TITLE":         (COL_TITLE,      "Continuous"),
        "NOTES":         (colors.WHITE,   "Continuous"),
    }
    for name, (color, lt) in layers_def.items():
        if name not in doc.layers:
            layer = doc.layers.add(name)   # create first …
            layer.dxf.color    = color     # … then set attrs explicitly
            layer.dxf.linetype = lt



def parse_mermaid_sequence(mermaid: str):
    nodes = {}
    edges = []
    groups = {}
    order = 0
    current_group = None

    for line in mermaid.splitlines():
        line = line.strip()
        if not line:
            continue

        # box "Group Name"
        m = re.match(r'box .*?"(.+?)"', line)
        if m:
            current_group = m.group(1)
            continue

        if line == "end":
            current_group = None
            continue

        # participant A as Label
        m = re.match(r'participant\s+(\w+)\s+as\s+(.+)', line)
        if m:
            pid, label = m.groups()
            nodes[pid] = Node(
                id=pid,
                label=label.strip(),
                group=current_group,
                order=order,
            )
            order += 1
            continue

        # A->>B: message
        m = re.match(r'(\w+)->>\s*(\w+):\s*(.+)', line)
        if m:
            src, dst, msg = m.groups()
            edges.append(Edge(src, dst, msg))
            continue

    return list(nodes.values()), edges

def normalize_for_dxf(nodes, edges):
    # Order nodes top → bottom based on appearance
    nodes = sorted(nodes, key=lambda n: n.order)

    components = []
    for n in nodes:
        cid = n.id.lower()
        components.append((cid, n.label))

    return {
        "components": components,
        "flags": {
            "show_neutral": False,
            "show_earth": False,
            "show_fault_paths": False,
        },
        "voltage": "",
        "language": "en",
        "edges": edges,  # keep for wiring phase
    }


def export_dxf(parsed_data: dict, output_path: str) -> None:
    """
    Convert parsed_data (as produced by MermaidGenerator / OllamaClient)
    into a DXF electrical single-line diagram.

    Parameters
    ----------
    parsed_data : dict
        Keys used:
          "components"  – list of (id, label) tuples
          "flags"       – dict with show_neutral, show_earth, show_rcd,
                          show_fault_paths, show_protection_notes
          "voltage"     – string e.g. "230V AC"
          "language"    – "en" or "ja"
    output_path : str
        Destination file path (should end in .dxf).
    """

    # ── Unpack parsed_data ────────────────────────────────────────────────────
    components: list[tuple[str, str]] = parsed_data.get("components", [])
    flags: dict = parsed_data.get("flags", {})
    voltage: str = parsed_data.get("voltage", "")
    language: str = parsed_data.get("language", "en")

    comp_map = {cid: _clean(lbl) for cid, lbl in components}

    show_neutral  = flags.get("show_neutral",  "nbar" in comp_map)
    show_earth    = flags.get("show_earth",    "ebar" in comp_map)
    show_rcd      = flags.get("show_rcd",      "rcd"  in comp_map or "rcbo" in comp_map)
    show_faults   = flags.get("show_fault_paths", False)
    show_notes    = flags.get("show_protection_notes", False)

    # Outgoing branch breakers
    outcb_ids = sorted(
        [cid for cid in comp_map if cid.startswith("outcb_")],
        key=lambda s: int(s.split("_")[1]) if s.split("_")[1].isdigit() else 0,
    )
    if not outcb_ids and "outcb" in comp_map:
        outcb_ids = ["outcb"]

 
    main_column_ids = []
    for cid in ["supply", "maincb", "rcd", "rcbo", "bus"] + outcb_ids + ["loads"]:
        if cid in comp_map:
            main_column_ids.append(cid)


    ORIGIN_X = 20.0    # left margin
    ORIGIN_Y = 20.0    # bottom margin
    col_x    = ORIGIN_X

    # Calculate Y positions (top of drawing = largest Y)
    n_main = len(main_column_ids)
    total_h = n_main * BOX_H + (n_main - 1) * V_GAP
    start_y = ORIGIN_Y + total_h   # top of first box

    box_positions: dict[str, tuple[float, float]] = {}  # cid → (left_x, bottom_y)

    for i, cid in enumerate(main_column_ids):
        bx = col_x
        by = start_y - i * H_STEP
        box_positions[cid] = (bx, by)

    # Side branches: NBar and EBar are to the right of 'bus'
    side_base_x = col_x + BOX_W + SIDE_OFFSET
    if "bus" in box_positions:
        bus_y = box_positions["bus"][1]
        if "nbar" in comp_map:
            box_positions["nbar"] = (side_base_x, bus_y)
        if "ebar" in comp_map:
            ebar_y = bus_y - H_STEP if "nbar" in comp_map else bus_y
            box_positions["ebar"] = (side_base_x, ebar_y)

    # ── Create DXF document ───────────────────────────────────────────────────
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"]   = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric
    doc.header["$LUNITS"]     = 4  # millimetres
    _add_linetypes(doc)
    _add_layers(doc)
    msp = doc.modelspace()

    # ── Title block ───────────────────────────────────────────────────────────
    title_lines = [
        "ELECTRICAL DISTRIBUTION DIAGRAM",
        f"Voltage: {voltage}" if voltage else "",
        "Generated by Electrical Diagram Tool",
    ]
    ty = start_y + BOX_H + 25
    for line in title_lines:
        if line:
            msp.add_text(
                line,
                dxfattribs={"layer": "TITLE", "height": FONT_H_MAIN + 1,
                            "color": COL_TITLE},
            ).set_placement((col_x, ty), align=TextEntityAlignment.BOTTOM_LEFT)
            ty += (FONT_H_MAIN + 1) * 2.0

    # ── Draw component boxes ──────────────────────────────────────────────────
    for cid, (bx, by) in box_positions.items():
        label = comp_map.get(cid, cid.upper())
        # Split label at ' | ' for two-line display
        parts = label.split(" | ", 1)
        main_lbl = parts[0]
        sub_lbl  = parts[1] if len(parts) > 1 else ""
        _draw_box(msp, bx, by, main_lbl, sub_lbl, layer="COMPONENTS")

    # ── Helper: mid-bottom / mid-top of a box ────────────────────────────────
    def top_mid(cid):
        bx, by = box_positions[cid]
        return (_cx(bx), by + BOX_H)

    def bot_mid(cid):
        bx, by = box_positions[cid]
        return (_cx(bx), by)

    def right_mid(cid):
        bx, by = box_positions[cid]
        return (bx + BOX_W, _cy(by))

    def left_mid(cid):
        bx, by = box_positions[cid]
        return (bx, _cy(by))

    for edge in parsed_data.get("edges", []):
        if edge.src not in box_positions or edge.dst not in box_positions:
            continue
        p1 = bot_mid(edge.src)
        p2 = top_mid(edge.dst)
        _draw_wire(msp, [p1, p2], color=COL_PHASE, layer="WIRES_PHASE")

        # Wire label midpoint
        lx = p1[0] + 3
        ly = (p1[1] + p2[1]) / 2
        if language == "ja":
            wire_lbl = "L (相線)"
        else:
            wire_lbl = "L (Phase)"
        _draw_label(msp, lx, ly, wire_lbl, color=COL_PHASE)

    # ── Neutral wires: bus → nbar ─────────────────────────────────────────────
    if show_neutral and "nbar" in box_positions and "bus" in box_positions:
        bus_rm  = right_mid("bus")
        nbar_lm = left_mid("nbar")
        _draw_wire(
            msp,
            [bus_rm, (nbar_lm[0], bus_rm[1]), nbar_lm],
            color=COL_NEUTRAL,
            layer="WIRES_NEUTRAL",
            linetype="DASHED",
            lineweight=18,
        )
        lx = (bus_rm[0] + nbar_lm[0]) / 2
        ly = bus_rm[1] + 3
        n_lbl = "N (中性線)" if language == "ja" else "N (Neutral)"
        _draw_label(msp, lx, ly, n_lbl, color=COL_NEUTRAL)

    # ── Earth wires: bus → ebar (or nbar → ebar) ─────────────────────────────
    if show_earth and "ebar" in box_positions:
        src = "nbar" if ("nbar" in box_positions) else "bus"
        src_rm  = right_mid(src) if src == "bus" else bot_mid("nbar")
        ebar_lm = left_mid("ebar") if src == "bus" else top_mid("ebar")
        _draw_wire(
            msp,
            [src_rm, ebar_lm],
            color=COL_EARTH,
            layer="WIRES_EARTH",
            linetype="DASHDOT",
            lineweight=13,
        )
        lx = (src_rm[0] + ebar_lm[0]) / 2
        ly = (src_rm[1] + ebar_lm[1]) / 2 + 3
        e_lbl = "E (接地線)" if language == "ja" else "E (Earth/PE)"
        _draw_label(msp, lx, ly, e_lbl, color=COL_EARTH)

    # ── Fault path: ebar → rcd → maincb (dashed magenta) ────────────────────
    if show_faults and "ebar" in box_positions:
        # Draw a fault path loop to the left of the main column
        fault_x = col_x - 30
        pts = []
        if "ebar" in box_positions:
            pts.append(left_mid("ebar"))
        rcd_key = "rcd" if "rcd" in box_positions else ("rcbo" if "rcbo" in box_positions else None)
        if rcd_key:
            ex, ey = pts[0] if pts else (fault_x, 0)
            rx, ry = left_mid(rcd_key)
            pts += [(fault_x, ey), (fault_x, ry), (rx, ry)]
        if "maincb" in box_positions:
            mx, my = left_mid("maincb")
            pts += [(fault_x, my), (mx, my)]
        if len(pts) >= 2:
            _draw_wire(msp, pts, color=COL_FAULT,
                       layer="WIRES_FAULT", linetype="DASHED", lineweight=13)
            # Fault label
            if pts:
                fl_lbl = "故障電流経路 (E)" if language == "ja" else "Fault Current Path (E)"
                _draw_label(msp, fault_x - 5, pts[0][1] + 5,
                            fl_lbl, color=COL_FAULT)

    # ── Protection notes ──────────────────────────────────────────────────────
    if show_notes:
        note_x = col_x + BOX_W + 5
        notes = []
        if "maincb" in box_positions:
            bx, by = box_positions["maincb"]
            notes.append((_cx(bx) + BOX_W / 2 + 5, _cy(by),
                          "Overload / Short-circuit protection"))
        rcd_key = "rcd" if "rcd" in box_positions else ("rcbo" if "rcbo" in box_positions else None)
        if rcd_key:
            bx, by = box_positions[rcd_key]
            notes.append((_cx(bx) + BOX_W / 2 + 5, _cy(by),
                          "RCD: 30mA trip threshold"))
        for nx, ny, note_text in notes:
            _draw_label(msp, note_x, ny, f"* {note_text}",
                        color=colors.YELLOW, layer="NOTES")

    # ── Legend block (bottom-left) ────────────────────────────────────────────
    lx = col_x
    ly = ORIGIN_Y - 15
    legend_items = [
        (COL_PHASE,   "Continuous", "Phase (L)"),
    ]
    if show_neutral:
        legend_items.append((COL_NEUTRAL, "DASHED",    "Neutral (N)"))
    if show_earth:
        legend_items.append((COL_EARTH,   "DASHDOT",   "Earth / PE (E)"))
    if show_faults:
        legend_items.append((COL_FAULT,   "DASHED",    "Fault Current Path"))

    for color, lt, desc in legend_items:
        _draw_wire(msp, [(lx, ly), (lx + 20, ly)],
                   color=color, layer="WIRE_LABELS", linetype=lt, lineweight=18)
        _draw_label(msp, lx + 22, ly, desc, color=color)
        ly -= 8

    # ── Border / drawing frame ────────────────────────────────────────────────
    max_x = side_base_x + BOX_W + 40 if ("nbar" in box_positions or "ebar" in box_positions) else col_x + BOX_W + 40
    min_y = ly - 10
    max_y = ty + 10
    # FIX 4: close=True ensures the border rectangle is properly closed.
    msp.add_lwpolyline(
        [(col_x - 15, min_y), (max_x, min_y),
         (max_x, max_y), (col_x - 15, max_y)],
        close=True,
        dxfattribs={"layer": "TITLE", "color": COL_TITLE, "lineweight": 50},
    )

    try:
        bb = ezdxf_bbox.extents(msp)
        ex0, ey0 = bb.extmin.x, bb.extmin.y
        ex1, ey1 = bb.extmax.x, bb.extmax.y
    except Exception:
        ex0, ey0 = col_x - 15, min_y
        ex1, ey1 = max_x, max_y

    # Zoom the default viewport to extents so viewers open on the geometry
    doc.set_modelspace_vport(
        height=ey1 - ey0,
        center=((ex0 + ex1) / 2, (ey0 + ey1) / 2),
    )

    # ── Save with patched extents ─────────────────────────────────────────────
    stream = io.StringIO()
    doc.write(stream)
    raw = stream.getvalue().replace('\r\n', '\n')  # normalize line endings for regex

    def _patch_point(text: str, varname: str, x: float, y: float,
                     z: float = 0.0) -> str:
        """Replace the x/y/z values of a DXF header point variable."""
        # Pattern matches DXF group codes 10/20/30 that follow the var name tag
        escaped = re.escape(varname)
        pattern = (
            r'(\$' + escaped + r'\n 10\n)[^\n]+'
            r'(\n 20\n)[^\n]+(\n 30\n)[^\n]+'
        )
        return re.sub(
            pattern,
            lambda m: f'{m.group(1)}{x}{m.group(2)}{y}{m.group(3)}{z}',
            text,
        )

    raw = _patch_point(raw, 'EXTMIN', ex0, ey0)
    raw = _patch_point(raw, 'EXTMAX', ex1, ey1)
    # LIMMIN/LIMMAX are 2-D points (no group 30), so patch x/y only
    def _patch_point2d(text: str, varname: str, x: float, y: float) -> str:
        escaped = re.escape(varname)
        pattern = r'(\$' + escaped + r'\n 10\n)[^\n]+(\n 20\n)[^\n]+'
        return re.sub(
            pattern,
            lambda m: f'{m.group(1)}{x}{m.group(2)}{y}',
            text,
        )
    raw = _patch_point2d(raw, 'LIMMIN', ex0, ey0)
    raw = _patch_point2d(raw, 'LIMMAX', ex1, ey1)

    with open(output_path, 'w', encoding='utf-8') as fh:
        fh.write(raw)

def mermaid_to_dxf(mermaid_code: str, output_path: str):
    nodes, edges = parse_mermaid_sequence(mermaid_code)
    parsed_data = normalize_for_dxf(nodes, edges)
    export_dxf(parsed_data, output_path)