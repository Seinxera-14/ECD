# diagram_canvas.py
import json
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtWebEngineWidgets import *
from PySide6.QtWebChannel import *
# from PySide6.QtWebEngineCore import QWebEngineSettings
import os

from mermaid_generator import MermaidGenerator
from ollama_client import OllamaClient, GenerationWorker
from web_bridge import WebBridge
from element_editor import ElementEditorDialog
from constants import COMPLEXITY_LEVELS
from ValidationWorker import ValidationWorker, ValidationPanel, MermaidFixWorker

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