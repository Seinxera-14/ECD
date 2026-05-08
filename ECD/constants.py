# constants.py
import re

# ── Complexity level definitions ─────────────────────────────────────────────
COMPLEXITY_LEVELS = {
    "Simple": {
        "components": ["supply", "maincb", "loads"],
        "show_neutral": False,
        "show_earth": False,
        "show_protection_notes": False,
        "show_fault_paths": False,
        "description": "Phase (L) only — no neutral/earth, minimal steps",
    },
    "Standard": {
        "components": ["supply", "maincb", "bus", "nbar", "ebar", "loads"],
        "show_neutral": True,
        "show_earth": True,
        "show_protection_notes": False,
        "show_fault_paths": False,
        "description": "L / N / E — breakers and busbars",
    },
    "Detailed": {
        "components": ["supply", "maincb", "bus", "nbar", "ebar", "outcb", "loads"],
        "show_neutral": True,
        "show_earth": True,
        "show_protection_notes": True,
        "show_fault_paths": True,
        "description": "Outgoing MCBs, protection notes, fault paths",
    },
}

# Color assignments for box types
SECTION_COLORS = {
    "incoming": "rgb(238,242,255)",      # Light blue
    "distribution": "rgb(240,253,244)",  # Light green
    "load": "rgb(255,247,237)",          # Light orange
}

# Locked section labels (yellow boxes) - fixed positions
SECTION_LABELS = {
    "section_incoming": {"en": "Incoming Source", "ja": "入力電源"},
    "section_distribution": {"en": "Distribution Panel Components", "ja": "分電盤部品"},
    "section_load": {"en": "Load Side", "ja": "負荷側"},
}

# Component IDs and their section assignments
COMPONENT_SECTIONS = {
    "supply": "incoming",
    "maincb": "distribution",
    "bus": "distribution",
    "nbar": "distribution",
    "ebar": "distribution",
    "outcb": "distribution",
    "loads": "load",
}