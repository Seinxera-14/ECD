import sys
import re
from typer.cli import app
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
import json
import requests
from Kicad_exporter import export_kicad_schematic
from dxf_generator import mermaid_to_dxf, export_dxf



class OllamaClient:
    def __init__(self, model="mistral:7b-instruct", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        system_prompt = f"""You are an expert electrical diagram assistant. Convert the user's description into structured JSON for an electrical distribution diagram.

Return ONLY valid JSON. No explanation. No markdown. No preamble. No text before or after the JSON object.
Start your response with {{ and end with }}. Nothing else.

=== OUTPUT SCHEMA ===
{{
  "components": [
    ["supply", "label"],
    ["maincb", "label"],
    ["rcd", "label"],
    ["bus", "label"],
    ["nbar", "label"],
    ["ebar", "label"],
    ["outcb_1", "label"],
    ["loads", "label"]
  ],
  "flags": {{
    "show_neutral": true,
    "show_earth": true,
    "show_rcd": true,
    "show_protection_notes": true,
    "show_fault_paths": true
  }},
  "voltage": "230V AC",
  "language": "en"
}}

=== ALLOWED COMPONENT IDs ===
supply, maincb, rcd, rcbo, bus, nbar, ebar, loads
outcb_1, outcb_2, outcb_3, outcb_4, outcb_5

=== COMPONENT MEANINGS ===
supply   = incoming mains / grid source
maincb   = main circuit breaker (MCB / MCCB)
rcd      = residual current device (earth fault protection, monitors leakage)
rcbo     = combined RCD + MCB in one unit
bus      = busbar / distribution bar
nbar     = neutral bar / neutral link
ebar     = earth bar / protective earth bar / safety earth
outcb_N  = outgoing branch circuit breaker (one per named circuit)
loads    = load circuits / consuming devices

=== COMPLEXITY LEVEL IN EFFECT: {complexity} ===

COMPLEXITY RULES:

"Neutral" (prompt-only mode):
  - Include ONLY what the user actually describes. Do not add anything they did not mention.
  - If the user says "supply and a breaker" output only supply + maincb + loads.
  - Do not inject busbar, RCD, neutral bar, earth bar unless the user mentions them.
  - flags must reflect ONLY what the user described.

"Simple":
  - Phase wire only. No neutral, no earth, no RCD, no fault paths.
  - Always include: supply, maincb, loads.
  - show_neutral=false, show_earth=false, show_rcd=false, show_fault_paths=false.
  - Add any extra components the user explicitly names, but never add implicit ones.

"Standard":
  - Default set: supply, maincb, rcd, bus, nbar, ebar, loads.
  - Always include the defaults PLUS anything the user explicitly names.
  - show_neutral=true, show_earth=true, show_rcd=true.
  - show_fault_paths=false unless user asks for fault paths.

"Detailed":
  - Default set: supply, maincb, rcd, bus, nbar, ebar, loads.
  - Always include defaults PLUS every component the user names.
  - For each named circuit add a separate outcb_N with a descriptive label.
  - show_neutral=true, show_earth=true, show_rcd=true, show_fault_paths=true, show_protection_notes=true.

=== EXPLICIT EXCLUSIONS — ALWAYS OVERRIDE COMPLEXITY ===
If the user says "no RCD", "no fault path", "no neutral", "no earth", "simple breaker only":
  Remove that component and set its flag to false. This overrides everything above.
  User prompt is the ultimate source of truth. If they say "no RCD" then there is no RCD, even in Detailed mode.

=== INFERENCE RULES ===
1. Voltage: extract from prompt. Format: "230V AC" or "415V AC". Default: "unspecified".
2. Language: Japanese text (hiragana/katakana/kanji) -> "ja". Otherwise -> "en".
3. supply label must include voltage. Example: "Main Supply (230V AC)".
4. rcd / rcbo label: use whatever the user names it. If user doesn't name it, use "RCD (Earth Fault Protection)".
5. outcb_N: only multiple entries if user names distinct/multiple circuits. Max 5.
6. "standard distribution panel" with no detail at Standard/Detailed complexity -> include full default set.
7. The supply and load should always be present on any complexity level unless user explicitly says "no loads" or "direct connection" or "no supply.
"""

        payload = {
                "model": self.model,
                "prompt": f"{system_prompt.strip()}\n\nUSER PROMPT:\n{prompt}\n\nJSON:",
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "top_p": 0.9,
                    "num_predict": 1024,
                    "num_ctx": 8192,
                }
            }

        print(f"Parsing prompt using {self.model} | complexity={complexity}")
        response = requests.post(self.url, json=payload, timeout=90)
        response.raise_for_status()

        raw = response.json().get("response", "").strip()
        json_obj = self._extract_json(raw)

        if json_obj is None:
            raise ValueError(f"Invalid or missing JSON output:\n{raw[:500]}")

        return json_obj
    

    def _extract_json(self, text: str) -> dict | None:
        """Try to extract and parse a JSON object from text. Returns dict or None."""
        text = text.strip()
        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find first { ... last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None
        
class GenerationWorker(QThread):
    """Runs the blocking Ollama LLM call on a background thread."""
    finished = Signal(dict)       # emits parsed_data on success
    failed   = Signal(str)        # emits error message on failure

    def __init__(self, prompt: str, complexity: str, generator):
        super().__init__()
        self.prompt     = prompt
        self.complexity = complexity
        self.generator  = generator   # MermaidGenerator instance (thread-safe reads only)

    def run(self):
        try:
            ollama      = OllamaClient()
            parsed_data = ollama.prompt_to_structured_data(self.prompt, self.complexity)

            if not isinstance(parsed_data, dict) or "components" not in parsed_data:
                raise ValueError("Invalid LLM output — missing components key")

            # Normalise components to (id, label) tuples
            parsed_data["components"] = [
                (c[0], c[1]) if isinstance(c, (list, tuple)) and len(c) >= 2 else (str(c), str(c))
                for c in parsed_data["components"]
            ]
            self.finished.emit(parsed_data)

        except Exception as e:
            self.failed.emit(str(e))


class ValidationWorker(QThread):
    validationComplete = Signal(str, bool)  # message, has_issues
    findingsReady = Signal(list)  

    def __init__(self, prompt: str, mermaid_code: str, complexity: str = "Standard"):
        super().__init__()
        self.prompt = prompt
        self.mermaid_code = mermaid_code
        self.complexity = complexity


    def run(self):
        try:
            complexity = self.complexity
            complexity_context = {
                "Simple": """COMPLEXITY: Simple mode is intentionally minimal.
- Only Phase (L) wire is shown. Neutral and Earth wires are deliberately hidden.
- No fault paths, no protection notes. This is expected and NOT a fault.
- Only validate: supply → breaker → loads chain integrity.""",

                "Neutral": """COMPLEXITY: Neutral / prompt-driven mode.
- The diagram contains ONLY what the user explicitly described. Nothing more is expected.
- Do NOT flag absent RCD, busbar, neutral bar, earth bar, fault paths, or outgoing MCBs
  unless the user specifically asked for them in their prompt.
- Do NOT flag missing protection notes or fault current paths — these are never expected here.
- ONLY flag: components the user asked for that are genuinely absent, or a broken
  supply → load chain (e.g. load with no upstream connection at all).""",

                "Standard": """COMPLEXITY: Standard mode shows L/N/E but has intentional omissions.
- Fault protection paths are deliberately excluded. Do NOT flag missing fault paths.
- Outgoing MCBs (branch breakers) are excluded. Do NOT flag their absence.
- Validate: supply → breaker → busbar → neutral bar → earth bar → loads connectivity.""",

                 "Detailed": """COMPLEXITY: Detailed mode is the full diagram.
- All components must be present: supply, main breaker, RCD, busbar, neutral bar, earth bar, outgoing MCBs, loads.
- RCD MUST appear between main breaker and busbar. Flag if missing (unless user explicitly excluded it).
- Fault path MUST route through RCD: EBar → RCD → MainCB trip. Flag if fault path skips RCD.
- Outgoing MCBs: if user named N specific circuits, expect N outgoing breaker nodes.
- Protection notes on main breaker and RCD MUST be present. Flag if missing.
- Validate everything strictly.
- Exception: if user said "no RCD" or "no fault path", do NOT flag their absence."""
            }.get(complexity, "")

            system_prompt = f"""You are an expert electrical diagram validator.
You will receive:
1. The user's original prompt
2. The complexity level and what it intentionally omits
3. The generated Mermaid sequence diagram code

{complexity_context}

Your job is to compare the user's intent against the Mermaid output and flag ONLY real problems:
- Components the user explicitly asked for but are missing (accounting for complexity omissions above)
- Logically incorrect electrical flow (e.g. load directly connected to supply with no breaker)
- Components present that the user never asked for
- In Detailed mode only: missing fault paths or protection notes

Do NOT flag components that are intentionally hidden by the complexity level.
Also, check if the diagram and circuit workflow practically makes sense or not. 
For example, if there is a load connected directly to the supply with no breaker, that is a real issue and should be flagged, even if the user didn't explicitly say "I want a breaker". The diagram must be logically correct as an electrical distribution system, not just contain the components mentioned by the user.

Respond in this exact format:
STATUS: OK or ISSUES_FOUND
FINDINGS:
- finding 1
- finding 2
(or write "None" if STATUS is OK)

Be concise. Only flag real problems."""

            payload = {
                "model": "mistral:7b-instruct",
                "prompt": f"{system_prompt.strip()}\n\nUSER PROMPT:\n{self.prompt}\n\nMERMAID CODE:\n{self.mermaid_code}",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512,
                    "num_ctx": 4096,
                }
            }
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
            response.raise_for_status()
            text = response.json().get("response", "").strip()
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

            has_issues = "ISSUES_FOUND" in text
            self.validationComplete.emit(text, has_issues)
            findings_block = text.split("FINDINGS:")[-1].strip() if "FINDINGS:" in text else ""
            findings_list = [
                line.lstrip("- ").strip()
                for line in findings_block.splitlines()
                if line.strip() and line.strip() != "None"
            ]
            if has_issues and findings_list:
                self.findingsReady.emit(findings_list)
        except Exception as e:
            self.validationComplete.emit(f"Validation unavailable: {e}", False)


class MermaidFixWorker(QThread):
    """
    LLM #3: receives the current Mermaid code + validation findings and returns
    a corrected Mermaid code string.

    Rules enforced in the system prompt:
    - ONLY add missing participants / arrows. Never delete existing ones.
    - Return raw sequenceDiagram code only — no markdown fences, no explanation.
    - Preserve all existing participant aliases, box groupings, and arrow labels.
    """

    fixComplete = Signal(str)   # emits corrected mermaid code on success
    fixFailed   = Signal(str)   # emits error message on failure

    def __init__(
        self,
        mermaid_code: str,
        findings: list,
        prompt: str,
        complexity: str = "Standard",
    ):
        super().__init__()
        self.mermaid_code = mermaid_code
        self.findings     = findings
        self.prompt       = prompt
        self.complexity   = complexity

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences if the model wraps its output in them."""
        text = text.strip()
        # Strip ```mermaid ... ``` or ``` ... ```
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        return text.strip()

    @staticmethod
    def _is_valid_mermaid(text: str) -> bool:
        """Minimal sanity check: must start with sequenceDiagram and have arrows."""
        return (
            text.strip().startswith("sequenceDiagram")
            and ("->>" in text or "-->" in text)
        )

    @staticmethod
    def _sanitize_labels(code: str) -> str:
        """
        Replace characters that are valid in Mermaid label strings but break
        Mermaid 10.x's parser when used in arrow labels or participant aliases.
        Called after fence-stripping, before the validity check.
        """
        # Fix lines with arrow labels: replace bare < > & with safe equivalents
        def _fix_arrow_line(m):
            prefix = m.group(1)   # e.g.  "    Supply->>MainCB: "
            label  = m.group(2)   # the label text after the colon
            label  = label.replace('&', 'and')
            label  = label.replace('<', '(').replace('>', ')')
            # Remove or replace em-dash (—) which some LLMs emit
            label  = label.replace('—', '-').replace('–', '-')
            return prefix + label

        # Match arrow lines: optional spaces, SRC->>/-->>DEST: LABEL
        code = re.sub(
            r'([ \t]*\w[\w ]*(?:->>|-->>)\w[\w ]*:[ \t]*)(.*)',
            _fix_arrow_line,
            code,
            flags=re.MULTILINE,
        )

        def _fix_note_over(m):
            prefix = m.group(1)          # "    Note over "
            participants = [p.strip() for p in m.group(2).split(',')]
            label = m.group(3)           # ": some text"
            if len(participants) > 2:
                return f"{prefix}{participants[0]},{participants[-1]}{label}"
            return m.group(0)

        code = re.sub(
            r'([ \t]*Note over )([\w ,]+?)(:.*)',
            _fix_note_over,
            code,
            flags=re.MULTILINE,
        )

        return code

    @staticmethod
    def _is_valid_mermaid(text: str) -> bool:
        """Minimal sanity check: must start with sequenceDiagram and have arrows."""
        stripped = text.strip()
        if not stripped.startswith("sequenceDiagram"):
            return False
        if "->>" not in stripped and "-->" not in stripped:
            return False
        # Mermaid 10.x requires autonumber to be on its own line (if present)
        for line in stripped.splitlines():
            line = line.strip()
            if line.startswith("autonumber") and len(line) > len("autonumber"):
                return False   # "autonumber 1" or "autonumber participant X" — both invalid
        return True

    # ── thread entry ──────────────────────────────────────────────────────────

    def run(self):
        findings_text = "\n".join(f"- {f}" for f in self.findings)

        complexity_rules = {
            "Simple":   "Only Phase (L) wire is shown. Do NOT add neutral, earth, RCD, or fault paths.",
            "Neutral":  "Add only what the original user prompt describes. Do not add standard defaults.",
            "Standard": "Do NOT add fault paths or outgoing MCBs. You may add supply, main breaker, RCD, busbar, neutral bar, earth bar, loads.",
            "Detailed": "You may add any missing electrical component required for a complete distribution diagram.",
        }.get(self.complexity, "")

        system_prompt = f"""You are an expert electrical diagram code editor for Mermaid sequenceDiagram syntax.

You will receive:
1. The user's original description of what they want
2. The current Mermaid sequenceDiagram code that was generated
3. A list of validation findings — problems found in the diagram

Your task is to fix the Mermaid code by addressing every finding listed.

=== STRICT RULES ===
1. NEVER remove or rename any existing participant, box, note, or arrow.
   Existing components may have been added by the complexity level and must be preserved.
2. ONLY add new participants and/or new arrows to fix the identified issues.
3. New participants must be added inside the correct box section (box...end block).
   - Components belonging to the distribution panel go inside the green box.
   - Load-side components go inside the orange box.
   - If a component does not fit an existing box, add it after the last end keyword
     as a standalone participant before the autonumber line.
4. New arrows must follow Mermaid sequenceDiagram syntax:
   - Solid arrow:  A->>B: label
   - Dashed arrow: A-->>B: label
5. Maintain logical electrical flow: supply → breaker → [rcd] → busbar → loads.
   New arrows must not violate this order.
6. Do NOT add components that the user explicitly excluded (e.g. "no RCD", "no neutral").
7. Complexity constraint for this diagram: {complexity_rules}

