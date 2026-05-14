# sidebar.py
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *


from constants import COMPLEXITY_LEVELS


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
            ok = self.main_window.canvas.generate_from_prompt(prompt, complexity)
            if ok:
                self.reset_btn.setEnabled(True)

    def _reset(self):
        if not hasattr(self.main_window, 'canvas') or not self.main_window.canvas.original_parsed_data:
            return
        self.main_window.canvas.current_parsed_data = self.main_window.canvas.original_parsed_data.copy()
        self.main_window.canvas.refresh_diagram()
        if hasattr(self.main_window, 'status'):
            self.main_window.status.showMessage("Diagram reset to original state", 3000)