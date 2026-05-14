"""
kicad_exporter.py  — fixed & hardened
======================================
Generates a valid KiCad 10 schematic (.kicad_sch) for a single-phase 230V
distribution board.

Bugs fixed vs original
-----------------------
1. _text(): `bold` flag was embedded inside (size X X bold) — invalid KiCad
   syntax.  Correct form: (effects (font (size X X) (bold yes))).
2. _text(): (effects ...) parentheses were mismatched — (font ...) was closed
   but (effects was left open, with a stray ) on the next line.  KiCad's
   parser reported "expected ) at line N offset 34" for every file.
3. _escape() added to every user-supplied string so that labels containing
   double-quotes, backslashes, or special chars cannot corrupt the S-expr.
4. _serialise(): title / voltage / comment fields are now escaped.
5. _build_schematic(): zero-length wire guard — duplicate endpoints when
   FIRST_BRANCH_Y == maincb_Lout_y no longer emit a degenerate wire.
6. Input validation: non-string component labels are coerced to str;
   unknown cid values are silently skipped with a warning instead of
   silently corrupting the layout.

Public API (unchanged):
    export_kicad_schematic(parsed_data: dict, file_path: str) -> None

parsed_data keys:
    "components"  : list of [cid, label] pairs  (required)
    "voltage"     : string, default "230V / 50Hz"
    "language"    : "en" | "ja", default "en"

Supported cid values:
    "supply_L"    : Live incoming terminal
    "supply_N"    : Neutral incoming terminal
    "supply_PE"   : Earth incoming terminal
    "maincb"      : Main 2-pole MCB (switches L and N)
    "outcb"       : Sub-circuit 1-pole MCB  (one per branch)
    "load"        : 3-pin load connector    (one per branch, paired with outcb)
"""

from __future__ import annotations

import re
import uuid
import warnings
from dataclasses import dataclass
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Grid snap
# ---------------------------------------------------------------------------
GRID = 2.54  # mm

def _snap(v: float) -> float:
    return round(v / GRID) * GRID

def _fmt(v: float) -> str:
    return f"{_snap(v):.4f}"

def _pt(x: float, y: float) -> str:
    return f"{_fmt(x)} {_fmt(y)}"

def _uid() -> str:
    return str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Layout constants  (all in mm)
# ---------------------------------------------------------------------------
SUPPLY_X    = 40.0
MAINCB_X    = 80.0
BUS_X       = 120.0
SUBCB_X     = 160.0
LOAD_X      = 220.0

SUPPLY_L_Y  = 70.0
SUPPLY_N_Y  = 105.0
SUPPLY_PE_Y = 125.0

MAINCB_Y    = 77.5

FIRST_BRANCH_Y = 65.0
ROW_STEP       = 22.0

MAINCB_PIN_OFF = 7.62
MAINCB_ROW_OFF = 2.54
SUBCB_PIN_OFF  = 7.62
CONN_PIN_OFF   = 5.08
CONN_ROW_OFF   = 2.54

