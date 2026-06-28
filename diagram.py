import sys
import os
import json
import math
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsItemGroup, QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem,
    QGraphicsEllipseItem, QGraphicsRectItem, QFileDialog, QPushButton, QToolBar,
    QStatusBar, QMessageBox, QTextEdit, QSplitter,
    QSpinBox, QComboBox, QMenu, QDialog, QDialogButtonBox, QVBoxLayout as QVBoxLayout2,
    QGroupBox, QDoubleSpinBox, QGridLayout, QFrame, QMenuBar
)
from PySide6.QtGui import (
    QPixmap, QIcon, QPainter, QPainterPath, QPen, QColor, QBrush,
    QTransform, QMouseEvent, QAction, QFont, QLinearGradient
)
from PySide6.QtCore import Qt, QSize, QPoint, QPointF, QRectF

try:
    import ezdxf
except Exception:
    ezdxf = None

# -------------------------
# Dark Theme Color Scheme
# -------------------------
COLOR_BACKGROUND = QColor(30, 30, 40)       # Dark blue-gray background
COLOR_SIDEBAR_BG = QColor(40, 40, 50)      # Slightly lighter sidebar
COLOR_PRIMARY = QColor(52, 152, 219)       # Blue accent color
COLOR_SECONDARY = QColor(100, 100, 120)    # Gray for secondary elements
COLOR_ACCENT = COLOR_PRIMARY               # Single accent color for all buttons
COLOR_DANGER = QColor(231, 76, 60)         # Red for delete/danger
COLOR_SUCCESS = QColor(46, 204, 113)       # Green for success
COLOR_WARNING = QColor(241, 196, 15)       # Yellow for warning
COLOR_TEXT = QColor(240, 240, 240)         # White text
COLOR_TEXT_LIGHT = QColor(180, 180, 190)   # Light gray text
COLOR_BORDER = QColor(70, 70, 80)          # Dark border

# Grid Settings for dark theme
GRID_SIZE = 20
GRID_MAJOR_SIZE = 100
GRID_COLOR_MINOR = QColor(50, 50, 60)
GRID_COLOR_MAJOR = QColor(70, 70, 80)
GRID_COLOR_AXIS = QColor(100, 100, 120)
GRID_COLOR_TEXT = COLOR_TEXT_LIGHT