=== OUTPUT FORMAT ===
Return ONLY the corrected Mermaid sequenceDiagram code.
No explanation. No markdown fences. No preamble. Start with: sequenceDiagram"""

        user_content = (
            f"USER DESCRIPTION:\n{self.prompt}\n\n"
            f"VALIDATION FINDINGS TO FIX:\n{findings_text}\n\n"
            f"CURRENT MERMAID CODE:\n{self.mermaid_code}\n\n"
            f"FIXED MERMAID CODE:"
        )

        payload = {
            "model": "mistral:7b-instruct",
            "prompt": f"{system_prompt.strip()}\n\n{user_content}",
            "stream": False,
            "options": {
                "temperature": 0.0,   # deterministic — we want exact syntax
                "num_predict": 1536,  # generous enough for a full diagram
                "num_ctx":     6144,
            },
        }

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=90,
            )
            response.raise_for_status()

            raw = response.json().get("response", "").strip()
            # Strip any <think>...</think> blocks (some reasoning models emit these)
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            fixed_code = self._strip_fences(raw)
            fixed_code = self._sanitize_labels(fixed_code)

            if not self._is_valid_mermaid(fixed_code):
                self.fixFailed.emit(
                    f"Fix worker returned invalid Mermaid output.\n\nRaw response:\n{raw[:400]}"
                )
                return

            self.fixComplete.emit(fixed_code)

        except Exception as e:
            self.fixFailed.emit(str(e))


class WebBridge(QObject):
    elementDoubleClicked = Signal(str, str, str)
    elementEdited = Signal(str, str, str, float, float)
    diagramChanged = Signal(str)

    def __init__(self):
        super().__init__()

    @Slot(str, str, str)
    def onElementDoubleClicked(self, element_id, element_type, current_text):
        self.elementDoubleClicked.emit(element_id, element_type, current_text)

    @Slot(str, str, str, float, float)
    def onElementEdited(self, element_id, element_type, new_text, x, y):
        self.elementEdited.emit(element_id, element_type, new_text, x, y)

    @Slot(str)
    def onDiagramTextChanged(self, new_mermaid_code):
        self.diagramChanged.emit(new_mermaid_code)



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


class MermaidGenerator:
    def __init__(self):
        self.components_map = {
            "main incoming supply": {"en": "Main Incoming Supply<br/>(230V / 415V)", "ja": "主電源<br/>(230V / 415V)"},
            "main breaker": {"en": "Main Breaker<br/>(MCB/MCCB)", "ja": "主遮断器<br/>(MCB/MCCB)"},
            "rcd": {"en": "RCD<br/>(Earth Fault Protection)", "ja": "漏電遮断器<br/>(RCD/RCBO)"},
            "busbar": {"en": "Busbar<br/>(Distribution)", "ja": "母線<br/>(配電)"},
            "neutral bar": {"en": "Neutral Bar", "ja": "中性線バー"},
            "earth bar": {"en": "Earth Bar", "ja": "接地バー"},
            "outgoing mcbs": {"en": "Outgoing MCBs", "ja": "出力MCB"},
            "load circuits": {"en": "Load Circuits<br/>(Lights, Sockets)", "ja": "負荷回路<br/>(照明、コンセント)"},
        }
        self.keywords_map = {
            "incoming": {
                "en": [
                    "incoming", "supply", "source", "230v", "415v", "mains", "grid", "utility", "infeed", "line in",
                    "three-phase", "3-phase", "three phase", "3phase", "ryb", "ryw", "rst", "uvw",
                    "single-phase", "1-phase", "single phase",
                ],
                "ja": [
                    "主電源", "受電", "電源", "入力電源",
                    "三相", "単相", "系統",
                ],
            },            
            "breaker": {
                "en": [
                    "breaker", "mcb", "mccb", "protection", "circuit breaker", "main cb", "main breaker",
                    "isolator", "isolating switch", "main switch", "elcb",
                    "fuse", "fuse switch", "switch fuse", "acb", "vcb", "contactor",
                ],
                "ja": [
                    "遮断器", "ブレーカー", "ブレーカ",
                    "主開閉器", "漏電遮断器", "配線用遮断器",
                    "ヒューズ", "開閉器",
                ],
            },

            "rcd": {
                "en": ["rcd", "rcbo", "elcb", "residual current", "earth fault", "leakage",
                    "earth leakage", "ground fault", "residual", "30ma", "100ma", "300ma"],
                "ja": ["漏電遮断器", "漏電ブレーカー", "漏電", "地絡", "残留電流"],
            },

            "busbar": {
                "en": [
                    "busbar", "distribution", "panel", "bus bar", "bus-bar", "copper bar", "copper strip", 
                    "db", "distribution board", "distribution box", "switchboard", "switchgear", "mdb", "pcc", "mcc",                                 
                ],
                "ja": [
                    "母線", "バスバー", "配電盤", "分電盤",
                    "銅バー", "主幹", "盤",
                ],
            },            
            
            "neutral": {
                "en": [
                    "neutral", "return",
                    "neutral bar", "n bar", "n-bar",
                    "neutral link", "neutral terminal",
                    "neutral bus", "common neutral",
                    "neutral return", "return path",
                    # three-phase star point terms
                    "star point", "centre point",
                ],
                "ja": [
                    "中性線", "ニュートラル", "零線", "N線",
                    "中性点", "中性線バー",
                ],
            },            

            "earth": {
                "en": [
                    "earth", "ground", "safety",
                    "earth bar", "e bar", "e-bar",
                    "earthing", "grounding",
                    "protective earth", "pe",
                    "cpc", "safety earth", "protective conductor",
                    "bonding", "equipotential bonding",
                    "earth terminal", "earth bus",
                    "chassis earth", "frame earth",
                ],
                "ja": [
                    "接地", "アース", "グラウンド", "地線",
                    "保護接地", "接地バー", "PE線",
                ],
            }, 

            "outgoing": {
                "en": [
                    "outgoing", "branch", "circuit",
                    "sub breaker", "sub-breaker", "sub mcb",
                    "outgoing mcb", "outgoing breaker",
                    "final circuit", "branch circuit",
                    "feeder", "sub feeder",
                    "downstream breaker", "individual breaker",
                    "motor breaker", "lighting breaker",
                ],
                "ja": [
                    "出力", "分岐", "回路",
                    "分岐ブレーカー", "出力MCB", "子ブレーカー",
                ],
            },

           
            "load": {
                "en": [
                    "load", "circuit", "light", "socket", "appliance",
                    # common load descriptions users write
                    "lighting", "lights", "lamps", "luminaire",
                    "power socket", "outlet", "plug point",
                    "motor", "pump", "fan", "hvac", "air conditioning",
                    "equipment", "machine", "device", "consumer",
                    "balanced load", "unbalanced load",
                    "three-phase load", "single-phase load",
                ],
                "ja": [
                    "負荷", "回路", "照明", "コンセント",
                    "モーター", "ポンプ", "機器", "電気機器",
                ],
            },
        }
        self.diagram_labels = {
            "section_incoming":     {"en": "Incoming Source",               "ja": "入力電源"},
            "section_distribution": {"en": "Distribution Panel Components", "ja": "分電盤部品"},
            "section_load":         {"en": "Load Side",                     "ja": "負荷側"},
            "note_power_entry":     {"en": "1. INCOMING POWER ENTRY",       "ja": "1. 受電"},
            "note_internal":        {"en": "2. INTERNAL DISTRIBUTION",      "ja": "2. 内部配電"},
            "note_outgoing":        {"en": "3. OUTGOING CIRCUITS",          "ja": "3. 出力回路"},
            "note_fault":           {"en": "4. FAULT CURRENT PATH (E)",     "ja": "4. 故障電流経路 (E)"},            
            "wire_phase":           {"en": "Phase/Line Wire (L)",           "ja": "相線/ラインワイヤ (L)"},
            "wire_neutral":         {"en": "Neutral Wire (N)",              "ja": "中性線 (N)"},
            "wire_earth":           {"en": "Earth Wire (E)",                "ja": "接地線 (E)"},
            "action_energize":      {"en": "Energize Busbar (L)",           "ja": "母線を励磁 (L)"},
            "action_protection":    {"en": "Protection: Overload/Short",    "ja": "保護: 過負荷/短絡"},
            "action_rcd_monitor":   {"en": "Current Monitoring (RCD)",      "ja": "電流監視 (RCD)"},
            "action_rcd_pass":      {"en": "Protected Distribution (L)",    "ja": "保護配電 (L)"},
            "action_rcd_note":      {"en": "RCD: Residual Current\nTrip", "ja": "RCD: 漏電検知\n30mA以下でトリップ"},
            "action_distribute":    {"en": "Distribute to Branch Breakers", "ja": "分岐ブレーカーに配電"},
            "action_feed":          {"en": "Line (L) - Protected Feed",     "ja": "ライン (L) - 保護給電"},
            "action_return":        {"en": "Neutral (N) - Return Path",     "ja": "中性線 (N) - 帰路"},
            "action_safety":        {"en": "Earth (E) - Safety Grounding",  "ja": "接地 (E) - 安全接地"},
            "action_fault":         {"en": "Fault Current Detected (E)",    "ja": "故障電流検知 (E)"},
            "action_fault_return":  {"en": "Fault Return Path to Source",         "ja": "故障電流帰路 (電源へ)"},
            "action_rcd_isolate":   {"en": "Open Contacts — Isolate Circuit",     "ja": "接点開放 — 回路遮断"},
            "action_rcd_trip":      {"en": "RCD Trip Signal",               "ja": "RCDトリップ信号"},
            "action_cb_open":       {"en": "Circuit Open — Supply Isolated", "ja": "回路開放 — 電源遮断"},
        }
        
    def detect_language(self, text):
        if re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]').search(text):
            return "ja"
        return "en"


    

    def parse_prompt(self, prompt_text, complexity_level="Neutral"):
        print('parsing prompt with hardcoded rules')
        if not prompt_text or not isinstance(prompt_text, str):
            return {"components": self.get_default_components("en", "230V / 415V", "Standard"),
                    "voltage": "230V / 415V", "language": "en", "complexity": complexity_level}

        exclusions = {
            "rcd":  ["no rcd", "no residual", "no earth fault"],
            "nbar": ["no neutral"],
            "ebar": ["no earth", "no ground"],
            "bus":  ["no busbar", "no bus"],
        }
        prompt_lower = prompt_text.lower()

        # ✅ Assign BEFORE use
        language = self.detect_language(prompt_text)
        voltage_text = "230V / 415V"

        try:
            for pattern in [r'(\d+)\s*[Vv]\s*[/／]?\s*(\d+)\s*[Vv]', r'(\d+)\s*[Vv]', r'(\d+)\s*volts?']:
                m = re.search(pattern, prompt_text)
                if m:
                    voltage_text = f"{m.group(1)}V / {m.group(2)}V" if len(m.groups()) >= 2 else f"{m.group(1)}V"
                    break
        except Exception:
            pass

        # ✅ For Neutral mode, keyword-detect from prompt instead of using empty allowed list
        if complexity_level == "Neutral":
            KEYWORD_TO_COMPONENT = {
                "supply":  ["supply", "mains", "source", "incoming", "grid"],
                "maincb":  ["breaker", "mcb", "mccb", "circuit breaker", "main cb"],
                "rcd":     ["rcd", "rcbo", "residual", "earth fault"],
                "bus":     ["busbar", "bus bar", "bus-bar", "distribution"],
                "nbar":    ["neutral bar", "neutral link", "n bar"],
                "ebar":    ["earth bar", "earth terminal", "e bar"],
                "loads":   ["load", "loads", "lighting", "socket", "appliance", "circuit"],
            }
            all_possible = self.get_default_components(language, voltage_text, "Standard")
            all_possible_dict = dict(all_possible)

            found_ids = []
            for cid, keywords in KEYWORD_TO_COMPONENT.items():
                if any(kw in prompt_lower for kw in keywords):
                    if cid not in [ex for ex in exclusions if any(ex_kw in prompt_lower for ex_kw in exclusions.get(cid, []))]:
                        found_ids.append(cid)

            # Always ensure supply and loads if detected; fallback to supply+maincb+loads minimum
            if not found_ids:
                found_ids = ["supply", "maincb", "loads"]

            found_components = [
                (cid, all_possible_dict[cid]) for cid in found_ids
                if cid in all_possible_dict
                and not any(ex in prompt_lower for ex in exclusions.get(cid, []))
            ]
        else:
            # Non-Neutral: use the complexity level's allowed list
            found_components = self.get_default_components(language, voltage_text, complexity_level)
            comp_dict = dict(found_components)
            if "supply" in comp_dict:
                comp_dict["supply"] = self.components_map["main incoming supply"][language].replace(
                    "230V / 415V", voltage_text
                )
            found_components = [
                (cid, lbl) for cid, lbl in comp_dict.items()
                if not any(ex in prompt_lower for ex in exclusions.get(cid, []))
            ]

        return {"components": found_components, "voltage": voltage_text,
                "language": language, "complexity": complexity_level}

    def get_default_components(self, language, voltage_text="230V / 415V", complexity_level="Standard"):
        level_cfg = COMPLEXITY_LEVELS[complexity_level]
        allowed_ids = level_cfg["components"]  # outcb_N no longer in here for Detailed

        # allowed_ids = COMPLEXITY_LEVELS[complexity_level]["components"]
        all_defaults = [
            ("supply", self.components_map["main incoming supply"][language].replace("230V / 415V", voltage_text)),
            ("maincb", self.components_map["main breaker"][language]),
            ("rcd",    self.components_map["rcd"][language]),
            ("bus",    self.components_map["busbar"][language]),
            ("nbar",   self.components_map["neutral bar"][language]),
            ("ebar",   self.components_map["earth bar"][language]),
            ("loads",  self.components_map["load circuits"][language]),
        ]

        return [(cid, lbl) for cid, lbl in all_defaults if cid in allowed_ids]

    def generate_mermaid_code(self, parsed_data):
        components = parsed_data["components"]
        language   = parsed_data.get("language", "en")
        complexity = parsed_data.get("complexity", "Neutral")
        comp_map   = {cid: lbl for cid, lbl in components}
        L          = self.diagram_labels

        # ── Merge flags ───────────────────────────────────────────────────────────────────
        # Complexity defaults WIN when they require True.
        # The LLM can add True flags (e.g. user asked for fault paths on Standard),
        # but must NOT suppress flags that the complexity level mandates.
        # This fixes Detailed mode where Mistral often returns show_fault_paths=false.
        complexity_cfg = COMPLEXITY_LEVELS.get(complexity, COMPLEXITY_LEVELS["Neutral"])
        llm_flags = parsed_data.get("flags", {})

        # def _merge_flag(key):
        #     complexity_val = complexity_cfg[key]
        #     llm_val = llm_flags.get(key, None)
        #     # OR: if complexity requires it, keep it; LLM can only add True
        #     # return complexity_val or llm_val
        #     if llm_val is not None:
        #         return llm_val
        #     return complexity_val

        prompt_text = parsed_data.get("prompt", "")

        EXPLICIT_ENABLE_KEYWORDS = {
            "show_fault_paths":       ["fault path", "fault current", "earth fault path"],
            "show_neutral":           ["neutral wire", "show neutral", "include neutral"],
            "show_earth":             ["earth wire", "show earth", "include earth"],
            "show_rcd":               ["rcd", "residual current", "earth fault protection"],
            "show_protection_notes":  ["protection note", "show notes", "annotation"],
        }

        def _prompt_explicitly_enables(key, text):
            t = text.lower()
            return any(kw in t for kw in EXPLICIT_ENABLE_KEYWORDS.get(key, []))

        def _merge_flag(key):
            complexity_val = complexity_cfg[key]
            llm_val = llm_flags.get(key, None)

            # If complexity REQUIRES False (e.g. Simple hides fault paths),
            # only override if the prompt explicitly asks for it
            if complexity_val is False:
                # Only allow True if LLM was explicitly instructed by prompt
                # (prompt_text is stored in parsed_data["prompt"])
                prompt_explicitly_requests = _prompt_explicitly_enables(key, prompt_text)
                return True if prompt_explicitly_requests else False

            # If complexity requires True, LLM cannot suppress it
            if complexity_val is True:
                return True

            # Neutral / unset — LLM decides
            return llm_val if llm_val is not None else complexity_val


        cfg = {
            "show_neutral":          _merge_flag("show_neutral"),
            "show_earth":            _merge_flag("show_earth"),
            "show_rcd":              _merge_flag("show_rcd"),
            "show_protection_notes": _merge_flag("show_protection_notes"),
            "show_fault_paths":      _merge_flag("show_fault_paths"),
        }

        voltage_str = parsed_data.get("voltage", "")
        prompt_text = parsed_data.get("prompt", "")   # see note below about storing prompt

        THREE_PHASE_TERMS = ["415", "three-phase", "3-phase", "3phase", "ryb", "ryw", "rst", "uvw", "three phase"]
        is_three_phase = any(t in voltage_str.lower() for t in THREE_PHASE_TERMS)

        def clean_label(lbl):
            return re.sub(r'<br\s*/?>', ' ', lbl).strip()

        # ── Build participant ID map — handle dynamic outcb_1..5 ──────────────────
        pid = {
            "supply": "Supply",
            "maincb": "MainCB",
            "rcd":    "RCD",
            "rcbo":   "RCD",
            "bus":    "Bus",
            "nbar":   "NBar",
            "ebar":   "EBar",
            "outcb":  "OutCB",
            "loads":  "Loads",
        }
        # Add dynamic outcb_N entries
        for cid, _ in components:
            if cid.startswith("outcb_"):
                pid[cid] = cid.replace("outcb_", "OutCB")

        outcb_ids = [cid for cid, _ in components if cid.startswith("outcb_")]
        # Also support legacy single "outcb"
        if "outcb" in comp_map and not outcb_ids:
            outcb_ids = ["outcb"]

        lines = ["sequenceDiagram",  ""]

        # ── Box: Incoming Source ──────────────────────────────────────────────────
        lines.append(f'    box rgb(238,242,255) "{L["section_incoming"][language]}"')
        if "supply" in comp_map:
            lines.append(f'        participant {pid["supply"]} as {clean_label(comp_map["supply"])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Distribution Panel ───────────────────────────────────────────────
        lines.append(f'    box rgb(240,253,244) "{L["section_distribution"][language]}"')
        dist_order = ["maincb", "rcd", "rcbo", "bus", "nbar", "ebar"] + outcb_ids
        for cid in dist_order:
            if cid in comp_map:
                lines.append(f'        participant {pid[cid]} as {clean_label(comp_map[cid])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Load Side ────────────────────────────────────────────────────────
        lines.append(f'    box rgb(255,247,237) "{L["section_load"][language]}"')
        if "loads" in comp_map:
            lines.append(f'        participant {pid["loads"]} as {clean_label(comp_map["loads"])}')
        lines.append("    end")
        lines.append("")

        lines.append("   autonumber")
        lines.append("")

        # ── Section 1: Incoming Power Entry ──────────────────────────────────────
        if "supply" in comp_map:
            note_right_order = ["loads", "ebar", "nbar"] + list(reversed(outcb_ids)) + ["bus", "rcd", "maincb"]
            # note_right = next((pid[c] for c in note_right_order if c in comp_map), pid["supply"])
            # lines.append(f'    Note over {pid["supply"]},{note_right}: {L["note_power_entry"][language]}')
            all_pids_in_order = [pid[c] for c in note_right_order if c in comp_map]
            # lines.append(f'    Note over {all_pids_in_order[0]},{all_pids_in_order[-1]}: ...')
            if len(all_pids_in_order) >= 2:
                lines.append(f'    Note over {all_pids_in_order[0]},{all_pids_in_order[-1]}: {L["note_power_entry"][language]}')
            else:
                lines.append(f'    Note over {pid["supply"]}: {L["note_power_entry"][language]}')

            # Phase wire: supply → maincb (or directly to rcd if no maincb — shouldn't happen)
            if "maincb" in comp_map:
                # lines.append(f'    {pid["supply"]}->>{pid["maincb"]}: {L["wire_phase"][language]}')
                phase_label = L["wire_phase"][language]
                if is_three_phase:
                    phase_label = f"3-Phase Supply (L1/L2/L3) — {voltage_str}" if language == "en" else f"三相電源 (L1/L2/L3) — {voltage_str}"
                lines.append(f'    {pid["supply"]}->>{pid["maincb"]}: {phase_label}')
            # Neutral: supply → nbar (direct, parallel path)
            if cfg["show_neutral"] and "nbar" in comp_map:
                lines.append(f'    {pid["supply"]}->>{pid["nbar"]}: {L["wire_neutral"][language]}')
            # Earth: supply → ebar (direct, safety path)
            if cfg["show_earth"] and "ebar" in comp_map:
                lines.append(f'    {pid["supply"]}-->>{pid["ebar"]}: {L["wire_earth"][language]}')
            lines.append("")

            

        # ── Section 2: Internal Distribution ─────────────────────────────────────
        if "maincb" in comp_map:
            # dist_right_order = (outcb_ids or []) + ["ebar", "nbar", "bus", "rcd"]
            # In Section 2, replace the Note over maincb,dist_right line with:
            dist_pids = [pid[c] for c in ["maincb", "rcd", "bus", "nbar", "ebar"] + outcb_ids if c in comp_map]
            if len(dist_pids) >= 2:
                lines.append(f'    Note over {dist_pids[0]},{dist_pids[-1]}: {L["note_internal"][language]}')
            elif dist_pids:
                lines.append(f'    Note over {dist_pids[0]}: {L["note_internal"][language]}')           
           # Lines 648-649 — protection notes block
            if cfg["show_protection_notes"]:
                lines.append(f'    Note right of {pid["maincb"]}: {"Overcurrent / Short Circuit Protection" if language == "en" else "過電流/短絡保護"}')
                if cfg["show_rcd"] and "rcd" in comp_map:
                    lines.append(f'    Note right of {pid["rcd"]}: {"Earth Fault / Residual Current Protection" if language == "en" else "地絡/残留電流保護"}')

            # maincb → rcd (if RCD present)
            if cfg["show_rcd"] and "rcd" in comp_map:
                lines.append(f'    {pid["maincb"]}->>{pid["rcd"]}: {L["action_rcd_monitor"][language]}')
                
                # rcd → bus (or directly to outcb if no bus)
                if "bus" in comp_map:
                    lines.append(f'    {pid["rcd"]}->>{pid["bus"]}: {L["action_rcd_pass"][language]}')
                elif outcb_ids:
                    for oid in outcb_ids:
                        lines.append(f'    {pid["rcd"]}->>{pid[oid]}: {L["action_distribute"][language]}')
            else:
                # No RCD — maincb → bus or outcb directly
                if "bus" in comp_map:
                    lines.append(f'    {pid["maincb"]}->>{pid["bus"]}: {L["action_energize"][language]}')
                elif outcb_ids:
                    for oid in outcb_ids:
                        lines.append(f'    {pid["maincb"]}->>{pid[oid]}: {L["action_distribute"][language]}')

            # bus → outcb_N
            if "bus" in comp_map and outcb_ids:
                for oid in outcb_ids:
                    lines.append(f'    {pid["bus"]}->>{pid[oid]}: {L["action_distribute"][language]}')

            lines.append("")

        # ── Section 3: Outgoing Circuits ──────────────────────────────────────────
        if "loads" in comp_map:
            load_src_order = outcb_ids + ["bus", "rcd", "maincb"]
            load_src_cid = next((c for c in load_src_order if c in comp_map), None)

            if load_src_cid is None:
                lines.append(f'    Note over {pid["loads"]}: ⚠ WARNING: No upstream protection found')
            else:
                if load_src_cid != "loads":
                    lines.append(f'    Note over {pid[load_src_cid]},{pid["loads"]}: {L["note_outgoing"][language]}')
                else:
                    lines.append(f'    Note over {pid["loads"]}: {L["note_outgoing"][language]}')

                # ── NEW: outcb → Loads feed arrows ───────────────────────────────
                if outcb_ids:
                    feed_label = "Protected Feed (L)" if language == "en" else "保護給電 (L)"
                    for oid in outcb_ids:
                        lines.append(f'    {pid[oid]}->>{pid["loads"]}: {feed_label}')
                elif load_src_cid and load_src_cid != "loads":
                    # No outcbs — draw direct feed from whatever upstream exists
                    lines.append(f'    {pid[load_src_cid]}->>{pid["loads"]}: {L["action_feed"][language]}')

                # Neutral return and earth (unchanged)
                if cfg["show_neutral"] and "nbar" in comp_map:
                    lines.append(f'    {pid["loads"]}->>{pid["nbar"]}: {L["action_return"][language]}')
                if cfg["show_earth"] and "ebar" in comp_map:
                    lines.append(f'    {pid["ebar"]}-->>{pid["loads"]}: {L["action_safety"][language]}')

            lines.append("")


        # ── Section 4: Fault Protection Paths ─────────────────────────────────
        if cfg["show_fault_paths"] and "ebar" in comp_map and "loads" in comp_map:
            L = self.diagram_labels
            language = parsed_data.get("language", "en")

            lines.append("")
            # Note over must span left-to-right in participant order: EBar is left of Loads
            lines.append(f'    Note over {pid["ebar"]},{pid["loads"]}: {L["note_fault"][language]}')

            # Step 1: Fault current flows from load (motor casing) through CPC to Earth Bar
            lines.append(f'    {pid["loads"]}-->>{pid["ebar"]}: {L["action_fault"][language]}')

            # Step 2: Fault return path travels from Earth Bar back to supply source
            # (via main earth terminal / transformer star-point bond)
            if "supply" in comp_map:
                lines.append(f'    {pid["ebar"]}-->>{pid["supply"]}: {L["action_fault_return"][language]}')

            # Step 3: RCD monitors live vs neutral — shown as a note, not an arrow
            # because RCD is a sensing device; fault current does NOT flow through it
            if cfg["show_rcd"] and "rcd" in comp_map:
                lines.append(f'    Note over {pid["rcd"]}: {"Monitors L vs N current | Trips on imbalance ≥ 30mA" if language == "en" else "L線とN線の電流を監視 | 30mA以上の不平衡でトリップ"}')

                # Step 4: RCD opens contacts to isolate the faulted circuit (not the whole panel)
                # Target is the load/motor circuit, not MainCB
                lines.append(f'    {pid["rcd"]}-->>{pid["loads"]}: {L["action_rcd_isolate"][language]}')
        return "\n".join(lines)

    def generate_display_html(self, mermaid_code, parsed_data, title=None, enable_editing=True):
        language = parsed_data.get("language", "en")
        voltage = parsed_data.get("voltage", "230V / 415V")
        complexity = parsed_data.get("complexity", "Standard")

        if title is None:
            title = "電力配電盤図" if language == "ja" else "Power Distribution Panel Diagram"

        complexity_badge_colors = {"Neutral":  "#f59e0b", "Simple": "#10b981", "Standard": "#3b82f6", "Detailed": "#8b5cf6"}
        complexity_color = complexity_badge_colors.get(complexity, "#f59e0b")

        key_texts = {
            "en": {
                "logic_title": "Key Logic:",
                "logic_items": ["Line (L) passes through Breakers", "Neutral (N) goes direct to Neutral Bar", "Earth (E) goes direct to Earth Bar"],
                "safety_title": "Safety:",
                "safety_items": ["Main Breaker isolates entire panel", "RCD monitors L/N current imbalance — trips faulted circuit at ≥30mA", "Outgoing MCBs protect individual circuits", "Earth (CPC) carries fault current to source — RCD senses the imbalance",],
                "components_title": "Components:",
                "components_items": ["<strong>MCCB:</strong> Molded Case Circuit Breaker", "<strong>MCB:</strong> Miniature Circuit Breaker", "<strong>RCD/RCBO:</strong> Residual Current Device", "<strong>Busbar:</strong> Copper strip for distribution"],
                "generated": "Generated from prompt description",
                "tip": "Tip: Drag any box to move it. Double-click any text to edit it. Edit code below to update diagram.",
                "code_label": "Mermaid Code (edit to update diagram →)",
                "complexity_label": f"Mode: {complexity}",
            },
            "ja": {
                "logic_title": "主要ロジック:",
                "logic_items": ["相線(L)は遮断器を通過", "中性線(N)は中性線バーへ直接接続", "接地線(E)は接地バーへ直接接続"],
                "safety_title": "安全機能:",
                "safety_items": ["主遮断器は全盤を絶縁",  "RCDはL/N電流の不平衡を監視し30mA以上で該当回路を遮断", "出力MCBは個々の回路を保護", "CPC(接地線)が故障電流を電源に帰還させRCDが不平衡を検知",],
                "components_items": ["<strong>MCCB:</strong> モールドケース遮断器", "<strong>MCB:</strong> 配線用遮断器", "<strong>Busbar:</strong> 銅製配電用導体"],
                "generated": "プロンプトから生成",
                "tip": "ヒント: ボックスをドラッグして移動。ダブルクリックでテキストを編集。コードを編集して図を更新。",
                "code_label": "Mermaidコード (編集で図を更新 →)",
                "complexity_label": f"モード: {complexity}",
            }
        }
        key = key_texts.get(language, key_texts["en"])

        # escaped_mermaid = mermaid_code.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

        import html as _html
        html_safe_mermaid = _html.escape(mermaid_code)

        editor_js = """
