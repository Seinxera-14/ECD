import sys
import re
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
import json
import os
import math
import requests

from diagram_canvas import DiagramCanvas
from sidebar import Sidebar
from Kicad_exporter import export_kicad_schematic


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
            "</ul>"
            "<p><b>Drag</b> participant boxes to reposition.<br>"
            "<b>Double-click</b> any text to edit it in-place.</p>"
            "<p>Built with PySide6 · Mermaid.js</p>")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canvas.web_view.page().runJavaScript(
                "if(window.mermaidEditor && window.mermaidEditor.editState) {"
                "  window.mermaidEditor.editState.input.blur(); }", 0)
        super().keyPressEvent(event)

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