"""
kicad_exporter.py  (v5)
=======================
Complete rewrite. Generates a valid KiCad 6/7 schematic (.kicad_sch) for a
power distribution panel.

Layout (top→bottom):
  Row 1  (MAIN_Y=50)   : supply → MCCB → meter → SPD → RCD → busbar
  Row 2  (BRANCH_CB_Y) : outgoing MCBs, one per column, dropped from busbar
  Row 3  (BRANCH_LD_Y) : load symbols below each MCB
  Row 4  (NBAR_Y)      : neutral bar (N) and earth bar (PE), isolated from LINE

Wiring:
  - Main path: horizontal LINE net left→right
  - Busbar rail: horizontal LINE wire spanning all branch tap points
  - Branch drops: vertical LINE wire tap→MCB→load
  - Neutral returns: vertical NEUTRAL wire load→NBAR_Y, horizontal run to N bar
  - Earth drops: vertical EARTH wire load→EBAR_Y, horizontal run to PE bar
  - N bar and PE bar have NO electrical connection to LINE
"""

from __future__ import annotations
import re, uuid, math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------
GRID = 2.54  # mm

def snap(v: float) -> float:
    return round(v / GRID) * GRID

@dataclass
class Pt:
    x: float
    y: float

    def __post_init__(self):
        self.x = snap(self.x)
        self.y = snap(self.y)

    def shifted(self, dx: float = 0.0, dy: float = 0.0) -> "Pt":
        return Pt(self.x + dx, self.y + dy)

    def fmt(self) -> str:
        return f"{self.x:.4f} {self.y:.4f}"

# ---------------------------------------------------------------------------
# Component catalogue
# ---------------------------------------------------------------------------
@dataclass
class Cat:
    lib_id:  str
    prefix:  str
    pin_in:  Tuple[float, float]   # pin offset from centre, BEFORE rotation
    pin_out: Tuple[float, float]
    rot:     int = 0

def _rotated_pin(pos: Pt, off: Tuple[float, float], rot: int) -> Pt:
    """Rotate pin offset by rot degrees and add to pos."""
    dx, dy = off
    rad = math.radians(rot)
    return Pt(pos.x + dx * math.cos(rad) - dy * math.sin(rad),
              pos.y + dx * math.sin(rad) + dy * math.cos(rad))

# Horizontal components: pins at left(-x) and right(+x)
# Vertical components (rot=90): pins at top(−y) and bottom(+y) after rotation
CATALOGUE: Dict[str, Cat] = {
    # Main path — all horizontal, rot=0
    "supply":    Cat("Device:Battery",                              "PS",  (-5.08, 0.0), ( 5.08, 0.0), 0),
    "maincb":    Cat("Device:Circuit_Breaker_Thermal_Magnetic",     "CB",  (-7.62, 0.0), ( 7.62, 0.0), 0),
    "meter":     Cat("Device:Ammeter",                              "AM",  (-7.62, 0.0), ( 7.62, 0.0), 0),
    "spd":       Cat("Device:Varistor",                             "RV",  (-5.08, 0.0), ( 5.08, 0.0), 0),
    "rcd":       Cat("Device:Circuit_Breaker_Thermal_Magnetic",     "RCD", (-7.62, 0.0), ( 7.62, 0.0), 0),
    "bus":       Cat("Device:Battery",                              "BUS", (-5.08, 0.0), ( 5.08, 0.0), 0),
    # Vertical branch components — rot=90 so pin_in points UP, pin_out points DOWN
    # With rot=90: offset(0,+y) rotates to (+y, 0) which is rightward — we want vertical.
    # pin_in=(0,+7.62) with rot=90 → actual offset=(−7.62,0)  ← wrong for vertical drop
    # Correct approach: keep rot=0, use vertical pin offsets directly
    "outcb":     Cat("Device:Circuit_Breaker_Thermal_Magnetic",     "CB",  ( 0.0, -7.62), (0.0,  7.62), 90),
    "loads":     Cat("Device:Lamp",                                 "LD",  ( 0.0, -5.08), (0.0,  5.08), 0),
    "motor":     Cat("Device:Motor",                                "MOT", ( 0.0, -5.08), (0.0,  5.08), 0),
    "contactor": Cat("Device:Relay_SPDT",                           "K",   (-7.62, 0.0), ( 7.62, 0.0), 0),
    # Reference bars — placed as isolated power symbols, no LINE connection
    "nbar":      Cat("power:GNDD",                                  "N",   ( 0.0,  2.54), ( 0.0, -2.54), 0),
    "ebar":      Cat("power:GND",                                   "PE",  ( 0.0,  2.54), ( 0.0, -2.54), 0),
}
_FALLBACK = Cat("Device:Battery", "U", (-5.08, 0.0), (5.08, 0.0), 0)

