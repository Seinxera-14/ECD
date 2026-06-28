import sys
import re
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
import json
import os
import ezdxf
import math

class WebBridge(QObject):
    """Bridge for communication between JavaScript and Python"""
    elementDoubleClicked = Signal(str, str, str)  # element_id, element_type, current_text
    elementEdited = Signal(str, str, str, float, float)  # element_id, element_type, new_text, x, y
    
    def __init__(self):
        super().__init__()
    
    @Slot(str, str, str)
    def onElementDoubleClicked(self, element_id, element_type, current_text):
        """Called from JavaScript when an element is double-clicked"""
        self.elementDoubleClicked.emit(element_id, element_type, current_text)
    
    @Slot(str, str, str, float, float)
    def onElementEdited(self, element_id, element_type, new_text, x, y):
        """Called from JavaScript when an element edit is completed"""
        self.elementEdited.emit(element_id, element_type, new_text, x, y)

class MermaidGenerator:
    """Generates Mermaid.js sequence diagrams from electrical distribution prompts (English/Japanese)"""
    
    def __init__(self):
        # Bilingual component mapping
        self.components_map = {
            "main incoming supply": {
                "en": "Main Incoming Supply<br/>(230V / 415V)",
                "ja": "主電源<br/>(230V / 415V)"
            },
            "main breaker": {
                "en": "Main Breaker<br/>(MCB/MCCB)",
                "ja": "主遮断器<br/>(MCB/MCCB)"
            },
            "busbar": {
                "en": "Busbar<br/>(Distribution)",
                "ja": "母線<br/>(配電)"
            },
            "neutral bar": {
                "en": "Neutral Bar",
                "ja": "中性線バー"
            },
            "earth bar": {
                "en": "Earth Bar",
                "ja": "接地バー"
            },
            "outgoing mcbs": {
                "en": "Outgoing MCBs",
                "ja": "出力MCB"
            },
            "load circuits": {
                "en": "Load Circuits<br/>(Lights, Sockets)",
                "ja": "負荷回路<br/>(照明、コンセント)"
            },
            "circuit breaker": {
                "en": "Circuit Breaker",
                "ja": "回路遮断器"
            },
            "distribution panel": {
                "en": "Distribution Panel",
                "ja": "分電盤"
            },
            "power source": {
                "en": "Power Source",
                "ja": "電源"
            }
        }
        
        # Bilingual keywords for parsing
        self.keywords_map = {
            "incoming": {
                "en": ["incoming", "supply", "source", "230v", "415v"],
                "ja": ["主電源", "受電", "電源", "入力電源", "230V", "415V"]
            },
            "breaker": {
                "en": ["breaker", "mcb", "mccb", "protection"],
                "ja": ["遮断器", "ブレーカー", "ブレーカ", "安全装置"]
            },
            "busbar": {
                "en": ["busbar", "distribution", "panel"],
                "ja": ["母線", "バスバー", "配電盤", "分電盤"]
            },
            "neutral": {
                "en": ["neutral", "return"],
                "ja": ["中性線", "ニュートラル", "零線", "N線"]
            },
            "earth": {
                "en": ["earth", "ground", "safety"],
                "ja": ["接地", "アース", "グラウンド", "地線", "E線"]
            },
            "outgoing": {
                "en": ["outgoing", "branch", "circuit"],
                "ja": ["出力", "分岐", "回路", "分岐回路"]
            },
            "load": {
                "en": ["load", "circuit", "light", "socket", "appliance"],
                "ja": ["負荷", "回路", "照明", "コンセント", "機器", "電気機器"]
            }
        }
        
        # Bilingual labels for diagram
        self.diagram_labels = {
            "section_incoming": {
                "en": "Incoming Source",
                "ja": "入力電源"
            },
            "section_distribution": {
                "en": "Distribution Panel Components",
                "ja": "分電盤部品"
            },
            "section_load": {
                "en": "Load Side",
                "ja": "負荷側"
            },
            "note_power_entry": {
                "en": "1. INCOMING POWER ENTRY",
                "ja": "1. 受電"
            },
            "note_internal": {
                "en": "2. INTERNAL DISTRIBUTION",
                "ja": "2. 内部配電"
            },
            "note_outgoing": {
                "en": "3. OUTGOING CIRCUITS",
                "ja": "3. 出力回路"
            },
            "wire_phase": {
                "en": "Phase/Line Wire (L)",
                "ja": "相線/ラインワイヤ (L)"
            },
            "wire_neutral": {
                "en": "Neutral Wire (N)",
                "ja": "中性線 (N)"
            },
            "wire_earth": {
                "en": "Earth Wire (E)",
                "ja": "接地線 (E)"
            },
            "action_energize": {
                "en": "Energize Busbar (L)",
                "ja": "母線を励磁 (L)"
            },
            "action_protection": {
                "en": "Protection: Overload/Short",
                "ja": "保護: 過負荷/短絡"
            },
            "action_distribute": {
                "en": "Distribute to Branch Breakers",
                "ja": "分岐ブレーカーに配電"
            },
            "action_feed": {
                "en": "Line (L) - Protected Feed",
                "ja": "ライン (L) - 保護給電"
            },
            "action_return": {
                "en": "Neutral (N) - Return Path",
                "ja": "中性線 (N) - 帰路"
            },
            "action_safety": {
                "en": "Earth (E) - Safety Grounding",
                "ja": "接地 (E) - 安全接地"
            }
        }
        
        self.color_map = {
            "incoming": "#eef2ff",  # Light blue
            "distribution": "#f0fdf4",  # Light green
            "load": "#fff7ed"  # Light orange
        }
    
    def detect_language(self, text):
        """Detect if text contains Japanese characters"""
        # Check for Japanese characters (Hiragana, Katakana, Kanji)
        japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
        if japanese_pattern.search(text):
            return "ja"
        return "en"
    
    def parse_prompt(self, prompt_text):
        """Parse natural language prompt to extract diagram components (English/Japanese)"""
        if not prompt_text or not isinstance(prompt_text, str):
            return {
                "components": self.get_default_components("en"),
                "layout": "horizontal",
                "voltage": "230V / 415V",
                "language": "en"
            }
        
        prompt = prompt_text.lower()
        
        # Detect language
        language = self.detect_language(prompt_text)
        
        # Extract voltage information - FIXED REGEX
        voltage_text = "230V / 415V"
        try:
            # Try multiple patterns
            patterns = [
                r'(\d+)\s*[Vv]\s*[/／]?\s*(\d+)\s*[Vv]',  # 230V/415V
                r'(\d+)\s*[Vv]',  # Just 230V
                r'(\d+)\s*volts?',  # 230 volts
            ]
            
            for pattern in patterns:
                voltage_match = re.search(pattern, prompt_text)
                if voltage_match:
                    if len(voltage_match.groups()) >= 2:
                        voltage_text = f"{voltage_match.group(1)}V / {voltage_match.group(2)}V"
                    else:
                        voltage_text = f"{voltage_match.group(1)}V"
                    break
        except:
            voltage_text = "230V / 415V"
        
        # Check for layout preference
        layout = "horizontal"
        if "horizontal" in prompt or "水平" in prompt_text:
            layout = "horizontal"
        elif "vertical" in prompt or "垂直" in prompt_text:
            layout = "vertical"
        
        # Map components based on keywords in detected language
        found_components = []
        
        # Helper function to check keywords
        def check_keywords(category):
            en_keywords = self.keywords_map.get(category, {}).get("en", [])
            ja_keywords = self.keywords_map.get(category, {}).get("ja", [])
            
            # Check both English and Japanese keywords regardless of detected language
            en_match = any(keyword in prompt for keyword in en_keywords)
            ja_match = any(keyword in prompt_text for keyword in ja_keywords)
            return en_match or ja_match
        
        # Incoming source
        if check_keywords("incoming"):
            comp_label = self.components_map.get("main incoming supply", {}).get(language, "Main Incoming Supply")
            comp_label = comp_label.replace("230V / 415V", voltage_text)
            found_components.append(("supply", comp_label))
        
        # Protection components
        if check_keywords("breaker"):
            found_components.append(("maincb", self.components_map.get("main breaker", {}).get(language, "Main Breaker")))
        
        # Distribution components
        if check_keywords("busbar"):
            found_components.append(("bus", self.components_map.get("busbar", {}).get(language, "Busbar")))
        
        if check_keywords("neutral"):
            found_components.append(("nbar", self.components_map.get("neutral bar", {}).get(language, "Neutral Bar")))
        
        if check_keywords("earth"):
            found_components.append(("ebar", self.components_map.get("earth bar", {}).get(language, "Earth Bar")))
        
        # Outgoing protection
        if check_keywords("outgoing"):
            found_components.append(("outcb", self.components_map.get("outgoing mcbs", {}).get(language, "Outgoing MCBs")))
        
        # Load side
        if check_keywords("load"):
            found_components.append(("loads", self.components_map.get("load circuits", {}).get(language, "Load Circuits")))
        
        # If no specific components found, use default set
        if not found_components:
            found_components = self.get_default_components(language, voltage_text)
        
        return {
            "components": found_components,
            "layout": layout,
            "voltage": voltage_text,
            "language": language
        }

    def get_default_components(self, language, voltage_text="230V / 415V"):
        """Get default set of components"""
        return [
            ("supply", self.components_map.get("main incoming supply", {}).get(language, "Main Incoming Supply").replace("230V / 415V", voltage_text)),
            ("maincb", self.components_map.get("main breaker", {}).get(language, "Main Breaker")),
            ("bus", self.components_map.get("busbar", {}).get(language, "Busbar")),
            ("nbar", self.components_map.get("neutral bar", {}).get(language, "Neutral Bar")),
            ("ebar", self.components_map.get("earth bar", {}).get(language, "Earth Bar")),
            ("outcb", self.components_map.get("outgoing mcbs", {}).get(language, "Outgoing MCBs")),
            ("loads", self.components_map.get("load circuits", {}).get(language, "Load Circuits"))
        ]
    
    def generate_mermaid_code(self, parsed_data):
        """Generate Mermaid.js sequence diagram code in detected language"""
        components = parsed_data["components"]
        language = parsed_data.get("language", "en")
        
        # Create component map with IDs for editing
        comp_map = {}
        for comp_id, comp_label in components:
            comp_map[comp_id] = comp_label
        
        # Build the Mermaid diagram
        mermaid_code = """sequenceDiagram
    autonumber
    
    """
        
        # Add boxes for different sections
        mermaid_code += f"""    box "{self.diagram_labels['section_incoming'][language]}" #eef2ff
"""
        if "supply" in comp_map:
            mermaid_code += f"""        participant Supply as {comp_map['supply']}
"""
        mermaid_code += """    end
    
    """
        
        mermaid_code += f"""    box "{self.diagram_labels['section_distribution'][language]}" #f0fdf4
"""
        for comp_id, comp_label in components:
            if comp_id in ["maincb", "bus", "nbar", "ebar", "outcb"]:
                if comp_id == "maincb":
                    mermaid_code += f"""        participant MainCB as {comp_label}
"""
                elif comp_id == "bus":
                    mermaid_code += f"""        participant Bus as {comp_label}
"""
                elif comp_id == "nbar":
                    mermaid_code += f"""        participant NBar as {comp_label}
"""
                elif comp_id == "ebar":
                    mermaid_code += f"""        participant EBar as {comp_label}
"""
                elif comp_id == "outcb":
                    mermaid_code += f"""        participant OutCB as {comp_label}
"""
        mermaid_code += """    end
    
    """
        
        mermaid_code += f"""    box "{self.diagram_labels['section_load'][language]}" #fff7ed
"""
        if "loads" in comp_map:
            mermaid_code += f"""        participant Loads as {comp_map['loads']}
"""
        mermaid_code += """    end

    """
        
        # Add sequence steps
        mermaid_code += f"""    Note over Supply, EBar: {self.diagram_labels['note_power_entry'][language]}
    """
        
        # Add connections based on available components
        if "supply" in comp_map and "maincb" in comp_map:
            mermaid_code += f"""    Supply->>MainCB: {self.diagram_labels['wire_phase'][language]}
    """
        
        if "supply" in comp_map and "nbar" in comp_map:
            mermaid_code += f"""    Supply->>NBar: {self.diagram_labels['wire_neutral'][language]}
    """
        
        if "supply" in comp_map and "ebar" in comp_map:
            mermaid_code += f"""    Supply-->>EBar: {self.diagram_labels['wire_earth'][language]}
    
    """
        
        mermaid_code += f"""    Note over MainCB, OutCB: {self.diagram_labels['note_internal'][language]}
    """
        
        if "maincb" in comp_map and "bus" in comp_map:
            mermaid_code += f"""    MainCB->>Bus: {self.diagram_labels['action_energize'][language]}
    """
        
        if "bus" in comp_map and "outcb" in comp_map:
            mermaid_code += f"""    Note right of MainCB: {self.diagram_labels['action_protection'][language]}
    Bus->>OutCB: {self.diagram_labels['action_distribute'][language]}
    
    """
        
        mermaid_code += f"""    Note over OutCB, Loads: {self.diagram_labels['note_outgoing'][language]}
    """
        
        if "outcb" in comp_map and "loads" in comp_map:
            mermaid_code += f"""    OutCB->>Loads: {self.diagram_labels['action_feed'][language]}
    """
        
        if "nbar" in comp_map and "loads" in comp_map:
            mermaid_code += f"""    NBar->>Loads: {self.diagram_labels['action_return'][language]}
    """
        
        if "ebar" in comp_map and "loads" in comp_map:
            mermaid_code += f"""    EBar-->>Loads: {self.diagram_labels['action_safety'][language]}"""
        
        return mermaid_code
    
    def generate_display_html(self, mermaid_code, parsed_data, title=None, enable_editing=True):
        """Generate HTML for display with bilingual support and double-click editing"""
        language = parsed_data.get("language", "en")
        voltage = parsed_data.get("voltage", "230V / 415V")
        
        # Set title based on language
        if title is None:
            if language == "ja":
                title = "電力配電盤図"
            else:
                title = "Power Distribution Panel Diagram"
        
        # Bilingual key texts with safe defaults
        key_texts = {
            "en": {
                "logic_title": "Key Logic:",
                "logic_items": [
                    "Line (L) passes through Breakers",
                    "Neutral (N) goes direct to Neutral Bar", 
                    "Earth (E) goes direct to Earth Bar"
                ],
                "safety_title": "Safety:",
                "safety_items": [
                    "Main Breaker isolates entire panel",
                    "Outgoing MCBs protect individual circuits",
                    "Earth ensures chassis safety"
                ],
                "components_title": "Components:",
                "components_items": [
                    "<strong>MCCB:</strong> Molded Case Circuit Breaker",
                    "<strong>MCB:</strong> Miniature Circuit Breaker", 
                    "<strong>Busbar:</strong> Copper strip for distribution"
                ],
                "generated": "Generated from prompt description",
                "tip": "Tip: Double-click on any element to edit it"
            },
            "ja": {
                "logic_title": "主要ロジック:",
                "logic_items": [
                    "相線(L)は遮断器を通過",
                    "中性線(N)は中性線バーへ直接接続",
                    "接地線(E)は接地バーへ直接接続"
                ],
                "safety_title": "安全機能:",
                "safety_items": [
                    "主遮断器は全盤を絶縁",
                    "出力MCBは個々の回路を保護",
                    "接地は筐体の安全性を確保"
                ],
                "components_title": "構成部品:",
                "components_items": [
                    "<strong>MCCB:</strong> モールドケース遮断器",
                    "<strong>MCB:</strong> 配線用遮断器",
                    "<strong>Busbar:</strong> 銅製配電用導体"
                ],
                "generated": "プロンプトから生成",
                "tip": "ヒント: ダブルクリックで要素を編集できます"
            }
        }
        
        # Get key text for current language, default to English if not found
        key = key_texts.get(language, key_texts["en"])
        
        # JavaScript for double-click editing - SIMPLE AND RELIABLE VERSION
        editing_js = ""
        if enable_editing:
            editing_js = """
                <script>
                // Enhanced editor for Mermaid diagrams with better line dragging
                class EnhancedMermaidEditor {
                    constructor() {
                        this.currentEdit = null;
                        this.currentDrag = null;
                        this.dragStartTime = 0;
                        this.dragThreshold = 300; // 300ms for long press
                        this.setupEventListeners();
                    }
                    
                    setupEventListeners() {
                        // Wait for SVG to load
                        const checkInterval = setInterval(() => {
                            const svg = document.querySelector('.mermaid svg');
                            if (svg) {
                                clearInterval(checkInterval);
                                this.initSVG(svg);
                            }
                        }, 100);
                    }
                    
                    initSVG(svg) {
                        // Make sure all text is visible
                        this.ensureTextVisible(svg);
                        
                        // Get SVG transform for coordinate conversion
                        this.svg = svg;
                        this.svgPoint = svg.createSVGPoint();
                        
                        // Add double-click listener for text editing
                        svg.addEventListener('dblclick', (e) => this.handleDoubleClick(e, svg));
                        
                        // Add mouse events for line dragging
                        svg.addEventListener('mousedown', (e) => this.handleMouseDown(e));
                        svg.addEventListener('mousemove', (e) => this.handleMouseMove(e));
                        svg.addEventListener('mouseup', (e) => this.handleMouseUp(e));
                        svg.addEventListener('mouseleave', (e) => this.handleMouseUp(e));
                        
                        // Add hover effect for text
                        svg.addEventListener('mouseover', (e) => {
                            const target = e.target;
                            if (target.tagName === 'text' || target.tagName === 'tspan') {
                                target.style.cursor = 'text';
                                target.style.textShadow = '0 0 2px rgba(59, 130, 246, 0.5)';
                            } else if (this.isLineElement(target)) {
                                target.style.cursor = 'move';
                                target.style.strokeWidth = '3';
                            }
                        });
                        
                        svg.addEventListener('mouseout', (e) => {
                            const target = e.target;
                            if (target.tagName === 'text' || target.tagName === 'tspan') {
                                target.style.textShadow = '';
                            } else if (this.isLineElement(target) && !this.currentDrag) {
                                target.style.strokeWidth = '';
                            }
                        });
                    }
                    
                    ensureTextVisible(svg) {
                        // Force all text to be dark for visibility
                        const allText = svg.querySelectorAll('text, tspan');
                        allText.forEach(el => {
                            const currentFill = el.getAttribute('fill');
                            if (!currentFill || currentFill === 'currentColor' || currentFill === 'inherit') {
                                el.setAttribute('fill', '#333333');
                            } else if (currentFill === '#ffffff' || currentFill === '#fff' || 
                                    currentFill.startsWith('rgb(255') || currentFill === 'white') {
                                el.setAttribute('fill', '#333333');
                            }
                        });
                    }
                    
                    isLineElement(element) {
                        // Check if element is a line or path that could be dragged
                        if (!element) return false;
                        
                        const tagName = element.tagName;
                        const stroke = element.getAttribute('stroke');
                        
                        // Check for lines, paths, and polylines that have stroke
                        if ((tagName === 'line' || tagName === 'path' || tagName === 'polyline') && stroke) {
                            // Exclude very short lines or decorative elements
                            const className = element.getAttribute('class') || '';
                            if (className.includes('note') || className.includes('label') || className.includes('actor')) {
                                return false;
                            }
                            return true;
                        }
                        return false;
                    }
                    
                    // Convert screen coordinates to SVG coordinates
                    screenToSVG(svg, x, y) {
                        const pt = this.svgPoint;
                        pt.x = x;
                        pt.y = y;
                        return pt.matrixTransform(svg.getScreenCTM().inverse());
                    }
                    
                    handleMouseDown(e) {
                        if (this.currentEdit || this.currentDrag) return;
                        
                        const target = e.target;
                        
                        // Check if target is a line element
                        if (this.isLineElement(target)) {
                            e.preventDefault();
                            e.stopPropagation();
                            
                            // Get SVG coordinates for the click
                            const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                            
                            // Start tracking for long press
                            this.dragStartTime = Date.now();
                            this.potentialDrag = {
                                element: target,
                                startScreenX: e.clientX,
                                startScreenY: e.clientY,
                                startSVGX: svgCoords.x,
                                startSVGY: svgCoords.y,
                                originalLine: this.getLineData(target)
                            };
                            
                            // Highlight the line
                            target.style.stroke = '#ff6b6b';
                            target.style.strokeWidth = '3';
                        }
                    }
                    
                    handleMouseMove(e) {
                        // Handle line dragging
                        if (this.potentialDrag && !this.currentDrag) {
                            const timeElapsed = Date.now() - this.dragStartTime;
                            const dx = e.clientX - this.potentialDrag.startScreenX;
                            const dy = e.clientY - this.potentialDrag.startScreenY;
                            const distance = Math.sqrt(dx * dx + dy * dy);
                            
                            // Start dragging after threshold time OR if moved enough
                            if (timeElapsed > this.dragThreshold || distance > 3) {
                                this.startLineDrag(e);
                            }
                        } else if (this.currentDrag) {
                            this.updateLineDrag(e);
                        }
                    }
                    
                    handleMouseUp(e) {
                        // Finish dragging
                        if (this.currentDrag) {
                            this.finishLineDrag(e);
                        } else if (this.potentialDrag) {
                            // Cancel potential drag (click without drag)
                            this.cancelLineDrag();
                        }
                    }
                    
                    startLineDrag(e) {
                        if (!this.potentialDrag) return;
                        
                        // Get SVG coordinates
                        const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                        
                        this.currentDrag = {
                            element: this.potentialDrag.element,
                            startScreenX: this.potentialDrag.startScreenX,
                            startScreenY: this.potentialDrag.startScreenY,
                            startSVGX: this.potentialDrag.startSVGX,
                            startSVGY: this.potentialDrag.startSVGY,
                            originalLine: this.potentialDrag.originalLine,
                            currentSVGX: svgCoords.x,
                            currentSVGY: svgCoords.y
                        };
                        
                        // Show visual feedback
                        this.currentDrag.element.style.stroke = '#4299e1';
                        this.currentDrag.element.style.strokeWidth = '4';
                        this.currentDrag.element.style.strokeDasharray = '5,5';
                        
                        // Create a visual indicator
                        this.createDragIndicator();
                        
                        this.potentialDrag = null;
                    }
                    
                    updateLineDrag(e) {
                        if (!this.currentDrag) return;
                        
                        // Get current SVG coordinates
                        const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                        
                        // Calculate delta in SVG coordinates
                        const dxSVG = svgCoords.x - this.currentDrag.currentSVGX;
                        const dySVG = svgCoords.y - this.currentDrag.currentSVGY;
                        
                        // Update current position
                        this.currentDrag.currentSVGX = svgCoords.x;
                        this.currentDrag.currentSVGY = svgCoords.y;
                        
                        // Update line position based on drag direction
                        this.updateLinePosition(this.currentDrag.element, dxSVG, dySVG);
                        
                        // Update drag indicator
                        if (this.dragIndicator) {
                            const dxScreen = e.clientX - this.currentDrag.startScreenX;
                            const dyScreen = e.clientY - this.currentDrag.startScreenY;
                            this.dragIndicator.textContent = `Δx: ${dxScreen.toFixed(0)}, Δy: ${dyScreen.toFixed(0)}`;
                            this.dragIndicator.style.left = (e.clientX - 10) + 'px';
                            this.dragIndicator.style.top = (e.clientY - 10) + 'px';
                        }
                    }
                    
                    finishLineDrag(e) {
                        if (!this.currentDrag) return;
                        
                        // Get final SVG coordinates
                        const svgCoords = this.screenToSVG(this.svg, e.clientX, e.clientY);
                        const dxSVG = svgCoords.x - this.currentDrag.currentSVGX;
                        const dySVG = svgCoords.y - this.currentDrag.currentSVGY;
                        
                        // Final update to line position
                        this.updateLinePosition(this.currentDrag.element, dxSVG, dySVG);
                        
                        // Restore line style
                        this.currentDrag.element.style.stroke = '';
                        this.currentDrag.element.style.strokeWidth = '';
                        this.currentDrag.element.style.strokeDasharray = '';
                        
                        // Remove drag indicator
                        this.removeDragIndicator();
                        
                        // Notify Python about the change
                        if (window.qtBridge && window.qtBridge.onElementEdited) {
                            const dxScreen = e.clientX - this.currentDrag.startScreenX;
                            const dyScreen = e.clientY - this.currentDrag.startScreenY;
                            window.qtBridge.onElementEdited(
                                'line_' + Date.now(),
                                this.currentDrag.element.tagName,
                                `dx:${dxScreen.toFixed(1)},dy:${dyScreen.toFixed(1)}`,
                                e.clientX,
                                e.clientY
                            );
                        }
                        
                        // Show success message
                        const dxScreen = e.clientX - this.currentDrag.startScreenX;
                        const dyScreen = e.clientY - this.currentDrag.startScreenY;
                        this.showDragSuccess(dxScreen, dyScreen);
                        
                        this.currentDrag = null;
                    }
                    
                    cancelLineDrag() {
                        if (this.potentialDrag) {
                            // Restore original line style
                            this.potentialDrag.element.style.stroke = '';
                            this.potentialDrag.element.style.strokeWidth = '';
                            this.potentialDrag.element.style.strokeDasharray = '';
                        }
                        
                        this.potentialDrag = null;
                        this.currentDrag = null;
                        this.removeDragIndicator();
                    }
                    
                    getLineData(element) {
                        const tagName = element.tagName;
                        
                        if (tagName === 'line') {
                            return {
                                type: 'line',
                                x1: parseFloat(element.getAttribute('x1')),
                                y1: parseFloat(element.getAttribute('y1')),
                                x2: parseFloat(element.getAttribute('x2')),
                                y2: parseFloat(element.getAttribute('y2'))
                            };
                        } else if (tagName === 'polyline') {
                            return {
                                type: 'polyline',
                                points: element.getAttribute('points')
                            };
                        } else if (tagName === 'path') {
                            return {
                                type: 'path',
                                d: element.getAttribute('d')
                            };
                        }
                        
                        return null;
                    }
                    
                    updateLinePosition(element, dxSVG, dySVG) {
                        const tagName = element.tagName;
                        
                        if (tagName === 'line') {
                            // For simple lines
                            const x1 = parseFloat(element.getAttribute('x1'));
                            const y1 = parseFloat(element.getAttribute('y1'));
                            const x2 = parseFloat(element.getAttribute('x2'));
                            const y2 = parseFloat(element.getAttribute('y2'));
                            
                            // Determine line orientation
                            const isHorizontal = Math.abs(y2 - y1) < 10; // Threshold for horizontal
                            const isVertical = Math.abs(x2 - x1) < 10; // Threshold for vertical
                            
                            if (isHorizontal) {
                                // Horizontal line - only adjust x2
                                element.setAttribute('x2', (x2 + dxSVG).toString());
                            } else if (isVertical) {
                                // Vertical line - only adjust y2
                                element.setAttribute('y2', (y2 + dySVG).toString());
                            } else {
                                // Diagonal line - adjust based on primary direction
                                const angle = Math.atan2(y2 - y1, x2 - x1);
                                const dxAdjusted = dxSVG * Math.cos(angle);
                                const dyAdjusted = dySVG * Math.sin(angle);
                                element.setAttribute('x2', (x2 + dxAdjusted).toString());
                                element.setAttribute('y2', (y2 + dyAdjusted).toString());
                            }
                        } else if (tagName === 'polyline') {
                            // For polylines, adjust the last point
                            const pointsAttr = element.getAttribute('points');
                            const points = pointsAttr.split(' ');
                            
                            if (points.length >= 2) {
                                const lastPoint = points[points.length - 1];
                                const [lastX, lastY] = lastPoint.split(',').map(parseFloat);
                                
                                // Try to determine if we should adjust X or Y based on line direction
                                if (points.length >= 3) {
                                    const secondLastPoint = points[points.length - 2];
                                    const [secondLastX, secondLastY] = secondLastPoint.split(',').map(parseFloat);
                                    
                                    const isHorizontal = Math.abs(lastY - secondLastY) < 10;
                                    const isVertical = Math.abs(lastX - secondLastX) < 10;
                                    
                                    if (isHorizontal) {
                                        // Horizontal segment
                                        points[points.length - 1] = `${lastX + dxSVG},${lastY}`;
                                    } else if (isVertical) {
                                        // Vertical segment
                                        points[points.length - 1] = `${lastX},${lastY + dySVG}`;
                                    } else {
                                        // Diagonal
                                        points[points.length - 1] = `${lastX + dxSVG},${lastY + dySVG}`;
                                    }
                                } else {
                                    // Just adjust both coordinates
                                    points[points.length - 1] = `${lastX + dxSVG},${lastY + dySVG}`;
                                }
                                
                                element.setAttribute('points', points.join(' '));
                            }
                        } else if (tagName === 'path') {
                            // For paths, handle simple straight lines
                            const d = element.getAttribute('d');
                            if (d.includes('L') || d.includes('l')) {
                                // Simple line path
                                const commands = d.split(/(?=[A-Za-z])/);
                                
                                if (commands.length >= 2) {
                                    // Get last command (assuming it's a line to command)
                                    const lastCmd = commands[commands.length - 1];
                                    const cmdType = lastCmd.charAt(0);
                                    const coords = lastCmd.substring(1).trim().split(/[,\s]+/).map(parseFloat);
                                    
                                    if ((cmdType === 'L' || cmdType === 'l') && coords.length >= 2) {
                                        // Update line coordinates
                                        const lastX = coords[coords.length - 2];
                                        const lastY = coords[coords.length - 1];
                                        
                                        coords[coords.length - 2] = lastX + dxSVG;
                                        coords[coords.length - 1] = lastY + dySVG;
                                        
                                        commands[commands.length - 1] = cmdType + coords.join(',');
                                        element.setAttribute('d', commands.join(''));
                                    }
                                }
                            }
                        }
                    }
                    
                    createDragIndicator() {
                        // Remove existing indicator
                        this.removeDragIndicator();
                        
                        // Create new indicator
                        const indicator = document.createElement('div');
                        indicator.id = 'drag-indicator';
                        indicator.style.position = 'fixed';
                        indicator.style.left = '10px';
                        indicator.style.top = '10px';
                        indicator.style.backgroundColor = 'rgba(66, 153, 225, 0.9)';
                        indicator.style.color = 'white';
                        indicator.style.padding = '5px 10px';
                        indicator.style.borderRadius = '4px';
                        indicator.style.fontSize = '12px';
                        indicator.style.fontFamily = 'monospace';
                        indicator.style.zIndex = '10001';
                        indicator.style.pointerEvents = 'none';
                        indicator.textContent = 'Dragging line...';
                        
                        document.body.appendChild(indicator);
                        this.dragIndicator = indicator;
                    }
                    
                    removeDragIndicator() {
                        if (this.dragIndicator && this.dragIndicator.parentElement) {
                            this.dragIndicator.parentElement.removeChild(this.dragIndicator);
                        }
                        this.dragIndicator = null;
                    }
                    
                    showDragSuccess(dx, dy) {
                        const success = document.createElement('div');
                        success.style.position = 'fixed';
                        success.style.left = '50%';
                        success.style.top = '20px';
                        success.style.transform = 'translateX(-50%)';
                        success.style.backgroundColor = 'rgba(72, 187, 120, 0.9)';
                        success.style.color = 'white';
                        success.style.padding = '8px 16px';
                        success.style.borderRadius = '4px';
                        success.style.fontSize = '14px';
                        success.style.zIndex = '10001';
                        success.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
                        success.textContent = `Line adjusted: Δx=${dx.toFixed(0)}, Δy=${dy.toFixed(0)}`;
                        
                        document.body.appendChild(success);
                        
                        // Remove after 2 seconds
                        setTimeout(() => {
                            if (success.parentElement) {
                                success.parentElement.removeChild(success);
                            }
                        }, 2000);
                    }
                    
                    handleDoubleClick(event, svg) {
                        if (this.currentEdit || this.currentDrag) {
                            if (this.currentEdit) this.cancelEdit();
                            if (this.currentDrag) this.cancelLineDrag();
                            return;
                        }
                        
                        event.preventDefault();
                        event.stopPropagation();
                        
                        const target = event.target;
                        let textElement = null;
                        
                        // Find the text element
                        if (target.tagName === 'text') {
                            textElement = target;
                        } else if (target.tagName === 'tspan') {
                            textElement = target.parentElement;
                        }
                        
                        if (!textElement) return;
                        
                        // Get current text
                        const currentText = this.getTextContent(textElement);
                        if (!currentText.trim()) return;
                        
                        // Store original text color
                        const originalFill = textElement.getAttribute('fill') || '#333333';
                        
                        // Create input element
                        this.createEditInput(textElement, currentText, originalFill, svg);
                    }
                    
                    getTextContent(element) {
                        // Handle tspan children
                        const tspans = element.querySelectorAll('tspan');
                        if (tspans.length > 0) {
                            return Array.from(tspans).map(t => t.textContent).join('\\n');
                        }
                        return element.textContent || '';
                    }
                    
                    createEditInput(textElement, currentText, originalFill, svg) {
                        // Get position
                        const rect = textElement.getBoundingClientRect();
                        
                        // Create input
                        const input = document.createElement('input');
                        input.type = 'text';
                        input.value = currentText;
                        input.style.position = 'fixed';
                        input.style.left = (rect.left + window.scrollX) + 'px';
                        input.style.top = (rect.top + window.scrollY) + 'px';
                        input.style.width = Math.max(rect.width + 20, 150) + 'px';
                        input.style.height = rect.height + 10 + 'px';
                        input.style.zIndex = '10000';
                        input.style.padding = '4px 8px';
                        input.style.border = '2px solid #4299e1';
                        input.style.borderRadius = '4px';
                        input.style.fontSize = window.getComputedStyle(textElement).fontSize;
                        input.style.fontFamily = window.getComputedStyle(textElement).fontFamily;
                        input.style.fontWeight = window.getComputedStyle(textElement).fontWeight;
                        input.style.color = '#000000';
                        input.style.backgroundColor = '#ffffff';
                        input.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
                        
                        // Add to body
                        document.body.appendChild(input);
                        this.currentEdit = {input, textElement, originalFill};
                        
                        // Focus and select
                        input.focus();
                        input.select();
                        
                        // Handle events
                        const handleKeyDown = (e) => this.handleKeyDown(e);
                        const handleBlur = () => {
                            this.finishEdit(true);
                            input.removeEventListener('keydown', handleKeyDown);
                            input.removeEventListener('blur', handleBlur);
                        };
                        
                        input.addEventListener('keydown', handleKeyDown);
                        input.addEventListener('blur', handleBlur);
                    }
                    
                    handleKeyDown(event) {
                        if (!this.currentEdit) return;
                        
                        switch(event.key) {
                            case 'Enter':
                                event.preventDefault();
                                this.finishEdit(true);
                                break;
                            case 'Escape':
                                event.preventDefault();
                                this.cancelEdit();
                                break;
                        }
                    }
                    
                    finishEdit(saveChanges) {
                        if (!this.currentEdit) return;
                        
                        const {input, textElement, originalFill} = this.currentEdit;
                        const newText = input.value.trim();
                        const currentText = this.getTextContent(textElement);
                        
                        // Remove input from DOM
                        if (input && input.parentElement) {
                            try {
                                input.parentElement.removeChild(input);
                            } catch (e) {
                                // Already removed
                            }
                        }
                        
                        if (saveChanges && newText && newText !== currentText) {
                            // Update the text
                            this.updateTextElement(textElement, newText);
                            textElement.setAttribute('fill', originalFill);
                            
                            // Send to Python
                            if (window.qtBridge && window.qtBridge.onElementEdited) {
                                const rect = textElement.getBoundingClientRect();
                                window.qtBridge.onElementEdited(
                                    'element_' + Date.now(),
                                    'text',
                                    newText,
                                    rect.left,
                                    rect.top
                                );
                            }
                        } else {
                            textElement.setAttribute('fill', originalFill);
                        }
                        
                        this.currentEdit = null;
                    }
                    
                    cancelEdit() {
                        if (!this.currentEdit) return;
                        
                        const {input, textElement, originalFill} = this.currentEdit;
                        
                        if (input && input.parentElement) {
                            try {
                                input.parentElement.removeChild(input);
                            } catch (e) {
                                // Already removed
                            }
                        }
                        
                        textElement.setAttribute('fill', originalFill);
                        this.currentEdit = null;
                    }
                    
                    updateTextElement(textElement, newText) {
                        const tspans = textElement.querySelectorAll('tspan');
                        
                        if (tspans.length > 0) {
                            const lines = newText.split('\\n');
                            tspans.forEach((tspan, index) => {
                                if (index < lines.length) {
                                    tspan.textContent = lines[index];
                                }
                            });
                            
                            if (lines.length > tspans.length) {
                                for (let i = tspans.length; i < lines.length; i++) {
                                    const newTspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
                                    newTspan.textContent = lines[i];
                                    newTspan.setAttribute('x', tspans[0].getAttribute('x') || '0');
                                    newTspan.setAttribute('dy', '1.2em');
                                    textElement.appendChild(newTspan);
                                }
                            }
                        } else {
                            textElement.textContent = newText;
                        }
                    }
                }
                
                // Initialize when page loads
                document.addEventListener('DOMContentLoaded', function() {
                    setTimeout(() => {
                        window.mermaidEditor = new EnhancedMermaidEditor();
                    }, 1500); // Increased delay to ensure SVG is fully loaded
                });
                </script>
                <style>
                    /* Ensure text is always visible */
                    .mermaid svg text,
                    .mermaid svg tspan {
                        fill: #333333 !important;
                        color: #333333 !important;
                    }
                    
                    /* Highlight lines on hover */
                    .mermaid svg line:hover,
                    .mermaid svg path:hover,
                    .mermaid svg polyline:hover {
                        stroke-width: 3px !important;
                        cursor: move !important;
                    }
                    
                    /* Edit input styling */
                    input.mermaid-edit {
                        position: fixed !important;
                        z-index: 10000 !important;
                    }
                    
                    /* Drag indicator styling */
                    #drag-indicator {
                        font-family: 'Courier New', monospace;
                        font-weight: bold;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    }
                </style>
            """
        
        html_template = f'''<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'base',
                themeVariables: {{
                    primaryColor: '#e0e7ff',
                    edgeLabelBackground: '#ffffff',
                    tertiaryColor: '#f0fdf4',
                    // Ensure text is dark
                    primaryTextColor: '#333333',
                    secondaryTextColor: '#333333',
                    tertiaryTextColor: '#333333',
                    noteTextColor: '#333333',
                    noteBkgColor: '#fffacd',
                    actorBkgColor: '#e0e7ff',
                    actorBorderColor: '#a5b4fc',
                    actorTextColor: '#333333',
                    labelBoxBkgColor: '#f0fdf4',
                    labelBoxBorderColor: '#86efac',
                    labelTextColor: '#333333',
                    // Force dark font
                    fontFamily: 'Arial, sans-serif',
                    fontSize: '16px'
                }}
            }});
            </script>
            {editing_js if enable_editing else ''}
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    background-color: #f9fafb;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                    padding: 24px;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 24px;
                }}
                .header h1 {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #1f2937;
                    margin-bottom: 8px;
                }}
                .header p {{
                    color: #6b7280;
                    font-size: 14px;
                }}
                .voltage-info {{
                    display: inline-block;
                    background: #f3f4f6;
                    padding: 4px 12px;
                    border-radius: 16px;
                    font-size: 12px;
                    color: #4b5563;
                    margin-left: 10px;
                }}
                .key-box {{
                    margin-top: 24px;
                    padding-top: 16px;
                    border-top: 1px solid #e5e7eb;
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 16px;
                }}
                @media (min-width: 768px) {{
                    .key-box {{
                        grid-template-columns: repeat(3, 1fr);
                    }}
                }}
                .key-section {{
                    padding: 12px;
                    background: #f9fafb;
                    border-radius: 8px;
                }}
                .key-section strong {{
                    display: block;
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                .key-section ul {{
                    list-style-type: disc;
                    padding-left: 20px;
                    margin: 0;
                }}
                .key-section li {{
                    margin-bottom: 4px;
                    font-size: 13px;
                    color: #4b5563;
                }}
                .blue-text {{ color: #1d4ed8; }}
                .green-text {{ color: #047857; }}
                .orange-text {{ color: #ea580c; }}
                .language-badge {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: {'#3b82f6' if language == 'en' else '#ef4444'};
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                }}
                .edit-hint {{
                    background: #fef3c7;
                    border: 1px solid #fbbf24;
                    border-radius: 6px;
                    padding: 8px 12px;
                    margin-top: 10px;
                    font-size: 12px;
                    color: #92400e;
                    text-align: center;
                }}
                
                /* FORCE ALL TEXT TO BE DARK */
                .mermaid svg text {{
                    fill: #333333 !important;
                }}
                
                .mermaid svg tspan {{
                    fill: #333333 !important;
                }}
                
                .mermaid svg .actor text {{
                    fill: #333333 !important;
                    font-weight: bold;
                }}
                
                .mermaid svg .note text {{
                    fill: #333333 !important;
                }}
                
                .mermaid svg .messageText {{
                    fill: #333333 !important;
                }}
                
                .mermaid svg .label text {{
                    fill: #333333 !important;
                }}
            </style>
        </head>
        <body>

            <div class="container">
                <div class="language-badge">{'English' if language == 'en' else '日本語'}</div>
                
                <div class="header">
                    <h1>{title}</h1>
                    <p>{key['generated']} <span class="voltage-info">Voltage: {voltage}</span></p>
                    <div class="edit-hint">{key['tip']}</div>
                </div>

                <div class="mermaid">
        {mermaid_code}
                </div>
                
                <div class="key-box">
                    <div class="key-section">
                        <strong class="blue-text">{key['logic_title']}</strong>
                        <ul>
                            <li>{key['logic_items'][0]}</li>
                            <li>{key['logic_items'][1]}</li>
                            <li>{key['logic_items'][2]}</li>
                        </ul>
                    </div>
                    <div class="key-section">
                        <strong class="green-text">{key['safety_title']}</strong>
                        <ul>
                            <li>{key['safety_items'][0]}</li>
                            <li>{key['safety_items'][1]}</li>
                            <li>{key['safety_items'][2]}</li>
                        </ul>
                    </div>
                    <div class="key-section">
                        <strong class="orange-text">{key['components_title']}</strong>
                        <ul>
                            <li>{key['components_items'][0]}</li>
                            <li>{key['components_items'][1]}</li>
                            <li>{key['components_items'][2]}</li>
                        </ul>
                    </div>
                </div>
            </div>

        </body>
        </html>'''
            
        return html_template

