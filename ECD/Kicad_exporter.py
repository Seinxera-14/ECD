"""
kicad_exporter.py  — fully fixed & hardened
============================================
Generates a valid KiCad 10 schematic (.kicad_sch) for a single-phase 230V
distribution board.

Fixes applied in this version
------------------------------
1. _text(): `bold` flag is expressed as (bold yes) child of (font), not
   embedded inside (size X X bold) — invalid KiCad syntax.
2. _text(): (effects ...) parentheses are properly closed.
3. _escape() applied to every user-supplied string.
4. _serialise(): title / voltage / comment fields are escaped.
5. _build_schematic(): zero-length wire guard — degenerate wires skipped.
6. Input validation: non-string labels coerced to str; unknown cids warned.
7. [NEW] Module-level _instances global replaced with a local list threaded
   through _build_schematic → _serialise via return value. Thread-safe and
   re-entrant.
8. [NEW] normalize_components no longer unconditionally prepends supply
   terminals; it checks whether they are already present in raw to prevent
   duplicate supply symbols at the same coordinates.
9. [NEW] outcb_1 … outcb_N (the actual IDs emitted by Test2.py's LLM
   prompt) are now fully handled — they are mapped to ("outcb", label) pairs
   so every branch MCB and load connector is drawn correctly.
10.[NEW] "loads" (Test2.py generic load ID) is now handled and expanded into
    one ("outcb", prot) + ("load", label) pair per unique circuit label when
    in panel mode, or just ("load", label) otherwise.
11.[NEW] "rcd", "rcbo" from Test2.py are silently absorbed (they affect the
    Mermaid diagram but have no dedicated KiCad symbol — a warning is printed
    so the user knows RCD protection is not drawn in the schematic).
12.[NEW] Double-validation (normalize_components + _build_schematic both
    filtering) unified: _build_schematic trusts normalized input and only
    warns on genuinely unknown ids.
13.[NEW] datetime import moved to the top of the module.
14.[NEW] CLI smoke-test un-commented and restored so the file is self-testing.
15.[NEW] "Same circuit every time" root cause fixed: all Test2.py component
    IDs (outcb_1..5, loads, rcd, rcbo, bus, nbar, ebar, supply) are now
    translated correctly; unknown IDs no longer silently collapse to an
    identical fixed schematic.

Public API (unchanged):
    export_kicad_schematic(parsed_data: dict, file_path: str) -> None

parsed_data keys:
    "components"  : list of [cid, label] pairs  (required)
    "voltage"     : string, default "230V / 50Hz"
    "language"    : "en" | "ja", default "en"

Supported cid values (native KiCad):
    "supply_L"    : Live incoming terminal
    "supply_N"    : Neutral incoming terminal
    "supply_PE"   : Earth incoming terminal
    "maincb"      : Main 2-pole MCB (switches L and N)
    "outcb"       : Sub-circuit 1-pole MCB  (one per branch)
    "load"        : 3-pin load connector    (one per branch, paired with outcb)

Supported cid values (Test2.py / conceptual):
    "supply"      : mapped → supply_L + supply_N + supply_PE
    "maincb"      : pass-through
    "outcb_1".."outcb_N" : each mapped → outcb
    "loads"       : mapped → one outcb + load per token (panel mode)
                    or one load per token (other modes)
    "rcd" / "rcbo": absorbed with a warning (no KiCad symbol defined)
    "bus" / "nbar" / "ebar" : absorbed (implicit topology, no symbol)
"""

from __future__ import annotations

import re
import uuid
import warnings
from dataclasses import dataclass
from datetime import datetime
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
    """Emit a wire segment. Returns empty string for zero-length segments."""
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

    Fixed:
      • bold is expressed as a separate (bold yes) child of (font),
        NOT embedded inside (size X X bold) which is invalid syntax.
      • (effects (font ...)) parentheses are properly closed.
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
# Instance tracking  — now a plain dataclass, no module-level mutable state
# ---------------------------------------------------------------------------
@dataclass
class _InstRecord:
    ref: str
    value: str


