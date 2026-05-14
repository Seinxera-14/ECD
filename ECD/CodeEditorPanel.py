from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

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