class DXFGenerator:
    """Generates Professional Electrical Single Line Diagrams (SLD) in DXF"""
    
    def __init__(self):
        # Configuration for SLD spacing
        self.start_y = 1000
        self.center_x = 0
        self.bus_width = 300
        self.vertical_step = 60
        self.symbol_scale = 10
    
    def _setup_resources(self, doc):
        """Define layers, linetypes, and block definitions (Symbols)"""
        # Create standard text style (REQUIRED for AutoCAD)
        if 'STANDARD' not in doc.styles:
            doc.styles.new('STANDARD', dxfattribs={'font': 'arial.ttf'})
        
        # Layers with proper ACI colors - only create if they don't exist
        layer_names = ['SLD_SYMBOLS', 'SLD_WIRING', 'SLD_TEXT', 'SLD_BUSBAR']
        layer_colors = [7, 1, 3, 5]  # White, Red, Green, Blue
        
        for name, color in zip(layer_names, layer_colors):
            if name not in doc.layers:
                doc.layers.new(name=name, dxfattribs={'color': color})
        
        # --- BLOCK DEFINITIONS (Reusable Symbols) ---
        
        # 1. Breaker Symbol (Box with Cross)
        if 'BREAKER' not in doc.blocks:
            breaker = doc.blocks.new(name='BREAKER')
            breaker.add_lwpolyline([(-5, -5), (5, -5), (5, 5), (-5, 5)], close=True)
            breaker.add_line((-5, -5), (5, 5))
            breaker.add_line((-5, 5), (5, -5))

        # 2. Motor/Load Symbol (Circle with M)
        if 'MOTOR' not in doc.blocks:
            motor = doc.blocks.new(name='MOTOR')
            motor.add_circle((0, 0), 8)
            mtext = motor.add_text('M', dxfattribs={'height': 6})
            mtext.dxf.style = 'STANDARD'
            mtext.dxf.insert = (-2.5, -3)

        # 3. Source/Grid Symbol (Circle with Sine)
        if 'SOURCE' not in doc.blocks:
            source = doc.blocks.new(name='SOURCE')
            source.add_circle((0, 0), 10)
            source.add_line((-5, 0), (5, 0))
            stext = source.add_text('~', dxfattribs={'height': 8})
            stext.dxf.style = 'STANDARD'
            stext.dxf.insert = (-3, -4)

        # 4. Earth Symbol
        if 'EARTH' not in doc.blocks:
            earth = doc.blocks.new(name='EARTH')
            earth.add_line((-8, 0), (8, 0))
            earth.add_line((-5, -3), (5, -3))
            earth.add_line((-2, -6), (2, -6))
        
    def generate_dxf(self, parsed_data, file_path):
        try:
            # Create DXF document with proper setup
            doc = ezdxf.new('R2010', setup=True)  # 'setup=True' adds required sections
            
            doc.header['$INSUNITS'] = 4  # 4 = Millimeters
            
            # Set limits (drawing area)
            doc.header['$LIMMIN'] = (-500, 400)
            doc.header['$LIMMAX'] = (500, 1200)
            
            self._setup_resources(doc)
            msp = doc.modelspace()
            
            components = parsed_data["components"]
            comp_map = {c[0]: c[1] for c in components}
            
            # --- DRAWING LOGIC (Top to Bottom) ---
            current_y = self.start_y
            
            # 1. DRAW SUPPLY (Top)
            if "supply" in comp_map:
                msp.add_blockref('SOURCE', (0, current_y), dxfattribs={'layer': 'SLD_SYMBOLS'})
                self._add_label(msp, "Incoming Supply", (15, current_y - 2))
                current_y -= 15
            
            # 2. DRAW MAIN CABLE/LINE
            msp.add_line((0, current_y), (0, current_y - 30), dxfattribs={'layer': 'SLD_WIRING'})
            current_y -= 30
            
            # 3. DRAW MAIN BREAKER
            if "maincb" in comp_map:
                msp.add_blockref('BREAKER', (0, current_y), dxfattribs={'layer': 'SLD_SYMBOLS'})
                self._add_label(msp, "Main VCB/ACB", (15, current_y - 2))
                msp.add_line((0, current_y - 5), (0, current_y - 30), dxfattribs={'layer': 'SLD_WIRING'})
                current_y -= 30

            # 4. DRAW BUSBAR (Horizontal Line)
            if "bus" in comp_map:
                # Draw thick busbar line (using polyline for thickness)
                busbar = msp.add_lwpolyline([
                    (-self.bus_width/2, current_y),
                    (self.bus_width/2, current_y)
                ], dxfattribs={'layer': 'SLD_BUSBAR'})
                busbar.dxf.const_width = 3  # Set line width
                
                self._add_label(msp, "Main Busbar", (self.bus_width/2 + 10, current_y))
                bus_y = current_y
                current_y -= 30
            
            # 5. DRAW OUTGOING FEEDERS
            feeder_x = -50 
            
            if "outcb" in comp_map or "loads" in comp_map:
                msp.add_line((feeder_x, bus_y), (feeder_x, bus_y - 30), dxfattribs={'layer': 'SLD_WIRING'})
                feeder_y = bus_y - 30
                
                msp.add_blockref('BREAKER', (feeder_x, feeder_y), dxfattribs={'layer': 'SLD_SYMBOLS'})
                self._add_label(msp, "Feeder MCB", (feeder_x + 10, feeder_y - 2))
                
                msp.add_line((feeder_x, feeder_y - 5), (feeder_x, feeder_y - 40), dxfattribs={'layer': 'SLD_WIRING'})
                feeder_y -= 40
                
                msp.add_blockref('MOTOR', (feeder_x, feeder_y), dxfattribs={'layer': 'SLD_SYMBOLS'})
                self._add_label(msp, "Load / Motor", (feeder_x + 15, feeder_y - 2))
                
                # Earth connection with proper line type
                if "ebar" in comp_map:
                    msp.add_line((feeder_x, feeder_y - 8), (feeder_x, feeder_y - 20), 
                                dxfattribs={'layer': 'SLD_WIRING', 'linetype': 'DASHED'})
                    msp.add_blockref('EARTH', (feeder_x, feeder_y - 20), dxfattribs={'layer': 'SLD_SYMBOLS'})

            # Add Title Block
            self._add_title_block(doc, msp, parsed_data)
            
            # Remove viewport creation - it's not needed for basic DXF files
            # _add_viewport method has been removed
            
            # Validate the DXF document
            auditor = doc.audit()
            if auditor.has_errors:
                print(f"DXF validation warnings: {auditor.errors}")
            
            # Save the file
            doc.saveas(file_path)
            return True
            
        except Exception as e:
            raise Exception(f"Failed to generate SLD DXF: {str(e)}")

    def _add_label(self, msp, text, pos):
        """Helper to add text labels next to symbols"""
        mtext = msp.add_text(text, dxfattribs={
            'layer': 'SLD_TEXT',
            'height': 5.0,
            'insert': pos
        })
        mtext.dxf.style = 'STANDARD'  # Use standard text style

    def _add_title_block(self, doc, msp, parsed_data):
        """Add a professional engineering title block"""
        min_x, max_x = -200, 200
        min_y, max_y = 500, 1100
        
        # Frame
        frame_points = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
        msp.add_lwpolyline(frame_points, close=True, dxfattribs={'layer': 'SLD_SYMBOLS'})
        
        # Title Box at bottom right
        title_h = 40
        title_w = 120
        title_x = max_x - title_w
        title_y = min_y
        
        msp.add_lwpolyline([
            (title_x, title_y), (max_x, title_y), 
            (max_x, title_y + title_h), (title_x, title_y + title_h)
        ], close=True, dxfattribs={'layer': 'SLD_SYMBOLS'})
        
        # Text - specify style explicitly
        title_text = msp.add_text("SINGLE LINE DIAGRAM", dxfattribs={
            'height': 4, 
            'insert': (title_x + 5, title_y + 25)
        })
        title_text.dxf.style = 'STANDARD'
        
        voltage_text = msp.add_text(f"Voltage: {parsed_data.get('voltage', 'N/A')}", dxfattribs={
            'height': 3, 
            'insert': (title_x + 5, title_y + 15)
        })
        voltage_text.dxf.style = 'STANDARD'
        
        from datetime import datetime
        date_text = msp.add_text(f"Date: {datetime.now().strftime('%Y-%m-%d')}", dxfattribs={
            'height': 3, 
            'insert': (title_x + 5, title_y + 5)
        })
        date_text.dxf.style = 'STANDARD'