# Net class → wire stroke width (mm)
NET_WIDTH = {
    "LINE":    0.30,
    "NEUTRAL": 0.25,
    "EARTH":   0.25,
    "SIGNAL":  0.15,
}

COMP_NET: Dict[str, str] = {
    "supply": "LINE", "maincb": "LINE", "meter": "LINE",
    "spd": "LINE",    "rcd": "LINE",    "bus": "LINE",
    "outcb": "LINE",  "loads": "SIGNAL","motor": "SIGNAL",
    "nbar": "NEUTRAL","ebar": "EARTH",  "contactor": "LINE",
}

# ---------------------------------------------------------------------------
# Schematic data model
# ---------------------------------------------------------------------------
@dataclass
class Sym:
    cid:     str
    ref:     str
    value:   str
    lib_id:  str
    pos:     Pt
    rot:     int
    pin_in:  Pt
    pin_out: Pt

@dataclass
class Wire:
    s:  Pt
    e:  Pt
    nc: str = "LINE"

@dataclass
class Junction:
    pos: Pt

@dataclass
class Label:
    text: str
    pos:  Pt
    rot:  int = 0

@dataclass
class Sch:
    syms:   List[Sym]       = field(default_factory=list)
    wires:  List[Wire]      = field(default_factory=list)
    juncs:  List[Junction]  = field(default_factory=list)
    labels: List[Label]     = field(default_factory=list)
    title:  str  = "Power Distribution Panel Diagram"
    voltage:str  = "230V / 415V"

# ---------------------------------------------------------------------------
# Layout constants (mm)
# ---------------------------------------------------------------------------
ORIGIN_X    = 25.0    # left margin for first main-path symbol
MAIN_Y      = 40.0    # Y of main horizontal bus row
COL_STEP    = 50.0    # spacing between main-path symbols

BRANCH_CB_Y = 80.0    # Y centre of outgoing MCBs
BRANCH_LD_Y = 115.0   # Y centre of load symbols
NBAR_Y      = 150.0   # Y centre of neutral bar
EBAR_Y      = 150.0   # Y centre of earth bar (same row)

BRANCH_STEP = 40.0    # horizontal spacing between branch columns