<script>
class EnhancedMermaidEditor {
    constructor() {
        this.dragState   = null;
        this.lineDrag    = null;
        this.editState   = null;
        this.svgEl       = null;
        this.resizeState = null;   
        this._waitForSVG();
    }

    _waitForSVG() {
        const iv = setInterval(() => {
            const svg = document.querySelector('.mermaid svg');
            if (svg) {
                clearInterval(iv);
                setTimeout(() => this._init(svg), 300);
            }
        }, 100);
    }

    _init(svg) {
        this.svgEl = svg;
        this._fixAllText(svg);
        this._groupActorBoxes(svg);
        this._attachSVGListeners(svg);
    }

    _fixAllText(svg) {
        svg.querySelectorAll('text, tspan').forEach(el => {
            const f = el.getAttribute('fill');
            if (!f || f === 'currentColor' || f === 'inherit' ||
                f === '#ffffff' || f === '#fff' || f === 'white') {
                el.setAttribute('fill', '#1a202c');
            }
        });
    }


    _onNoteResizeStart(e, g, rect, side) {
        const pt = this._screenToSVG(e.clientX, e.clientY);
        this.resizeState = {
            g,
            rect,
            side,                                           // 'left' or 'right'
            startX:    pt.x,
            origX:     parseFloat(rect.getAttribute('x')),
            origWidth: parseFloat(rect.getAttribute('width')),
        };
        rect.style.outline = '2px dashed #f59e0b';         // visual feedback
    }

