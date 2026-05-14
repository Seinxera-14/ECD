import re
import requests
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

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
            if has_issues:
                findings_block = text.split("FINDINGS:")[-1].strip() if "FINDINGS:" in text else ""
            findings_list = [
                line.lstrip("- ").strip()
                for line in findings_block.splitlines()
                if line.strip() and line.strip() != "None"
            ]
            if findings_list:
                self.findingsReady.emit(findings_list)
        except Exception as e:
            self.validationComplete.emit(f"Validation unavailable: {e}", False)


class ValidationPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.setMaximumHeight(120)

    def show_loading(self):
        self.setStyleSheet("ValidationPanel{border:1px solid #bee3f8;border-radius:6px;background:#ebf8ff;}")
        self.icon_lbl.setText("🔍")
        self.title_lbl.setText("Validating diagram against prompt…")
        self.findings_lbl.setText("")
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

        findings = ""
        if "FINDINGS:" in text:
            findings = text.split("FINDINGS:")[-1].strip()
        self.findings_lbl.setText(findings if findings and findings != "None" else "")
        self.show()