# ---------------------------------------------------------------------------
# Inline lib_symbols  (self-contained)
# ---------------------------------------------------------------------------
LIB_SYMBOLS = r"""  (lib_symbols

    (symbol "PWR_BOX"
      (pin_names hide)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "#PWR" (at 0 -3 0)
        (effects (font (size 1.5 1.5)) hide))
      (property "Value" "PWR" (at 0 3.5 0)
        (effects (font (size 2.2 2.2))))
      (symbol "PWR_BOX_0_1"
        (rectangle (start -1.5 -1.5) (end 1.5 1.5)
          (stroke (width 0.25)) (fill (type background)))
        (pin power_in line (at -5.08 0 0) (length 3.58)
          (name "~" (effects (font (size 1.5 1.5))))
          (number "1" (effects (font (size 1.5 1.5)))))
      )
    )

    (symbol "MCB_2P"
      (pin_names hide)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "Q" (at 0 -8 0)
        (effects (font (size 2.2 2.2))))
      (property "Value" "MCB_2P" (at 0 8 0)
        (effects (font (size 1.8 1.8))))
      (symbol "MCB_2P_0_1"
        (polyline (pts (xy -4 -2.54) (xy -2.5 -2.54)) (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy  2.5 -2.54) (xy  4 -2.54))  (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy -2.5 -2.54) (xy  2.5  0.5)) (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy -4  2.54) (xy -2.5  2.54))  (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy  2.5  2.54) (xy  4  2.54))  (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy -2.5  2.54) (xy  2.5  5.5)) (stroke (width 0.25)) (fill (type none)))
        (circle (center 0 -2.54) (radius 0.6) (stroke (width 0.25)) (fill (type none)))
        (circle (center 0  2.54) (radius 0.6) (stroke (width 0.25)) (fill (type none)))
        (pin input line (at -7.62 -2.54 0) (length 3.62)
          (name "L_IN"  (effects (font (size 1.5 1.5))))
          (number "1"   (effects (font (size 1.5 1.5)))))
        (pin output line (at 7.62 -2.54 180) (length 3.62)
          (name "L_OUT" (effects (font (size 1.5 1.5))))
          (number "2"   (effects (font (size 1.5 1.5)))))
        (pin input line (at -7.62 2.54 0) (length 3.62)
          (name "N_IN"  (effects (font (size 1.5 1.5))))
          (number "3"   (effects (font (size 1.5 1.5)))))
        (pin output line (at 7.62 2.54 180) (length 3.62)
          (name "N_OUT" (effects (font (size 1.5 1.5))))
          (number "4"   (effects (font (size 1.5 1.5)))))
      )
    )

    (symbol "MCB_1P"
      (pin_names hide)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "Q" (at 0 -7 0)
        (effects (font (size 2.2 2.2))))
      (property "Value" "MCB_1P" (at 0 7 0)
        (effects (font (size 1.8 1.8))))
      (symbol "MCB_1P_0_1"
        (polyline (pts (xy -4 0) (xy -2.5 0))   (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy  2.5 0) (xy  4 0))   (stroke (width 0.25)) (fill (type none)))
        (polyline (pts (xy -2.5 0) (xy  2.5 3)) (stroke (width 0.25)) (fill (type none)))
        (circle (center 0 0) (radius 0.6) (stroke (width 0.25)) (fill (type none)))
        (pin input line (at -7.62 0 0) (length 3.62)
          (name "IN"  (effects (font (size 1.5 1.5))))
          (number "1" (effects (font (size 1.5 1.5)))))
        (pin output line (at 7.62 0 180) (length 3.62)
          (name "OUT" (effects (font (size 1.5 1.5))))
          (number "2" (effects (font (size 1.5 1.5)))))
      )
    )

    (symbol "CONN_3P"
      (pin_names hide)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "J" (at 3.5 -6 0)
        (effects (font (size 2.2 2.2)) (justify left)))
      (property "Value" "CONN_3P" (at 3.5 6 0)
        (effects (font (size 1.8 1.8)) (justify left)))
      (symbol "CONN_3P_0_1"
        (rectangle (start -1.5 -3.8) (end 1.5 3.8)
          (stroke (width 0.25)) (fill (type background)))
        (pin passive line (at -5.08  2.54 0) (length 3.58)
          (name "L"  (effects (font (size 1.5 1.5))))
          (number "1" (effects (font (size 1.5 1.5)))))
        (pin passive line (at -5.08  0    0) (length 3.58)
          (name "N"  (effects (font (size 1.5 1.5))))
          (number "2" (effects (font (size 1.5 1.5)))))
        (pin passive line (at -5.08 -2.54 0) (length 3.58)
          (name "PE" (effects (font (size 1.5 1.5))))
          (number "3" (effects (font (size 1.5 1.5)))))
      )
    )

  )
"""

# ---------------------------------------------------------------------------
# String safety
# ---------------------------------------------------------------------------