    _groupActorBoxes(svg) {
        const seen = new Set();
        // After the existing note-grouping loop, add:
        svg.querySelectorAll('rect.actor, rect[class*="actor"]').forEach((rect, idx) => {
            if (seen.has(rect)) return;
            seen.add(rect);

            const rBBox = rect.getBoundingClientRect();
            if (rBBox.width < 4 || rBBox.height < 4) return;

            // Find text labels that overlap this actor rect
            const matchedTexts = Array.from(svg.querySelectorAll('text')).filter(t => {
                if (seen.has(t)) return false;
                const tBBox = t.getBoundingClientRect();
                const tCx = tBBox.left + tBBox.width / 2;
                const tCy = tBBox.top + tBBox.height / 2;
                const tol = 8;
                return (tCx >= rBBox.left - tol && tCx <= rBBox.right + tol &&
                        tCy >= rBBox.top - tol && tCy <= rBBox.bottom + tol);
            });
            matchedTexts.forEach(t => seen.add(t));

            // Also grab the actor LINE (vertical lifeline) associated with this box
            // Mermaid draws lifelines as <line class="actor-line"> sharing the same x center
            const rectCenterX = rBBox.left + rBBox.width / 2;
            const matchedLines = Array.from(svg.querySelectorAll('line.actor-line, line[class*="actor"]')).filter(line => {
                const svgPt = svg.createSVGPoint();
                const lx1 = parseFloat(line.getAttribute('x1'));
                const svgRect = svg.getBoundingClientRect();
                const scaleX = svgRect.width / parseFloat(svg.getAttribute('viewBox')?.split(' ')[2] || svgRect.width);
                const lineScreenX = svgRect.left + lx1 * scaleX;
                return Math.abs(lineScreenX - rectCenterX) < 10;
            });

            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('data-actor-group', `actor-${idx}`);
            g.setAttribute('data-draggable', `actor-${idx}`);
            g.setAttribute('data-tx', '0');
            g.setAttribute('data-ty', '0');
            g.setAttribute('data-actor-lines', JSON.stringify(
                matchedLines.map((_, i) => `actor-line-ref-${idx}-${i}`)
            ));
            g.style.cursor = 'grab';

            rect.parentNode.insertBefore(g, rect);
            g.appendChild(rect);
            matchedTexts.forEach(t => g.appendChild(t));
            // Store line refs but keep lines in DOM (don't move them with box)
            g._actorLines = matchedLines;

            g.addEventListener('mousedown', e => this._onBoxMouseDown(e, g));
            // ... hover effects same as note boxes


                        // After building the note group `g`:
            const toggle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            toggle.textContent = '▲';
            toggle.setAttribute('font-size', '10');
            toggle.setAttribute('fill', '#92400e');
            toggle.setAttribute('cursor', 'pointer');
            toggle.setAttribute('data-collapsed', 'false');

            // Position at top-right corner of the note rect
            const rX = parseFloat(rect.getAttribute('x') || 0);
            const rY = parseFloat(rect.getAttribute('y') || 0);
            const rW = parseFloat(rect.getAttribute('width') || 60);
            toggle.setAttribute('x', rX + rW - 14);
            toggle.setAttribute('y', rY + 12);

            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const collapsed = toggle.getAttribute('data-collapsed') === 'true';
                const noteTexts = g.querySelectorAll('text:not([data-toggle])');
                const noteRect  = g.querySelector('rect');
                
                if (!collapsed) {
                    // Minimize: shrink rect height, hide text
                    noteRect._fullHeight = noteRect.getAttribute('height');
                    noteRect.setAttribute('height', '16');
                    noteTexts.forEach(t => { t._prevVis = t.style.display; t.style.display = 'none'; });
                    toggle.textContent = '▼';
                    toggle.setAttribute('data-collapsed', 'true');
                } else {
                    // Restore
                    if (noteRect._fullHeight) noteRect.setAttribute('height', noteRect._fullHeight);
                    noteTexts.forEach(t => { t.style.display = t._prevVis || ''; });
                    toggle.textContent = '▲';
                    toggle.setAttribute('data-collapsed', 'false');
                }
            });

            toggle.setAttribute('data-toggle', 'true');
            g.appendChild(toggle);
            // After g.appendChild(rect) and texts, add resize handles:
            const MIN_NOTE_WIDTH = 60; // minimum enforced width in SVG units

            ['left', 'right'].forEach(side => {
                const handle = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                const rX = parseFloat(rect.getAttribute('x') || 0);
                const rY = parseFloat(rect.getAttribute('y') || 0);
                const rH = parseFloat(rect.getAttribute('height') || 30);
                const rW = parseFloat(rect.getAttribute('width') || 100);

                handle.setAttribute('x', side === 'left' ? rX - 4 : rX + rW - 4);
                handle.setAttribute('y', rY);
                handle.setAttribute('width', '8');
                handle.setAttribute('height', rH);
                handle.setAttribute('fill', 'transparent');
                handle.setAttribute('cursor', 'ew-resize');
                handle.setAttribute('data-resize-handle', side);
                handle.style.cursor = 'ew-resize';

                handle.addEventListener('mousedown', e => {
                    e.stopPropagation(); // prevent box drag from firing
                    this._onNoteResizeStart(e, g, rect, side);
                });

                g.appendChild(handle);
                // Store handle refs on the group for later repositioning
                if (!g._resizeHandles) g._resizeHandles = {};
                g._resizeHandles[side] = handle;
            });
        });
    }

    _attachSVGListeners(svg) {
        svg.addEventListener('mousemove', e => this._onMouseMove(e));
        svg.addEventListener('mouseup', e => this._onMouseUp(e));
        svg.addEventListener('mouseleave', e => this._onMouseUp(e));
        svg.addEventListener('touchmove', e => this._onTouchMove(e), {passive: false});
        svg.addEventListener('touchend', e => this._onTouchEnd(e), {passive: false});
        svg.addEventListener('mousedown', e => this._onMouseDown(e));
        svg.addEventListener('dblclick', e => this._onDblClick(e));
        window.addEventListener('mousemove', e => this._onMouseMove(e));
        window.addEventListener('mouseup', e => this._onMouseUp(e));
    }

    _screenToSVG(x, y) {
        const pt = this.svgEl.createSVGPoint();
        pt.x = x; pt.y = y;
        return pt.matrixTransform(this.svgEl.getScreenCTM().inverse());
    }

    _onBoxMouseDown(e, g) {
        if (e.target.getAttribute('data-resize-handle')) return;
        e.stopPropagation()
        e.stopPropagation();
        const pt = this._screenToSVG(e.clientX, e.clientY);
        this.dragState = {g, startX: pt.x, startY: pt.y,
            tx: parseFloat(g.getAttribute('data-tx')),
            ty: parseFloat(g.getAttribute('data-ty'))};
        g.style.cursor = 'grabbing';
        g.style.opacity = '0.85';
    }

    _onBoxTouchStart(e, g) {
        e.preventDefault();
        const t = e.touches[0];
        const pt = this._screenToSVG(t.clientX, t.clientY);
        this.dragState = {g, startX: pt.x, startY: pt.y,
            tx: parseFloat(g.getAttribute('data-tx')),
            ty: parseFloat(g.getAttribute('data-ty'))};
    }

    _onMouseDown(e) {
        if (!this._isLineEl(e.target)) return;
        const pt = this._screenToSVG(e.clientX, e.clientY);
        const el = e.target;
        let mode = 'move';
        if (el.tagName.toLowerCase() === 'line') {
            const hit = this._getLineEndpointHit(el, pt);
            if (hit) mode = hit;
        }
        // this.pendingLineDrag = {el, sx: pt.x, sy: pt.y, mode};
    }

    _onMouseMove(e) {
        if (this.resizeState) {
            const pt = this._screenToSVG(e.clientX, e.clientY);
            const dx = pt.x - this.resizeState.startX;
            const { rect, side, origX, origWidth, g } = this.resizeState;
            const MIN_NOTE_WIDTH = 60;

            let newX     = origX;
            let newWidth = origWidth;

            if (side === 'right') {
                // Drag right edge: only width changes, x stays
                newWidth = Math.max(MIN_NOTE_WIDTH, origWidth + dx);
            } else {
                // Drag left edge: x moves right, width shrinks (or x moves left, width grows)
                const proposed = origWidth - dx;
                if (proposed >= MIN_NOTE_WIDTH) {
                    newX     = origX + dx;
                    newWidth = proposed;
                } else {
                    // Clamp to minimum: pin right edge
                    newX     = origX + origWidth - MIN_NOTE_WIDTH;
                    newWidth = MIN_NOTE_WIDTH;
                }
            }

            // Check overlap with sibling note groups before applying
            const wouldOverlap = this._checkNoteOverlap(g, newX, newWidth);
            if (!wouldOverlap) {
                rect.setAttribute('x', newX);
                rect.setAttribute('width', newWidth);
                this._repositionNoteContents(g, rect, newX, newWidth);
                this._repositionHandles(g, rect, newX, newWidth);
            }
            return;
        }

        if (this.dragState) {
            const pt = this._screenToSVG(e.clientX, e.clientY);
            const dx = pt.x - this.dragState.startX;
            let dy = pt.y - this.dragState.startY;

            // Actor boxes: horizontal reposition only (lock Y)
            const isActor = this.dragState.g.getAttribute('data-actor-group')?.startsWith('actor-');
            if (isActor) dy = 0;

            const newTx = this.dragState.tx + dx;
            const newTy = this.dragState.ty + (isActor ? 0 : dy);         
            this.dragState.g.setAttribute('transform', `translate(${newTx},${newTy})`);
            this.dragState.g.setAttribute('data-tx', newTx);
            this.dragState.g.setAttribute('data-ty', newTy);
            return;
        }
        if (this.lineDrag) {
            this._updateLineDrag(e.clientX, e.clientY);
            return;
        }
        if (!this.pendingLineDrag) return;
        const cur = this._screenToSVG(e.clientX, e.clientY);
        const dx = cur.x - this.pendingLineDrag.sx;
        const dy = cur.y - this.pendingLineDrag.sy;
        if (Math.hypot(dx, dy) < 3) return;
        this.lineDrag = {el: this.pendingLineDrag.el, pvx: this.pendingLineDrag.sx, pvy: this.pendingLineDrag.sy, mode: this.pendingLineDrag.mode};
        this.pendingLineDrag = null;
    }

    _onTouchMove(e) {
        e.preventDefault();
        const t = e.touches[0];
        if (this.dragState) {
            const fakeEv = {clientX: t.clientX, clientY: t.clientY};
            this._onMouseMove(fakeEv);
        } else if (this.lineDrag) {
            this._updateLineDrag(t.clientX, t.clientY);
        }
    }

    _repositionNoteContents(g, rect, newX, newWidth) {
        const centerX = newX + newWidth / 2;
        g.querySelectorAll('text').forEach(t => {
            // Only reposition text that isn't a resize handle label
            if (t.getAttribute('data-resize-handle')) return;
            t.setAttribute('x', centerX);
            t.querySelectorAll('tspan').forEach(ts => ts.setAttribute('x', centerX));
        });
    }

    _repositionHandles(g, rect, newX, newWidth) {
        if (!g._resizeHandles) return;
        const rY = parseFloat(rect.getAttribute('y') || 0);
        const rH = parseFloat(rect.getAttribute('height') || 30);

        const lh = g._resizeHandles['left'];
        const rh = g._resizeHandles['right'];

        if (lh) { lh.setAttribute('x', newX - 4);              lh.setAttribute('y', rY); lh.setAttribute('height', rH); }
        if (rh) { rh.setAttribute('x', newX + newWidth - 4);   rh.setAttribute('y', rY); rh.setAttribute('height', rH); }
    }

    _checkNoteOverlap(currentGroup, proposedX, proposedWidth) {
        const proposedRight = proposedX + proposedWidth;
        const allNoteGroups = Array.from(
            this.svgEl.querySelectorAll('[data-actor-group^="note-"]')
        );

        return allNoteGroups.some(g => {
            if (g === currentGroup) return false;
            const r = g.querySelector('rect');
            if (!r) return false;
            const otherX     = parseFloat(r.getAttribute('x'));
            const otherWidth = parseFloat(r.getAttribute('width'));
            const otherRight = otherX + otherWidth;
            const GAP = 4; // minimum gap between boxes in SVG units
            // Overlap if proposed range intersects other range
            return proposedX < otherRight + GAP && proposedRight > otherX - GAP;
        });
    }    

    


    _onMouseUp(e) {
        if (this.dragState) {
            const g = this.dragState.g;
            g.style.cursor = 'grab';
            g.style.opacity = '1';

            // If this was an actor box, reattach vertical lifeline
            if (g._actorLines && g._actorLines.length > 0) {
                const rect = g.querySelector('rect');
                if (rect) {
                    const rBBox = rect.getBoundingClientRect();
                    const svgRect = this.svgEl.getBoundingClientRect();
                    const viewBox = this.svgEl.viewBox.baseVal;
                    const scaleX = viewBox.width / svgRect.width;
                    const newCenterX = (rBBox.left + rBBox.width / 2 - svgRect.left) * scaleX;

                    g._actorLines.forEach(line => {
                        line.setAttribute('x1', newCenterX);
                        line.setAttribute('x2', newCenterX);
                    });
                }
            }

            // Store position for external use
            const tx = parseFloat(g.getAttribute('data-tx'));
            const ty = parseFloat(g.getAttribute('data-ty'));
            g.setAttribute('data-final-x', tx);
            g.setAttribute('data-final-y', ty);

            this.dragState = null;
        }
        if (this.dragState) {
            this.dragState.g.style.cursor = 'grab';
            this.dragState.g.style.opacity = '1';
            this.dragState = null;
        }
    /*    if (this.lineDrag) this._finishLineDrag();
        this.pendingLineDrag = null; */

        if (window.qtBridge && window.qtBridge.onElementEdited) {
            window.qtBridge.onElementEdited(
                g.getAttribute('data-actor-group'),  // element_id
                'actor',                              // element_type
                '',                                   // new_text (empty = position update)
                parseFloat(g.getAttribute('data-tx')),
                parseFloat(g.getAttribute('data-ty'))
            );
        }
        if (this.resizeState) {
            this.resizeState.rect.style.outline = '';   // remove visual feedback
            // Snap to nearest 10px grid (optional but clean)
            const rect  = this.resizeState.rect;
            const snapW = Math.round(parseFloat(rect.getAttribute('width'))  / 10) * 10;
            const snapX = Math.round(parseFloat(rect.getAttribute('x'))      / 10) * 10;
            rect.setAttribute('width', snapW);
            rect.setAttribute('x',     snapX);
            this._repositionNoteContents(this.resizeState.g, rect, snapX, snapW);
            this._repositionHandles(this.resizeState.g, rect, snapX, snapW);
            this.resizeState = null;
        }
    }

    _onTouchEnd(e) {
        if (this.dragState) {
            this.dragState.g.style.opacity = '1';
            this.dragState = null;
        }
        if (this.lineDrag) this._finishLineDrag();
    }

    _getLineEndpointHit(el, pt, tol = 6) {
        const x1 = parseFloat(el.getAttribute('x1'));
        const y1 = parseFloat(el.getAttribute('y1'));
        const x2 = parseFloat(el.getAttribute('x2'));
        const y2 = parseFloat(el.getAttribute('y2'));
        if (Math.hypot(pt.x - x1, pt.y - y1) <= tol) return 'start';
        if (Math.hypot(pt.x - x2, pt.y - y2) <= tol) return 'end';
        return null;
    }

    _isLineEl(el) {
        if (!el) return false;
        const tag = el.tagName.toLowerCase();
        const cls = el.getAttribute('class') || '';
        if (!['line', 'path', 'polyline'].includes(tag)) return false;
        if (!el.getAttribute('stroke')) return false;
        if (cls.includes('actor') || cls.includes('note') || cls.includes('label')) return false;
        if (tag === 'line') {
            const x1 = parseFloat(el.getAttribute('x1') || 0);
            const x2 = parseFloat(el.getAttribute('x2') || 0);
            if (Math.abs(x1 - x2) < 3) return false;
        }
        return true;
    }

    _updateLineDrag(cx, cy) {
        const cur = this._screenToSVG(cx, cy);
        const dx = cur.x - this.lineDrag.pvx;
        const dy = cur.y - this.lineDrag.pvy;
        this.lineDrag.pvx = cur.x;
        this.lineDrag.pvy = cur.y;
        if (this.lineDrag.mode === 'move') this._shiftLineEl(this.lineDrag.el, dx, dy);
        else this._extendLineEl(this.lineDrag.el, dx, dy, this.lineDrag.mode);
    }

    _finishLineDrag() {
        if (!this.lineDrag) return;
        const el = this.lineDrag.el;
        el.style.stroke = '';
        el.style.strokeWidth = '';
        el.style.strokeDasharray = '';
        this.lineDrag = null;
    }

    _extendLineEl(el, dx, dy, which) {
        if (el.tagName.toLowerCase() !== 'line') return;
        if (which === 'start') {
            el.setAttribute('x1', parseFloat(el.getAttribute('x1')) + dx);
            el.setAttribute('y1', parseFloat(el.getAttribute('y1')) + dy);
        }
        if (which === 'end') {
            el.setAttribute('x2', parseFloat(el.getAttribute('x2')) + dx);
            el.setAttribute('y2', parseFloat(el.getAttribute('y2')) + dy);
        }
    }

    _shiftLineEl(el, dx, dy) {
        const tag = el.tagName;
        if (tag === 'line') {
            ['x1','x2'].forEach(a => el.setAttribute(a, parseFloat(el.getAttribute(a)) + dx));
            ['y1','y2'].forEach(a => el.setAttribute(a, parseFloat(el.getAttribute(a)) + dy));
        } else if (tag === 'polyline') {
            const pts = el.getAttribute('points').trim().split(/\s+/).map(p => {
                const [x, y] = p.split(',').map(parseFloat);
                return `${x + dx},${y + dy}`;
            });
            el.setAttribute('points', pts.join(' '));
        } else if (tag === 'path') {
            const d = el.getAttribute('d').replace(
                /([ML])\s*([\d.+-]+)[,\s]+([\d.+-]+)/gi,
                (_, cmd, x, y) => `${cmd}${parseFloat(x)+dx},${parseFloat(y)+dy}`
            );
            el.setAttribute('d', d);
        }
    }

    _onDblClick(e) {
        if (this.lineDrag) return;
        let textEl = null;
        if (e.target.tagName === 'text')  textEl = e.target;
        if (e.target.tagName === 'tspan') textEl = e.target.parentElement;
        if (!textEl) return;
        const current = this._getTextContent(textEl);
        if (!current.trim()) return;
        this._openTextEditor(textEl, current);
    }

    _getTextContent(el) {
        const spans = el.querySelectorAll('tspan');
        if (spans.length) return Array.from(spans).map(s => s.textContent).join('\\n');
        return el.textContent || '';
    }

    _openTextEditor(textEl, current) {
        const rect = textEl.getBoundingClientRect();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = current;
        Object.assign(input.style, {
            position: 'fixed',
            left: rect.left + 'px',
            top: rect.top + 'px',
            width: Math.max(rect.width + 24, 160) + 'px',
            height: rect.height + 10 + 'px',
            zIndex: '10000',
            padding: '3px 8px',
            border: '2px solid #4299e1',
            borderRadius: '4px',
            fontSize: window.getComputedStyle(textEl).fontSize,
            fontFamily: window.getComputedStyle(textEl).fontFamily,
            fontWeight: window.getComputedStyle(textEl).fontWeight,
            color: '#000',
            backgroundColor: '#fff',
            boxShadow: '0 4px 12px rgba(0,0,0,0.18)',
            outline: 'none',
        });
        document.body.appendChild(input);
        this.editState = {input, textEl, original: current};
        input.focus(); input.select();

        const done = (save) => {
            const val = input.value.trim();
            if (save && val && val !== current) {
                this._applyTextEdit(textEl, val);
                this._syncDiagramToCode();
                if (window.qtBridge && window.qtBridge.onElementEdited) {
                    const r = textEl.getBoundingClientRect();
                    window.qtBridge.onElementEdited('el_'+Date.now(), 'text', val, r.left, r.top);
                }
            }
            document.body.removeChild(input);
            this.editState = null;
        };

        input.addEventListener('keydown', e => {
            if (e.key === 'Enter')  { e.preventDefault(); done(true); }
            if (e.key === 'Escape') { e.preventDefault(); done(false); }
        });
        input.addEventListener('blur', () => done(true));
    }

    _applyTextEdit(textEl, newVal) {
        const spans = textEl.querySelectorAll('tspan');
        const lines = newVal.split('\\n');
        if (spans.length) {
            spans.forEach((s, i) => { if (i < lines.length) s.textContent = lines[i]; });
        } else {
            textEl.textContent = newVal;
        }
    }

    _syncDiagramToCode() {
        const codeArea = document.getElementById('mermaid-code-editor');
        if (!codeArea) return;

        const groups = document.querySelectorAll('[data-actor-group]');
        let code = codeArea.value;

        groups.forEach(g => {
            const textEls = g.querySelectorAll('text');
            if (!textEls.length) return;
            const newLabel = Array.from(textEls).map(t => {
                const spans = t.querySelectorAll('tspan');
                return spans.length
                    ? Array.from(spans).map(s => s.textContent).join('<br/>')
                    : t.textContent;
            }).join('<br/>').trim();

            if (!newLabel) return;

            code = code.replace(
                /(participant\s+\w+\s+as\s+).+/,
                (match, prefix) => prefix + newLabel
            );
        });

        codeArea.value = code;
        if (window.qtBridge && window.qtBridge.onDiagramTextChanged) {
            window.qtBridge.onDiagramTextChanged(code);
        }
    }
}

