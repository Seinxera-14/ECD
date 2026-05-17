# element_editor.py
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

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