# -------------------------
# Built-in Electrical Symbols (Updated for dark theme)
# -------------------------
class BuiltInSymbols:
    """Built-in library of electrical symbols"""
    
    @staticmethod
    def create_resistor():
        """Create a resistor symbol"""
        group = QGraphicsItemGroup()
        
        # Create resistor zigzag
        path = QPainterPath()
        path.moveTo(0, 25)
        
        # Zigzag pattern
        points = [
            (10, 25), (15, 15), (25, 35), (35, 15), 
            (45, 35), (55, 15), (65, 35), (75, 15), (80, 25)
        ]
        
        for x, y in points:
            path.lineTo(x, y)
        
        # Add connecting leads
        path.moveTo(-20, 25)
        path.lineTo(0, 25)
        path.moveTo(80, 25)
        path.lineTo(100, 25)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(item)
        
        # Add label
        label = QGraphicsTextItem("R")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(40, -10)
        label.setScale(0.8)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_capacitor():
        """Create a capacitor symbol"""
        group = QGraphicsItemGroup()
        
        # Create two parallel plates
        line1 = QGraphicsLineItem(30, 10, 30, 40)
        line2 = QGraphicsLineItem(50, 10, 50, 40)
        line1.setPen(QPen(COLOR_TEXT, 2))
        line2.setPen(QPen(COLOR_TEXT, 2))
        
        # Add connecting leads
        line3 = QGraphicsLineItem(0, 25, 30, 25)
        line4 = QGraphicsLineItem(50, 25, 80, 25)
        line3.setPen(QPen(COLOR_TEXT, 2))
        line4.setPen(QPen(COLOR_TEXT, 2))
        
        group.addToGroup(line1)
        group.addToGroup(line2)
        group.addToGroup(line3)
        group.addToGroup(line4)
        
        # Add label
        label = QGraphicsTextItem("C")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(40, -10)
        label.setScale(0.8)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_inductor():
        """Create an inductor symbol"""
        group = QGraphicsItemGroup()
        
        # Create coil
        path = QPainterPath()
        path.moveTo(0, 25)
        
        # Draw semicircles for coil
        for i in range(4):
            center_x = 10 + i * 20
            path.arcTo(center_x - 10, 15, 20, 20, 0, 180)
        
        # Add connecting leads
        path.moveTo(80, 25)
        path.lineTo(100, 25)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(item)
        
        # Add label
        label = QGraphicsTextItem("L")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(40, -10)
        label.setScale(0.8)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_battery():
        """Create a battery symbol"""
        group = QGraphicsItemGroup()
        
        # Create battery body (long and short lines)
        line1 = QGraphicsLineItem(20, 10, 20, 40)  # Long line
        line2 = QGraphicsLineItem(40, 15, 40, 35)  # Short line
        line1.setPen(QPen(COLOR_TEXT, 3))
        line2.setPen(QPen(COLOR_TEXT, 3))
        
        # Add connecting leads
        line3 = QGraphicsLineItem(0, 25, 20, 25)
        line4 = QGraphicsLineItem(40, 25, 60, 25)
        line3.setPen(QPen(COLOR_TEXT, 2))
        line4.setPen(QPen(COLOR_TEXT, 2))
        
        group.addToGroup(line1)
        group.addToGroup(line2)
        group.addToGroup(line3)
        group.addToGroup(line4)
        
        # Add labels
        plus = QGraphicsTextItem("+")
        plus.setDefaultTextColor(COLOR_TEXT)
        plus.setPos(18, 5)
        plus.setScale(0.7)
        
        minus = QGraphicsTextItem("-")
        minus.setDefaultTextColor(COLOR_TEXT)
        minus.setPos(38, 5)
        minus.setScale(0.7)
        
        group.addToGroup(plus)
        group.addToGroup(minus)
        
        return group
    
    @staticmethod
    def create_ground():
        """Create a ground symbol"""
        group = QGraphicsItemGroup()
        
        # Create ground symbol (horizontal line with decreasing vertical lines)
        path = QPainterPath()
        path.moveTo(30, 0)
        path.lineTo(30, 15)  # Vertical line
        
        # Horizontal line
        path.moveTo(10, 15)
        path.lineTo(50, 15)
        
        # Decreasing vertical lines
        path.moveTo(15, 15)
        path.lineTo(15, 25)
        path.moveTo(25, 15)
        path.lineTo(25, 30)
        path.moveTo(35, 15)
        path.lineTo(35, 30)
        path.moveTo(45, 15)
        path.lineTo(45, 25)
        
        item = QGraphicsPathItem(path)
        item.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(item)
        
        # Add label
        label = QGraphicsTextItem("GND")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(20, 35)
        label.setScale(0.6)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_led():
        """Create an LED symbol"""
        group = QGraphicsItemGroup()
        
        # Create LED (triangle with arrows)
        # Triangle
        triangle = QGraphicsPathItem()
        triangle_path = QPainterPath()
        triangle_path.moveTo(40, 5)
        triangle_path.lineTo(70, 25)
        triangle_path.lineTo(40, 45)
        triangle_path.closeSubpath()
        triangle.setPath(triangle_path)
        triangle.setPen(QPen(COLOR_TEXT, 2))
        triangle.setBrush(QBrush(QColor(52, 152, 219)))  # Blue accent
        group.addToGroup(triangle)
        
        # Light rays (arrows)
        for i in range(5):
            angle = 30 + i * 15
            rad = math.radians(angle)
            x1 = 70
            y1 = 25
            x2 = 85 + math.cos(rad) * 15
            y2 = 25 + math.sin(rad) * 15
            
            ray = QGraphicsLineItem(x1, y1, x2, y2)
            ray.setPen(QPen(QColor(100, 180, 255), 1, Qt.DashLine))
            group.addToGroup(ray)
        
        # Connecting leads
        line1 = QGraphicsLineItem(10, 25, 40, 25)
        line2 = QGraphicsLineItem(70, 25, 100, 25)
        line1.setPen(QPen(COLOR_TEXT, 2))
        line2.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line1)
        group.addToGroup(line2)
        
        # Add label
        label = QGraphicsTextItem("LED")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(35, -10)
        label.setScale(0.7)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_diode():
        """Create a diode symbol"""
        group = QGraphicsItemGroup()
        
        # Create diode (triangle with line)
        # Triangle
        triangle = QGraphicsPathItem()
        triangle_path = QPainterPath()
        triangle_path.moveTo(40, 5)
        triangle_path.lineTo(70, 25)
        triangle_path.lineTo(40, 45)
        triangle_path.closeSubpath()
        triangle.setPath(triangle_path)
        triangle.setPen(QPen(COLOR_TEXT, 2))
        triangle.setBrush(QBrush(COLOR_BACKGROUND))
        group.addToGroup(triangle)
        
        # Line
        line = QGraphicsLineItem(40, 5, 40, 45)
        line.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line)
        
        # Connecting leads
        line1 = QGraphicsLineItem(10, 25, 40, 25)
        line2 = QGraphicsLineItem(70, 25, 100, 25)
        line1.setPen(QPen(COLOR_TEXT, 2))
        line2.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line1)
        group.addToGroup(line2)
        
        # Add label
        label = QGraphicsTextItem("D")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(35, -10)
        label.setScale(0.8)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_switch():
        """Create a switch symbol"""
        group = QGraphicsItemGroup()
        
        # Create switch (break in line with lever)
        # Open contacts
        line1 = QGraphicsLineItem(10, 25, 35, 25)
        line2 = QGraphicsLineItem(45, 25, 80, 25)
        line1.setPen(QPen(COLOR_TEXT, 2))
        line2.setPen(QPen(COLOR_TEXT, 2))
        
        # Lever
        lever = QGraphicsLineItem(40, 25, 40, 10)
        lever.setPen(QPen(COLOR_TEXT, 2))
        
        group.addToGroup(line1)
        group.addToGroup(line2)
        group.addToGroup(lever)
        
        # Add label
        label = QGraphicsTextItem("SW")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(35, 30)
        label.setScale(0.7)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_motor():
        """Create a motor symbol"""
        group = QGraphicsItemGroup()
        
        # Create motor (circle with M)
        circle = QGraphicsEllipseItem(20, 5, 40, 40)
        circle.setPen(QPen(COLOR_TEXT, 2))
        circle.setBrush(QBrush(COLOR_BACKGROUND))
        group.addToGroup(circle)
        
        # Add M inside
        label = QGraphicsTextItem("M")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(37, 15)
        label.setScale(1.2)
        group.addToGroup(label)
        
        # Connecting terminals
        line1 = QGraphicsLineItem(0, 25, 20, 25)
        line2 = QGraphicsLineItem(60, 25, 80, 25)
        line1.setPen(QPen(COLOR_TEXT, 2))
        line2.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line1)
        group.addToGroup(line2)
        
        return group
    
    @staticmethod
    def create_lamp():
        """Create a lamp/bulb symbol"""
        group = QGraphicsItemGroup()
        
        # Create lamp (circle with X inside)
        circle = QGraphicsEllipseItem(20, 5, 40, 40)
        circle.setPen(QPen(COLOR_TEXT, 2))
        circle.setBrush(QBrush(COLOR_BACKGROUND))
        group.addToGroup(circle)
        
        # Add X inside
        line1 = QGraphicsLineItem(25, 10, 55, 40)
        line2 = QGraphicsLineItem(55, 10, 25, 40)
        line1.setPen(QPen(COLOR_TEXT, 2))
        line2.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line1)
        group.addToGroup(line2)
        
        # Connecting leads
        line3 = QGraphicsLineItem(0, 25, 20, 25)
        line4 = QGraphicsLineItem(60, 25, 80, 25)
        line3.setPen(QPen(COLOR_TEXT, 2))
        line4.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line3)
        group.addToGroup(line4)
        
        # Add label
        label = QGraphicsTextItem("LAMP")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(25, 45)
        label.setScale(0.5)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def create_transformer():
        """Create a transformer symbol"""
        group = QGraphicsItemGroup()
        
        # Create two inductors
        path1 = QPainterPath()
        path1.moveTo(20, 10)
        for i in range(2):
            center_x = 30 + i * 20
            path1.arcTo(center_x - 10, 0, 20, 20, 0, 180)
        
        path2 = QPainterPath()
        path2.moveTo(20, 30)
        for i in range(2):
            center_x = 30 + i * 20
            path2.arcTo(center_x - 10, 20, 20, 20, 0, 180)
        
        item1 = QGraphicsPathItem(path1)
        item2 = QGraphicsPathItem(path2)
        item1.setPen(QPen(COLOR_TEXT, 2))
        item2.setPen(QPen(COLOR_TEXT, 2))
        
        group.addToGroup(item1)
        group.addToGroup(item2)
        
        # Add labels
        label1 = QGraphicsTextItem("P")
        label1.setDefaultTextColor(COLOR_TEXT)
        label1.setPos(15, 5)
        label1.setScale(0.6)
        
        label2 = QGraphicsTextItem("S")
        label2.setDefaultTextColor(COLOR_TEXT)
        label2.setPos(15, 45)
        label2.setScale(0.6)
        
        group.addToGroup(label1)
        group.addToGroup(label2)
        
        return group
    
    @staticmethod
    def create_fuse():
        """Create a fuse symbol"""
        group = QGraphicsItemGroup()
        
        # Create fuse (rectangle with line through)
        rect = QGraphicsRectItem(20, 15, 40, 20)
        rect.setPen(QPen(COLOR_TEXT, 2))
        rect.setBrush(QBrush(COLOR_BACKGROUND))
        group.addToGroup(rect)
        
        # Line through
        line1 = QGraphicsLineItem(30, 20, 50, 30)
        line1.setPen(QPen(COLOR_DANGER, 2))
        group.addToGroup(line1)
        
        # Connecting leads
        line2 = QGraphicsLineItem(0, 25, 20, 25)
        line3 = QGraphicsLineItem(60, 25, 80, 25)
        line2.setPen(QPen(COLOR_TEXT, 2))
        line3.setPen(QPen(COLOR_TEXT, 2))
        group.addToGroup(line2)
        group.addToGroup(line3)
        
        # Add label
        label = QGraphicsTextItem("F")
        label.setDefaultTextColor(COLOR_TEXT)
        label.setPos(35, 35)
        label.setScale(0.8)
        group.addToGroup(label)
        
        return group
    
    @staticmethod
    def get_symbol(component_type):
        """Get a built-in symbol by type"""
        symbols = {
            "resistor": BuiltInSymbols.create_resistor,
            "capacitor": BuiltInSymbols.create_capacitor,
            "inductor": BuiltInSymbols.create_inductor,
            "battery": BuiltInSymbols.create_battery,
            "ground": BuiltInSymbols.create_ground,
            "led": BuiltInSymbols.create_led,
            "diode": BuiltInSymbols.create_diode,
            "switch": BuiltInSymbols.create_switch,
            "motor": BuiltInSymbols.create_motor,
            "lamp": BuiltInSymbols.create_lamp,
            "transformer": BuiltInSymbols.create_transformer,
            "fuse": BuiltInSymbols.create_fuse,
        }
        
        if component_type in symbols:
            return symbols[component_type]()
        else:
            # Default: rectangle with component name
            group = QGraphicsItemGroup()
            rect = QGraphicsRectItem(0, 0, 80, 40)
            rect.setPen(QPen(COLOR_TEXT, 2))
            rect.setBrush(QBrush(COLOR_BACKGROUND))
            group.addToGroup(rect)
            
            label = QGraphicsTextItem(component_type.upper())
            label.setDefaultTextColor(COLOR_TEXT)
            label.setPos(10, 10)
            label.setScale(0.8)
            group.addToGroup(label)
            
            return group