function applyCodeToDiagram() {
    const codeArea = document.getElementById('mermaid-code-editor');
    const container = document.getElementById('mermaid-container');
    if (!codeArea || !container) return;

    const code = codeArea.value.trim();
    if (!code) return;

    container.innerHTML = '<div class="mermaid">' + code + '</div>';

    if (window.mermaid) {
        try {
            window.mermaid.run({nodes: container.querySelectorAll('.mermaid')}).then(() => {
                setTimeout(() => {
                    window.mermaidEditor = new EnhancedMermaidEditor();
                }, 400);
            });
        } catch(e) {
            console.error('Mermaid render error:', e);
            container.innerHTML = '<p style="color:red;padding:12px;">⚠ Mermaid syntax error. Check the code and try again.</p>';
        }
    }

    if (window.qtBridge && window.qtBridge.onDiagramTextChanged) {
        window.qtBridge.onDiagramTextChanged(code);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { window.mermaidEditor = new EnhancedMermaidEditor(); }, 400);

    const applyBtn = document.getElementById('apply-code-btn');
    if (applyBtn) applyBtn.addEventListener('click', applyCodeToDiagram);

    const codeArea = document.getElementById('mermaid-code-editor');
    if (codeArea) {
        codeArea.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                applyCodeToDiagram();
            }
        });
    }
});
</script>
<style>
.mermaid svg text,
.mermaid svg tspan { fill: #1a202c !important; }
[data-actor-group], [data-draggable] { cursor: grab; }
[data-actor-group]:active, [data-draggable]:active { cursor: grabbing; }
[data-actor-group]:hover rect,
[data-draggable]:hover rect {
    filter: drop-shadow(0 0 5px rgba(66,153,225,0.6));
}
[data-actor-group], [data-draggable] { transition: opacity 0.1s ease; }
.mermaid svg line:hover,
.mermaid svg path:hover,
.mermaid svg polyline:hover {
    stroke-width: 3px !important;
    cursor: move !important;
}
#mermaid-code-editor {
    width: 100%;
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
    color: #1a202c;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s;
}
#mermaid-code-editor:focus {
    border-color: #4299e1;
    box-shadow: 0 0 0 3px rgba(66,153,225,0.15);
}
#apply-code-btn {
    background: #2c5282;
    color: #fff;
    border: none;
    border-radius: 5px;
    padding: 7px 18px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 6px;
    transition: background 0.15s;
}
#apply-code-btn:hover { background: #2a4365; }
.code-panel-label {
    font-size: 11px;
    font-weight: 600;
    color: #718096;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 4px;
    margin-top: 14px;
}
.apply-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 6px;
}
.apply-hint {
    font-size: 11px;
    color: #a0aec0;
}
</style>
"""

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
window.mermaid = mermaid;
mermaid.initialize({{
    startOnLoad: true,
    theme: 'base',
    themeVariables: {{
        primaryColor: '#e0e7ff',
        primaryTextColor: '#1a202c',
        secondaryTextColor: '#1a202c',
        tertiaryTextColor: '#1a202c',
        noteTextColor: '#1a202c',
        noteBkgColor: '#fffacd',
        actorBkgColor: '#e0e7ff',
        actorBorderColor: '#a5b4fc',
        actorTextColor: '#1a202c',
        labelBoxBkgColor: '#f0fdf4',
        labelBoxBorderColor: '#86efac',
        labelTextColor: '#1a202c',
        fontFamily: 'Arial, sans-serif',
        fontSize: '15px'
    }}
}});
</script>
{"" if not enable_editing else editor_js}
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f4f8;
    padding: 20px;
    min-height: 100vh;
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
    padding: 28px 32px 24px;
    position: relative;
}}
.badge-row {{
    position: absolute;
    top: 16px; right: 20px;
    display: flex; gap: 6px; align-items: center;
}}
.lang-badge {{
    background: {'#3b82f6' if language == 'en' else '#ef4444'};
    color: #fff;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
.complexity-badge {{
    background: {complexity_color};
    color: #fff;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
.header {{ text-align: center; margin-bottom: 20px; }}
.header h1 {{ font-size: 26px; font-weight: 700; color: #1a202c; margin-bottom: 6px; }}
.header p  {{ color: #718096; font-size: 13px; }}
.voltage-pill {{
    display: inline-block;
    background: #edf2f7; padding: 3px 12px;
    border-radius: 20px; font-size: 12px; color: #4a5568;
    margin-left: 8px;
}}
.tip-bar {{
    background: #fefce8; border: 1px solid #fde68a;
    border-radius: 8px; padding: 8px 14px;
    font-size: 12px; color: #92400e;
    text-align: center; margin-bottom: 16px;
}}
.mermaid-wrap {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    overflow: auto;
    user-select: none;
    -webkit-user-select: none;
}}
.mermaid {{ min-height: 200px; }}
.key-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #e2e8f0;
}}
.key-card {{
    background: #f9fafb;
    border-radius: 8px;
    padding: 12px 14px;
}}
.key-card strong {{ display: block; margin-bottom: 6px; font-size: 13px; }}
.key-card ul {{ padding-left: 18px; margin: 0; }}
.key-card li {{ font-size: 12px; color: #4a5568; margin-bottom: 3px; }}
.blue  {{ color: #1d4ed8; }}
.green {{ color: #047857; }}
.amber {{ color: #b45309; }}
</style>
</head>
<body>
<div class="container">
    <div class="badge-row">
        <span class="complexity-badge">{key['complexity_label']}</span>
        <span class="lang-badge">{'English' if language == 'en' else '日本語'}</span>
    </div>
    <div class="header">
        <h1>{title}</h1>
        <p>{key['generated']} <span class="voltage-pill">⚡ {voltage}</span></p>
    </div>
    <div class="tip-bar">{key['tip']}</div>
    <div class="mermaid-wrap" id="diagram-root">
        <div id="mermaid-container">
            <div class="mermaid">
{html_safe_mermaid}
            </div>
        </div>
    </div>

    <div class="code-panel-label">{key['code_label']}</div>
    <textarea id="mermaid-code-editor" rows="10">{html_safe_mermaid}</textarea>
    <div class="apply-row">
        <button id="apply-code-btn">▶ Apply (Ctrl+↵)</button>
        <span class="apply-hint">Ctrl+Enter to apply • diagram edits sync here</span>
    </div>

    <div class="key-grid">
        <div class="key-card">
            <strong class="blue">{key['logic_title']}</strong>
            <ul>{''.join(f'<li>{i}</li>' for i in key['logic_items'])}</ul>
        </div>
        <div class="key-card">
            <strong class="green">{key['safety_title']}</strong>
            <ul>{''.join(f'<li>{i}</li>' for i in key['safety_items'])}</ul>
        </div>
        <div class="key-card">
            <strong class="amber">{key['components_title']}</strong>
            <ul>{''.join(f'<li>{i}</li>' for i in key['components_items'])}</ul>
        </div>
    </div>
</div>
</body>
</html>'''
        return html


class ElementEditorDialog(QDialog):
    def __init__(self, element_id, element_type, current_text, parent=None):
        super().__init__(parent)
        self.element_id = element_id
        self.element_type = element_type
        self.current_text = current_text
        self.new_text = current_text
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle(f"Edit {self.element_type}")
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)

        lbl = QLabel(f"Editing {self.element_type}")
        lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#2c5282;")
        lay.addWidget(lbl)

        lay.addWidget(QLabel("New text:"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.current_text)
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setStyleSheet("border:2px solid #4299e1;border-radius:5px;padding:6px;")
        lay.addWidget(self.text_edit)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def get_new_text(self):
        return self.text_edit.toPlainText()


class CodeEditorPanel(QWidget):
    codeChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        lbl = QLabel("📝 Mermaid Code")
        lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#2c5282;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        self.apply_btn = QPushButton("▶ Apply  Ctrl+ENTER")
        self.apply_btn.setStyleSheet("""
            QPushButton {background:#2c5282;color:#fff;border:none;border-radius:4px;
                         padding:5px 12px;font-size:11px;font-weight:bold;}
            QPushButton:hover {background:#2a4365;}
        """)
        self.apply_btn.clicked.connect(self._apply)
        hdr.addWidget(self.apply_btn)
        lay.addLayout(hdr)

        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier New", 10))
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background:#1e2434; color:#e2e8f0;
                border:1px solid #4a5568; border-radius:6px; padding:8px;
            }
        """)
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.editor)
        shortcut.activated.connect(self._apply)
        lay.addWidget(self.editor)

        hint = QLabel("Ctrl+Enter to apply")
        hint.setFont(QFont("Arial", 9))
        hint.setStyleSheet("color:#718096;")
        lay.addWidget(hint)

        self.setMinimumHeight(180)

    def set_code(self, code: str):
        if self.editor.toPlainText() != code:
            self.editor.setPlainText(code)

    def get_code(self) -> str:
        return self.editor.toPlainText()

    def _apply(self):
        self.codeChanged.emit(self.get_code())



