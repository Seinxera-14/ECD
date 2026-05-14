# web_bridge.py
from PySide6.QtCore import *
import os

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