# -------------------------
# Graphics items: symbol group & wire item
# -------------------------
class SymbolItem(QGraphicsItemGroup):
    def __init__(self, component_type: str, parent=None):
        super().__init__(parent)
        self.component_type = component_type
        self.comp_id = str(uuid4())
        self.create_graphics()
        
        # Set up properties
        self.setFlags(
            QGraphicsItemGroup.ItemIsMovable |
            QGraphicsItemGroup.ItemIsSelectable |
            QGraphicsItemGroup.ItemIsFocusable |
            QGraphicsItemGroup.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.OpenHandCursor)
        
        # Connection points
        self.connection_points = []
        self.add_connection_points()
        
        # Connected wires
        self.connected_wires = []
    
    def create_graphics(self):
        """Create the symbol graphics"""
        # Clear any existing children
        for child in self.childItems()[:]:
            self.removeFromGroup(child)
        
        # Get the built-in symbol
        symbol = BuiltInSymbols.get_symbol(self.component_type)
        
        # Add all items from the symbol to this group
        for child in symbol.childItems():
            self.addToGroup(child)
        
        # Store the symbol's position
        self.setPos(0, 0)
    
    def add_connection_points(self):
        """Add connection points to the symbol"""
        bbox = self.boundingRect()
        
        # Points at midpoints of each side
        self.connection_points = [
            (bbox.left(), bbox.center().y()),     # Left
            (bbox.right(), bbox.center().y()),    # Right
            (bbox.center().x(), bbox.top()),      # Top
            (bbox.center().x(), bbox.bottom())    # Bottom
        ]
    
    def get_connection_point(self, index):
        """Get a connection point in scene coordinates"""
        if 0 <= index < len(self.connection_points):
            x, y = self.connection_points[index]
            return self.mapToScene(QPointF(x, y))
        return self.sceneBoundingRect().center()
    
    def contextMenuEvent(self, event):
        """Right-click context menu"""
        menu = QMenu()
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_symbol)
        
        rotate_action = QAction("Rotate 90°", self)
        rotate_action.triggered.connect(self.rotate_symbol)
        
        properties_action = QAction("Properties", self)
        properties_action.triggered.connect(self.show_properties)
        
        menu.addAction(rotate_action)
        menu.addAction(properties_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        
        menu.exec(event.screenPos())
    
    def delete_symbol(self):
        """Delete this symbol"""
        scene = self.scene()
        if scene:
            # Remove connected wires
            for wire in self.connected_wires[:]:
                scene.removeItem(wire)
            scene.removeItem(self)
    
    def rotate_symbol(self):
        """Rotate the symbol 90 degrees"""
        self.setRotation(self.rotation() + 90)
        self.update_connected_wires()
    
    def update_connected_wires(self):
        """Update all connected wires"""
        for wire in self.connected_wires:
            if hasattr(wire, 'update_connection'):
                wire.update_connection()
    
    def show_properties(self):
        """Show symbol properties dialog"""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.component_type.upper()} Properties")
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2A2A35;
            }
            QLabel {
                color: #F0F0F0;
            }
            QGroupBox {
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout2()
        
        # Position controls
        pos_group = QGroupBox("Position")
        pos_layout = QVBoxLayout2()
        
        x_spin = QDoubleSpinBox()
        x_spin.setRange(-10000, 10000)
        x_spin.setValue(self.x())
        x_spin.setPrefix("X: ")
        x_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        y_spin = QDoubleSpinBox()
        y_spin.setRange(-10000, 10000)
        y_spin.setValue(self.y())
        y_spin.setPrefix("Y: ")
        y_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        rot_spin = QDoubleSpinBox()
        rot_spin.setRange(-360, 360)
        rot_spin.setValue(self.rotation())
        rot_spin.setPrefix("Rotation: ")
        rot_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        pos_layout.addWidget(x_spin)
        pos_layout.addWidget(y_spin)
        pos_layout.addWidget(rot_spin)
        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            self.setPos(x_spin.value(), y_spin.value())
            self.setRotation(rot_spin.value())
            self.update_connected_wires()
    
    def to_dict(self):
        """Convert to dictionary for saving"""
        pos = self.pos()
        return {
            "id": self.comp_id,
            "type": self.component_type,
            "x": pos.x(),
            "y": pos.y(),
            "rotation": self.rotation()
        }
    
    @staticmethod
    def from_dict(d, scene):
        """Create from dictionary"""
        item = SymbolItem(d["type"])
        item.setPos(d.get("x", 0), d.get("y", 0))
        item.setRotation(d.get("rotation", 0))
        scene.addItem(item)
        return item

class WireItem(QGraphicsLineItem):
    def __init__(self, x1, y1, x2, y2, parent=None):
        super().__init__(x1, y1, x2, y2, parent)
        self.setPen(QPen(COLOR_TEXT, 3))
        self.setFlags(
            QGraphicsLineItem.ItemIsSelectable |
            QGraphicsLineItem.ItemIsFocusable |
            QGraphicsLineItem.ItemIsMovable
        )
        self.setAcceptHoverEvents(True)
        
        # Connected symbols
        self.start_symbol = None
        self.end_symbol = None
        self.start_point_idx = -1
        self.end_point_idx = -1
        
        # Drag handles
        self.drag_handle_size = 8
        self.create_drag_handles()
        self.dragging_endpoint = None
    
    def create_drag_handles(self):
        """Create drag handles at endpoints"""
        line = self.line()
        
        # Start handle
        self.start_handle = QGraphicsEllipseItem(
            line.x1() - self.drag_handle_size/2,
            line.y1() - self.drag_handle_size/2,
            self.drag_handle_size, self.drag_handle_size,
            self
        )
        self.start_handle.setPen(QPen(COLOR_ACCENT, 1))
        self.start_handle.setBrush(QBrush(COLOR_BACKGROUND))
        self.start_handle.setVisible(False)
        
        # End handle
        self.end_handle = QGraphicsEllipseItem(
            line.x2() - self.drag_handle_size/2,
            line.y2() - self.drag_handle_size/2,
            self.drag_handle_size, self.drag_handle_size,
            self
        )
        self.end_handle.setPen(QPen(COLOR_ACCENT, 1))
        self.end_handle.setBrush(QBrush(COLOR_BACKGROUND))
        self.end_handle.setVisible(False)
    
    def show_drag_handles(self, show=True):
        """Show or hide drag handles"""
        self.start_handle.setVisible(show)
        self.end_handle.setVisible(show)
    
    def hoverEnterEvent(self, event):
        """Show handles when hovering"""
        if self.isSelected():
            self.show_drag_handles(True)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Hide handles when leaving"""
        self.show_drag_handles(False)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        pos = event.pos()
        line = self.line()
        
        # Check if clicking near start handle
        if (pos - line.p1()).manhattanLength() < 15:
            self.dragging_endpoint = 'start'
            event.accept()
            return
        
        # Check if clicking near end handle
        if (pos - line.p2()).manhattanLength() < 15:
            self.dragging_endpoint = 'end'
            event.accept()
            return
        
        # Otherwise, drag the entire wire
        self.dragging_endpoint = None
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse movement for dragging"""
        if self.dragging_endpoint:
            # Update the dragged endpoint
            scene_pos = self.mapToScene(event.pos())
            line = self.line()
            
            if self.dragging_endpoint == 'start':
                self.setLine(scene_pos.x(), scene_pos.y(), line.x2(), line.y2())
            else:  # 'end'
                self.setLine(line.x1(), line.y1(), scene_pos.x(), scene_pos.y())
            
            # Update drag handles
            self.update_drag_handles()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if self.dragging_endpoint:
            self.dragging_endpoint = None
            # Snap to nearby symbols
            self.snap_to_nearest_symbols()
        super().mouseReleaseEvent(event)
    
    def update_drag_handles(self):
        """Update drag handle positions"""
        line = self.line()
        self.start_handle.setRect(
            line.x1() - self.drag_handle_size/2,
            line.y1() - self.drag_handle_size/2,
            self.drag_handle_size, self.drag_handle_size
        )
        self.end_handle.setRect(
            line.x2() - self.drag_handle_size/2,
            line.y2() - self.drag_handle_size/2,
            self.drag_handle_size, self.drag_handle_size
        )
    
    def snap_to_nearest_symbols(self):
        """Snap wire endpoints to nearest symbols"""
        scene = self.scene()
        if not scene:
            return
        
        line = self.line()
        snap_distance = 30
        
        # Check start point
        start_pos = self.mapToScene(line.p1())
        start_symbol, start_idx = self.find_nearest_connection(start_pos, snap_distance)
        if start_symbol:
            self.start_symbol = start_symbol
            self.start_point_idx = start_idx
            start_symbol.connected_wires.append(self)
            point_pos = start_symbol.get_connection_point(start_idx)
            local_pos = self.mapFromScene(point_pos)
            self.setLine(local_pos.x(), local_pos.y(), line.x2(), line.y2())
        
        # Check end point
        end_pos = self.mapToScene(line.p2())
        end_symbol, end_idx = self.find_nearest_connection(end_pos, snap_distance)
        if end_symbol:
            self.end_symbol = end_symbol
            self.end_point_idx = end_idx
            end_symbol.connected_wires.append(self)
            point_pos = end_symbol.get_connection_point(end_idx)
            local_pos = self.mapFromScene(point_pos)
            self.setLine(line.x1(), line.y1(), local_pos.x(), local_pos.y())
    
    def find_nearest_connection(self, scene_pos, max_distance):
        """Find nearest connection point"""
        scene = self.scene()
        if not scene:
            return None, -1
        
        nearest_symbol = None
        nearest_idx = -1
        min_dist = float('inf')
        
        for item in scene.items():
            if isinstance(item, SymbolItem):
                for i in range(len(item.connection_points)):
                    point_pos = item.get_connection_point(i)
                    dist = (point_pos - scene_pos).manhattanLength()
                    if dist < min_dist and dist < max_distance:
                        min_dist = dist
                        nearest_symbol = item
                        nearest_idx = i
        
        return nearest_symbol, nearest_idx
    
    def update_connection(self):
        """Update wire position when connected symbol moves"""
        line = self.line()
        
        if self.start_symbol and self.start_point_idx >= 0:
            point_pos = self.start_symbol.get_connection_point(self.start_point_idx)
            local_pos = self.mapFromScene(point_pos)
            self.setLine(local_pos.x(), local_pos.y(), line.x2(), line.y2())
        
        if self.end_symbol and self.end_point_idx >= 0:
            point_pos = self.end_symbol.get_connection_point(self.end_point_idx)
            local_pos = self.mapFromScene(point_pos)
            self.setLine(line.x1(), line.y1(), local_pos.x(), local_pos.y())
    
    def contextMenuEvent(self, event):
        """Right-click context menu"""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
            }
            QMenu::item {
                padding: 5px 20px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
        """)
        
        delete_action = QAction("Delete Wire", self)
        delete_action.triggered.connect(self.delete_wire)
        
        edit_action = QAction("Edit Wire", self)
        edit_action.triggered.connect(self.edit_wire)
        
        menu.addAction(edit_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        
        menu.exec(event.screenPos())
    
    def delete_wire(self):
        """Delete this wire"""
        scene = self.scene()
        if scene:
            # Remove from connected symbols
            if self.start_symbol and self in self.start_symbol.connected_wires:
                self.start_symbol.connected_wires.remove(self)
            if self.end_symbol and self in self.end_symbol.connected_wires:
                self.end_symbol.connected_wires.remove(self)
            
            scene.removeItem(self)
    
    def edit_wire(self):
        """Edit wire properties"""
        dialog = QDialog()
        dialog.setWindowTitle("Edit Wire")
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2A2A35;
            }
            QLabel {
                color: #F0F0F0;
            }
        """)
        layout = QVBoxLayout2()
        
        line = self.line()
        
        x1_spin = QDoubleSpinBox()
        x1_spin.setRange(-10000, 10000)
        x1_spin.setValue(line.x1())
        x1_spin.setPrefix("X1: ")
        x1_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        y1_spin = QDoubleSpinBox()
        y1_spin.setRange(-10000, 10000)
        y1_spin.setValue(line.y1())
        y1_spin.setPrefix("Y1: ")
        y1_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        x2_spin = QDoubleSpinBox()
        x2_spin.setRange(-10000, 10000)
        x2_spin.setValue(line.x2())
        x2_spin.setPrefix("X2: ")
        x2_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        y2_spin = QDoubleSpinBox()
        y2_spin.setRange(-10000, 10000)
        y2_spin.setValue(line.y2())
        y2_spin.setPrefix("Y2: ")
        y2_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        layout.addWidget(x1_spin)
        layout.addWidget(y1_spin)
        layout.addWidget(x2_spin)
        layout.addWidget(y2_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            self.setLine(x1_spin.value(), y1_spin.value(), x2_spin.value(), y2_spin.value())
            self.update_drag_handles()
    
    def to_dict(self):
        """Convert to dictionary for saving"""
        line = self.line()
        return {
            "x1": line.x1(), "y1": line.y1(),
            "x2": line.x2(), "y2": line.y2(),
            "start_symbol": self.start_symbol.comp_id if self.start_symbol else None,
            "end_symbol": self.end_symbol.comp_id if self.end_symbol else None,
            "start_point_idx": self.start_point_idx,
            "end_point_idx": self.end_point_idx
        }

# -------------------------
# Diagram Canvas with Grid Background
# -------------------------
class DiagramCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        scene = QGraphicsScene()
        scene.setSceneRect(-2000, -2000, 4000, 4000)
        self.setScene(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        
        # Enable scroll bars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # Grid settings
        self.show_grid = True
        self.grid_size = GRID_SIZE
        self.major_grid_size = GRID_MAJOR_SIZE
        
        self.wire_mode = False
        self.wire_start = None
        self.temp_wire = None
        
        # Set background color
        self.setBackgroundBrush(QBrush(COLOR_BACKGROUND))
    
    def set_wire_mode(self, enabled):
        """Set wire drawing mode"""
        self.wire_mode = enabled
        self.wire_start = None
        if self.temp_wire:
            self.scene().removeItem(self.temp_wire)
            self.temp_wire = None
        
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            self.setDragMode(QGraphicsView.RubberBandDrag)
    
    def toggle_grid(self):
        """Toggle grid visibility"""
        self.show_grid = not self.show_grid
        self.viewport().update()
    
    def drawBackground(self, painter, rect):
        """Draw grid background with only dotted grid"""
        if not self.show_grid:
            return
        
        painter.save()
        
        # Fill background with dark color
        painter.fillRect(rect, QBrush(COLOR_BACKGROUND))
        
        # Get the visible rectangle in scene coordinates
        view_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        
        # Calculate grid boundaries
        left = int(view_rect.left() / self.grid_size) * self.grid_size
        top = int(view_rect.top() / self.grid_size) * self.grid_size
        right = int(view_rect.right() / self.grid_size) * self.grid_size
        bottom = int(view_rect.bottom() / self.grid_size) * self.grid_size
        
        # Draw only dotted minor grid lines
        painter.setPen(QPen(GRID_COLOR_MINOR, 1, Qt.DotLine))
        
        # Draw vertical grid lines
        x = left
        while x <= right:
            painter.drawLine(x, top, x, bottom)
            x += self.grid_size
        
        # Draw horizontal grid lines
        y = top
        while y <= bottom:
            painter.drawLine(left, y, right, y)
            y += self.grid_size
        
        painter.restore()
    
    def place_symbol(self, component_type, pos):
        """Place a symbol on the canvas"""
        item = SymbolItem(component_type)
        item.setPos(pos)
        self.scene().addItem(item)
        return item
    
    def mousePressEvent(self, event):
        if self.wire_mode and event.button() == Qt.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            
            if self.wire_start is None:
                # Start new wire
                self.wire_start = pos
                self.temp_wire = QGraphicsLineItem(pos.x(), pos.y(), pos.x(), pos.y())
                self.temp_wire.setPen(QPen(COLOR_TEXT, 2, Qt.DashLine))
                self.scene().addItem(self.temp_wire)
            else:
                # Finish wire
                wire = WireItem(self.wire_start.x(), self.wire_start.y(), pos.x(), pos.y())
                self.scene().addItem(wire)
                
                # Try to snap to symbols
                wire.snap_to_nearest_symbols()
                
                # Cleanup
                if self.temp_wire:
                    self.scene().removeItem(self.temp_wire)
                    self.temp_wire = None
                self.wire_start = None
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.wire_mode and self.wire_start is not None and self.temp_wire:
            pos = self.mapToScene(event.position().toPoint())
            self.temp_wire.setLine(self.wire_start.x(), self.wire_start.y(), pos.x(), pos.y())
        else:
            super().mouseMoveEvent(event)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Delete:
            # Delete selected items
            for item in self.scene().selectedItems()[:]:
                self.scene().removeItem(item)
        elif event.key() == Qt.Key_Escape:
            # Clear selection
            self.scene().clearSelection()
        elif event.key() == Qt.Key_G:
            # Toggle grid with Ctrl+G
            if event.modifiers() & Qt.ControlModifier:
                self.toggle_grid()
        super().keyPressEvent(event)

# -------------------------
# Prompt Parser
# -------------------------
class PromptParser:
    def __init__(self):
        self.component_types = [
            "resistor", "capacitor", "inductor", "battery", 
            "ground", "led", "diode", "switch", "motor", 
            "lamp", "transformer", "fuse"
        ]
    
    def parse_prompt(self, prompt_text, layout_style="auto"):
        """Parse natural language prompt"""
        prompt = prompt_text.lower()
        components = []
        
        # Check for each component type
        for comp_type in self.component_types:
            if comp_type in prompt:
                components.append({
                    "type": comp_type,
                    "x": 0,  # Will be arranged
                    "y": 0
                })
        
        # Also check for abbreviations
        if "r" in prompt.split() and "resistor" not in prompt:
            components.append({"type": "resistor", "x": 0, "y": 0})
        if "c" in prompt.split() and "capacitor" not in prompt:
            components.append({"type": "capacitor", "x": 0, "y": 0})
        if "l" in prompt.split() and "inductor" not in prompt:
            components.append({"type": "inductor", "x": 0, "y": 0})
        
        # Auto-arrange
        if components:
            components = self.auto_arrange(components, layout_style)
        
        # Create simple connections
        wires = []
        for i in range(len(components) - 1):
            wires.append([i, i + 1])
        
        return {"components": components, "wires": wires}
    
    def auto_arrange(self, components, style="grid"):
        """Arrange components"""
        if style == "grid":
            return self.arrange_grid(components)
        elif style == "horizontal":
            return self.arrange_horizontal(components)
        elif style == "vertical":
            return self.arrange_vertical(components)
        else:
            return self.arrange_grid(components)
    
    def arrange_grid(self, components):
        """Grid arrangement"""
        cols = math.ceil(math.sqrt(len(components)))
        for i, comp in enumerate(components):
            row = i // cols
            col = i % cols
            comp["x"] = col * 200
            comp["y"] = row * 150
        return components
    
    def arrange_horizontal(self, components):
        """Horizontal arrangement"""
        for i, comp in enumerate(components):
            comp["x"] = i * 150
            comp["y"] = 0
        return components
    
    def arrange_vertical(self, components):
        """Vertical arrangement"""
        for i, comp in enumerate(components):
            comp["x"] = 0
            comp["y"] = i * 120
        return components

# -------------------------
# Simplified Dark Theme Sidebar
# -------------------------
class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.parser = PromptParser()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title_label = QLabel("Circuit Designer")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #3498db; margin-bottom: 20px;")
        layout.addWidget(title_label)
        
        # AI Circuit Generator
        ai_label = QLabel("AI Circuit Generator")
        ai_label.setFont(QFont("Arial", 11, QFont.Bold))
        ai_label.setStyleSheet("color: #F0F0F0; margin-top: 10px;")
        layout.addWidget(ai_label)
        
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Describe your circuit...\nExample: 'LED circuit with 2 resistors and a battery'")
        self.prompt_text.setMaximumHeight(80)
        self.prompt_text.setStyleSheet("""
            QTextEdit {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.prompt_text)
        
        generate_btn = QPushButton("Generate Circuit")
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        generate_btn.clicked.connect(self.generate_circuit)
        layout.addWidget(generate_btn)
        
        layout.addSpacing(20)
        
        # Edit Mode
        mode_label = QLabel("Edit Mode")
        mode_label.setFont(QFont("Arial", 11, QFont.Bold))
        mode_label.setStyleSheet("color: #F0F0F0;")
        layout.addWidget(mode_label)
        
        mode_buttons_layout = QHBoxLayout()
        
        self.select_btn = QPushButton("Select")
        self.select_btn.setCheckable(True)
        self.select_btn.setChecked(True)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #3498db;
                border-color: #3498db;
            }
            QPushButton:hover {
                background-color: #464650;
            }
        """)
        self.select_btn.clicked.connect(lambda: self.set_mode("select"))
        mode_buttons_layout.addWidget(self.select_btn)
        
        self.wire_btn = QPushButton("Wire")
        self.wire_btn.setCheckable(True)
        self.wire_btn.setStyleSheet("""
            QPushButton {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #3498db;
                border-color: #3498db;
            }
            QPushButton:hover {
                background-color: #464650;
            }
        """)
        self.wire_btn.clicked.connect(lambda: self.set_mode("wire"))
        mode_buttons_layout.addWidget(self.wire_btn)
        
        layout.addLayout(mode_buttons_layout)
        
        layout.addSpacing(20)
        
        # Component Library
        comp_label = QLabel("Add Components")
        comp_label.setFont(QFont("Arial", 11, QFont.Bold))
        comp_label.setStyleSheet("color: #F0F0F0;")
        layout.addWidget(comp_label)
        
        # Component buttons grid
        component_grid = QGridLayout()
        component_grid.setSpacing(8)
        
        components = [
            "Resistor", "Capacitor", "Inductor", "Battery",
            "Ground", "LED", "Diode", "Switch", "Motor",
            "Lamp", "Transformer", "Fuse"
        ]
        
        for i, comp in enumerate(components):
            btn = QPushButton(comp)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3A3A45;
                    color: #F0F0F0;
                    border: 1px solid #464650;
                    border-radius: 5px;
                    padding: 8px 5px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #464650;
                }
                QPushButton:pressed {
                    background-color: #3498db;
                }
            """)
            btn.clicked.connect(lambda checked, c=comp: self.add_component(c.lower()))
            component_grid.addWidget(btn, i // 3, i % 3)
        
        layout.addLayout(component_grid)
        
        layout.addSpacing(20)
        
        # Quick Actions
        actions_label = QLabel("Quick Actions")
        actions_label.setFont(QFont("Arial", 11, QFont.Bold))
        actions_label.setStyleSheet("color: #F0F0F0;")
        layout.addWidget(actions_label)
        
        actions_layout = QHBoxLayout()
        
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #922b21;
            }
        """)
        delete_btn.clicked.connect(self.delete_selected)
        actions_layout.addWidget(delete_btn)
        
        rotate_btn = QPushButton("Rotate")
        rotate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        rotate_btn.clicked.connect(self.rotate_selected)
        actions_layout.addWidget(rotate_btn)
        
        layout.addLayout(actions_layout)
        
        layout.addStretch()
        
        # Status info at bottom
        info_label = QLabel("Tip: Ctrl+G to toggle grid\nCtrl+Delete to delete selected")
        info_label.setFont(QFont("Arial", 9))
        info_label.setStyleSheet("color: #B4B4C0; margin-top: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.setLayout(layout)
        self.setMaximumWidth(300)
        self.setStyleSheet("""
            QWidget {
                background-color: #282834;
            }
        """)
    
    def set_mode(self, mode):
        """Set edit mode"""
        if mode == "select":
            self.select_btn.setChecked(True)
            self.wire_btn.setChecked(False)
            self.main_window.canvas.set_wire_mode(False)
            self.main_window.status.showMessage("Select Mode: Click and drag to select items")
        elif mode == "wire":
            self.select_btn.setChecked(False)
            self.wire_btn.setChecked(True)
            self.main_window.canvas.set_wire_mode(True)
            self.main_window.status.showMessage("Wire Mode: Click to start wire, click again to end")
    
    def delete_selected(self):
        """Delete selected items"""
        for item in self.main_window.canvas.scene().selectedItems()[:]:
            self.main_window.canvas.scene().removeItem(item)
    
    def rotate_selected(self):
        """Rotate selected symbols"""
        for item in self.main_window.canvas.scene().selectedItems():
            if isinstance(item, SymbolItem):
                item.setRotation(item.rotation() + 90)
    
    def add_component(self, component_type):
        """Add selected component"""
        view_center = self.main_window.canvas.mapToScene(
            self.main_window.canvas.viewport().rect().center()
        )
        
        # Snap to grid
        grid_x = round(view_center.x() / GRID_SIZE) * GRID_SIZE
        grid_y = round(view_center.y() / GRID_SIZE) * GRID_SIZE
        
        self.main_window.canvas.place_symbol(component_type, QPointF(grid_x, grid_y))
        self.main_window.status.showMessage(f"Added {component_type} to canvas", 2000)
    
    def generate_circuit(self):
        """Generate circuit from prompt"""
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a circuit description.")
            return
        
        # Parse prompt
        config = self.parser.parse_prompt(prompt, "grid")
        
        if not config["components"]:
            QMessageBox.warning(self, "No Components", "Could not identify components from your description.")
            return
        
        # Generate diagram
        self.main_window.generate_diagram(config)

# -------------------------
# Main Window with Dark Theme
# -------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrical Circuit Designer")
        self.resize(1400, 800)
        
        # Apply dark theme style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1E1E28;
            }
            QMenuBar {
                background-color: #282834;
                color: #F0F0F0;
                border-bottom: 1px solid #464650;
            }
            QMenuBar::item {
                padding: 5px 15px;
            }
            QMenuBar::item:selected {
                background-color: #3498db;
            }
            QMenu {
                background-color: #3A3A45;
                color: #F0F0F0;
                border: 1px solid #464650;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
            QStatusBar {
                background-color: #282834;
                color: #B4B4C0;
                border-top: 1px solid #464650;
            }
        """)
        
        # Create menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.clear_canvas)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("Save Diagram", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_diagram)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load Diagram", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_diagram)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        # Export submenu
        export_menu = file_menu.addMenu("Export")
        
        export_dxf_action = QAction("Export DXF", self)
        export_dxf_action.triggered.connect(self.export_dxf)
        export_menu.addAction(export_dxf_action)
        
        export_png_action = QAction("Export PNG", self)
        export_png_action.triggered.connect(self.export_png)
        export_menu.addAction(export_png_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        clear_action = QAction("Clear All", self)
        clear_action.triggered.connect(self.clear_canvas)
        edit_menu.addAction(clear_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        toggle_grid_action = QAction("Toggle Grid", self)
        toggle_grid_action.setShortcut("Ctrl+G")
        toggle_grid_action.triggered.connect(self.toggle_grid)
        view_menu.addAction(toggle_grid_action)
        
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.canvas.scale(1.2, 1.2))
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.canvas.scale(1/1.2, 1/1.2))
        view_menu.addAction(zoom_out_action)
        
        view_menu.addSeparator()
        
        reset_view_action = QAction("Reset View", self)
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.triggered.connect(self.reset_view)
        view_menu.addAction(reset_view_action)
        
        # Central widget
        central = QWidget()
        central.setStyleSheet("background-color: #1E1E28;")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = Sidebar(self)
        layout.addWidget(self.sidebar)
        
        # Canvas area with coordinate display
        canvas_container = QWidget()
        canvas_container.setStyleSheet("background-color: #1E1E28;")
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        
        # Coordinate display bar
        coord_bar = QFrame()
        coord_bar.setStyleSheet("""
            QFrame {
                background-color: #282834;
                padding: 5px 15px;
                border-bottom: 1px solid #464650;
            }
            QLabel {
                color: #B4B4C0;
                font-size: 11px;
            }
        """)
        coord_bar.setMaximumHeight(30)
        coord_layout = QHBoxLayout(coord_bar)
        
        self.coord_label = QLabel("X: 0, Y: 0")
        self.coord_label.setFont(QFont("Arial", 10))
        coord_layout.addWidget(self.coord_label)
        coord_layout.addStretch()
        
        self.grid_status = QLabel("Grid: ON")
        self.grid_status.setFont(QFont("Arial", 10))
        coord_layout.addWidget(self.grid_status)
        
        canvas_layout.addWidget(coord_bar)
        
        # Canvas
        self.canvas = DiagramCanvas()
        self.canvas.mouseMoveEvent = self.canvas_mouse_move_event
        canvas_layout.addWidget(self.canvas)
        
        layout.addWidget(canvas_container, 1)
        
        self.setCentralWidget(central)
        
        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready - Select Mode | Press Ctrl+G to toggle grid")
    
    def canvas_mouse_move_event(self, event):
        """Handle mouse movement on canvas and update coordinates"""
        pos = self.canvas.mapToScene(event.position().toPoint())
        
        # Snap to grid
        grid_x = round(pos.x() / GRID_SIZE) * GRID_SIZE
        grid_y = round(pos.y() / GRID_SIZE) * GRID_SIZE
        
        # Update coordinate display
        self.coord_label.setText(f"X: {grid_x}, Y: {grid_y}")
        
        # Call original mouse move event
        QGraphicsView.mouseMoveEvent(self.canvas, event)
    
    def toggle_grid(self):
        """Toggle grid visibility"""
        self.canvas.toggle_grid()
        self.grid_status.setText("Grid: ON" if self.canvas.show_grid else "Grid: OFF")
        self.status.showMessage("Grid toggled", 2000)
    
    def reset_view(self):
        """Reset view to center"""
        self.canvas.resetTransform()
        self.canvas.centerOn(0, 0)
        self.status.showMessage("View reset to center", 2000)
    
    def generate_diagram(self, config):
        """Generate diagram from configuration"""
        self.clear_canvas()
        
        # Create symbols
        symbols = []
        for comp in config["components"]:
            # Snap to grid
            grid_x = round(comp["x"] / GRID_SIZE) * GRID_SIZE
            grid_y = round(comp["y"] / GRID_SIZE) * GRID_SIZE
            
            symbol = self.canvas.place_symbol(comp["type"], QPointF(grid_x, grid_y))
            symbols.append(symbol)
        
        # Create wires
        for wire in config["wires"]:
            if len(wire) == 2:
                idx1, idx2 = wire
                if idx1 < len(symbols) and idx2 < len(symbols):
                    # Connect center points
                    center1 = symbols[idx1].sceneBoundingRect().center()
                    center2 = symbols[idx2].sceneBoundingRect().center()
                    
                    # Snap to grid
                    center1_x = round(center1.x() / GRID_SIZE) * GRID_SIZE
                    center1_y = round(center1.y() / GRID_SIZE) * GRID_SIZE
                    center2_x = round(center2.x() / GRID_SIZE) * GRID_SIZE
                    center2_y = round(center2.y() / GRID_SIZE) * GRID_SIZE
                    
                    wire_item = WireItem(center1_x, center1_y, center2_x, center2_y)
                    self.canvas.scene().addItem(wire_item)
        
        # Center view on generated circuit
        if symbols:
            scene_rect = self.canvas.scene().itemsBoundingRect()
            self.canvas.fitInView(scene_rect, Qt.KeepAspectRatio)
        
        self.status.showMessage(f"Generated circuit with {len(symbols)} components", 3000)
    
    def save_diagram(self):
        """Save diagram to JSON"""
        data = {
            "components": [],
            "wires": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0",
                "grid_size": GRID_SIZE
            }
        }
        
        # Collect components
        for item in self.canvas.scene().items():
            if isinstance(item, SymbolItem):
                data["components"].append(item.to_dict())
        
        # Collect wires
        for item in self.canvas.scene().items():
            if isinstance(item, WireItem):
                data["wires"].append(item.to_dict())
        
        # Save file
        path, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)
                self.status.showMessage(f"Diagram saved to {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save: {e}")
    
    def load_diagram(self):
        """Load diagram from JSON"""
        path, _ = QFileDialog.getOpenFileName(self, "Load Diagram", "", "JSON Files (*.json)")
        if not path:
            return
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load: {e}")
            return
        
        # Clear canvas
        self.clear_canvas()
        
        # Load components
        symbol_map = {}
        for comp_data in data.get("components", []):
            symbol = SymbolItem.from_dict(comp_data, self.canvas.scene())
            symbol_map[comp_data["id"]] = symbol
        
        # Load wires
        for wire_data in data.get("wires", []):
            wire = WireItem(wire_data["x1"], wire_data["y1"], wire_data["x2"], wire_data["y2"])
            
            # Restore connections if possible
            start_id = wire_data.get("start_symbol")
            end_id = wire_data.get("end_symbol")
            start_idx = wire_data.get("start_point_idx", -1)
            end_idx = wire_data.get("end_point_idx", -1)
            
            if start_id in symbol_map and start_idx >= 0:
                wire.start_symbol = symbol_map[start_id]
                wire.start_point_idx = start_idx
                symbol_map[start_id].connected_wires.append(wire)
            
            if end_id in symbol_map and end_idx >= 0:
                wire.end_symbol = symbol_map[end_id]
                wire.end_point_idx = end_idx
                symbol_map[end_id].connected_wires.append(wire)
            
            self.canvas.scene().addItem(wire)
        
        # Center view
        if symbol_map:
            scene_rect = self.canvas.scene().itemsBoundingRect()
            self.canvas.fitInView(scene_rect, Qt.KeepAspectRatio)
        
        self.status.showMessage(f"Diagram loaded from {path}", 3000)
    
    def export_dxf(self):
        """Export diagram as DXF"""
        if ezdxf is None:
            QMessageBox.warning(self, "DXF Export", "ezdxf library not installed. Install with: pip install ezdxf")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Export DXF", "", "DXF Files (*.dxf)")
        if not path:
            return
        
        try:
            doc = ezdxf.new(dxfversion='R2010')
            msp = doc.modelspace()
            
            # Export symbols as rectangles
            for item in self.canvas.scene().items():
                if isinstance(item, SymbolItem):
                    bbox = item.sceneBoundingRect()
                    msp.add_line((bbox.left(), -bbox.top()), (bbox.right(), -bbox.top()))
                    msp.add_line((bbox.right(), -bbox.top()), (bbox.right(), -bbox.bottom()))
                    msp.add_line((bbox.right(), -bbox.bottom()), (bbox.left(), -bbox.bottom()))
                    msp.add_line((bbox.left(), -bbox.bottom()), (bbox.left(), -bbox.top()))
                    
                    # Add label
                    try:
                        center = bbox.center()
                        msp.add_text(item.component_type.upper(), 
                                    dxfattribs={'height': 3, 'insert': (center.x(), -center.y())})
                    except:
                        pass
                
                elif isinstance(item, WireItem):
                    line = item.line()
                    msp.add_line((line.x1(), -line.y1()), (line.x2(), -line.y2()))
            
            doc.saveas(path)
            self.status.showMessage(f"DXF exported to {path}", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "DXF Export Error", f"Could not export DXF: {e}")
    
    def export_png(self):
        """Export diagram as PNG"""
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG Files (*.png)")
        if not path:
            return
        
        try:
            # Get scene bounds
            rect = self.canvas.scene().itemsBoundingRect()
            
            # Create image
            image = QPixmap(int(rect.width() + 100), int(rect.height() + 100))
            image.fill(Qt.white)
            
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            self.canvas.scene().render(painter, QRectF(image.rect()), rect)
            painter.end()
            
            image.save(path)
            self.status.showMessage(f"PNG exported to {path}", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "PNG Export Error", f"Could not export PNG: {e}")
    
    def clear_canvas(self):
        """Clear the canvas"""
        reply = QMessageBox.question(self, "Clear Canvas", 
                                    "Are you sure you want to clear the canvas?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.canvas.scene().clear()
            self.status.showMessage("Canvas cleared", 2000)

# -------------------------
# Main Application
# -------------------------
def main():
    app = QApplication(sys.argv)
    
    # Set dark theme for application - simplified version
    app.setStyle("Fusion")
    
    # Apply dark theme using stylesheet instead of palette
    app.setStyleSheet("""
        QWidget {
            background-color: #1E1E28;
            color: #F0F0F0;
            font-family: Arial;
        }
        QMainWindow {
            background-color: #1E1E28;
        }
        QMenuBar {
            background-color: #282834;
            color: #F0F0F0;
            border-bottom: 1px solid #464650;
        }
        QMenuBar::item {
            padding: 5px 15px;
        }
        QMenuBar::item:selected {
            background-color: #3498db;
        }
        QMenu {
            background-color: #3A3A45;
            color: #F0F0F0;
            border: 1px solid #464650;
        }
        QMenu::item:selected {
            background-color: #3498db;
        }
        QStatusBar {
            background-color: #282834;
            color: #B4B4C0;
            border-top: 1px solid #464650;
        }
        QDialog {
            background-color: #2A2A35;
        }
        QLabel {
            color: #F0F0F0;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px 15px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #21618c;
        }
        QPushButton:disabled {
            background-color: #464650;
            color: #888888;
        }
        QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background-color: #3A3A45;
            color: #F0F0F0;
            border: 1px solid #464650;
            border-radius: 3px;
            padding: 5px;
        }
        QScrollBar:vertical {
            background-color: #2A2A35;
            width: 15px;
        }
        QScrollBar::handle:vertical {
            background-color: #464650;
            border-radius: 7px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #565660;
        }
    """)
    
    # Create and show window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()