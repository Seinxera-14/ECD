# element_editor.py
from PySide6.QtWidgets import *


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