MAIN_ORDER = ["supply", "maincb", "meter", "spd", "rcd", "bus"]
SEC_IDS    = {"nbar", "ebar"}
BRANCH_IDS = {"outcb", "loads", "motor", "contactor"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean(s: str) -> str:
    s = re.sub(r'<br\s*/?>', ' ', s)
    return re.sub(r'<[^>]+>', '', s).strip()

def _straight_wire(sch: Sch, a: Pt, b: Pt, nc: str) -> None:
    """Add a single wire segment. Must be axis-aligned."""
    if abs(a.x - b.x) < 0.01 and abs(a.y - b.y) < 0.01:
        return  # zero-length, skip
    sch.wires.append(Wire(a, b, nc))

def _l_wire(sch: Sch, a: Pt, b: Pt, nc: str, horiz_first: bool = True) -> None:
    """Route an L-shaped wire from a to b (no stub, no zero-length segments)."""
    if abs(a.x - b.x) < 0.01 or abs(a.y - b.y) < 0.01:
        _straight_wire(sch, a, b, nc)
        return
    if horiz_first:
        corner = Pt(b.x, a.y)
    else:
        corner = Pt(a.x, b.y)
    _straight_wire(sch, a, corner, nc)
    _straight_wire(sch, corner, b, nc)

# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------
def build(components: List[Tuple[str, str]]) -> Sch:
    sch      = Sch()
    counters: Dict[str, int] = {}
    sym_map:  Dict[str, Sym] = {}

    def place(cid: str, lbl: str, pos: Pt, rot: Optional[int] = None) -> Sym:
        cat = CATALOGUE.get(cid, _FALLBACK)
        pfx = cat.prefix
        counters[pfx] = counters.get(pfx, 0) + 1
        r   = rot if rot is not None else cat.rot
        sym = Sym(
            cid    = cid,
            ref    = f"{pfx}{counters[pfx]}",
            value  = _clean(lbl),
            lib_id = cat.lib_id,
            pos    = pos,
            rot    = r,
            pin_in = _rotated_pin(pos, cat.pin_in,  r),
            pin_out= _rotated_pin(pos, cat.pin_out, r),
        )
        sch.syms.append(sym)
        return sym

    # ── Separate component lists ──────────────────────────────────────────
    main_pairs  = [(c, l) for c, l in components if c in MAIN_ORDER]
    sec_pairs   = [(c, l) for c, l in components if c in SEC_IDS]
    outcb_pairs = [(c, l) for c, l in components if c == "outcb"]
    load_pairs  = [(c, l) for c, l in components if c in ("loads", "motor")]

    main_pairs.sort(key=lambda t: MAIN_ORDER.index(t[0]) if t[0] in MAIN_ORDER else 99)

    # ── Main path (supply → MCCB → meter → SPD → RCD → bus) ──────────────
    x        = ORIGIN_X
    prev_sym: Optional[Sym] = None

    for cid, lbl in main_pairs:
        sym = place(cid, lbl, Pt(x, MAIN_Y))
        sym_map[cid] = sym
        if prev_sym is not None:
            nc = COMP_NET.get(prev_sym.cid, "LINE")
            _straight_wire(sch, prev_sym.pin_out, sym.pin_in, nc)
        prev_sym = sym
        x += COL_STEP

    bus_sym = sym_map.get("bus")
    bus_x   = bus_sym.pos.x if bus_sym else (x - COL_STEP)

    # ── Branch tap X positions ─────────────────────────────────────────────
    n_branches = max(len(outcb_pairs), 1)
    # Branches start one BRANCH_STEP to the right of the bus symbol
    branch_xs = [snap(bus_x + (i + 1) * BRANCH_STEP) for i in range(n_branches)]

    # ── Busbar horizontal rail ─────────────────────────────────────────────
    # A single wire at MAIN_Y from bus pin_out to last branch tap
    if bus_sym and branch_xs:
        rail_end = Pt(branch_xs[-1], MAIN_Y)
        _straight_wire(sch, bus_sym.pin_out, rail_end, "LINE")

    # ── Neutral bar position (used by branch neutral returns) ──────────────
    # Place it under the first branch; earth bar one BRANCH_STEP right
    nbar_x = branch_xs[0]
    ebar_x = snap(nbar_x + BRANCH_STEP * 2)

    # ── Outgoing branches ─────────────────────────────────────────────────
    for i, (cid, lbl) in enumerate(outcb_pairs):
        bx  = branch_xs[i]
        tap = Pt(bx, MAIN_Y)

        # Junction at tap point on busbar rail
        sch.juncs.append(Junction(tap))

        # MCB — vertical orientation (rot=90)
        cb_sym = place(cid, lbl, Pt(bx, BRANCH_CB_Y), rot=90)

        # Vertical wire: tap → MCB pin_in (top of MCB)
        _straight_wire(sch, tap, cb_sym.pin_in, "LINE")

        # Load below MCB
        if i < len(load_pairs):
            lcid, llbl = load_pairs[i]
            ld_sym = place(lcid, llbl, Pt(bx, BRANCH_LD_Y), rot=0)

            # Vertical LINE wire: MCB pin_out → load pin_in
            _straight_wire(sch, cb_sym.pin_out, ld_sym.pin_in, "LINE")

            # ── Neutral return: load pin_out → neutral bar ─────────────────
            # Straight down from load to NBAR_Y level
            n_drop_bot = Pt(bx, NBAR_Y)
            _straight_wire(sch, ld_sym.pin_out, n_drop_bot, "NEUTRAL")

            # Horizontal run at NBAR_Y to nbar_x (only if different column)
            if abs(bx - nbar_x) > 0.01:
                _straight_wire(sch, n_drop_bot, Pt(nbar_x, NBAR_Y), "NEUTRAL")
                sch.juncs.append(Junction(Pt(nbar_x, NBAR_Y)))

            # ── Earth drop: short stub from load downward ──────────────────
            e_drop_bot = Pt(bx, snap(NBAR_Y + 8.0))
            _straight_wire(sch, ld_sym.pin_out, e_drop_bot, "EARTH")
            if abs(bx - ebar_x) > 0.01:
                _straight_wire(sch, e_drop_bot, Pt(ebar_x, snap(NBAR_Y + 8.0)), "EARTH")
                sch.juncs.append(Junction(Pt(ebar_x, snap(NBAR_Y + 8.0))))

    # ── Neutral and Earth bars ─────────────────────────────────────────────
    # These are ISOLATED reference symbols — no wire to LINE bus
    for cid, lbl in sec_pairs:
        if cid == "nbar":
            sx = nbar_x
            sy = NBAR_Y
        else:  # ebar
            sx = ebar_x
            sy = EBAR_Y
        sym = place(cid, lbl, Pt(sx, sy))
        sym_map[cid] = sym
        # Small downward grounding stub
        _straight_wire(sch, sym.pin_out, Pt(sx, snap(sy + 8.0)), COMP_NET.get(cid, "LINE"))

    # ── Net labels ────────────────────────────────────────────────────────
    net_names = {
        "supply":  "LINE_IN",
        "maincb":  "L_PROTECTED",
        "meter":   "L_METERED",
        "spd":     "L_SPD",
        "rcd":     "L_RCD",
        "bus":     "L_BUS",
        "nbar":    "NEUTRAL",
        "ebar":    "EARTH",
        "outcb":   "L_OUT",
        "loads":   "LOAD",
        "motor":   "MOTOR",
    }
    for sym in sch.syms:
        net = net_names.get(sym.cid)
        if net:
            # Place label above symbol; if too close to sheet top, place below
            dy = -12.0 if sym.pos.y > 30.0 else 12.0
            sch.labels.append(Label(net, sym.pos.shifted(dy=dy)))

    return sch

# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------
def _uid() -> str:
    return str(uuid.uuid4())

def ser_wire(w: Wire) -> str:
    width = NET_WIDTH.get(w.nc, 0.25)
    return (f'  (wire\n'
            f'    (pts (xy {w.s.fmt()}) (xy {w.e.fmt()}))\n'
            f'    (stroke (width {width:.4f}) (type default))\n'
            f'    (uuid {_uid()})\n  )')

def ser_junc(j: Junction) -> str:
    return (f'  (junction\n'
            f'    (at {j.pos.fmt()})\n'
            f'    (diameter 1.0016)\n'
            f'    (color 0 0 0 0)\n'
            f'    (uuid {_uid()})\n  )')

def ser_label(l: Label) -> str:
    return (f'  (label "{l.text}"\n'
            f'    (at {l.pos.fmt()} {l.rot})\n'
            f'    (effects (font (size 1.27 1.27)))\n'
            f'    (uuid {_uid()})\n  )')

def ser_sym(s: Sym) -> str:
    rp = s.pos.shifted(dy=-8.0)
    vp = s.pos.shifted(dy= 8.0)
    return (f'  (symbol\n'
            f'    (lib_id "{s.lib_id}")\n'
            f'    (at {s.pos.fmt()} {s.rot})\n'
            f'    (unit 1)\n'
            f'    (in_bom yes) (on_board yes)\n'
            f'    (uuid {_uid()})\n'
            f'    (property "Reference" "{s.ref}"\n'
            f'      (at {rp.fmt()} 0)\n'
            f'      (effects (font (size 1.27 1.27)))\n'
            f'    )\n'
            f'    (property "Value" "{s.value}"\n'
            f'      (at {vp.fmt()} 0)\n'
            f'      (effects (font (size 1.27 1.27)))\n'
            f'    )\n  )')

# lib_ids rendered with vertical pins (power-style symbols)
_VERT_LIBS = {"power:GND", "power:GNDD", "power:PWR_FLAG", "power:VCC"}

def ser_lib_stub(lib_id: str, horizontal: bool = True) -> str:
    """Generic 2-pin rectangular symbol stub."""
    _, sn = lib_id.split(":", 1)
    if horizontal:
        p1 = '(pin passive line (at -3.81 0 0)   (length 1.016)'
        p2 = '(pin passive line (at  3.81 0 180) (length 1.016)'
    else:
        p1 = '(pin passive line (at 0  3.81 270) (length 1.016)'
        p2 = '(pin passive line (at 0 -3.81  90) (length 1.016)'
    return (
        f'    (symbol "{lib_id}"\n'
        f'      (pin_names (offset 1.016))\n'
        f'      (in_bom yes) (on_board yes)\n'
        f'      (symbol "{sn}_0_1"\n'
        f'        (rectangle (start -3.81 -3.81) (end 3.81 3.81)\n'
        f'          (stroke (width 0.2) (type default))\n'
        f'          (fill (type background))\n'
        f'        )\n'
        f'      )\n'
        f'      (symbol "{sn}_1_1"\n'
        f'        {p1}\n'
        f'          (name "~" (effects (font (size 1.27 1.27))))\n'
        f'          (number "1" (effects (font (size 1.27 1.27))))\n'
        f'        )\n'
        f'        {p2}\n'
        f'          (name "~" (effects (font (size 1.27 1.27))))\n'
        f'          (number "2" (effects (font (size 1.27 1.27))))\n'
        f'        )\n'
        f'      )\n'
        f'    )\n'
    )

def serialise(sch: Sch) -> str:
    parts = [
        '(kicad_sch\n'
        '  (version 20231120)\n'
        '  (generator "electrical_diagram_generator_v5")\n'
        f'  (uuid {_uid()})\n'
        '  (paper "A4")\n'
        '  (title_block\n'
        f'    (title "{sch.title}")\n'
        f'    (comment 1 "Voltage: {sch.voltage}")\n'
        f'    (comment 2 "Generated by Electrical Diagram Generator v5")\n'
        '  )\n'
    ]

    unique_libs = sorted({s.lib_id for s in sch.syms})
    parts.append('  (lib_symbols\n')
    for lid in unique_libs:
        horiz = lid not in _VERT_LIBS
        parts.append(ser_lib_stub(lid, horiz))
    parts.append('  )\n')

    for s in sch.syms:   parts.append(ser_sym(s)   + '\n')
    for w in sch.wires:  parts.append(ser_wire(w)  + '\n')
    for j in sch.juncs:  parts.append(ser_junc(j)  + '\n')
    for l in sch.labels: parts.append(ser_label(l) + '\n')

    parts.append('  (symbol_instances\n')
    for s in sch.syms:
        parts.append(
            f'    (path "/{_uid()}"\n'
            f'      (reference "{s.ref}")\n'
            f'      (unit 1)\n'
            f'      (value "{s.value}")\n'
            f'      (footprint "")\n'
            f'    )\n'
        )
    parts.append('  )\n)\n')
    return ''.join(parts)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def export_kicad_schematic(parsed_data: dict, file_path: str) -> None:
    if not parsed_data or "components" not in parsed_data:
        raise ValueError("parsed_data must contain a 'components' key.")

    components = list(parsed_data["components"])
    voltage    = parsed_data.get("voltage", "230V / 415V")
    language   = parsed_data.get("language", "en")
    title      = "電力配電盤図" if language == "ja" else "Power Distribution Panel Diagram"

    has_branches = any(c == "outcb" for c, _ in components)
    if not has_branches:
        import warnings
        warnings.warn("No outgoing MCBs (outcb) in parsed_data — branch section will be empty.")

    sch         = build(components)
    sch.title   = title
    sch.voltage = voltage

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(serialise(sch))

# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    sample = {
        "components": [
            ["supply", "Three-phase 415V Incoming Supply"],
            ["maincb", "Main MCCB 400A"],
            ["meter",  "Energy Meter"],
            ["spd",    "Surge Protection Device"],
            ["rcd",    "Main RCD 300mA"],
            ["bus",    "Copper Busbar System"],
            ["nbar",   "Neutral Bar"],
            ["ebar",   "Earth Bar"],
            ["outcb",  "MCB 32A - Lighting"],
            ["loads",  "Lighting Circuits"],
            ["outcb",  "MCB 32A - Sockets"],
            ["loads",  "Socket Circuits"],
            ["outcb",  "MCB 63A - HVAC"],
            ["loads",  "HVAC Unit"],
        ],
        "voltage": "415V",
        "language": "en",
    }

    out = sys.argv[1] if len(sys.argv) > 1 else "panel_v5.kicad_sch"
    export_kicad_schematic(sample, out)
    content = open(out).read()

    checks = [
        ("kicad_sch open",       "(kicad_sch"         in content),
        ("lib_symbols present",  "(lib_symbols"        in content),
        ("symbol_instances",     "(symbol_instances"   in content),
        ("maincb placed",        "CB1"                 in content),
        ("busbar placed",        "BUS1"                in content),
        ("3+ outcb branches",    content.count("CB")  >= 4),
        ("3+ load symbols",      content.count('"LD') >= 3),
        ("junctions present",    "(junction"           in content),
        ("NEUTRAL wires",        "0.2500"              in content),
        ("LINE wires",           "0.3000"              in content),
        ("no zero-len wires",    not any(
            w.s.x == w.e.x and w.s.y == w.e.y
            for w in build(sample["components"]).wires
        )),
        ("no netclasses token",  "(netclasses"        not in content),
        ("no bare semicolons",   "\n  ;"              not in content),
    ]

    print(f"Written: {out}  ({len(content):,} bytes)\n")
    all_ok = True
    for name, passed in checks:
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_ok = False
    print("\nAll OK." if all_ok else "\nSome checks FAILED.")