# diagram_canvas.py
import json
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtWebEngineWidgets import *
from PySide6.QtWebChannel import *
from PySide6.QtWebEngineCore import QWebEngineSettings

from mermaid_generator import MermaidGenerator
from ollama_client import OllamaClient
from web_bridge import WebBridge
from element_editor import ElementEditorDialog
from constants import COMPLEXITY_LEVELS


class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.generator = MermaidGenerator()
        self.current_parsed_data = None
        self.original_parsed_data = None
        self.web_bridge = WebBridge()
        self._current_mermaid_code = ""
        self._svg_export_path = None
        self._svg_export_on_done = None
        self._export_orig_size = None
        self._build_ui()
        self._setup_channel()
        self.web_bridge.elementEdited.connect(self._on_element_edited)
        self.web_bridge.diagramChanged.connect(self._on_diagram_text_changed)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(500)

        # Enable JavaScript console for debugging
        self.web_view.page().settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        self.web_view.page().settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        self.web_bridge.elementDoubleClicked.connect(self._on_element_dblclicked)
        lay.addWidget(self.web_view)

        
        

        # Stub: code panel lives inside the WebView HTML now
        self.code_panel = type('_Stub', (), {
            'set_code': lambda self, c: None,
            'get_code': lambda self: ''
        })()

    def _setup_channel(self):
        ch = QWebChannel(self.web_view.page())
        ch.registerObject("qtBridge", self.web_bridge)
        self.web_view.page().setWebChannel(ch)

    def generate_from_prompt(self, prompt_text, complexity_level="Standard"):
        try:
            prompt_text = prompt_text.strip()
            if not prompt_text:
                QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
                return False

            parsed_data = None

            # ── Step 1: Parse prompt into structured data ──────────────────────
            try:
                ollama = OllamaClient()
                parsed_data = ollama.prompt_to_structured_data(prompt_text)
                if not isinstance(parsed_data, dict) or "components" not in parsed_data:
                    raise ValueError("Invalid LLM output")
                allowed_ids = COMPLEXITY_LEVELS[complexity_level]["components"]
                parsed_data["components"] = [
                    (c, l) for c, l in parsed_data["components"] if c in allowed_ids
                ]
                parsed_data["complexity"] = complexity_level
                print("DEBUG: Parsed via Ollama")
            except Exception as llm_err:
                print(f"LLM parsing failed, using regex fallback: {llm_err}")
                parsed_data = self.generator.parse_prompt(prompt_text, complexity_level)

            self.current_parsed_data = parsed_data
            self.original_parsed_data = parsed_data.copy()

            # ── Step 2: Generate Mermaid code ──────────────────────────────────
            mermaid_code = self.generator.generate_mermaid_code(parsed_data)

            self._current_mermaid_code = mermaid_code
            self.code_panel.set_code(mermaid_code)

            html = self.generator.generate_display_html(mermaid_code, parsed_data, enable_editing=True)
            # Debug: print first 500 chars of HTML to check
            print("DEBUG: HTML length:", len(html))
            print("DEBUG: HTML preview:", html[:500])
            print("DEBUG: Mermaid code:", mermaid_code[:200])
            self.web_view.setHtml(html, QUrl("")) 

            if self.parent_window and hasattr(self.parent_window, 'status'):
                lang_name = "English" if parsed_data.get("language") == "en" else "Japanese"
                self.parent_window.status.showMessage(
                    f"Diagram generated ({lang_name}, {complexity_level}), "
                    f"{len(parsed_data.get('components', []))} components. "
                    "Drag blue boxes · Double-click text · Edit code below.", 6000)
            return True
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")
            return False

    def _on_diagram_text_changed(self, new_code: str):
        self._current_mermaid_code = new_code
        self.code_panel.set_code(new_code)

    def _on_element_dblclicked(self, element_id, element_type, current_text):
        dlg = ElementEditorDialog(element_id, element_type, current_text, self)
        if dlg.exec() == ElementEditorDialog.DialogCode.Accepted:
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

            var clone = svg.cloneNode(true);
            clone.style.background = '#ffffff';

            clone.querySelectorAll('text, tspan').forEach(function(el) {
                var f = el.getAttribute('fill');
                if (!f || f === 'currentColor' || f === 'inherit' ||
                    f === '#ffffff' || f === '#fff' || f === 'white') {
                    el.setAttribute('fill', '#1a202c');
                }
            });

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
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Landscape,
            QMarginsF(10, 10, 10, 10),
            QPageLayout.Unit.Millimeter
        )

        def _on_pdf_done(success):
            if on_done:
                if success:
                    on_done(True, f"✓ PDF saved to {file_path}")
                else:
                    on_done(False, "PDF export failed")

        self.web_view.page().pdfPrintingFinished.connect(
            lambda path, success: on_done(True, f"✓ PDF saved to {file_path}") if success and on_done 
            else (on_done(False, "PDF export failed") if on_done else None)
        )
        self.web_view.page().printToPdf(file_path, page_layout)

    # ── SVG-only PNG Export ───────────────────────────────────────────────────
    def export_svg_as_png(self, file_path: str, on_done=None):
        self._svg_export_path = file_path
        self._svg_export_on_done = on_done
        self._export_orig_size = self.web_view.size()

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
            saved = pixmap.save(self._svg_export_path, "PNG")
        except Exception as e:
            saved = False

        self._restore_svg_export()
        self.web_view.setMinimumSize(0, 0)
        self.web_view.setMaximumSize(16777215, 16777215)
        self.web_view.resize(self._export_orig_size)

        if self._svg_export_on_done:
            if saved:
                self._svg_export_on_done(True, f"✓ Diagram PNG saved to {self._svg_export_path}")
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