class ElementEditorDialog(QDialog):
    """Dialog for editing diagram elements via double-click"""
    def __init__(self, element_id, element_type, current_text, parent=None):
        super().__init__(parent)
        self.element_id = element_id
        self.element_type = element_type
        self.current_text = current_text
        self.new_text = current_text
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"Edit {self.element_type}")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(f"Editing {self.element_type}")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c5282; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Element ID (read-only)
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Element ID:"))
        id_label = QLabel(self.element_id)
        id_label.setStyleSheet("font-style: italic; color: #718096;")
        id_layout.addWidget(id_label)
        id_layout.addStretch()
        layout.addLayout(id_layout)
        
        # Current text preview
        current_label = QLabel("Current text:")
        current_label.setFont(QFont("Arial", 10))
        layout.addWidget(current_label)
        
        current_preview = QTextEdit()
        current_preview.setPlainText(self.current_text)
        current_preview.setReadOnly(True)
        current_preview.setMaximumHeight(80)
        current_preview.setStyleSheet("""
            QTextEdit {
                background-color: #f7fafc;
                border: 1px solid #cbd5e0;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
        """)
        layout.addWidget(current_preview)
        
        # New text input
        new_label = QLabel("New text:")
        new_label.setFont(QFont("Arial", 10))
        layout.addWidget(new_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.current_text)
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 2px solid #4299e1;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        
        # Add formatting hints for different element types
        if self.element_type == "participant":
            hint = QLabel("Tip: Use <br/> for line breaks")
            hint.setStyleSheet("font-size: 11px; color: #718096; font-style: italic;")
            layout.addWidget(hint)
        
        layout.addWidget(self.text_edit)
        
        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_new_text(self):
        """Get the new text from the editor"""
        return self.text_edit.toPlainText()