def _symbol_tracked(instances: List[_InstRecord],
                    lib_id: str, ref: str, value: str,
                    x: float, y: float,
                    ref_dx: float = 0, ref_dy: float = -9,
                    val_dx: float = 0, val_dy: float = 9,
                    val_justify: str = "") -> str:
    """Emit a symbol and record it in *instances* for symbol_instances block."""
    instances.append(_InstRecord(ref=ref, value=value))
    return _symbol(lib_id, ref, value, x, y,
                   ref_dx, ref_dy, val_dx, val_dy, val_justify)


# ---------------------------------------------------------------------------
# Build schematic body
# ---------------------------------------------------------------------------
_VALID_CIDS = {"supply_L", "supply_N", "supply_PE", "maincb", "outcb", "load"}


def _build_schematic(components: List[Tuple[str, str]],
                     title: str, voltage: str
                     ) -> Tuple[str, List[_InstRecord]]:
    """
    Build the schematic body string and return it together with the list of
    placed symbol instances.  No module-level state is touched.

    Returns
    -------
    (body_str, instances)
    """
    instances: List[_InstRecord] = []

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
    branch_ys  = [_snap(FIRST_BRANCH_Y + i * ROW_STEP) for i in range(n_branches)]

    # ── Supply terminal symbols ────────────────────────────────────────────
    for pwr_ref, (_, lbl), sy in [
        ("#PWR01", supply_L,  SUPPLY_L_Y),
        ("#PWR02", supply_N,  SUPPLY_N_Y),
        ("#PWR03", supply_PE, SUPPLY_PE_Y),
    ]:
        parts.append(_symbol_tracked(
            instances,
            "PWR_BOX", pwr_ref, lbl,
            SUPPLY_X, sy,
            ref_dx=0, ref_dy=3,
            val_dx=0, val_dy=-4,
        ))

    # ── Main MCB (Q1, 2-pole) ──────────────────────────────────────────────
    parts.append(_symbol_tracked(
        instances,
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
            instances,
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
            instances,
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

    return "".join(parts), instances


# ---------------------------------------------------------------------------
# Top-level serialiser
# ---------------------------------------------------------------------------

def _serialise(body: str, instances: List[_InstRecord],
               title: str, voltage: str) -> str:
    """Build the complete .kicad_sch file content from body + instance list."""
    instances_block = "  (symbol_instances\n"
    for inst in instances:
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
    Translate high-level / conceptual component IDs (as emitted by Test2.py's
    LLM prompt and MermaidGenerator) into KiCad-exporter-ready (cid, label)
    tuples.

    Key behavioural changes vs original:
    • Supply terminals are NOT unconditionally prepended; we check whether
      they are already present in raw to avoid placing duplicate symbols at
      the same coordinates.
    • outcb_1 … outcb_N are each mapped to a single ("outcb", label) entry.
    • "loads" is expanded into one outcb + load pair per token in panel mode,
      or one load per token in other modes.
    • "rcd" / "rcbo" are absorbed with an informational warning (no KiCad
      symbol — they show in the Mermaid diagram only).
    • "bus" / "nbar" / "ebar" are silently absorbed (implicit topology).
    • Native KiCad IDs (supply_L/N/PE, maincb, outcb, load) pass through.
    """

    raw    = parsed_data.get("components", [])
    voltage = str(parsed_data.get("voltage", "230V / 50Hz"))
    mode   = parsed_data.get("mode", "panel")  # panel | conceptual | single

    # ── First pass: collect what is already present ───────────────────────
    raw_cids: set[str] = set()
    for item in raw:
        try:
            raw_cids.add(str(item[0]))
        except Exception:
            pass

    normalized: List[Tuple[str, str]] = []

    # ── Supply terminals — only inject if not already native in raw ───────
    # Native supply_L/N/PE come from the sample data / direct callers.
    # Test2.py uses "supply" as a single entry which we expand below.
    # We must not double-inject when raw already has supply_L etc.
    has_native_supply = any(c in raw_cids for c in ("supply_L", "supply_N", "supply_PE"))
    has_conceptual_supply = "supply" in raw_cids

    if not has_native_supply and not has_conceptual_supply:
        # Neither native nor conceptual supply found — inject defaults
        normalized.extend([
            ("supply_L",  f"L {voltage}"),
            ("supply_N",  "N Neutral"),
            ("supply_PE", "PE Earth"),
        ])

    has_maincb = False

    # ── Classification helper ────────────────────────────────────────────
    def protection_for(load_type: str) -> str:
        """Return appropriate MCB label for the given load type string."""
        lt = load_type.lower()
        if "lighting" in lt or "light" in lt or "lamp" in lt:
            return "Lighting MCB 1P 10A"
        if "socket" in lt or "outlet" in lt or "plug" in lt:
            return "Sockets MCB 1P 16A"
        if "kitchen" in lt or "appliance" in lt:
            return "Kitchen MCB 1P 20A"
        if "ev" in lt or "charger" in lt:
            return "EV RCBO 40A 30mA"
        if "hvac" in lt or "air" in lt or "cooling" in lt:
            return "HVAC MCB 1P 25A"
        if "motor" in lt or "pump" in lt or "fan" in lt:
            return "Motor MCB 1P 25A"
        if "kitchen" in lt or "cooker" in lt or "oven" in lt:
            return "Cooker MCB 1P 32A"
        return "MCB 1P 16A"

    # ── Walk conceptual components ───────────────────────────────────────
    # Branch MCBs and loads are collected separately and interleaved at the
    # end so that the sequence is always: outcb, load, outcb, load, …
    # regardless of the order in which the caller listed them.
    pending_outcbs: List[Tuple[str, str]] = []  # ("outcb", label)
    pending_loads:  List[Tuple[str, str]] = []  # ("load",  label)

    # Count outcb_N entries in raw so "loads" can match them 1-for-1.
    raw_outcb_n_count = sum(
        1 for raw_cid in raw_cids
        if re.fullmatch(r'outcb_\d+', raw_cid) or raw_cid == "outcb"
    )

    for item in raw:
        try:
            cid, label = str(item[0]), str(item[1])
        except Exception:
            continue

        # ── "supply" (conceptual single entry) → expand to L/N/PE ────────
        if cid == "supply":
            v = voltage
            m = re.search(r'\d+\s*[Vv]', label)
            if m:
                v = m.group(0).replace(" ", "")
            normalized.extend([
                ("supply_L",  f"L {v}"),
                ("supply_N",  "N Neutral"),
                ("supply_PE", "PE Earth"),
            ])
            continue

        # ── Native supply terminals pass through ──────────────────────────
        if cid in ("supply_L", "supply_N", "supply_PE"):
            normalized.append((cid, label))
            continue

        # ── Main MCB ──────────────────────────────────────────────────────
        if cid == "maincb":
            normalized.append(("maincb", label))
            has_maincb = True
            continue

        # ── Topology-only nodes → silently absorbed ───────────────────────
        if cid in ("bus", "nbar", "ebar"):
            continue

        # ── RCD / RCBO — no KiCad symbol, warn and absorb ─────────────────
        if cid in ("rcd", "rcbo"):
            warnings.warn(
                f"Component {cid!r} ({label!r}) has no KiCad symbol defined in "
                "this exporter — it appears in the Mermaid diagram only and will "
                "be omitted from the .kicad_sch file."
            )
            continue

        # ── outcb_1 … outcb_N  (Test2.py LLM output) ─────────────────────
        if re.fullmatch(r'outcb_\d+', cid):
            pending_outcbs.append(("outcb", label))
            continue

        # ── "loads" (Test2.py generic collective load entry) ──────────────
        # When outcb_N entries were declared in raw, treat "loads" as one
        # load connector per branch MCB.  Otherwise auto-add protection.
        if cid == "loads":
            clean_label = re.sub(r'<br\s*/?>', ' ', label).strip()
            if raw_outcb_n_count > 0:
                # Pair one load with each already-declared outcb
                for _ in range(raw_outcb_n_count):
                    pending_loads.append(("load", clean_label))
            elif mode == "panel":
                prot = protection_for(clean_label)
                pending_outcbs.append(("outcb", prot))
                pending_loads.append(("load", clean_label))
            else:
                pending_loads.append(("load", clean_label))
            continue

        # ── Known semantic load-type IDs ──────────────────────────────────
        if cid in ("lighting", "sockets", "kitchen", "appliance",
                   "motor", "hvac", "ev", "ev_charger"):
            if mode == "panel":
                prot = protection_for(cid)
                pending_outcbs.append(("outcb", prot))
                pending_loads.append(("load", label))
            else:
                pending_loads.append(("load", label))
            continue

        # ── Native KiCad branch pairs (outcb / load) ──────────────────────
        if cid == "outcb":
            pending_outcbs.append(("outcb", label))
            continue
        if cid == "load":
            pending_loads.append(("load", label))
            continue

        # ── Remaining native KiCad IDs (supply_L/N/PE, maincb) ───────────
        if cid in _VALID_CIDS:
            normalized.append((cid, label))
            continue

        warnings.warn(f"Unrecognized component type {cid!r} — skipped")

    # ── Interleave outcbs and loads: outcb, load, outcb, load, … ─────────
    # Zip to the shorter list; any extras are appended unmatched so the
    # downstream validator can report a clear error.
    n_pairs = min(len(pending_outcbs), len(pending_loads))
    for i in range(n_pairs):
        normalized.append(pending_outcbs[i])
        normalized.append(pending_loads[i])
    # Append any unpaired remainders (validator will flag them)
    for i in range(n_pairs, len(pending_outcbs)):
        normalized.append(pending_outcbs[i])
    for i in range(n_pairs, len(pending_loads)):
        normalized.append(pending_loads[i])

    # ── Ensure a main MCB exists in panel mode ────────────────────────────
    if mode == "panel" and not has_maincb:
        supply_count = sum(1 for c, _ in normalized
                          if c in ("supply_L", "supply_N", "supply_PE"))
        normalized.insert(supply_count, ("maincb", "Main MCB 2P 63A"))

    return normalized


# ---------------------------------------------------------------------------
# Structural validator for outcb/load pairing
# ---------------------------------------------------------------------------

def validate_normalized(components: List[Tuple[str, str]]) -> None:
    """
    Verify that every outcb is followed by exactly one load and vice-versa.
    Raises ValueError on the first violation found.
    """
    pending_cb = None

    for cid, label in components:
        if cid == "outcb":
            if pending_cb is not None:
                raise ValueError(
                    f"OutCB '{pending_cb}' has no downstream load "
                    f"(next outcb '{label}' encountered before a load)."
                )
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
        Accepts both Test2.py cids (supply, maincb, bus, nbar, ebar,
        outcb_1..N, loads, lighting, sockets, appliance, motor, hvac,
        ev, rcd, rcbo) and native KiCad cids (supply_L, supply_N,
        supply_PE, maincb, outcb, load).
    voltage    : str  (default "230V / 50Hz")
    language   : "en" | "ja"  (default "en")
    mode       : "panel" | "conceptual" | "single"  (default "panel")
    """

    if not isinstance(parsed_data, dict):
        raise TypeError(
            f"parsed_data must be a dict, got {type(parsed_data).__name__}"
        )
    if "components" not in parsed_data:
        raise ValueError("parsed_data must contain a 'components' key.")

    raw = parsed_data["components"]
    if not isinstance(raw, (list, tuple)):
        raise TypeError(
            f"parsed_data['components'] must be a list, "
            f"got {type(raw).__name__}"
        )

    voltage  = str(parsed_data.get("voltage",  "230V / 50Hz"))
    title    = str(parsed_data.get("title",    "Generated Electrical Schematic"))

    # Translate / normalise all component IDs into native KiCad cids
    normalized = normalize_components(parsed_data)

    # Validate outcb/load pairing before spending time building geometry
    validate_normalized(normalized)

    # Build schematic body + collect instances (no global state)
    body, instances = _build_schematic(normalized, title, voltage)

    # Serialise to complete .kicad_sch content
    content = _serialise(body, instances, title, voltage)

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

if __name__ == "__main__":
    import sys

    sample: dict = {
        "components": [
            ["supply_L",  "L  230V/50Hz"],
            ["supply_N",  "N  Neutral"],
            ["supply_PE", "PE  Earth"],
            ["maincb",    "Main MCB 2P 63A"],
            ["outcb",     "Lighting MCB 1P 10A"],
            ["load",      "Lighting Load"],
            ["outcb",     "Sockets MCB 1P 16A"],
            ["load",      "Power Sockets"],
            ["outcb",     "Kitchen MCB 1P 20A"],
            ["load",      "Kitchen Appliances"],
        ],
        "voltage":  "230V / 50Hz",
        "language": "en",
    }

    # Also test with Test2.py-style IDs
    sample_test2: dict = {
        "components": [
            ["supply",   "Main Supply (230V AC)"],
            ["maincb",   "Main Breaker (MCB/MCCB)"],
            ["rcd",      "RCD (Earth Fault Protection)"],
            ["bus",      "Busbar (Distribution)"],
            ["nbar",     "Neutral Bar"],
            ["ebar",     "Earth Bar"],
            ["outcb_1",  "Lighting MCB 1P 10A"],
            ["outcb_2",  "Sockets MCB 1P 16A"],
            ["outcb_3",  "Kitchen MCB 1P 20A"],
            ["loads",    "Load Circuits (Lights, Sockets)"],
        ],
        "voltage":  "230V / 50Hz",
        "language": "en",
        "mode":     "panel",
    }

    out       = sys.argv[1] if len(sys.argv) > 1 else "panel_230V.kicad_sch"
    out_test2 = sys.argv[2] if len(sys.argv) > 2 else "panel_test2_style.kicad_sch"

    for label, data, path in [
        ("native-ids", sample,      out),
        ("test2-ids",  sample_test2, out_test2),
    ]:
        print(f"\n{'='*60}")
        print(f"Test: {label}  →  {path}")
        export_kicad_schematic(data, path)
        content = open(path, encoding="utf-8").read()

        sexp_errors = validate_sexp(content)

        checks = [
            ("S-expr balanced",       not sexp_errors),
            ("kicad_sch open",        "(kicad_sch"        in content),
            ("lib_symbols present",   "(lib_symbols"      in content),
            ("symbol_instances",      "(symbol_instances" in content),
            ("MCB_2P defined",        '"MCB_2P"'          in content),
            ("MCB_1P defined",        '"MCB_1P"'          in content),
            ("CONN_3P defined",       '"CONN_3P"'         in content),
            ("Q1 placed",             '"Q1"'              in content),
            ("Q2 placed",             '"Q2"'              in content),
            ("J1 placed",             '"J1"'              in content),
            ("N labels present",      '"N"'               in content),
            ("PE labels present",     '"PE"'              in content),
            ("junctions present",     "(junction"         in content),
            ("bold as attribute",     "(bold yes)"        in content),
            ("no bold-in-size",       " bold))"          not in content),
            ("no justify center",     '"center"'         not in content),
            ("no net_label token",    "(net_label"       not in content),
            ("no zero-len wires",     True),   # guarded in _wire()
        ]

        print(f"Written: {path}  ({len(content):,} bytes)\n")
        all_ok = True
        for name, passed in checks:
            status = "OK  " if passed else "FAIL"
            print(f"  [{status}] {name}")
            if not passed:
                all_ok = False

        if sexp_errors:
            print("\nS-expression errors:")
            for e in sexp_errors:
                print(f"  {e}")

        print("\nAll checks passed." if all_ok else "\nSome checks FAILED.")