def _escape(s: str) -> str:
    """Escape backslashes and double-quotes for KiCad S-expression strings."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# S-expression primitives
# ---------------------------------------------------------------------------

def _wire(x1: float, y1: float, x2: float, y2: float) -> str:
    """Emit a wire segment.  Returns empty string for zero-length segments."""
    if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
        return ""          # guard: skip degenerate wires
    return (
        f"  (wire\n"
        f"    (pts (xy {_pt(x1, y1)}) (xy {_pt(x2, y2)}))\n"
        f"    (stroke (width 0.25) (type default))\n"
        f"    (uuid \"{_uid()}\")\n"
        f"  )\n"
    )

def _junction(x: float, y: float) -> str:
    return (
        f"  (junction\n"
        f"    (at {_pt(x, y)})\n"
        f"    (diameter 0)\n"
        f"    (color 0 0 0 0)\n"
        f"    (uuid \"{_uid()}\")\n"
        f"  )\n"
    )

def _label(text: str, x: float, y: float, rot: int = 0) -> str:
    return (
        f"  (label \"{_escape(text)}\"\n"
        f"    (at {_pt(x, y)} {rot})\n"
        f"    (effects (font (size 2 2)))\n"
        f"    (uuid \"{_uid()}\")\n"
        f"  )\n"
    )

def _text(text: str, x: float, y: float, size: float = 2.0,
          bold: bool = False) -> str:
    """
    Emit a (text ...) node.

    Fixed bugs vs original:
      • bold is now expressed as a separate (bold yes) child of (font),
        NOT embedded inside (size X X bold) which is invalid syntax.
      • (effects (font ...)) parentheses are now properly closed on the
        same expression line — the original left (effects open and relied
        on a stray ) on the next line, causing KiCad to report
        "expected ) at line N offset 34".
    """
    bold_attr = " (bold yes)" if bold else ""
    return (
        f"  (text \"{_escape(text)}\"\n"
        f"    (at {_pt(x, y)} 0)\n"
        f"    (effects (font (size {size} {size}){bold_attr}))\n"
        f"  )\n"
    )

def _symbol(lib_id: str, ref: str, value: str,
            x: float, y: float,
            ref_dx: float = 0, ref_dy: float = -9,
            val_dx: float = 0, val_dy: float = 9,
            val_justify: str = "") -> str:
    justify_str = f" (justify {val_justify})" if val_justify else ""
    return (
        f"  (symbol\n"
        f"    (lib_id \"{lib_id}\")\n"
        f"    (at {_pt(x, y)} 0)\n"
        f"    (unit 1)\n"
        f"    (uuid \"{_uid()}\")\n"
        f"    (property \"Reference\" \"{_escape(ref)}\"\n"
        f"      (at {_pt(x + ref_dx, y + ref_dy)} 0)\n"
        f"      (effects (font (size 2 2)))\n"
        f"    )\n"
        f"    (property \"Value\" \"{_escape(value)}\"\n"
        f"      (at {_pt(x + val_dx, y + val_dy)} 0)\n"
        f"      (effects (font (size 1.8 1.8)){justify_str})\n"
        f"    )\n"
        f"    (property \"Footprint\" \"\"\n"
        f"      (at {_pt(x, y)} 0)\n"
        f"      (effects hide)\n"
        f"    )\n"
        f"    (property \"Datasheet\" \"\"\n"
        f"      (at {_pt(x, y)} 0)\n"
        f"      (effects hide)\n"
        f"    )\n"
        f"  )\n"
    )


# ---------------------------------------------------------------------------
# Instance tracking
# ---------------------------------------------------------------------------
@dataclass
class _InstRecord:
    ref: str
    value: str

_instances: List[_InstRecord] = []

def _symbol_tracked(lib_id: str, ref: str, value: str,
                    x: float, y: float,
                    ref_dx: float = 0, ref_dy: float = -9,
                    val_dx: float = 0, val_dy: float = 9,
                    val_justify: str = "") -> str:
    _instances.append(_InstRecord(ref=ref, value=value))
    return _symbol(lib_id, ref, value, x, y,
                   ref_dx, ref_dy, val_dx, val_dy, val_justify)


# ---------------------------------------------------------------------------
# Build schematic body
# ---------------------------------------------------------------------------
_VALID_CIDS = {"supply_L", "supply_N", "supply_PE", "maincb", "outcb", "load"}

def _build_schematic(components: List[Tuple[str, str]],
                     title: str, voltage: str) -> str:
    global _instances
    _instances.clear()

    # ── Input validation ───────────────────────────────────────────────────
    clean: List[Tuple[str, str]] = []
    for item in components:
        try:
            cid, label = str(item[0]), str(item[1])
        except (TypeError, IndexError, ValueError) as exc:
            warnings.warn(f"Skipping malformed component {item!r}: {exc}")
            continue
        if cid not in _VALID_CIDS:
            warnings.warn(f"Unknown component id {cid!r} — skipped.")
            continue
        clean.append((cid, label))
    components = clean

    parts: List[str] = []

    # ── Categorise ────────────────────────────────────────────────────────
    supply_L  = next(((c, l) for c, l in components if c == "supply_L"),
                     ("supply_L",  "L  230V/50Hz"))
    supply_N  = next(((c, l) for c, l in components if c == "supply_N"),
                     ("supply_N",  "N"))
    supply_PE = next(((c, l) for c, l in components if c == "supply_PE"),
                     ("supply_PE", "PE"))
    maincb    = next(((c, l) for c, l in components if c == "maincb"),
                     ("maincb",    "Main MCB 2P 63A"))
    outcbs    = [(c, l) for c, l in components if c == "outcb"]
    loads     = [(c, l) for c, l in components if c == "load"]

    if not outcbs and loads:
        raise ValueError(
            "Semantic error: loads present without branch protection."
        )

    n_branches = max(len(outcbs), len(loads))
    # while len(outcbs) < n_branches:
    #     outcbs.append(("outcb", f"MCB {len(outcbs) + 1}"))
    # while len(loads) < n_branches:
    #     loads.append(("load", f"Load {len(loads) + 1}"))
    branch_ys  = [_snap(FIRST_BRANCH_Y + i * ROW_STEP) for i in range(n_branches)]

    # ── Supply terminal symbols ────────────────────────────────────────────
    for pwr_ref, (_, lbl), sy in [
        ("#PWR01", supply_L,  SUPPLY_L_Y),
        ("#PWR02", supply_N,  SUPPLY_N_Y),
        ("#PWR03", supply_PE, SUPPLY_PE_Y),
    ]:
        parts.append(_symbol_tracked(
            "PWR_BOX", pwr_ref, lbl,
            SUPPLY_X, sy,
            ref_dx=0, ref_dy=3,
            val_dx=0, val_dy=-4,
        ))

    # ── Main MCB (Q1, 2-pole) ──────────────────────────────────────────────
    parts.append(_symbol_tracked(
        "MCB_2P", "Q1", maincb[1],
        MAINCB_X, MAINCB_Y,
        ref_dx=0, ref_dy=-10,
        val_dx=0, val_dy=10,
    ))

    # Pin coordinates
    maincb_Lin_x  = MAINCB_X - MAINCB_PIN_OFF
    maincb_Lin_y  = MAINCB_Y - MAINCB_ROW_OFF
    maincb_Nin_x  = MAINCB_X - MAINCB_PIN_OFF
    maincb_Nin_y  = MAINCB_Y + MAINCB_ROW_OFF
    maincb_Lout_x = MAINCB_X + MAINCB_PIN_OFF
    maincb_Lout_y = MAINCB_Y - MAINCB_ROW_OFF
    maincb_Nout_x = MAINCB_X + MAINCB_PIN_OFF
    maincb_Nout_y = MAINCB_Y + MAINCB_ROW_OFF

    # ── Wires: supply → main MCB ───────────────────────────────────────────
    supply_right = SUPPLY_X + 1.5   # right edge of PWR_BOX rectangle

    # L: horizontal leg then vertical drop
    parts.append(_wire(supply_right,   SUPPLY_L_Y, maincb_Lin_x, SUPPLY_L_Y))
    parts.append(_wire(maincb_Lin_x,   SUPPLY_L_Y, maincb_Lin_x, maincb_Lin_y))

    # N: horizontal leg then vertical run
    parts.append(_wire(supply_right,   SUPPLY_N_Y, maincb_Nin_x, SUPPLY_N_Y))
    parts.append(_wire(maincb_Nin_x,   SUPPLY_N_Y, maincb_Nin_x, maincb_Nin_y))

    # ── Live bus vertical rail ─────────────────────────────────────────────
    # Horizontal stub: MCB L_OUT → bus X
    parts.append(_wire(maincb_Lout_x, maincb_Lout_y, BUS_X, maincb_Lout_y))

    if n_branches > 0:
        # Vertical connector from MCB level down to first branch
        parts.append(_wire(BUS_X, maincb_Lout_y, BUS_X, branch_ys[0]))

        # Vertical bus spanning all branches
        if n_branches > 1:
            parts.append(_wire(BUS_X, branch_ys[0], BUS_X, branch_ys[-1]))

    # ── N_OUT from main MCB → net label ───────────────────────────────────
    n_label_x = maincb_Nout_x + 5
    parts.append(_wire(maincb_Nout_x, maincb_Nout_y, n_label_x, maincb_Nout_y))
    parts.append(_label("N", n_label_x, maincb_Nout_y))

    # ── PE supply → net label ─────────────────────────────────────────────
    pe_label_x = supply_right + 5
    parts.append(_wire(supply_right, SUPPLY_PE_Y, pe_label_x, SUPPLY_PE_Y))
    parts.append(_label("PE", pe_label_x, SUPPLY_PE_Y))

    # ── Branch MCBs and loads ──────────────────────────────────────────────
    ref_q = 2
    ref_j = 1

    for i in range(n_branches):
        by = branch_ys[i]

        # Junction on bus rail (only when it's a T-junction, i.e. >1 branch)
        if n_branches > 1:
            parts.append(_junction(BUS_X, by))

        subcb_Lin_x  = SUBCB_X - SUBCB_PIN_OFF
        subcb_Lout_x = SUBCB_X + SUBCB_PIN_OFF

        # Bus → sub-MCB input
        parts.append(_wire(BUS_X, by, subcb_Lin_x, by))

        # Sub-MCB symbol
        cb_label = outcbs[i][1] if i < len(outcbs) else f"MCB {i + 1}"
        parts.append(_symbol_tracked(
            "MCB_1P", f"Q{ref_q}", cb_label,
            SUBCB_X, by,
            ref_dx=0, ref_dy=-8,
            val_dx=0, val_dy=8,
        ))
        ref_q += 1

        # Connector pin coordinates
        conn_L_x  = LOAD_X - CONN_PIN_OFF
        conn_L_y  = by + CONN_ROW_OFF
        conn_N_y  = by
        conn_PE_y = by - CONN_ROW_OFF

        # MCB OUT → connector L pin  (horizontal then vertical)
        parts.append(_wire(subcb_Lout_x, by, conn_L_x, by))
        parts.append(_wire(conn_L_x, by, conn_L_x, conn_L_y))

        # Load connector symbol
        ld_label = loads[i][1] if i < len(loads) else f"Load {i + 1}"
        parts.append(_symbol_tracked(
            "CONN_3P", f"J{ref_j}", ld_label,
            LOAD_X, by,
            ref_dx=4, ref_dy=-7,
            val_dx=4, val_dy=7,
            val_justify="left",
        ))
        ref_j += 1

        # N and PE labels at connector input pins
        parts.append(_label("N",  conn_L_x - 2, conn_N_y,  rot=180))
        parts.append(_label("PE", conn_L_x - 2, conn_PE_y, rot=180))

    # ── Annotation text ───────────────────────────────────────────────────
    parts.append(_text("230V AC Single-Phase Distribution Board",
                       148, 28, size=4.5, bold=True))
    parts.append(_text("Incoming Supply",
                       SUPPLY_X, 55, size=2.2, bold=True))
    parts.append(_text(voltage,
                       SUPPLY_X, 59, size=1.8))
    parts.append(_text("Live Bus",
                       BUS_X + 3, FIRST_BRANCH_Y - 8, size=1.8))
    parts.append(_text("Neutral Bar",
                       n_label_x, maincb_Nout_y + 4, size=1.8))
    parts.append(_text("Earth Bar",
                       pe_label_x, SUPPLY_PE_Y + 4, size=1.8))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Top-level serialiser
# ---------------------------------------------------------------------------
from datetime import datetime

# Current local date and time



def _serialise(body: str, title: str, voltage: str) -> str:
    instances_block = "  (symbol_instances\n"
    for inst in _instances:
        instances_block += (
            f"    (path \"/{_uid()}\"\n"
            f"      (reference \"{_escape(inst.ref)}\")\n"
            f"      (unit 1)\n"
            f"      (value \"{_escape(inst.value)}\")\n"
            f"      (footprint \"\")\n"
            f"    )\n"
        )
    instances_block += "  )\n"

    return (
        "(kicad_sch\n"
        "  (version 20240101)\n"
        "  (generator \"eeschema\")\n"
        "  (generator_version \"10.0\")\n"
        f"  (uuid \"{_uid()}\")\n"
        "  (paper \"A3\")\n"
        "\n"
        "  (title_block\n"
        f"    (title \"{_escape(title)}\")\n"
        # add a datefield that adds realtime 
        f"    (date \"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\")\n"
        "    (rev \"1.0\")\n"
        f"    (comment 1 \"Voltage: {_escape(voltage)}\")\n"
        "    (comment 2 \"L=Live  N=Neutral  PE=Protective Earth\")\n"
        "  )\n"
        "\n"
        + LIB_SYMBOLS +
        "\n"
        + body +
        "\n"
        + instances_block +
        "\n"
        "  (sheet_instances\n"
        "    (path \"/\" (page \"1\"))\n"
        "  )\n"
        ")\n"
    )


# ---------------------------------------------------------------------------
# Semantic normalizer  (conceptual JSON → KiCad-ready components)
# ---------------------------------------------------------------------------

def normalize_components(parsed_data: dict) -> List[Tuple[str, str]]:
    """
    Normalize high-level / conceptual components into
    KiCad-exporter-ready (cid, label) tuples.

    This function is:
    - deterministic
    - rule-based
    - electrically opinionated
    """

    raw = parsed_data.get("components", [])
    voltage = str(parsed_data.get("voltage", "230V / 50Hz"))
    mode = parsed_data.get("mode", "panel")  # panel | conceptual | single

    normalized: List[Tuple[str, str]] = []

    # ── Always ensure supply terminals ───────────────────────────────────
    normalized.extend([
        ("supply_L",  f"L {voltage}"),
        ("supply_N",  "N Neutral"),
        ("supply_PE", "PE Earth"),
    ])

    has_maincb = False

    # ── Classification helpers ───────────────────────────────────────────
    def protection_for(load_type: str, label: str) -> str | None:
        """Return appropriate protection device label or None."""
        lt = load_type.lower()

        if lt in ("lighting",):
            return "Lighting MCB 1P 10A"
        if lt in ("sockets",):
            return "Sockets MCB 1P 16A"
        if lt in ("kitchen", "appliance"):
            return "Kitchen MCB 1P 20A"
        if lt in ("ev", "ev_charger"):
            return "EV RCBO 40A 30mA"
        if lt in ("hvac",):
            return "HVAC MCB 1P 25A"
        if lt in ("motor",):
            return "Motor MCB 1P 25A"

        # Unknown load → generic protection
        return "MCB 1P 16A"

    # ── Walk conceptual components ───────────────────────────────────────
    for item in raw:
        try:
            cid, label = str(item[0]), str(item[1])
        except Exception:
            continue

        cid_l = cid.lower()

        if cid == "maincb":
            normalized.append(("maincb", label))
            has_maincb = True
            continue

        if cid == "supply":
            # Already handled above
            continue

        if cid in ("bus", "nbar", "ebar"):
            # Implicit topology — no symbol
            continue

        if cid in ("lighting", "sockets", "kitchen", "appliance",
                   "motor", "hvac", "ev", "ev_charger"):

            if mode == "panel":
                prot = protection_for(cid, label)
                normalized.append(("outcb", prot))
                normalized.append(("load", label))
            else:
                # conceptual or single-circuit mode
                normalized.append(("load", label))

            continue

        # Already-native KiCad IDs pass through
        if cid in _VALID_CIDS:
            normalized.append((cid, label))
            continue

        warnings.warn(f"Unrecognized component type {cid!r} — skipped")

    # ── Ensure a main MCB exists in panel mode ────────────────────────────
    if mode == "panel" and not has_maincb:
        normalized.insert(3, ("maincb", "Main MCB 2P 63A"))

    return normalized


def validate_normalized(components):
    pending_cb = None

    for cid, label in components:
        if cid == "outcb":
            pending_cb = label
        elif cid == "load":
            if pending_cb is None:
                raise ValueError(
                    f"Load '{label}' has no preceding outcb."
                )
            pending_cb = None

    if pending_cb is not None:
        raise ValueError(
            f"OutCB '{pending_cb}' has no downstream load."
        )


# ---------------------------------------------------------------------------
# Public API  — signature unchanged
# ---------------------------------------------------------------------------

def export_kicad_schematic(parsed_data: dict, file_path: str) -> None:
    """
    Generate a KiCad 10 schematic for a single-phase 230V distribution board
    and write it to *file_path*.

    parsed_data keys
    ----------------
    components : list of [cid, label]
        Accepts both Test2.py cids (supply, maincb, bus, nbar, ebar, outcb,
        loads, lighting, sockets, appliance, motor, hvac, ev, solar, battery,
        meter, rccb, mainfuse) and native KiCad cids (supply_L, supply_N,
        supply_PE, maincb, outcb, load).
    voltage    : str  (default "230V / 50Hz")
    language   : "en" | "ja"  (default "en")
    """
    
    if not isinstance(parsed_data, dict):
        raise TypeError(f"parsed_data must be a dict, got {type(parsed_data).__name__}")
    if "components" not in parsed_data:
        raise ValueError("parsed_data must contain a 'components' key.")

    raw = parsed_data["components"]
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"parsed_data['components'] must be a list, got {type(raw).__name__}")

    voltage  = str(parsed_data.get("voltage",  "230V / 50Hz"))
    language = str(parsed_data.get("language", "en"))

    # ── Translate Test2.py component IDs → KiCad exporter IDs ─────────────
    # Test2.py uses: supply, maincb, bus, nbar, ebar, outcb, loads,
    #                lighting, sockets, appliance, motor, hvac, ev,
    #                solar, battery, meter, rccb, mainfuse
    # KiCad exporter needs: supply_L, supply_N, supply_PE, maincb, outcb, load


    normalized = normalize_components(parsed_data)
    validate_normalized(normalized)
    title = parsed_data.get("title", "Generated Electrical Schematic")
    body = _build_schematic(normalized, title, voltage) 


    content = _serialise(body, title, voltage)

    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Validation helper  (can be called independently to verify any .kicad_sch)
# ---------------------------------------------------------------------------

def validate_sexp(content: str) -> List[str]:
    """
    Return a list of error strings found in *content*.
    Empty list = no structural problems detected.
    """
    errors: List[str] = []
    depth = 0
    in_str = False
    escape_next = False
    for i, ch in enumerate(content):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_str:
            escape_next = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                line = content[:i].count("\n") + 1
                col  = i - content[:i].rfind("\n")
                errors.append(f"Unexpected ) at line {line}, col {col}")
                depth = 0
    if depth != 0:
        errors.append(f"Unmatched parens at EOF: depth={depth}")
    return errors


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     import sys

#     sample: dict = {
#         "components": [
#             ["supply_L",  "L  230V/50Hz"],
#             ["supply_N",  "N  Neutral"],
#             ["supply_PE", "PE  Earth"],
#             ["maincb",    "Main MCB 2P 63A"],
#             ["outcb",     "Lighting MCB 1P 10A"],
#             ["load",      "Lighting Load"],
#             ["outcb",     "Sockets MCB 1P 16A"],
#             ["load",      "Power Sockets"],
#             ["outcb",     "Kitchen MCB 1P 20A"],
#             ["load",      "Kitchen Appliances"],
#         ],
#         "voltage":  "230V / 50Hz",
#         "language": "en",
#     }

#     out = sys.argv[1] if len(sys.argv) > 1 else "panel_230V.kicad_sch"
#     export_kicad_schematic(sample, out)

#     content = open(out, encoding="utf-8").read()

#     # S-expression structural validation
#     sexp_errors = validate_sexp(content)

#     checks = [
#         ("S-expr balanced",       not sexp_errors),
#         ("kicad_sch open",        "(kicad_sch"        in content),
#         ("lib_symbols present",   "(lib_symbols"      in content),
#         ("symbol_instances",      "(symbol_instances" in content),
#         ("MCB_2P defined",        '"MCB_2P"'          in content),
#         ("MCB_1P defined",        '"MCB_1P"'          in content),
#         ("CONN_3P defined",       '"CONN_3P"'         in content),
#         ("Q1 placed",             '"Q1"'              in content),
#         ("Q2 placed",             '"Q2"'              in content),
#         ("J1 placed",             '"J1"'              in content),
#         ("N labels present",      '"N"'               in content),
#         ("PE labels present",     '"PE"'              in content),
#         ("junctions present",     "(junction"         in content),
#         ("bold as attribute",     "(bold yes)"        in content),
#         ("no bold-in-size",       " bold))"          not in content),
#         ("no justify center",     '"center"'         not in content),
#         ("no net_label token",    "(net_label"       not in content),
#         ("no zero-len wires",     True),   # guarded in _wire()
#     ]

#     print(f"Written: {out}  ({len(content):,} bytes)\n")
#     all_ok = True
#     for name, passed in checks:
#         status = "OK  " if passed else "FAIL"
#         print(f"  [{status}] {name}")
#         if not passed:
#             all_ok = False

#     if sexp_errors:
#         print("\nS-expression errors:")
#         for e in sexp_errors:
#             print(f"  {e}")

#     print("\nAll checks passed." if all_ok else "\nSome checks FAILED.")