class DiagramCanvas(QWidget):
    """Canvas for displaying the generated diagram with double-click editing"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.generator = MermaidGenerator()
        self.dxf_generator = DXFGenerator()
        self.current_parsed_data = None
        self.original_parsed_data = None
        self.web_bridge = WebBridge()
        
        self.init_ui()
        self.setup_web_channel()
        self.web_bridge.elementEdited.connect(self.handle_element_edited)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Web view for displaying HTML diagram
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(600)
        
        # Connect bridge signals
        self.web_bridge.elementDoubleClicked.connect(self.handle_element_double_clicked)
        
        layout.addWidget(self.web_view)
        
        self.setLayout(layout)
    
    def setup_web_channel(self):
        """Setup web channel for JavaScript-Python communication"""
        # Create web channel
        channel = QWebChannel(self.web_view.page())
        
        # Register the bridge object
        channel.registerObject("qtBridge", self.web_bridge)
        
        # Set the web channel on the page
        self.web_view.page().setWebChannel(channel)
    
    def generate_from_prompt(self, prompt_text):
        """Generate diagram from text prompt"""
        try:
            prompt_text = prompt_text.strip()
            if not prompt_text:
                QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
                return False
            
            # Parse prompt
            parsed_data = self.generator.parse_prompt(prompt_text)
            self.current_parsed_data = parsed_data
            self.original_parsed_data = parsed_data.copy()  # Save original
            
            print(f"DEBUG: Parsed data: {parsed_data}")  # Debug output
            
            # Generate Mermaid code
            mermaid_code = self.generator.generate_mermaid_code(parsed_data)
            
            print(f"DEBUG: Mermaid code generated: {len(mermaid_code)} chars")  # Debug output
            
            # Generate HTML for display with editing enabled
            html_content = self.generator.generate_display_html(mermaid_code, parsed_data, enable_editing=True)
            
            print(f"DEBUG: HTML generated: {len(html_content)} chars")  # Debug output
            
            # Display in web view
            self.web_view.setHtml(html_content)
            
            # Update status with language info
            if self.parent_window and hasattr(self.parent_window, 'status'):
                language = parsed_data.get('language', 'en')
                lang_name = "English" if language == "en" else "Japanese"
                self.parent_window.status.showMessage(
                    f"Diagram generated in {lang_name} with {len(parsed_data['components'])} components. Double-click to edit elements.", 
                    4000
                )
            
            return True
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR DETAILS: {error_details}")  # Print to console
            
            QMessageBox.critical(
                self, 
                "Generation Error", 
                f"Failed to generate diagram:\n\n{str(e)}\n\nCheck console for details."
            )
            return False
    
    def handle_element_double_clicked(self, element_id, element_type, current_text):
        """Handle double-click events from JavaScript"""
        # Show editing dialog
        editor = ElementEditorDialog(element_id, element_type, current_text, self)
        
        if editor.exec() == QDialog.DialogCode.Accepted:
            new_text = editor.get_new_text()
            
            # Update the parsed data based on the edited element
            self.update_parsed_data_from_edit(element_id, element_type, new_text)
            
            # Regenerate and update the diagram
            self.refresh_diagram()
            
            # Update status
            if self.parent_window and hasattr(self.parent_window, 'status'):
                self.parent_window.status.showMessage(f"Updated {element_type}: {new_text[:50]}...", 3000)
    
    def update_parsed_data_from_edit(self, element_id, element_type, new_text):
        """Update parsed data based on edited element"""
        if not self.current_parsed_data:
            return
        
        components = self.current_parsed_data["components"]
        
        # Map of component types to indices in the components list
        component_type_map = {
            "participant": ["supply", "maincb", "bus", "nbar", "ebar", "outcb", "loads"],
            "note": ["note_power_entry", "note_internal", "note_outgoing"],
            "message": ["wire_phase", "wire_neutral", "wire_earth", 
                    "action_energize", "action_protection", "action_distribute",
                    "action_feed", "action_return", "action_safety"]
        }
        
        # Update based on element type
        if element_type == "participant":
            # For participant elements, we need to find which one was edited
            # This is simplified - in practice, you'd need better logic
            updated = False
            
            for i, (comp_id, comp_label) in enumerate(components):
                # Check if this label matches (remove HTML for comparison)
                clean_label = re.sub(r'<[^>]+>', '', comp_label)
                
                # Simple heuristic: if the new text contains keywords from the old label
                if any(keyword in new_text.lower() for keyword in comp_id.lower().split('_')):
                    # Preserve line breaks if they exist in original
                    if "<br/>" in comp_label:
                        # Try to maintain the formatting
                        if "<br/>" not in new_text and ("(" in new_text or "/" in new_text):
                            # Add line break before parentheses or slash
                            new_label = new_text.replace("(", "<br/>(").replace("/", "<br/>/")
                        else:
                            new_label = new_text.replace("\n", "<br/>")
                    else:
                        new_label = new_text
                    
                    components[i] = (comp_id, new_label)
                    updated = True
                    break
            
            # If not found, add as new component (optional)
            if not updated and element_type == "participant":
                new_id = f"custom_{len(components)}"
                components.append((new_id, new_text))
        
        elif element_type == "note" or element_type == "message":
            # For notes and messages, update the diagram_labels
            # We need to map the edited text back to diagram_labels keys
            # This is complex and might require additional context
            pass
        
        # Update the parsed data
        self.current_parsed_data["components"] = components
    
    def refresh_diagram(self):
        """Refresh the diagram with updated data"""
        if not self.current_parsed_data:
            return
        
        try:
            # Generate new Mermaid code
            mermaid_code = self.generator.generate_mermaid_code(self.current_parsed_data)
            
            # Generate HTML for display
            html_content = self.generator.generate_display_html(mermaid_code, self.current_parsed_data, enable_editing=True)
            
            # Display in web view
            self.web_view.setHtml(html_content)
            
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", f"Failed to refresh diagram: {str(e)}")

    def handle_element_edited(self, element_id, element_type, new_text, x, y):
        """Handle in-place editing completion"""
        # Update the parsed data
        self.update_parsed_data_from_edit(element_id, element_type, new_text)
        
        # Refresh the diagram
        self.refresh_diagram()
        
        # Show success message
        if self.parent_window and hasattr(self.parent_window, 'status'):
            short_text = new_text[:30] + "..." if len(new_text) > 30 else new_text
            self.parent_window.status.showMessage(f"✓ Updated element: {short_text}", 2000)

class Sidebar(QWidget):
    """Sidebar with prompt input and controls"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_label = QLabel("シーケンス図ジェネレーター")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c5282; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Prompt input
        prompt_label = QLabel("図の説明を入力してください:")
        prompt_label.setFont(QFont("Arial", 10))
        layout.addWidget(prompt_label)
        
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText(
            "電気配線図について説明してください...\n"
            "例: 「主電源、ブレーカー、バスバー、負荷回路を含む電力配分図を作成する」"
        )
        self.prompt_text.setMaximumHeight(150)
        self.prompt_text.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #2d3748;
                border: 1px solid #cbd5e0;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.prompt_text)
        
        # Quick templates
        templates_label = QLabel("クイックテンプレート:")
        templates_label.setFont(QFont("Arial", 10))
        layout.addWidget(templates_label)
        
        templates_combo = QComboBox()
        templates = [
            "基本的な配電",
            "産業用パネルレイアウト", 
            "住宅用回路図",
            "三相システム",
            "安全接地システム"
        ]
        templates_combo.addItems(templates)
        templates_combo.setStyleSheet("color: #000000;")
        templates_combo.currentTextChanged.connect(self.load_template)
        layout.addWidget(templates_combo)
        
        # Generate button
        generate_btn = QPushButton("Generate Diagram")
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c5282;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #2a4365;
            }
            QPushButton:pressed {
                background-color: #1a365d;
            }
        """)
        generate_btn.clicked.connect(self.generate_diagram)
        layout.addWidget(generate_btn)
        
        # Reset button
        self.reset_btn = QPushButton("Reset to Original")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #80C2FE;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #4AA8FE;
            }
            QPushButton:pressed {
                background-color: #80C2FE;
            }
            QPushButton:disabled {
                background-color: #cbd5e0;
                color: #718096;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_diagram)
        self.reset_btn.setEnabled(False)
        layout.addWidget(self.reset_btn)
        
        layout.addSpacing(20)
        
        layout.addStretch()
        
        # Info
        info_label = QLabel("ヒント: 「ブレーカー」、「バスバー」、「ニュートラル」、「アース」、「負荷」などのキーワードを使用します。ダブルクリックで要素を編集できます。")
        info_label.setFont(QFont("Arial", 9))
        info_label.setStyleSheet("color: #718096; margin-top: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.setLayout(layout)
        self.setMinimumWidth(300)
        self.setMaximumWidth(350)
        self.setStyleSheet("""
            QWidget {
                background-color: #f7fafc;
                border-right: 1px solid #e2e8f0;
            }
            QLabel {
                color: #2d3748;
            }
        """)
    
    def load_template(self, template_name):
        """Load a predefined template"""
        templates = {
            "基本的な配電": "主電源、回路ブレーカー、配電バスバー、中性線バー、接地バー、照明とコンセントの負荷回路を含むクリーンな電力配分図を作成します。",
            "産業用パネルレイアウト": "三相入力電源、メインMCCBブレーカー、銅製バスバーシステム、機械用複数出力MCB、包括的な中性線および接地バーを備えた産業用電気パネル。",
            "住宅用回路図": "単相電源、メインMCB、照明、電源コンセント、キッチン家電、および安全接地接続用の個別回路ブレーカーを備えた住宅用配電盤。",
            "三相システム": "RYB相、メインブレーカー、バスバー配電、平衡負荷回路、中性点戻り経路、保護接地を備えた三相配電システム。",
            "安全接地システム": "接地システムに重点を置いた電気安全図。主な接地バー接続、回路保護導体、機器接地ポイントを示します。"
        }
        
        if template_name in templates:
            self.prompt_text.setPlainText(templates[template_name])
    
    def generate_diagram(self):
        """Generate diagram from prompt"""
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
            return
        
        # Generate diagram
        if hasattr(self.main_window, 'canvas'):
            success = self.main_window.canvas.generate_from_prompt(prompt)
            if success:
                
                # Enable reset button
                if hasattr(self.main_window.canvas, 'original_parsed_data'):
                    self.reset_btn.setEnabled(True)  # Use instance variable
    
    def reset_diagram(self):
        """Reset diagram to original state"""
        if not hasattr(self.main_window, 'canvas') or not self.main_window.canvas.original_parsed_data:
            return
        
        # Restore original data
        self.main_window.canvas.current_parsed_data = self.main_window.canvas.original_parsed_data.copy()
        
        # Refresh diagram
        self.main_window.canvas.refresh_diagram()
        
        # Update status
        if hasattr(self.main_window, 'status'):
            self.main_window.status.showMessage("Diagram reset to original state", 3000)
    
    def export_dxf(self):
        """Export current diagram as DXF file"""
        if not hasattr(self.main_window, 'canvas') or not self.main_window.canvas.current_parsed_data:
            QMessageBox.warning(self, "図なし", "まず図を生成してください。")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "DXFのエクスポート", "", "DXF Files (*.dxf)"
        )
        
        if file_path:
            try:
                # Generate DXF from parsed data
                self.main_window.canvas.dxf_generator.generate_dxf(
                    self.main_window.canvas.current_parsed_data,
                    file_path
                )
                QMessageBox.information(self, "成功", f"DXF exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export DXF: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("電気配電図ジェネレータ")
        self.resize(1400, 800)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Initialize UI
        self.init_ui()
    
    def create_menu_bar(self):
        """Create File, View, Edit menus"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_diagram)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("&Save Diagram", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_diagram)
        file_menu.addAction(save_action)
        
        export_menu = file_menu.addMenu("&Export")
        
        export_dxf_action = QAction("Export as DXF", self)
        export_dxf_action.triggered.connect(self.export_as_dxf)
        export_menu.addAction(export_dxf_action)
        
        export_png_action = QAction("Export as PNG", self)
        export_png_action.triggered.connect(self.export_as_png)
        export_menu.addAction(export_png_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        
        reset_action = QAction("&Reset Diagram", self)
        reset_action.setShortcut("Ctrl+R")
        reset_action.triggered.connect(self.reset_diagram)
        edit_menu.addAction(reset_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction("&Copy Mermaid Code", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy_diagram)
        edit_menu.addAction(copy_action)
        
        edit_menu.addSeparator()
        
        clear_action = QAction("C&lear All", self)
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(self.clear_all)
        edit_menu.addAction(clear_action)
        
        # View Menu
        view_menu = menubar.addMenu("&View")
        
        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        
        view_menu.addSeparator()
        
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        docs_action = QAction("&Documentation", self)
        docs_action.triggered.connect(self.show_documentation)
        help_menu.addAction(docs_action)
    
    def init_ui(self):
        # Central widget
        central = QWidget()
        central.setStyleSheet("background-color: #f8fafc;")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = Sidebar(self)
        layout.addWidget(self.sidebar)
        
        # Main canvas area
        canvas_container = QWidget()
        canvas_container.setStyleSheet("background-color: #ffffff;")
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        
        # Toolbar
        toolbar = QFrame()
        toolbar.setMaximumHeight(40)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #edf2f7;
                border-bottom: 1px solid #cbd5e0;
                padding: 5px 15px;
            }
            QLabel {
                color: #4a5568;
                font-size: 12px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        
        self.status_label = QLabel("準備完了 - プロンプトを入力して「Generate」をクリック。ダブルクリックで要素を編集できます。")
        self.status_label.setFont(QFont("Arial", 10))
        toolbar_layout.addWidget(self.status_label)
        toolbar_layout.addStretch()
        
        canvas_layout.addWidget(toolbar)
        
        # Canvas
        self.canvas = DiagramCanvas(self)
        canvas_layout.addWidget(self.canvas)
        
        layout.addWidget(canvas_container, 1)
        
        self.setCentralWidget(central)
        
        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("準備完了 - 図を生成するにはプロンプトを入力してください。ダブルクリックで要素を編集できます。")
    
    # Menu action handlers
    def new_diagram(self):
        """Clear current diagram and prompt"""
        if hasattr(self.sidebar, 'prompt_text'):
            self.sidebar.prompt_text.clear()
        if hasattr(self.canvas, 'web_view'):
            self.canvas.web_view.setHtml("")
        
        # Disable reset button
        for btn in self.sidebar.findChildren(QPushButton):
            if btn.text() == "Reset to Original":
                btn.setEnabled(False)
        
        self.status.showMessage("New diagram started", 2000)
    
    def save_diagram(self):
        """Save current diagram configuration"""
        if not hasattr(self.canvas, 'current_parsed_data'):
            QMessageBox.warning(self, "No Diagram", "Please generate a diagram first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Diagram", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Save parsed data as JSON
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.canvas.current_parsed_data, f, ensure_ascii=False, indent=2)
                self.status.showMessage(f"Diagram saved to {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save diagram: {str(e)}")
    
    def export_as_dxf(self):
        """Export as DXF"""
        if hasattr(self.sidebar, 'export_dxf'):
            self.sidebar.export_dxf()
    
    def export_as_png(self):
        """Export diagram as PNG"""
        if not hasattr(self.canvas, 'web_view'):
            QMessageBox.warning(self, "No Diagram", "Please generate a diagram first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "", "PNG Files (*.png)"
        )
        
        if file_path:
            try:
                # Take screenshot of web view
                pixmap = self.canvas.web_view.grab()
                pixmap.save(file_path, "PNG")
                self.status.showMessage(f"PNG exported to {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export PNG: {str(e)}")
    
    def reset_diagram(self):
        """Reset diagram to original"""
        if hasattr(self.sidebar, 'reset_diagram'):
            self.sidebar.reset_diagram()
    
    def zoom_in(self):
        """Zoom in on diagram"""
        if hasattr(self.canvas, 'web_view'):
            self.canvas.web_view.setZoomFactor(self.canvas.web_view.zoomFactor() * 1.2)
    
    def zoom_out(self):
        """Zoom out on diagram"""
        if hasattr(self.canvas, 'web_view'):
            self.canvas.web_view.setZoomFactor(self.canvas.web_view.zoomFactor() / 1.2)
    
    def reset_zoom(self):
        """Reset zoom to 100%"""
        if hasattr(self.canvas, 'web_view'):
            self.canvas.web_view.setZoomFactor(1.0)
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def copy_diagram(self):
        """Copy diagram to clipboard"""
        if not hasattr(self.canvas, 'current_parsed_data'):
            QMessageBox.warning(self, "No Diagram", "No diagram to copy.")
            return
        
        clipboard = QApplication.clipboard()
        # Copy the Mermaid code
        try:
            # Generate Mermaid code from parsed data
            mermaid_code = self.canvas.generator.generate_mermaid_code(self.canvas.current_parsed_data)
            clipboard.setText(mermaid_code)
            self.status.showMessage("Mermaid code copied to clipboard", 2000)
        except Exception as e:
            QMessageBox.warning(self, "Copy Error", f"Failed to copy diagram: {str(e)}")
    
    def clear_all(self):
        """Clear everything"""
        reply = QMessageBox.question(
            self, "Clear All", 
            "Are you sure you want to clear the prompt and diagram?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.new_diagram()
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
        <h2>Electrical Distribution Diagram Generator</h2>
        <p>Version 3.0</p>
        <p>Generate professional electrical distribution diagrams from natural language prompts.</p>
        <p>Supports English and Japanese language input.</p>
        <p>Double-click on any element to edit it directly!</p>
        <p>Supports PNG, DXF, and JSON export formats.</p>
        <p>Built with PyQt6, Mermaid.js, and ezdxf</p>
        <p>© 2024 - All rights reserved</p>
        """
        QMessageBox.about(self, "About", about_text)
    
    def show_documentation(self):
        """Show documentation"""
        doc_text = """
        <h3>How to Use:</h3>
        <ol>
        <li>Enter a description of your electrical distribution system in the prompt box</li>
        <li>Use keywords like: breaker, busbar, neutral, earth, load, circuit</li>
        <li>Click 'Generate Diagram' to create the sequence diagram</li>
        <li><strong>Double-click on any element</strong> (participants, notes, labels) to edit them</li>
        <li>Use export options to save your diagram as PNG, DXF, or JSON</li>
        </ol>
        
        <h3>Double-Click Editing:</h3>
        <ul>
        <li><strong>Participants:</strong> Double-click on any component (Supply, MainCB, Bus, etc.) to edit its label</li>
        <li><strong>Notes:</strong> Double-click on numbered notes to edit the text</li>
        <li><strong>Labels:</strong> Double-click on wire labels and action descriptions to edit them</li>
        <li><strong>Formatting:</strong> Use &lt;br/&gt; for line breaks in labels</li>
        </ul>
        
        <h3>Language Support:</h3>
        <ul>
        <li><strong>English:</strong> Use English keywords like 'breaker', 'busbar', 'neutral'</li>
        <li><strong>Japanese:</strong> Use Japanese keywords like '遮断器', '母線', '中性線'</li>
        </ul>
        
        <h3>Export Formats:</h3>
        <ul>
        <li><strong>PNG:</strong> Image file for documentation</li>
        <li><strong>DXF:</strong> CAD format for technical drawings</li>
        <li><strong>JSON:</strong> Save diagram configuration for later use</li>
        </ul>
        
        <h3>Example Prompts:</h3>
        <ul>
        <li>"Create a power distribution diagram with main supply, breaker, busbar, and load circuits"</li>
        <li>"主電源、遮断器、母線、負荷回路を含む電力配電図を作成"</li>
        <li>"Show three-phase system with neutral and earth bars"</li>
        </ul>
        """
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Documentation")
        dialog.resize(500, 500)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(doc_text)
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def keyPressEvent(self, event):
        """Handle global keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Escape and hasattr(self, 'canvas'):
            # Cancel any active edit
            if hasattr(self.canvas.web_view, 'page'):
                self.canvas.web_view.page().runJavaScript("""
                    if (window.mermaidEditor && window.mermaidEditor.currentEdit) {
                        window.mermaidEditor.cancelEdit();
                    }
                """)
        
        super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()