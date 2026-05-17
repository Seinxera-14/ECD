# constants.py
import re

# ── Complexity level definitions ─────────────────────────────────────────────
COMPLEXITY_LEVELS = {
    "Simple": {
        "components": ["supply", "maincb", "loads"],
        "show_neutral": False,
        "show_earth": False,
        "show_rcd": False,
        "show_protection_notes": False,
        "show_fault_paths": False,
        "description": "Phase (L) only — no neutral/earth, minimal steps",
    },
    "Neutral": {
        "components": [],
        "show_neutral": False,
        "show_earth": False,
        "show_rcd": False,
        "show_protection_notes": False,
        "show_fault_paths": False,
        "description": "Prompt-driven only — components come entirely from what you describe",
    },
    "Standard": {
        "components": ["supply", "maincb", "bus", "nbar", "ebar", "rcd", "loads"],
        "show_neutral": True,
        "show_earth": True,
        "show_rcd": True,
        "show_protection_notes": False,
        "show_fault_paths": False,
        "description": "L / N / E — breakers and busbars",
    },
    "Detailed": {
        "components": ["supply", "maincb", "bus", "rcd", "nbar", "ebar", "loads"], 
        "allow_outcb": True, 
        "show_neutral": True,
        "show_earth": True,
        "show_rcd": True,
        "show_protection_notes": True,
        "show_fault_paths": True,
        "description": "Outgoing MCBs, protection notes, fault paths",
    },
}