class ValidationPanel(QWidget):
    fixRequested = Signal()   # emitted when user clicks "Fix Issues"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_findings: list = []
        self._build_ui()
        self.hide()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        header = QHBoxLayout()
        self.icon_lbl = QLabel("🔍")
        self.title_lbl = QLabel("Validating diagram…")
        self.title_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header.addWidget(self.icon_lbl)
        header.addWidget(self.title_lbl)
        header.addStretch()

        # Fix Issues button — enabled only when there are real findings
        self.fix_btn = QPushButton("🔧 Fix Issues")
        self.fix_btn.setFixedHeight(24)
        self.fix_btn.setEnabled(False)
        self.fix_btn.setStyleSheet("""
            QPushButton {
                background:#c53030;color:#fff;
                border:none;border-radius:4px;
                padding:2px 10px;font-size:11px;font-weight:bold;
            }
            QPushButton:hover   { background:#9b2c2c; }
            QPushButton:pressed { background:#742a2a; }
            QPushButton:disabled{ background:#cbd5e0;color:#718096; }
        """)
        self.fix_btn.setToolTip("Auto-patch the diagram to resolve the findings above")
        self.fix_btn.clicked.connect(self._on_fix_clicked)
        header.addWidget(self.fix_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet("border:none; color:#718096; font-size:12px;")
        self.close_btn.clicked.connect(self.hide)
        header.addWidget(self.close_btn)
        lay.addLayout(header)

        self.findings_lbl = QLabel("")
        self.findings_lbl.setWordWrap(True)
        self.findings_lbl.setFont(QFont("Arial", 9))
        lay.addWidget(self.findings_lbl)

        self.setStyleSheet("""
            ValidationPanel {
                border: 1px solid #fed7aa;
                border-radius: 6px;
                background: #fff7ed;
            }
        """)
        self.setMaximumHeight(140)

    def set_findings(self, findings: list):
        """Store parsed findings so the Fix button can forward them."""
        self._current_findings = findings
        self.fix_btn.setEnabled(bool(findings))

    def _on_fix_clicked(self):
        self.fixRequested.emit()

    def show_loading(self):
        self.setStyleSheet("ValidationPanel{border:1px solid #bee3f8;border-radius:6px;background:#ebf8ff;}")
        self.icon_lbl.setText("🔍")
        self.title_lbl.setText("Validating diagram against prompt…")
        self.findings_lbl.setText("")
        self.fix_btn.setEnabled(False)
        self._current_findings = []
        self.show()

    def show_fixing(self):
        """Called when MermaidFixWorker starts — disables Fix button, shows progress."""
        self.setStyleSheet("ValidationPanel{border:1px solid #fbd38d;border-radius:6px;background:#fffbeb;}")
        self.icon_lbl.setText("🔧")
        self.title_lbl.setText("Applying fixes…")
        self.title_lbl.setStyleSheet("color:#b7791f;")
        self.findings_lbl.setText("LLM is patching the diagram. This may take a few seconds.")
        self.fix_btn.setEnabled(False)
        self.show()

    def show_fix_error(self, error_msg: str):
        """Called when MermaidFixWorker fails."""
        self.setStyleSheet("ValidationPanel{border:1px solid #feb2b2;border-radius:6px;background:#fff5f5;}")
        self.icon_lbl.setText("❌")
        self.title_lbl.setText("Fix failed")
        self.title_lbl.setStyleSheet("color:#c53030;")
        self.findings_lbl.setText(f"Could not apply fix: {error_msg[:200]}")
        self.fix_btn.setEnabled(bool(self._current_findings))  # re-enable so user can retry
        self.show()

    def show_result(self, text: str, has_issues: bool):
        if has_issues:
            self.setStyleSheet("ValidationPanel{border:1px solid #feb2b2;border-radius:6px;background:#fff5f5;}")
            self.icon_lbl.setText("⚠️")
            self.title_lbl.setText("Potential issues found")
            self.title_lbl.setStyleSheet("color:#c53030;")
        else:
            self.setStyleSheet("ValidationPanel{border:1px solid #9ae6b4;border-radius:6px;background:#f0fff4;}")
            self.icon_lbl.setText("✅")
            self.title_lbl.setText("Diagram looks good")
            self.title_lbl.setStyleSheet("color:#276749;")
            self.fix_btn.setEnabled(False)

        findings = ""
        if "FINDINGS:" in text:
            findings = text.split("FINDINGS:")[-1].strip()
        self.findings_lbl.setText(findings if findings and findings != "None" else "")
        self.show()


class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.generator = MermaidGenerator()
        self.current_parsed_data = None
        self.original_parsed_data = None
        self.web_bridge = WebBridge()
        self._current_mermaid_code = ""
        self._build_ui()
        self._setup_channel()
        self.web_bridge.elementEdited.connect(self._on_element_edited)
        self.web_bridge.diagramChanged.connect(self._on_diagram_text_changed)
        self._last_prompt = ""
        self._validation_worker = None
        self._gen_worker = None
        self._fix_worker = None

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(500)
        self.web_bridge.elementDoubleClicked.connect(self._on_element_dblclicked)
        lay.addWidget(self.web_view)
        self.validation_panel = ValidationPanel()
        lay.addWidget(self.validation_panel)
        # "Fix Issues" button in the panel triggers auto-correction using stored findings
        self.validation_panel.fixRequested.connect(
            lambda: self._on_validation_issues_found(self.validation_panel._current_findings)
        )

        # Stub: code panel lives inside the WebView HTML now
        self.code_panel = type('_Stub', (), {
            'set_code': lambda self, c: None,
            'get_code': lambda self: ''
        })()

    def _setup_channel(self):
        ch = QWebChannel(self.web_view.page())
        ch.registerObject("qtBridge", self.web_bridge)
        self.web_view.page().setWebChannel(ch)
        self._show_welcome()

    def closeEvent(self, event):
        if self._validation_worker is not None and self._validation_worker.isRunning():
            self._validation_worker.quit()
            self._validation_worker.wait(5000)

        super().closeEvent(event)


    # ── Add this method to DiagramCanvas ─────────────────────────────────────
    def _show_welcome(self):
        """Display a branded welcome screen before any diagram is generated."""
        html = """<!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        background: #f0f4f8;
        height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .welcome-card {
        text-align: center;
        background: #ffffff;
        border-radius: 16px;
        padding: 56px 72px;
        box-shadow: 0 4px 32px rgba(44,82,130,0.12);
        max-width: 560px;
    }
    .icon { font-size: 64px; margin-bottom: 20px; }
    h1 {
        font-size: 26px;
        font-weight: 700;
        color: #2c5282;
        margin-bottom: 10px;
        letter-spacing: -0.5px;
    }
    .subtitle {
        font-size: 14px;
        color: #718096;
        margin-bottom: 32px;
        line-height: 1.6;
    }
    .steps {
        display: flex;
        justify-content: center;
        gap: 24px;
        flex-wrap: wrap;
    }
    .step {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
        width: 130px;
    }
    .step-num {
        background: #ebf4ff;
        color: #2c5282;
        font-weight: 700;
        font-size: 13px;
        border-radius: 50%;
        width: 32px; height: 32px;
        display: flex; align-items: center; justify-content: center;
    }
    .step-txt { font-size: 12px; color: #4a5568; text-align: center; line-height: 1.4; }
    .divider { color: #cbd5e0; font-size: 20px; margin-top: 8px; }
    </style>
    </head>
    <body>
    <div class="welcome-card">
    <div class="icon">⚡</div>
    <h1>Electrical Diagram Generator</h1>
    <p class="subtitle">
        Describe your electrical system in plain language<br>
        and get a professional distribution diagram instantly.
    </p>
    <div class="steps">
        <div class="step">
        <div class="step-num">1</div>
        <div class="step-txt">Type a description in the panel</div>
        </div>
        <div class="divider">→</div>
        <div class="step">
        <div class="step-num">2</div>
        <div class="step-txt">Choose a detail level</div>
        </div>
        <div class="divider">→</div>
        <div class="step">
        <div class="step-num">3</div>
        <div class="step-txt">Press ⚡ Generate Diagram</div>
        </div>
    </div>
    </div>
    </body>
    </html>"""
        self.web_view.setHtml(html)


    def _show_loading(self):
        """Replace the canvas with an animated loading screen while generating."""
        html = """<!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        background: #f0f4f8;
        height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .card {
        text-align: center;
        background: #ffffff;
        border-radius: 16px;
        padding: 56px 72px;
        box-shadow: 0 4px 32px rgba(44,82,130,0.12);
    }
    .spinner {
        width: 56px; height: 56px;
        border: 5px solid #ebf4ff;
        border-top-color: #2c5282;
        border-radius: 50%;
        animation: spin 0.9s linear infinite;
        margin: 0 auto 24px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    h2 { font-size: 20px; color: #2c5282; font-weight: 700; margin-bottom: 8px; }
    p  { font-size: 13px; color: #718096; }
    </style>
    </head>
    <body>
    <div class="card">
    <div class="spinner"></div>
    <h2>Generating Diagram…</h2>
    <p>Parsing your description and building the diagram.<br>This may take a few seconds.</p>
    </div>
    </body>
    </html>"""
        self.web_view.setHtml(html)

    def generate_from_prompt_OLD_BLOCKING(self, prompt_text, complexity_level="Neutral"):
        try:
            prompt_text = prompt_text.strip()
            if not prompt_text:
                QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
                return False

            self._show_loading()
            parsed_data = None

            # ── Step 1: Parse prompt via LLM ──────────────────────────────────────
            try:
                ollama = OllamaClient()
                parsed_data = ollama.prompt_to_structured_data(prompt_text, complexity_level)

                if not isinstance(parsed_data, dict) or "components" not in parsed_data:
                    raise ValueError("Invalid LLM output — missing components key")

                # ── Hard safety minimum: supply and maincb must always exist ──────
                # Normalise LLM components to clean (id, label) tuples immediately after parsing
                parsed_data["components"] = [
                    (c[0], c[1]) if isinstance(c, (list, tuple)) and len(c) >= 2 else (str(c), str(c))
                    for c in parsed_data["components"]
                ]
                comp_ids = [c for c, _ in parsed_data["components"]]  # now safe                lang = parsed_data.get("language", "en")
                
                voltage = parsed_data.get("voltage", "230V / 415V")
                if "supply" not in comp_ids:
                    parsed_data["components"].insert(0, (
                        "supply",
                        self.generator.components_map["main incoming supply"][lang].replace("230V / 415V", voltage)
                    ))
                if "maincb" not in comp_ids:
                    parsed_data["components"].insert(1, (
                        "maincb",
                        self.generator.components_map["main breaker"][lang]
                    ))

                # Only inject if prompt didn't explicitly exclude them
                explicit_no_breaker = any(p in prompt_text.lower() for p in ["no breaker", "direct connection", "no maincb"])
                if "supply" not in comp_ids:
                    parsed_data["components"].insert(0, ("supply", ...))
                if "maincb" not in comp_ids and not explicit_no_breaker:
                    parsed_data["components"].insert(1, ("maincb", ...))

                # For complexity filtering: keep anything the LLM explicitly included
                llm_comp_ids = set(c for c, _ in parsed_data["components"])
                if complexity_level != "Neutral":
                    allowed_ids = set(COMPLEXITY_LEVELS[complexity_level]["components"])
                    allow_outcb = COMPLEXITY_LEVELS[complexity_level].get("allow_outcb", False)
                else:
                    # Neutral = prompt-driven, accept everything the LLM returned
                    allowed_ids = set(c for c, _ in parsed_data["components"])
                    allow_outcb = True
                # Components that are explicitly named in the raw prompt text
                prompt_lower = prompt_text.lower()
                COMPONENT_KEYWORDS = {
                    "rcd":  ["rcd", "residual current", "rcbo", "earth fault"],
                    "nbar": ["neutral bar", "neutral link"],
                    "ebar": ["earth bar", "earth terminal"],
                    "bus":  ["busbar", "bus bar", "copper bar"],
                }

                def prompt_mentions(cid):
                    return any(kw in prompt_lower for kw in COMPONENT_KEYWORDS.get(cid, []))

                parsed_data["components"] = [
                    (c, l) for c, l in parsed_data["components"]
                    if c in allowed_ids
                    or (allow_outcb and c.startswith("outcb_"))
                    or prompt_mentions(c)   # ← only survive if prompt LITERALLY says them
                ]

                # ── After line 2185: backfill complexity defaults for non-Neutral modes ──
                if complexity_level != "Neutral":
                    explicit_exclusions = {
                        "rcd":  ["no rcd", "no residual", "no earth fault"],
                        "nbar": ["no neutral"],
                        "ebar": ["no earth", "no ground"],
                        "bus":  ["no busbar", "no bus"],
                        "maincb": ["no breaker", "direct connection", "no maincb"],
                    }
                    current_ids = {c for c, _ in parsed_data["components"]}
                    lang = parsed_data.get("language", "en")
                    voltage = parsed_data.get("voltage", "230V / 415V")
                    defaults = self.generator.get_default_components(lang, voltage, complexity_level)
                    
                    for cid, lbl in defaults:
                        if cid not in current_ids and not cid.startswith("outcb_"):
                            excluded = any(ex in prompt_lower for ex in explicit_exclusions.get(cid, []))
                            if not excluded:
                                parsed_data["components"].append((cid, lbl))

                if complexity_level == "Detailed":
                    has_outcb = any(c.startswith("outcb_") for c, _ in parsed_data["components"])
                    if not has_outcb:
                        lang = parsed_data.get("language", "en")
                        generic_label = self.generator.components_map["outgoing mcbs"][lang]
                        parsed_data["components"].insert(-1, ("outcb_1", generic_label))

                parsed_data["complexity"] = complexity_level
                parsed_data["prompt"] = prompt_text    # ← store original prompt for generator to read
                parsed_data["language"] = self.generator.detect_language(prompt_text)
                print(f"Parsed via LLM ")

            except Exception as llm_err:
            
                print(f"LLM parsing failed, using regex fallback: {llm_err}")
                parsed_data = self.generator.parse_prompt(prompt_text, complexity_level)

            self.current_parsed_data = parsed_data
            self.original_parsed_data = parsed_data.copy()

            # ── Step 2: Generate Mermaid code ─────────────────────────────────────
            mermaid_code = self.generator.generate_mermaid_code(parsed_data)
            self._current_mermaid_code = mermaid_code
            self.code_panel.set_code(mermaid_code)

            html = self.generator.generate_display_html(mermaid_code, parsed_data, enable_editing=True)
            self.web_view.setHtml(html)

            if self.parent_window and hasattr(self.parent_window, 'status'):
                lang_name = "English" if parsed_data.get("language") == "en" else "Japanese"
                self.parent_window.status.showMessage(
                    f"Diagram generated ({lang_name}, {complexity_level}), "
                    f"{len(parsed_data.get('components', []))} components. "
                    "Drag boxes · Double-click text · Edit code below.", 6000)

            # ── Step 3: Async validation ───────────────────────────────────────────
            self._last_prompt = prompt_text
            self._run_validation(prompt_text, mermaid_code)
            return True

        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")
            return False


    # ── Async generation (non-blocking) ───────────────────────────────────────

    def generate_from_prompt(self, prompt_text, complexity_level="Neutral"):
        """Kick off diagram generation asynchronously so the UI stays responsive."""
        prompt_text = prompt_text.strip()
        if not prompt_text:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
            return False

        # Cancel any in-flight generation worker
        if getattr(self, "_gen_worker", None) is not None:
            if self._gen_worker.isRunning():
                self._gen_worker.requestInterruption()
                self._gen_worker.quit()
                self._gen_worker.wait(2000)
            self._gen_worker.deleteLater()
            self._gen_worker = None

        self._show_loading()
        self._pending_prompt     = prompt_text
        self._pending_complexity = complexity_level

        self._gen_worker = GenerationWorker(prompt_text, complexity_level, self.generator)
        self._gen_worker.finished.connect(self._on_llm_finished)
        self._gen_worker.failed.connect(self._on_llm_failed)
        self._gen_worker.start()
        return True   # returns immediately; diagram arrives via signal

    def _on_llm_failed(self, error_msg: str):
        """LLM unavailable — fall back to fast regex parser on the main thread."""
        print(f"LLM parsing failed, using regex fallback: {error_msg}")
        try:
            parsed_data = self.generator.parse_prompt(
                self._pending_prompt, self._pending_complexity)
            self._finalise_generation(parsed_data, self._pending_prompt, self._pending_complexity)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")

    def _on_llm_finished(self, parsed_data: dict):
        """Called on the main thread once the background LLM call succeeds."""
        prompt_text      = self._pending_prompt
        complexity_level = self._pending_complexity
        try:
            comp_ids = [c for c, _ in parsed_data["components"]]
            lang     = parsed_data.get("language", self.generator.detect_language(prompt_text))
            voltage  = parsed_data.get("voltage", "230V / 415V")

            # Safety minimum
            if "supply" not in comp_ids:
                parsed_data["components"].insert(0, (
                    "supply",
                    self.generator.components_map["main incoming supply"][lang].replace("230V / 415V", voltage)
                ))
            explicit_no_breaker = any(
                p in prompt_text.lower()
                for p in ["no breaker", "direct connection", "no maincb"])
            if "maincb" not in comp_ids and not explicit_no_breaker:
                parsed_data["components"].insert(1, (
                    "maincb", self.generator.components_map["main breaker"][lang]))

            # Complexity filtering
            prompt_lower = prompt_text.lower()
            COMPONENT_KEYWORDS = {
                "rcd":  ["rcd", "residual current", "rcbo", "earth fault"],
                "nbar": ["neutral bar", "neutral link"],
                "ebar": ["earth bar", "earth terminal"],
                "bus":  ["busbar", "bus bar", "copper bar"],
            }
            def prompt_mentions(cid):
                return any(kw in prompt_lower for kw in COMPONENT_KEYWORDS.get(cid, []))

            if complexity_level != "Neutral":
                allowed_ids = set(COMPLEXITY_LEVELS[complexity_level]["components"])
                allow_outcb = COMPLEXITY_LEVELS[complexity_level].get("allow_outcb", False)
            else:
                allowed_ids = set(c for c, _ in parsed_data["components"])
                allow_outcb = True

            parsed_data["components"] = [
                (c, l) for c, l in parsed_data["components"]
                if c in allowed_ids
                or (allow_outcb and c.startswith("outcb_"))
                or prompt_mentions(c)
            ]

            # Backfill defaults for non-Neutral modes
            if complexity_level != "Neutral":
                explicit_exclusions = {
                    "rcd":    ["no rcd", "no residual", "no earth fault"],
                    "nbar":   ["no neutral"],
                    "ebar":   ["no earth", "no ground"],
                    "bus":    ["no busbar", "no bus"],
                    "maincb": ["no breaker", "direct connection", "no maincb"],
                }
                current_ids = {c for c, _ in parsed_data["components"]}
                defaults    = self.generator.get_default_components(lang, voltage, complexity_level)
                for cid, lbl in defaults:
                    if cid not in current_ids and not cid.startswith("outcb_"):
                        if not any(ex in prompt_lower for ex in explicit_exclusions.get(cid, [])):
                            parsed_data["components"].append((cid, lbl))

            if complexity_level == "Detailed":
                if not any(c.startswith("outcb_") for c, _ in parsed_data["components"]):
                    generic_label = self.generator.components_map["outgoing mcbs"][lang]
                    parsed_data["components"].insert(-1, ("outcb_1", generic_label))

            parsed_data["complexity"] = complexity_level
            parsed_data["prompt"]     = prompt_text
            parsed_data["language"]   = self.generator.detect_language(prompt_text)
            print("Parsed via LLM")
            self._finalise_generation(parsed_data, prompt_text, complexity_level)

        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")

    def _finalise_generation(self, parsed_data: dict, prompt_text: str, complexity_level: str):
        """Shared final step: build Mermaid, render HTML, kick off async validation."""
        self.current_parsed_data  = parsed_data
        self.original_parsed_data = parsed_data.copy()

        mermaid_code = self.generator.generate_mermaid_code(parsed_data)
        self._current_mermaid_code = mermaid_code
        self.code_panel.set_code(mermaid_code)

        html = self.generator.generate_display_html(mermaid_code, parsed_data, enable_editing=True)
        self.web_view.setHtml(html)

        if self.parent_window and hasattr(self.parent_window, "status"):
            lang_name = "English" if parsed_data.get("language") == "en" else "Japanese"
            self.parent_window.status.showMessage(
                f"Diagram generated ({lang_name}, {complexity_level}), "
                f"{len(parsed_data.get('components', []))} components. "
                "Drag boxes · Double-click text · Edit code below.", 6000)

        # Re-enable the sidebar Reset button
        if self.parent_window and hasattr(self.parent_window, "sidebar"):
            self.parent_window.sidebar.reset_btn.setEnabled(True)

        self._last_prompt = prompt_text
        self._run_validation(prompt_text, mermaid_code)

    # ─────────────────────────────────────────────────────────────────────────
    def _on_diagram_text_changed(self, new_code: str):
        self._current_mermaid_code = new_code
        self.code_panel.set_code(new_code)

    def _on_qt_code_changed(self, new_code: str):
        self._current_mermaid_code = new_code
        escaped = new_code.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
        js = f"""
(function() {{
    var ta = document.getElementById('mermaid-code-editor');
    if (ta) ta.value = `{escaped}`;
    if (typeof applyCodeToDiagram === 'function') applyCodeToDiagram();
}})();
"""
        self.web_view.page().runJavaScript(js, 0)
        if self.parent_window and hasattr(self.parent_window, 'status'):
            self.parent_window.status.showMessage("✓ Diagram updated from code", 2000)

    def _on_element_dblclicked(self, element_id, element_type, current_text):
        dlg = ElementEditorDialog(element_id, element_type, current_text, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_text = dlg.get_new_text()
            self._update_parsed_data(element_id, element_type, new_text)
            self.refresh_diagram()
            if self.parent_window and hasattr(self.parent_window, 'status'):
                self.parent_window.status.showMessage(f"Updated {element_type}: {new_text[:50]}", 3000)

    def _update_parsed_data(self, element_id, element_type, new_text):
        if not self.current_parsed_data:
            return
        components = self.current_parsed_data["components"]
        if element_type == "participant":
            for i, (cid, lbl) in enumerate(components):
                if any(k in new_text.lower() for k in cid.lower().split('_')):
                    new_lbl = new_text.replace("\n", "<br/>")
                    components[i] = (cid, new_lbl)
                    break
        self.current_parsed_data["components"] = components

    def refresh_diagram(self):
        if not self.current_parsed_data:
            return
        try:
            mc = self.generator.generate_mermaid_code(self.current_parsed_data)
            self._current_mermaid_code = mc
            self.code_panel.set_code(mc)
            html = self.generator.generate_display_html(mc, self.current_parsed_data, enable_editing=True)
            self.web_view.setHtml(html)
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", str(e))

    def _run_validation(self, prompt: str, mermaid_code: str):
        self.validation_panel.show_loading()

        if self._validation_worker is not None:
            if self._validation_worker.isRunning():
                self._validation_worker.requestInterruption()
                self._validation_worker.quit()
                self._validation_worker.wait(3000)
            self._validation_worker.deleteLater()
            self._validation_worker = None

        complexity = self.current_parsed_data.get("complexity", "Standard") \
                    if self.current_parsed_data else "Standard"

        self._validation_worker = ValidationWorker(prompt, mermaid_code, complexity)
        self._validation_worker.validationComplete.connect(self.validation_panel.show_result)
        self._validation_worker.findingsReady.connect(self.validation_panel.set_findings)
        # ← findingsReady no longer connected to _on_validation_issues_found here
        self._validation_worker.start()


    def _on_validation_issues_found(self, findings: list):
        """
        Called when the user clicks Fix Issues.
    
        Spawns MermaidFixWorker (LLM #3) which receives the current raw Mermaid
        code and the validation findings, then returns a corrected Mermaid string.
    
        Rules enforced inside the worker:
        - NEVER removes existing participants or arrows (preserves complexity-level
        components the old keyword fixer could not handle).
        - ONLY adds what is needed to resolve each finding.
        - Returns the full corrected sequenceDiagram code directly.
        """
        if not findings:
            return
    
        # Guard: cancel any previous fix worker still running
        if self._fix_worker is not None:
            if self._fix_worker.isRunning():
                self._fix_worker.quit()
                self._fix_worker.wait(3000)
            self._fix_worker.deleteLater()
            self._fix_worker = None
    
        # Read the live Mermaid code (reflects any user edits in the code editor)
        current_code = self._current_mermaid_code
        if not current_code:
            return
    
        prompt     = self.current_parsed_data.get("prompt", self._last_prompt) \
                    if self.current_parsed_data else self._last_prompt
        complexity = self.current_parsed_data.get("complexity", "Standard") \
                    if self.current_parsed_data else "Standard"
    
        # Show "Applying fixes…" state in the panel immediately
        self.validation_panel.show_fixing()
    
        # Create and wire the fix worker
        self._fix_worker = MermaidFixWorker(current_code, findings, prompt, complexity)
        self._fix_worker.fixComplete.connect(self._on_fix_complete)
        self._fix_worker.fixFailed.connect(self._on_fix_failed)
        self._fix_worker.start()
    
    
    def _on_fix_complete(self, fixed_code: str):
        """Render the LLM-corrected Mermaid code and re-run validation."""
        self._current_mermaid_code = fixed_code
        self.code_panel.set_code(fixed_code)
    
        # Render — pass current parsed_data for sidebar metadata (voltage, language, etc.)
        # but the diagram content comes entirely from fixed_code.
        html = self.generator.generate_display_html(
            fixed_code,
            self.current_parsed_data or {},
            enable_editing=True,
        )
        self.web_view.setHtml(html)
    
        # Clear stored findings — they've been consumed
        self.validation_panel._current_findings = []
        self.validation_panel.fix_btn.setEnabled(False)
    
        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage(
                "✓ Diagram patched by LLM — re-validating…", 4000
            )
    
        # Re-run validation for display only.
        # findingsReady is NOT reconnected to _on_validation_issues_found here,
        # so there is no fix loop — only show_result and set_findings are connected.
        prompt = self.current_parsed_data.get("prompt", self._last_prompt) \
                if self.current_parsed_data else self._last_prompt
        self._run_validation(prompt, fixed_code)
    
    
    def _on_fix_failed(self, error_msg: str):
        """Surface the error in the validation panel without touching the diagram."""
        self.validation_panel.show_fix_error(error_msg)
        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage(f"Fix failed: {error_msg[:80]}", 5000)
 
    
    def _on_element_edited(self, element_id, element_type, new_text, x, y):
        self._update_parsed_data(element_id, element_type, new_text)
        self.refresh_diagram()
        if self.parent_window and hasattr(self.parent_window, 'status'):
            short = new_text[:30] + ("..." if len(new_text) > 30 else "")
            self.parent_window.status.showMessage(f"✓ Updated: {short}", 2000)

    def get_current_mermaid_code(self) -> str:
        return self.code_panel.get_code() or self._current_mermaid_code

    # ── SVG Export ────────────────────────────────────────────────────────────
    def export_svg(self, file_path: str, on_done=None):
        """Extract the SVG element from the rendered diagram and save it as a file."""
        js = """
        (function() {
            var svg = document.querySelector('.mermaid svg');
            if (!svg) return JSON.stringify({error: 'No SVG found'});

            // Clone so we don't mutate the live DOM
            var clone = svg.cloneNode(true);

            // Ensure white background
            clone.style.background = '#ffffff';

            // Fix any currentColor text fills
            clone.querySelectorAll('text, tspan').forEach(function(el) {
                var f = el.getAttribute('fill');
                if (!f || f === 'currentColor' || f === 'inherit' ||
                    f === '#ffffff' || f === '#fff' || f === 'white') {
                    el.setAttribute('fill', '#1a202c');
                }
            });

            // Add XML namespace if missing
            clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
            clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

            var serializer = new XMLSerializer();
            var svgString = '<?xml version="1.0" encoding="UTF-8"?>\\n' +
                            serializer.serializeToString(clone);

            return JSON.stringify({svg: svgString});
        })();
        """

        def _on_svg_data(result):
            try:
                import json as _json
                data = _json.loads(result)
                if "error" in data:
                    if on_done:
                        on_done(False, f"SVG export failed: {data['error']}")
                    return
                svg_content = data["svg"]
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(svg_content)
                if on_done:
                    on_done(True, f"✓ SVG saved to {file_path}")
            except Exception as e:
                if on_done:
                    on_done(False, f"SVG save error: {e}")

        self.web_view.page().runJavaScript(js, 0, _on_svg_data)

    # ── PDF Export ────────────────────────────────────────────────────────────
    def export_pdf(self, file_path: str, on_done=None):
        """Print the diagram page to a PDF using Qt's built-in PDF printing."""
        # Use QPageLayout for PDF output
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Landscape,
            QMarginsF(10, 10, 10, 10),
            QPageLayout.Unit.Millimeter
        )

        def _on_pdf_done(file_path_result):
            # Qt returns the path on success, empty string on failure
            if file_path_result:
                if on_done:
                    on_done(True, f"✓ PDF saved to {file_path}")
            else:
                if on_done:
                    on_done(False, "PDF export failed")

        self.web_view.page().printToPdf(file_path, page_layout)
        # printToPdf is async; connect to the signal for completion notification
        self.web_view.page().pdfPrintingFinished.connect(
            lambda path, success: on_done(success, f"✓ PDF saved to {file_path}" if success else "PDF export failed")
            if on_done else None
        )

    # ── SVG-only PNG Export (diagram only, no UI chrome) ─────────────────────
    def export_svg_as_png(self, file_path: str, on_done=None):
        self._svg_export_path    = file_path
        self._svg_export_on_done = on_done
        self._export_orig_size   = self.web_view.size()

        js_prepare = """
        (function() {
            var svg = document.querySelector('.mermaid svg');
            if (!svg) return JSON.stringify({error: 'No SVG found'});

            var allTopLevel = document.querySelectorAll(
                '.tip-bar, .key-grid, .code-panel-label, ' +
                '#mermaid-code-editor, .apply-row, .badge-row, ' +
                '.header, #apply-code-btn, .apply-hint'
            );
            allTopLevel.forEach(function(el) {
                el._prevDisplay = el.style.display;
                el.style.display = 'none';
            });

            var container = document.querySelector('.container');
            if (container) {
                container._prevStyle = container.getAttribute('style') || '';
                container.style.padding    = '0';
                container.style.boxShadow  = 'none';
                container.style.borderRadius = '0';
                container.style.background = '#ffffff';
            }

            var wrap = document.querySelector('.mermaid-wrap');
            if (wrap) {
                wrap._prevStyle = wrap.getAttribute('style') || '';
                wrap.style.border     = 'none';
                wrap.style.padding    = '16px';
                wrap.style.background = '#ffffff';
                wrap.style.overflow   = 'visible';
                wrap.style.maxHeight  = 'none';
            }

            document.body.style.background = '#ffffff';
            document.body.style.padding    = '0';
            document.body.style.margin     = '0';
            document.body.style.overflow   = 'visible';
            document.documentElement.style.overflow = 'hidden';
            window.scrollTo(0, 0);

            var rect = svg.getBoundingClientRect();
            return JSON.stringify({
                svgW: Math.ceil(rect.width)  + 8,
                svgH: Math.ceil(rect.height) + 8
            });
        })();
        """
        self.web_view.page().runJavaScript(js_prepare, 0, self._on_svg_export_data)

    def _on_svg_export_data(self, result):
        try:
            import json as _json
            data = _json.loads(result)

            if "error" in data:
                self._restore_svg_export()
                if self._svg_export_on_done:
                    self._svg_export_on_done(False, f"Export failed: {data['error']}")
                return

            svgW = max(data["svgW"], 400)
            svgH = max(data["svgH"], 200)

            self.web_view.setFixedSize(svgW, svgH)
            self.web_view.page().runJavaScript("window.scrollTo(0,0);", 0)
            QTimer.singleShot(600, self._grab_svg_only)

        except Exception as e:
            self._restore_svg_export()
            if self._svg_export_on_done:
                self._svg_export_on_done(False, f"Parse error: {e}")

    def _grab_svg_only(self):
        try:
            pixmap = self.web_view.grab()
            saved  = pixmap.save(self._svg_export_path, "PNG")
        except Exception as e:
            saved  = False

        self._restore_svg_export()
        self.web_view.setMinimumSize(0, 0)
        self.web_view.setMaximumSize(16777215, 16777215)
        self.web_view.resize(self._export_orig_size)

        if self._svg_export_on_done:
            if saved:
                self._svg_export_on_done(True,  f"✓ Diagram PNG saved to {self._svg_export_path}")
            else:
                self._svg_export_on_done(False, f"Failed to save PNG to {self._svg_export_path}")

    def _restore_svg_export(self):
        js_restore = """
        (function() {
            var toRestore = document.querySelectorAll(
                '.tip-bar, .key-grid, .code-panel-label, ' +
                '#mermaid-code-editor, .apply-row, .badge-row, ' +
                '.header, #apply-code-btn, .apply-hint'
            );
            toRestore.forEach(function(el) {
                el.style.display = (el._prevDisplay !== undefined)
                    ? el._prevDisplay : '';
            });

            var container = document.querySelector('.container');
            if (container && container._prevStyle !== undefined) {
                container.setAttribute('style', container._prevStyle);
            }

            var wrap = document.querySelector('.mermaid-wrap');
            if (wrap && wrap._prevStyle !== undefined) {
                wrap.setAttribute('style', wrap._prevStyle);
            }

            document.body.style.background = '';
            document.body.style.padding    = '';
            document.body.style.margin     = '';
            document.body.style.overflow   = '';
            document.documentElement.style.overflow     = '';
            window.scrollTo(0, 0);
        })();
        """
        self.web_view.page().runJavaScript(js_restore, 0)

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(12, 12, 12, 12)

        self._collapsed = False
        self._toggle_btn = QPushButton("◀ Hide")
        self._toggle_btn.setFixedHeight(24)
        self._toggle_btn.setStyleSheet(
            "QPushButton{background:#cbd5e0;border:none;border-radius:4px;"
            "font-size:11px;font-weight:bold;color:#2d3748;}"
            "QPushButton:hover{background:#a0aec0;}"
        )
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        lay.addWidget(self._toggle_btn)

        self._content = QWidget()
        content_lay = QVBoxLayout(self._content)
        content_lay.setSpacing(10)
        content_lay.setContentsMargins(0, 0, 0, 0)

        lay.addWidget(self._content)
        self.setMinimumWidth(280)
        self.setMaximumWidth(340)


        title = QLabel("Electrical Diagram Generator")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#2c5282; margin-bottom:8px;")
        title.setWordWrap(True)
        lay.addWidget(title)

        lay.addWidget(QLabel("Diagram description:"))
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText(
            "Describe your electrical system…\n"
            "e.g. 'Main supply, breaker, busbar, neutral bar, earth bar, load circuits at 415V'"
        )
        self.prompt_text.setMaximumHeight(130)
        self.prompt_text.setStyleSheet(
            "border:1px solid #cbd5e0; border-radius:5px; padding:6px; font-size:12px;"
            "color:#000000; background:#ffffff;"
        )
        lay.addWidget(self.prompt_text)

        detail_row = QHBoxLayout()
        detail_lbl = QLabel("Detail Level:")
        detail_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        detail_lbl.setStyleSheet("color:#2d3748;")
        detail_row.addWidget(detail_lbl)

        self.complexity_combo = QComboBox()
        self.complexity_combo.addItems(["Simple", "Neutral", "Standard", "Detailed"])
        self.complexity_combo.setCurrentText("Neutral")
        self.complexity_combo.setStyleSheet("""
            QComboBox {
                color: #ffffff;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 5px;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
            }
            QComboBox QAbstractItemView::item {
                color: #000000;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #e2e8f0;
                color: #000000;
            }
        """)
        self.complexity_combo.currentTextChanged.connect(self._on_complexity_changed)
        detail_row.addWidget(self.complexity_combo, 1)
        lay.addLayout(detail_row)

        self.complexity_hint = QLabel(COMPLEXITY_LEVELS["Standard"]["description"])
        self.complexity_hint.setFont(QFont("Arial", 9))
        self.complexity_hint.setStyleSheet("color:#718096; font-style:italic; margin-bottom:4px;")
        self.complexity_hint.setWordWrap(True)
        lay.addWidget(self.complexity_hint)

        lay.addWidget(QLabel("Quick templates:"))
        self.tmpl_combo = QComboBox()
        self.tmpl_combo.addItems([
            "Basic Distribution",
            "Industrial Panel",
            "Residential Board",
            "Three-Phase System",
            "Safety Earth System",
            "日本語: 基本的な配電",
        ])
        self.tmpl_combo.setStyleSheet("color:#000;")
        self.tmpl_combo.currentTextChanged.connect(self._load_template)
        lay.addWidget(self.tmpl_combo)

        gen_btn = QPushButton("⚡  Generate Diagram")
        gen_btn.setStyleSheet("""
            QPushButton {background:#2c5282;color:#fff;border:none;border-radius:6px;
                         padding:10px;font-weight:bold;font-size:12px;margin-top:8px;}
            QPushButton:hover {background:#2a4365;}
            QPushButton:pressed {background:#1a365d;}
        """)
        gen_btn.clicked.connect(self._generate)
        lay.addWidget(gen_btn)

        self.reset_btn = QPushButton("↺  Reset to Original")
        self.reset_btn.setStyleSheet("""
            QPushButton {background:#63b3ed;color:#fff;border:none;border-radius:6px;
                         padding:8px;font-size:12px;margin-top:4px;}
            QPushButton:hover {background:#4299e1;}
            QPushButton:disabled {background:#cbd5e0;color:#718096;}
        """)
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.setEnabled(False)
        lay.addWidget(self.reset_btn)

        lay.addStretch()

        hint = QLabel(
            "💡 Drag any coloured box to reposition it.\n"
            "Double-click any text to edit it in-place.\n"
            "Edit Mermaid code → Apply to update diagram."
        )
        hint.setFont(QFont("Arial", 9))
        hint.setStyleSheet("color:#718096; margin-top:10px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.setMinimumWidth(280)
        self.setMaximumWidth(340)
        self.setStyleSheet("QWidget{background:#f7fafc;border-right:1px solid #e2e8f0;} QLabel{color:#2d3748;}")

        self._update_complexity_style("Neutral")


    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        if self._collapsed:
            self.setFixedWidth(32)
            self._toggle_btn.setText("▶")
        else:
            self.setMinimumWidth(280)
            self.setMaximumWidth(340)
            self.setFixedWidth(QWIDGETSIZE_MAX)   # clear fixed width
            self._toggle_btn.setText("◀ Hide")

    def _on_complexity_changed(self, level: str):
        self.complexity_hint.setText(COMPLEXITY_LEVELS["Neutral"]["description"])
        self._update_complexity_style(level)

    def _update_complexity_style(self, level: str):
        colors = {"Neutral":  "#f59e0b", "Simple": "#10b981", "Standard": "#3b82f6", "Detailed": "#8b5cf6"}
        c = colors.get(level, "#f59e0b")
        self.complexity_combo.setStyleSheet(f"""
            QComboBox {{
                color: #000000;
                background: {c};
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 5px;
                border: none;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{ color: #000; background: #fff; }}
        """)

    def _load_template(self, name):
        templates = {
            "Basic Distribution": "Main incoming supply at 415V, main circuit breaker, busbar distribution, neutral bar, earth bar, and load circuits for lights and sockets.",
            "Industrial Panel":   "Three-phase 415V incoming supply, main MCCB breaker, copper busbar system, multiple outgoing MCBs for motors, neutral bar and earth bar.",
            "Residential Board":  "Single-phase 230V supply, main MCB, individual circuit breakers for lighting, power sockets, kitchen appliances, with safety earth.",
            "Three-Phase System": "Three-phase RYB supply at 415V, main breaker, busbar distribution, balanced load circuits, neutral return path, protective earth.",
            "Safety Earth System":"Electrical safety diagram focused on earthing: main earth bar connections, circuit protective conductors, equipment earth points, neutral bar.",
            "日本語: 基本的な配電": "主電源230V/415V、メインブレーカー、バスバー、中性線バー、接地バー、照明とコンセントの負荷回路を含む基本的な電力配電図。",
        }
        if name in templates:
            self.prompt_text.setPlainText(templates[name])

    def _generate(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
            return
        complexity = self.complexity_combo.currentText()
        if hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.generate_from_prompt(prompt, complexity)
            # reset_btn is re-enabled by _finalise_generation once the diagram is ready

    def _reset(self):
        if not hasattr(self.main_window, 'canvas') or not self.main_window.canvas.original_parsed_data:
            return
        self.main_window.canvas.current_parsed_data = self.main_window.canvas.original_parsed_data.copy()
        self.main_window.canvas.refresh_diagram()
        if hasattr(self.main_window, 'status'):
            self.main_window.status.showMessage("Diagram reset to original state", 3000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrical Distribution Diagram Generator")
        self.resize(1400, 900)
        self._build_menu()
        self._build_ui()
        self.installEventFilter(self)
        # In MainWindow.__init__ or wherever you set up the app:
        # app.aboutToQuit.connect(self.canvas.closeEvent)

    def _build_menu(self):
        mb = self.menuBar()

        file_m = mb.addMenu("&File")
        for label, shortcut, slot in [
            ("&New",          "Ctrl+N", self.new_diagram),
            ("&Save Diagram", "Ctrl+S", self.save_diagram),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(slot); file_m.addAction(a)
        file_m.addSeparator()

        # Export submenu with PNG, SVG, PDF, and Mermaid download
        exp = file_m.addMenu("&Export")
        for label, slot in [
            # ("Export as PNG (full page)",    self.export_as_png),
            ("Export as PNG", self.export_as_png),
            ("Export as SVG",                self.export_as_svg),
            ("Export as PDF",                self.export_as_pdf),
            ("Download Mermaid Code (.mmd)", self.download_mermaid_code),
            ("Export as KiCad Schematic",    self.export_as_kicad),   
            ("Export as DXF",                self.export_as_dxf),

        ]:
            a = QAction(label, self); a.triggered.connect(slot); exp.addAction(a)

        file_m.addSeparator()
        ex = QAction("E&xit", self); ex.setShortcut("Ctrl+Q"); ex.triggered.connect(self.close); file_m.addAction(ex)

        edit_m = mb.addMenu("&Edit")
        for label, shortcut, slot in [
            ("&Reset Diagram",    "Ctrl+R", self.reset_diagram),
            ("&Copy Mermaid Code","Ctrl+M", self.copy_mermaid),
            ("C&lear All",        "Ctrl+L", self.clear_all),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(slot); edit_m.addAction(a)

        view_m = mb.addMenu("&View")
        for label, shortcut, slot in [
            ("Zoom &In",    "Ctrl++", self.zoom_in),
            ("Zoom &Out",   "Ctrl+-", self.zoom_out),
            ("&Reset Zoom", "Ctrl+0", self.reset_zoom),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(slot); view_m.addAction(a)
        view_m.addSeparator()
        # fs = QAction("&Fullscreen", self); fs.setShortcut("F11"); fs.triggered.connect(self.toggle_fullscreen); view_m.addAction(fs)
        fs = QAction("&Fullscreen", self)
        fs.setShortcut("F11")
        fs.triggered.connect(self.toggle_fullscreen)
        view_m.addAction(fs)

        help_m = mb.addMenu("&Help")
        ab = QAction("&About", self); ab.triggered.connect(self.show_about); help_m.addAction(ab)

    def _build_ui(self):
        central = QWidget()
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        self.sidebar = Sidebar(self)
        root_lay.addWidget(self.sidebar)

        canvas_wrap = QWidget()
        canvas_lay = QVBoxLayout(canvas_wrap)
        canvas_lay.setContentsMargins(0, 0, 0, 0)
        canvas_lay.setSpacing(0)

        self.canvas = DiagramCanvas(self)
        canvas_lay.addWidget(self.canvas)
        root_lay.addWidget(canvas_wrap, 1)

        self.setCentralWidget(central)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(
            "Ready — enter a prompt, choose detail level, and click Generate. "
            "Drag boxes · Double-click text · Edit Mermaid code and Apply."
        )

    def _require_diagram(self, action_name="export"):
        if not self.canvas.current_parsed_data:
            QMessageBox.warning(self, "No Diagram", f"Generate a diagram before you {action_name}.")
            return False
        return True

    def new_diagram(self):
        self.sidebar.prompt_text.clear()
        self.canvas.web_view.setHtml("")
        self.canvas.code_panel.set_code("")
        self.sidebar.reset_btn.setEnabled(False)
        self.status.showMessage("New diagram started", 2000)

    def save_diagram(self):
        if not self._require_diagram("save"): return
        path, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", "JSON Files (*.json)")
        if path:
            data = dict(self.canvas.current_parsed_data)
            data["_mermaid_code"] = self.canvas.get_current_mermaid_code()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status.showMessage(f"Saved to {path}", 3000)


    def export_as_png(self):
        if not self._require_diagram(): return
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG (diagram only)", "", "PNG Files (*.png)")
        if not path: return
        self.status.showMessage("⏳ Preparing diagram-only PNG…", 0)
        self.canvas.export_svg_as_png(path, on_done=lambda ok, msg: (
            self.status.showMessage(msg, 4000),
            QMessageBox.information(self, "Exported", msg) if ok
            else QMessageBox.critical(self, "Export Error", msg)
        ))

    def export_as_svg(self):
        if not self._require_diagram(): return
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "", "SVG Files (*.svg)")
        if not path: return
        self.status.showMessage("⏳ Extracting SVG…", 0)

        def _done(ok, msg):
            self.status.showMessage(msg, 4000)
            if ok:
                QMessageBox.information(self, "Exported", msg)
            else:
                QMessageBox.critical(self, "Export Error", msg)

        self.canvas.export_svg(path, on_done=_done)

    def export_as_pdf(self):
        if not self._require_diagram(): return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF Files (*.pdf)")
        if not path: return
        self.status.showMessage("⏳ Generating PDF…", 0)

        # Disconnect any previously connected pdfPrintingFinished to avoid duplicates
        try:
            self.canvas.web_view.page().pdfPrintingFinished.disconnect()
        except RuntimeError:
            pass  # No connections yet




        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Landscape,
            QMarginsF(10, 10, 10, 10),
            QPageLayout.Unit.Millimeter
        )

        js_hide = """
        (function() {
            var toHide = document.querySelectorAll(
                '.tip-bar, .key-grid, .code-panel-label, ' +
                '#mermaid-code-editor, .apply-row, .badge-row, ' +
                '.header, #apply-code-btn, .apply-hint'
            );
            toHide.forEach(function(el) {
                el._prevDisplay = el.style.display;
                el.style.display = 'none';
            });
            var wrap = document.querySelector('.mermaid-wrap');
            if (wrap) {
                wrap._prevBorder = wrap.style.border;
                wrap._prevPad    = wrap.style.padding;
                wrap.style.border  = 'none';
                wrap.style.padding = '0';
            }
        })();
        """

        js_restore = """
        (function() {
            var toRestore = document.querySelectorAll(
                '.tip-bar, .key-grid, .code-panel-label, ' +
                '#mermaid-code-editor, .apply-row, .badge-row, ' +
                '.header, #apply-code-btn, .apply-hint'
            );
            toRestore.forEach(function(el) {
                el.style.display = el._prevDisplay !== undefined ? el._prevDisplay : '';
            });
            var wrap = document.querySelector('.mermaid-wrap');
            if (wrap) {
                wrap.style.border  = wrap._prevBorder || '';
                wrap.style.padding = wrap._prevPad    || '';
            }
        })();
        """

        def _on_pdf_done(file_path_result, success):
            self.canvas.web_view.page().runJavaScript(js_restore, 0)
            if success:
                msg = f"✓ PDF saved to {path}"
                self.status.showMessage(msg, 4000)
                QMessageBox.information(self, "Exported", msg)
            else:
                msg = "PDF export failed"
                self.status.showMessage(msg, 4000)
                QMessageBox.critical(self, "Export Error", msg)

        def _do_print():
            self.canvas.web_view.page().pdfPrintingFinished.connect(_on_pdf_done)
            self.canvas.web_view.page().printToPdf(path, page_layout)

        self.canvas.web_view.page().runJavaScript(js_hide, 0,
            lambda _: QTimer.singleShot(200, _do_print))
        

    def download_mermaid_code(self):
        """Save the current Mermaid code as a .mmd text file."""
        code = self.canvas.get_current_mermaid_code()
        if not code:
            QMessageBox.warning(self, "No Diagram", "Generate a diagram first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Download Mermaid Code", "diagram.mmd",
            "Mermaid Files (*.mmd);;Text Files (*.txt);;All Files (*)"
        )
        if not path: return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(code)
            msg = f"✓ Mermaid code saved to {path}"
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Downloaded", msg)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def export_as_dxf(self):
        """Export current diagram as a DXF single-line diagram (.dxf)."""
        if not self._require_diagram("export"):
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export DXF Diagram",
            "diagram.dxf",
            "DXF Files (*.dxf);;All Files (*)"
        )
        if not path:
            return

        try:
            # ✅ Use parsed_data directly — avoids re-parsing mermaid which loses components
            export_dxf(self.canvas.current_parsed_data, path)
            msg = f"✓ DXF saved to {path}"
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"DXF export failed: {e}"
            self.status.showMessage(msg, 4000)
            QMessageBox.critical(self, "Export Error", msg)

    # ── Edit / View actions ───────────────────────────────────────────────────

    def reset_diagram(self):  self.sidebar._reset()
    def zoom_in(self):
        self._scale_diagram(1.2)

    def zoom_out(self):
        self._scale_diagram(1/1.2)

    def reset_zoom(self):
        self.canvas.web_view.page().runJavaScript("""
            (function() {
                var el = document.getElementById('diagram-root');
                if (!el) return;
                el.dataset.scale = '1';
                el.style.transform = 'scale(1)';
                el.style.transformOrigin = 'top left';
            })();
        """)

    def _scale_diagram(self, factor):
        self.canvas.web_view.page().runJavaScript(f"""
            (function() {{
                var el = document.getElementById('diagram-root');
                if (!el) return;
                var current = el.dataset.scale ? parseFloat(el.dataset.scale) : 1.0;
                var next = Math.min(Math.max(current * {factor}, 0.2), 5.0);
                el.dataset.scale = next;
                el.style.transform = 'scale(' + next + ')';
                el.style.transformOrigin = 'top left';
            }})();
        """)

    def toggle_fullscreen(self):

        self.showNormal() if self.isFullScreen() else self.showFullScreen()


    # Exit fullscreen on ESC key
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key_Escape and self.isFullScreen():
                self.showNormal()
                return True
        return super().eventFilter(obj, event)

       


    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canvas.web_view.page().runJavaScript(
                "if(window.mermaidEditor && window.mermaidEditor.editState) {"
                "  window.mermaidEditor.editState.input.blur(); }", 0)
        super().keyPressEvent(event)

    def copy_mermaid(self):
        code = self.canvas.get_current_mermaid_code()
        if not code:
            QMessageBox.warning(self, "No Diagram", "No diagram to copy."); return
        QApplication.clipboard().setText(code)
        self.status.showMessage("Mermaid code copied to clipboard", 2000)

    def clear_all(self):
        if QMessageBox.question(self, "Clear All", "Clear prompt and diagram?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.new_diagram()

    def show_about(self):
        QMessageBox.about(self, "About",
            "<h2>Electrical Distribution Diagram Generator</h2>"
            "<p>Version 3.0</p>"
            "<p>Generate electrical distribution diagrams from natural language.</p>"
            "<p><b>Export formats:</b></p>"
            "<ul>"
            "<li>PNG — full page or diagram-only</li>"
            "<li>SVG — scalable vector graphic (diagram only)</li>"
            "<li>PDF — A4 landscape via Qt print engine</li>"
            "<li>Mermaid code — .mmd text file</li>"
            "<li>DXF — single-line diagram (AutoCAD / LibreCAD)</li>"
            "</ul>"
            "<p><b>Drag</b> participant boxes to reposition.<br>"
            "<b>Double-click</b> any text to edit it in-place.</p>"
            "<p>Built with PySide6 · Mermaid.js</p>")

    def export_as_kicad(self):
        """Export current diagram as a KiCad 6+ schematic (.kicad_sch)."""
        if not self._require_diagram("export"): return
 
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export KiCad Schematic",
            "diagram.kicad_sch",
            "KiCad Schematic Files (*.kicad_sch);;All Files (*)"
        )
        if not path:
            return
 
        try:
            export_kicad_schematic(self.canvas.current_parsed_data, path)
            msg = f"✓ KiCad schematic saved to {path}"
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"KiCad export failed: {e}"
            self.status.showMessage(msg, 4000)
            QMessageBox.critical(self, "Export Error", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()