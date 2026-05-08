# mermaid_generator.py
import re
from constants import COMPLEXITY_LEVELS, SECTION_COLORS, SECTION_LABELS, COMPONENT_SECTIONS


class MermaidGenerator:
    def __init__(self):
        self.components_map = {
            "main incoming supply": {"en": "Main Incoming Supply<br/>(230V / 415V)", "ja": "主電源<br/>(230V / 415V)"},
            "main breaker": {"en": "Main Breaker<br/>(MCB/MCCB)", "ja": "主遮断器<br/>(MCB/MCCB)"},
            "busbar": {"en": "Busbar<br/>(Distribution)", "ja": "母線<br/>(配電)"},
            "neutral bar": {"en": "Neutral Bar", "ja": "中性線バー"},
            "earth bar": {"en": "Earth Bar", "ja": "接地バー"},
            "outgoing mcbs": {"en": "Outgoing MCBs", "ja": "出力MCB"},
            "load circuits": {"en": "Load Circuits<br/>(Lights, Sockets)", "ja": "負荷回路<br/>(照明、コンセント)"},
        }
        self.keywords_map = {
            "incoming": {"en": ["incoming", "supply", "source", "230v", "415v"], "ja": ["主電源", "受電", "電源", "入力電源"]},
            "breaker": {"en": ["breaker", "mcb", "mccb", "protection"], "ja": ["遮断器", "ブレーカー", "ブレーカ"]},
            "busbar": {"en": ["busbar", "distribution", "panel"], "ja": ["母線", "バスバー", "配電盤", "分電盤"]},
            "neutral": {"en": ["neutral", "return"], "ja": ["中性線", "ニュートラル", "零線", "N線"]},
            "earth": {"en": ["earth", "ground", "safety"], "ja": ["接地", "アース", "グラウンド", "地線"]},
            "outgoing": {"en": ["outgoing", "branch", "circuit"], "ja": ["出力", "分岐", "回路"]},
            "load": {"en": ["load", "circuit", "light", "socket", "appliance"], "ja": ["負荷", "回路", "照明", "コンセント"]},
        }
        self.diagram_labels = {
            "section_incoming": {"en": "Incoming Source", "ja": "入力電源"},
            "section_distribution": {"en": "Distribution Panel Components", "ja": "分電盤部品"},
            "section_load": {"en": "Load Side", "ja": "負荷側"},
            "note_power_entry": {"en": "1. INCOMING POWER ENTRY", "ja": "1. 受電"},
            "note_internal": {"en": "2. INTERNAL DISTRIBUTION", "ja": "2. 内部配電"},
            "note_outgoing": {"en": "3. OUTGOING CIRCUITS", "ja": "3. 出力回路"},
            "wire_phase": {"en": "Phase/Line Wire (L)", "ja": "相線/ラインワイヤ (L)"},
            "wire_neutral": {"en": "Neutral Wire (N)", "ja": "中性線 (N)"},
            "wire_earth": {"en": "Earth Wire (E)", "ja": "接地線 (E)"},
            "action_energize": {"en": "Energize Busbar (L)", "ja": "母線を励磁 (L)"},
            "action_protection": {"en": "Protection: Overload/Short", "ja": "保護: 過負荷/短絡"},
            "action_distribute": {"en": "Distribute to Branch Breakers", "ja": "分岐ブレーカーに配電"},
            "action_feed": {"en": "Line (L) - Protected Feed", "ja": "ライン (L) - 保護給電"},
            "action_return": {"en": "Neutral (N) - Return Path", "ja": "中性線 (N) - 帰路"},
            "action_safety": {"en": "Earth (E) - Safety Grounding", "ja": "接地 (E) - 安全接地"},
            "action_fault": {"en": "Fault Path (E) - Trip Signal", "ja": "故障経路 (E) - トリップ信号"},
            "note_fault": {"en": "FAULT PROTECTION PATHS", "ja": "故障保護経路"},
        }

    def detect_language(self, text):
        if re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]').search(text):
            return "ja"
        return "en"

    def parse_prompt(self, prompt_text, complexity_level="Standard"):
        print('parsing prompt with hardcoded rules')
        if not prompt_text or not isinstance(prompt_text, str):
            return {"components": self.get_default_components("en"), 
                    "layout": "horizontal",
                    "voltage": "230V / 415V", 
                    "language": "en", 
                    "complexity": complexity_level}

        prompt = prompt_text.lower()
        language = self.detect_language(prompt_text)
        voltage_text = "230V / 415V"

        try:
            for pattern in [r'(\d+)\s*[Vv]\s*[/／]?\s*(\d+)\s*[Vv]', r'(\d+)\s*[Vv]', r'(\d+)\s*volts?']:
                m = re.search(pattern, prompt_text)
                if m:
                    voltage_text = f"{m.group(1)}V / {m.group(2)}V" if len(m.groups()) >= 2 else f"{m.group(1)}V"
                    break
        except:
            pass

        layout = "horizontal"
        if "horizontal" in prompt or "水平" in prompt_text:
            layout = "horizontal"
        elif "vertical" in prompt or "垂直" in prompt_text:
            layout = "vertical"

        def check_keywords(category):
            en_kws = self.keywords_map.get(category, {}).get("en", [])
            ja_kws = self.keywords_map.get(category, {}).get("ja", [])
            return any(k in prompt for k in en_kws) or any(k in prompt_text for k in ja_kws)

        found_components = []
        allowed_ids = COMPLEXITY_LEVELS[complexity_level]["components"]

        if check_keywords("incoming") and "supply" in allowed_ids:
            lbl = self.components_map["main incoming supply"][language].replace("230V / 415V", voltage_text)
            found_components.append(("supply", lbl))
        if check_keywords("breaker") and "maincb" in allowed_ids:
            found_components.append(("maincb", self.components_map["main breaker"][language]))
        if check_keywords("busbar") and "bus" in allowed_ids:
            found_components.append(("bus", self.components_map["busbar"][language]))
        if check_keywords("neutral") and "nbar" in allowed_ids:
            found_components.append(("nbar", self.components_map["neutral bar"][language]))
        if check_keywords("earth") and "ebar" in allowed_ids:
            found_components.append(("ebar", self.components_map["earth bar"][language]))
        if check_keywords("outgoing") and "outcb" in allowed_ids:
            found_components.append(("outcb", self.components_map["outgoing mcbs"][language]))
        if check_keywords("load") and "loads" in allowed_ids:
            found_components.append(("loads", self.components_map["load circuits"][language]))

        if not found_components:
            found_components = self.get_default_components(language, voltage_text, complexity_level)

        return {"components": found_components, "layout": layout, "voltage": voltage_text,
                "language": language, "complexity": complexity_level}

    def get_default_components(self, language, voltage_text="230V / 415V", complexity_level="Standard"):
        allowed_ids = COMPLEXITY_LEVELS[complexity_level]["components"]
        all_defaults = [
            ("supply", self.components_map["main incoming supply"][language].replace("230V / 415V", voltage_text)),
            ("maincb", self.components_map["main breaker"][language]),
            ("bus", self.components_map["busbar"][language]),
            ("nbar", self.components_map["neutral bar"][language]),
            ("ebar", self.components_map["earth bar"][language]),
            ("outcb", self.components_map["outgoing mcbs"][language]),
            ("loads", self.components_map["load circuits"][language]),
        ]
        return [(cid, lbl) for cid, lbl in all_defaults if cid in allowed_ids]

    def generate_mermaid_code(self, parsed_data):
        components = parsed_data["components"]
        language   = parsed_data.get("language", "en")
        complexity = parsed_data.get("complexity", "Standard")
        comp_map   = {cid: lbl for cid, lbl in components}
        L          = self.diagram_labels
        cfg        = COMPLEXITY_LEVELS[complexity]

        def clean_label(lbl):
            return re.sub(r'<br\s*/?>', ' ', lbl).strip()

        pid = {
            "supply": "Supply",
            "maincb": "MainCB",
            "bus":    "Bus",
            "nbar":   "NBar",
            "ebar":   "EBar",
            "outcb":  "OutCB",
            "loads":  "Loads",
        }

        lines = ["sequenceDiagram", "    autonumber", ""]

        # ── Box: Incoming Source ──────────────────────────────────────────────
        incoming_color = SECTION_COLORS["incoming"]
        lines.append(f'    box {incoming_color} "{L["section_incoming"][language]}"')
        if "supply" in comp_map:
            lines.append(f'        participant {pid["supply"]} as {clean_label(comp_map["supply"])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Distribution Panel ───────────────────────────────────────────
        dist_color = SECTION_COLORS["distribution"]
        lines.append(f'    box {dist_color} "{L["section_distribution"][language]}"')
        for cid in ["maincb", "bus", "nbar", "ebar", "outcb"]:
            if cid in comp_map:
                lines.append(f'        participant {pid[cid]} as {clean_label(comp_map[cid])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Load Side ────────────────────────────────────────────────────
        load_color = SECTION_COLORS["load"]
        lines.append(f'    box {load_color} "{L["section_load"][language]}"')
        if "loads" in comp_map:
            lines.append(f'        participant {pid["loads"]} as {clean_label(comp_map["loads"])}')
        lines.append("    end")
        lines.append("")

        # ── Section 1: Incoming Power Entry ──────────────────────────────────
        if "supply" in comp_map:
            note_right_order = ["ebar", "nbar", "outcb", "bus", "maincb", "loads"]
            note_right = next((pid[c] for c in note_right_order if c in comp_map), pid["supply"])
            lines.append(f'    Note over {pid["supply"]},{note_right}: {L["note_power_entry"][language]}')

            if "maincb" in comp_map:
                lines.append(f'    {pid["supply"]}->>{pid["maincb"]}: {L["wire_phase"][language]}')
            if cfg["show_neutral"] and "nbar" in comp_map:
                lines.append(f'    {pid["supply"]}->>{pid["nbar"]}: {L["wire_neutral"][language]}')
            if cfg["show_earth"] and "ebar" in comp_map:
                lines.append(f'    {pid["supply"]}-->>{pid["ebar"]}: {L["wire_earth"][language]}')
            lines.append("")

        # ── Section 2: Internal Distribution ─────────────────────────────────
        if "maincb" in comp_map:
            dist_right_order = ["outcb", "ebar", "nbar", "bus"]
            dist_right = next((pid[c] for c in dist_right_order if c in comp_map), pid["maincb"])
            lines.append(f'    Note over {pid["maincb"]},{dist_right}: {L["note_internal"][language]}')

            if "bus" in comp_map:
                lines.append(f'    {pid["maincb"]}->>{pid["bus"]}: {L["action_energize"][language]}')
                if cfg["show_protection_notes"]:
                    lines.append(f'    Note right of {pid["maincb"]}: {L["action_protection"][language]}')
                if "outcb" in comp_map:
                    lines.append(f'    {pid["bus"]}->>{pid["outcb"]}: {L["action_distribute"][language]}')
            elif "outcb" in comp_map:
                lines.append(f'    {pid["maincb"]}->>{pid["outcb"]}: {L["action_distribute"][language]}')
            lines.append("")

        # ── Section 3: Outgoing Circuits ──────────────────────────────────────
        if "loads" in comp_map:
            load_src_order = ["outcb", "bus", "maincb", "supply"]
            load_src = next((pid[c] for c in load_src_order if c in comp_map), None)
            if load_src:
                lines.append(f'    Note over {load_src},{pid["loads"]}: {L["note_outgoing"][language]}')
                lines.append(f'    {load_src}->>{pid["loads"]}: {L["action_feed"][language]}')
            if cfg["show_neutral"] and "nbar" in comp_map:
                lines.append(f'    {pid["nbar"]}->>{pid["loads"]}: {L["action_return"][language]}')
            if cfg["show_earth"] and "ebar" in comp_map:
                lines.append(f'    {pid["ebar"]}-->>{pid["loads"]}: {L["action_safety"][language]}')
            lines.append("")

        # ── Section 4: Fault Protection Paths (Detailed only) ────────────────
        if cfg["show_fault_paths"] and "ebar" in comp_map and "maincb" in comp_map:
            lines.append(f'    Note over {pid["ebar"]},{pid["maincb"]}: {L["note_fault"][language]}')
            lines.append(f'    {pid["ebar"]}-->>{pid["maincb"]}: {L["action_fault"][language]}')

        return "\n".join(lines)

    def generate_display_html(self, mermaid_code, parsed_data, title=None, enable_editing=True):
        language = parsed_data.get("language", "en")
        voltage = parsed_data.get("voltage", "230V / 415V")
        complexity = parsed_data.get("complexity", "Standard")

        if title is None:
            title = "電力配電盤図" if language == "ja" else "Power Distribution Panel Diagram"

        complexity_badge_colors = {"Simple": "#10b981", "Standard": "#3b82f6", "Detailed": "#8b5cf6"}
        complexity_color = complexity_badge_colors.get(complexity, "#3b82f6")

        key_texts = {
            "en": {
                "logic_title": "Key Logic:",
                "logic_items": ["Line (L) passes through Breakers", "Neutral (N) goes direct to Neutral Bar", "Earth (E) goes direct to Earth Bar"],
                "safety_title": "Safety:",
                "safety_items": ["Main Breaker isolates entire panel", "Outgoing MCBs protect individual circuits", "Earth ensures chassis safety"],
                "components_title": "Components:",
                "components_items": ["<strong>MCCB:</strong> Molded Case Circuit Breaker", "<strong>MCB:</strong> Miniature Circuit Breaker", "<strong>Busbar:</strong> Copper strip for distribution"],
                "generated": "Generated from prompt description",
                "tip": "Tip: Drag any blue box to move it. Double-click any text to edit it. Edit code below to update diagram.",
                "code_label": "Mermaid Code (edit to update diagram ->)",
                "complexity_label": f"Mode: {complexity}",
            },
            "ja": {
                "logic_title": "主要ロジック:",
                "logic_items": ["相線(L)は遮断器を通過", "中性線(N)は中性線バーへ直接接続", "接地線(E)は接地バーへ直接接続"],
                "safety_title": "安全機能:",
                "safety_items": ["主遮断器は全盤を絶縁", "出力MCBは個々の回路を保護", "接地は筐体の安全性を確保"],
                "components_title": "構成部品:",
                "components_items": ["<strong>MCCB:</strong> モールドケース遮断器", "<strong>MCB:</strong> 配線用遮断器", "<strong>Busbar:</strong> 銅製配電用導体"],
                "generated": "プロンプトから生成",
                "tip": "ヒント: 青色のボックスをドラッグして移動。ダブルクリックでテキストを編集。コードを編集して図を更新。",
                "code_label": "Mermaidコード (編集で図を更新 ->)",
                "complexity_label": f"モード: {complexity}",
            }
        }
        key = key_texts.get(language, key_texts["en"])
        
        # Define editor_js with raw string
        editor_js = r"""
<script>
class EnhancedMermaidEditor {
    constructor() {
        this.dragState   = null;
        this.editState   = null;
        this.svgEl       = null;
        this.arrowEndpoints = new Map();
        this.blueBoxes   = new Set();
        this._waitForSVG();
    }
    _waitForSVG() {
        const iv = setInterval(() => {
            const svg = document.querySelector('.mermaid svg');
            if (svg) { clearInterval(iv); setTimeout(() => this._init(svg), 300); }
        }, 100);
    }
    _init(svg) {
        this.svgEl = svg;
        this._fixAllText(svg);
        this._classifyBoxes(svg);
        this._storeArrowEndpoints(svg);
        this._attachSVGListeners(svg);
    }
    _fixAllText(svg) {
        svg.querySelectorAll('text, tspan').forEach(el => {
            const f = el.getAttribute('fill');
            if (!f || f === 'currentColor' || f === 'inherit' || f === '#ffffff' || f === '#fff' || f === 'white') {
                el.setAttribute('fill', '#1a202c');
            }
        });
    }
    _classifyBoxes(svg) {
        const seen = new Set();
        svg.querySelectorAll('rect.note, rect[class*="note"]').forEach((rect, idx) => {
            if (seen.has(rect)) return;
            seen.add(rect);
            const rBBox = rect.getBoundingClientRect();
            if (rBBox.width < 4 || rBBox.height < 4) return;
            const matchedTexts = Array.from(svg.querySelectorAll('text')).filter(t => {
                if (seen.has(t)) return false;
                const tBBox = t.getBoundingClientRect();
                if (tBBox.width === 0 && tBBox.height === 0) return false;
                const tCx = tBBox.left + tBBox.width / 2;
                const tCy = tBBox.top + tBBox.height / 2;
                const tol = 8;
                return (tCx >= rBBox.left - tol && tCx <= rBBox.right + tol && tCy >= rBBox.top - tol && tCy <= rBBox.bottom + tol);
            });
            matchedTexts.forEach(t => seen.add(t));
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('data-actor-group', 'note-' + idx);
            g.setAttribute('data-tx', '0');
            g.setAttribute('data-ty', '0');
            rect.parentNode.insertBefore(g, rect);
            g.appendChild(rect);
            matchedTexts.forEach(t => g.appendChild(t));
            const fill = rect.getAttribute('fill') || '';
            const rectColor = fill.toLowerCase();
            if (rectColor.includes('255,255,200') || rectColor.includes('#ffffcc') || rectColor.includes('255,250,205') || rectColor.includes('#fffacd') || rectColor.includes('lemonchiffon') || rectColor.includes('lightyellow')) {
                g.setAttribute('data-box-type', 'section-label');
                g.style.cursor = 'default';
                g.addEventListener('dblclick', e => this._onDblClick(e));
            }
            else if (rectColor.includes('224,231,255') || rectColor.includes('#e0e7ff') || rectColor.includes('200,220,255') || rectColor.includes('lightblue')) {
                g.setAttribute('data-box-type', 'component');
                g.setAttribute('data-draggable', 'component-' + idx);
                g.style.cursor = 'grab';
                this.blueBoxes.add('note-' + idx);
                g.addEventListener('mousedown', e => this._onComponentMouseDown(e, g, idx));
                g.addEventListener('touchstart', e => this._onComponentTouchStart(e, g, idx), {passive: false});
                g.addEventListener('mouseenter', () => { if (!this.dragState) rect.style.filter = 'drop-shadow(0 0 6px rgba(66,153,225,0.8))'; });
                g.addEventListener('mouseleave', () => { if (!this.dragState) rect.style.filter = ''; });
                g.addEventListener('dblclick', e => this._onDblClick(e));
            }
            else {
                g.setAttribute('data-box-type', 'static');
                g.style.cursor = 'default';
                g.addEventListener('dblclick', e => this._onDblClick(e));
            }
        });
    }
    _storeArrowEndpoints(svg) {
        const lines = svg.querySelectorAll('line, path.messageLine, polyline.messageLine');
        lines.forEach((line, idx) => {
            let x1, y1, x2, y2;
            if (line.tagName.toLowerCase() === 'line') {
                x1 = parseFloat(line.getAttribute('x1') || 0);
                y1 = parseFloat(line.getAttribute('y1') || 0);
                x2 = parseFloat(line.getAttribute('x2') || 0);
                y2 = parseFloat(line.getAttribute('y2') || 0);
            }
            if (x1 !== undefined && y1 !== undefined) {
                const key = 'arrow-' + idx;
                this.arrowEndpoints.set(key, { el: line, x1: x1, y1: y1, x2: x2, y2: y2, originalX1: x1, originalY1: y1, originalX2: x2, originalY2: y2 });
                line.setAttribute('data-system-arrow', 'true');
                line.style.cursor = 'default';
                line.style.pointerEvents = 'none';
            }
        });
        const paths = svg.querySelectorAll('path[marker-end], path[class*="arrow"], path[class*="message"]');
        paths.forEach(path => { path.setAttribute('data-system-arrow', 'true'); path.style.cursor = 'default'; path.style.pointerEvents = 'none'; });
    }
    _attachSVGListeners(svg) {
        svg.addEventListener('mousemove', e => this._onMouseMove(e));
        svg.addEventListener('mouseup', e => this._onMouseUp(e));
        svg.addEventListener('mouseleave', e => this._onMouseUp(e));
        svg.addEventListener('touchmove', e => this._onTouchMove(e), {passive: false});
        svg.addEventListener('touchend', e => this._onTouchEnd(e), {passive: false});
        svg.addEventListener('dblclick', e => this._onDblClick(e));
        window.addEventListener('mousemove', e => this._onMouseMove(e));
        window.addEventListener('mouseup', e => this._onMouseUp(e));
    }
    _screenToSVG(x, y) {
        const pt = this.svgEl.createSVGPoint();
        pt.x = x; pt.y = y;
        return pt.matrixTransform(this.svgEl.getScreenCTM().inverse());
    }
    _onComponentMouseDown(e, g, idx) {
        if (g.getAttribute('data-box-type') !== 'component') return;
        e.stopPropagation();
        const pt = this._screenToSVG(e.clientX, e.clientY);
        this.dragState = { g, startX: pt.x, startY: pt.y, tx: parseFloat(g.getAttribute('data-tx') || 0), ty: parseFloat(g.getAttribute('data-ty') || 0) };
        g.style.cursor = 'grabbing';
        g.style.opacity = '0.85';
    }
    _onComponentTouchStart(e, g, idx) {
        if (g.getAttribute('data-box-type') !== 'component') return;
        e.preventDefault();
        const t = e.touches[0];
        const pt = this._screenToSVG(t.clientX, t.clientY);
        this.dragState = { g, startX: pt.x, startY: pt.y, tx: parseFloat(g.getAttribute('data-tx') || 0), ty: parseFloat(g.getAttribute('data-ty') || 0) };
    }
    _onMouseDown(e) {
        const target = e.target;
        if (target.getAttribute && target.getAttribute('data-system-arrow') === 'true') { e.preventDefault(); e.stopPropagation(); return false; }
        const g = target.closest ? target.closest('[data-actor-group]') : null;
        if (g && g.getAttribute('data-box-type') !== 'component') { e.preventDefault(); e.stopPropagation(); return false; }
    }
    _onMouseMove(e) {
        if (!this.dragState) return;
        const pt = this._screenToSVG(e.clientX, e.clientY);
        let dx = pt.x - this.dragState.startX;
        let dy = pt.y - this.dragState.startY;
        const gridSize = 20;
        dx = Math.round(dx / gridSize) * gridSize;
        dy = Math.round(dy / gridSize) * gridSize;
        let newTx = this.dragState.tx + dx;
        let newTy = this.dragState.ty + dy;
        this.dragState.g.setAttribute('transform', 'translate(' + newTx + ',' + newTy + ')');
        this.dragState.g.setAttribute('data-tx', newTx);
        this.dragState.g.setAttribute('data-ty', newTy);
        this._updateConnectedArrows();
    }
    _updateConnectedArrows() {
        this.arrowEndpoints.forEach((arrowData, key) => {
            const arrow = arrowData.el;
            const g1 = this._findNearestComponent(arrowData.originalX1, arrowData.originalY1);
            const g2 = this._findNearestComponent(arrowData.originalX2, arrowData.originalY2);
            if (g1 && g2 && arrow.tagName && arrow.tagName.toLowerCase() === 'line') {
                arrow.setAttribute('x1', arrowData.originalX1 + parseFloat(g1.getAttribute('data-tx') || 0));
                arrow.setAttribute('y1', arrowData.originalY1 + parseFloat(g1.getAttribute('data-ty') || 0));
                arrow.setAttribute('x2', arrowData.originalX2 + parseFloat(g2.getAttribute('data-tx') || 0));
                arrow.setAttribute('y2', arrowData.originalY2 + parseFloat(g2.getAttribute('data-ty') || 0));
            }
        });
    }
    _findNearestComponent(x, y) {
        let nearest = null;
        let minDist = Infinity;
        this.svgEl.querySelectorAll('[data-box-type="component"]').forEach(g => {
            const bbox = g.getBoundingClientRect();
            const cx = bbox.left + bbox.width / 2;
            const cy = bbox.top + bbox.height / 2;
            const dist = Math.hypot(cx - x, cy - y);
            if (dist < minDist && dist < 100) { minDist = dist; nearest = g; }
        });
        return nearest;
    }
    _onTouchMove(e) { e.preventDefault(); if (this.dragState) { const t = e.touches[0]; this._onMouseMove({clientX: t.clientX, clientY: t.clientY}); } }
    _onMouseUp(e) { if (this.dragState) { this.dragState.g.style.cursor = 'grab'; this.dragState.g.style.opacity = '1'; this.dragState = null; this._syncDiagramToCode(); } }
    _onTouchEnd(e) { if (this.dragState) { this.dragState.g.style.opacity = '1'; this.dragState = null; this._syncDiagramToCode(); } }
    _onDblClick(e) {
        let textEl = null;
        if (e.target.tagName === 'text') textEl = e.target;
        if (e.target.tagName === 'tspan') textEl = e.target.parentElement;
        if (!textEl) return;
        const current = this._getTextContent(textEl);
        if (!current.trim()) return;
        this._openTextEditor(textEl, current);
    }
    _getTextContent(el) { const spans = el.querySelectorAll('tspan'); if (spans.length) return Array.from(spans).map(s => s.textContent).join('\\n'); return el.textContent || ''; }
    _openTextEditor(textEl, current) {
        const rect = textEl.getBoundingClientRect();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = current;
        Object.assign(input.style, {
            position: 'fixed', left: (rect.left + window.scrollX) + 'px', top: (rect.top + window.scrollY) + 'px',
            width: Math.max(rect.width + 24, 160) + 'px', height: rect.height + 10 + 'px',
            zIndex: '10000', padding: '3px 8px', border: '2px solid #4299e1', borderRadius: '4px',
            fontSize: window.getComputedStyle(textEl).fontSize, fontFamily: window.getComputedStyle(textEl).fontFamily,
            fontWeight: window.getComputedStyle(textEl).fontWeight, color: '#000', backgroundColor: '#fff',
            boxShadow: '0 4px 12px rgba(0,0,0,0.18)', outline: 'none'
        });
        document.body.appendChild(input);
        this.editState = {input, textEl, original: current};
        input.focus(); input.select();
        const done = (save) => {
            const val = input.value.trim();
            if (save && val && val !== current) {
                this._applyTextEdit(textEl, val);
                this._syncDiagramToCode();
                if (window.qtBridge && window.qtBridge.onElementEdited) {
                    const r = textEl.getBoundingClientRect();
                    window.qtBridge.onElementEdited('el_'+Date.now(), 'text', val, r.left, r.top);
                }
            }
            document.body.removeChild(input);
            this.editState = null;
        };
        input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); done(true); } if (e.key === 'Escape') { e.preventDefault(); done(false); } });
        input.addEventListener('blur', () => done(true));
    }
    _applyTextEdit(textEl, newVal) {
        const spans = textEl.querySelectorAll('tspan');
        const lines = newVal.split('\\n');
        if (spans.length) { spans.forEach((s, i) => { if (i < lines.length) s.textContent = lines[i]; }); }
        else { textEl.textContent = newVal; }
    }
    _syncDiagramToCode() {
        const codeArea = document.getElementById('mermaid-code-editor');
        if (!codeArea) return;
        const groups = document.querySelectorAll('[data-actor-group]');
        let code = codeArea.value;
        groups.forEach(g => {
            const textEls = g.querySelectorAll('text');
            if (!textEls.length) return;
            const newLabel = Array.from(textEls).map(t => {
                const spans = t.querySelectorAll('tspan');
                return spans.length ? Array.from(spans).map(s => s.textContent).join('<br/>') : t.textContent;
            }).join('<br/>').trim();
            if (!newLabel) return;
            code = code.replace(/(participant\s+\w+\s+as\s+).+/, (match, prefix) => prefix + newLabel);
        });
        codeArea.value = code;
        if (window.qtBridge && window.qtBridge.onDiagramTextChanged) { window.qtBridge.onDiagramTextChanged(code); }
    }
}
function applyCodeToDiagram() {
    const codeArea = document.getElementById('mermaid-code-editor');
    const container = document.getElementById('mermaid-container');
    if (!codeArea || !container) return;
    const code = codeArea.value.trim();
    if (!code) return;
    container.innerHTML = '<div class="mermaid">' + code + '</div>';
    if (window.mermaid) {
        try {
            window.mermaid.run({nodes: container.querySelectorAll('.mermaid')}).then(() => {
                setTimeout(() => { window.mermaidEditor = new EnhancedMermaidEditor(); }, 400);
            });
        } catch(e) {
            console.error('Mermaid render error:', e);
            container.innerHTML = '<p style="color:red;padding:12px;">Mermaid syntax error. Check the code and try again.</p>';
        }
    }
    if (window.qtBridge && window.qtBridge.onDiagramTextChanged) { window.qtBridge.onDiagramTextChanged(code); }
}
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { window.mermaidEditor = new EnhancedMermaidEditor(); }, 800);
    const applyBtn = document.getElementById('apply-code-btn');
    if (applyBtn) applyBtn.addEventListener('click', applyCodeToDiagram);
    const codeArea = document.getElementById('mermaid-code-editor');
    if (codeArea) {
        codeArea.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); applyCodeToDiagram(); }
        });
    }
});
</script>
<style>
.mermaid svg text, .mermaid svg tspan { fill: #1a202c !important; }
[data-box-type="component"] { cursor: grab; }
[data-box-type="component"]:active { cursor: grabbing; }
[data-box-type="component"]:hover rect { filter: drop-shadow(0 0 5px rgba(66,153,225,0.6)); }
[data-box-type="section-label"] { cursor: default !important; }
[data-box-type="section-label"]:hover rect { filter: drop-shadow(0 0 3px rgba(251,191,36,0.4)); }
[data-box-type="static"] { cursor: default !important; }
[data-system-arrow="true"] { cursor: default !important; pointer-events: none !important; }
[data-system-arrow="true"]:hover { stroke-width: inherit !important; cursor: default !important; }
.mermaid svg line[data-system-arrow="true"], .mermaid svg path[data-system-arrow="true"] { pointer-events: none !important; }
#mermaid-code-editor { width: 100%; font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace; font-size: 12px; line-height: 1.5; color: #1a202c; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 12px; resize: vertical; outline: none; transition: border-color 0.2s; }
#mermaid-code-editor:focus { border-color: #4299e1; box-shadow: 0 0 0 3px rgba(66,153,225,0.15); }
#apply-code-btn { background: #2c5282; color: #fff; border: none; border-radius: 5px; padding: 7px 18px; font-size: 12px; font-weight: 600; cursor: pointer; margin-top: 6px; transition: background 0.15s; }
#apply-code-btn:hover { background: #2a4365; }
.code-panel-label { font-size: 11px; font-weight: 600; color: #718096; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom: 4px; margin-top: 14px; }
.apply-row { display: flex; align-items: center; gap: 10px; margin-top: 6px; }
.apply-hint { font-size: 11px; color: #a0aec0; }
</style>
"""
        
        # Build the HTML using string concatenation (safer than f-string with raw strings)
        lang_badge_color = '#3b82f6' if language == 'en' else '#ef4444'
        lang_badge_text = 'English' if language == 'en' else '日本語'
        
        css_style = """* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f4f8; padding: 20px; min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; background: #fff; border-radius: 14px; box-shadow: 0 4px 24px rgba(0,0,0,0.10); padding: 28px 32px 24px; position: relative; }
.badge-row { position: absolute; top: 16px; right: 20px; display: flex; gap: 6px; align-items: center; }
.lang-badge { background: """ + lang_badge_color + """; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; }
.complexity-badge { background: """ + complexity_color + """; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; }
.header { text-align: center; margin-bottom: 20px; }
.header h1 { font-size: 26px; font-weight: 700; color: #1a202c; margin-bottom: 6px; }
.header p { color: #718096; font-size: 13px; }
.voltage-pill { display: inline-block; background: #edf2f7; padding: 3px 12px; border-radius: 20px; font-size: 12px; color: #4a5568; margin-left: 8px; }
.tip-bar { background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 8px 14px; font-size: 12px; color: #92400e; text-align: center; margin-bottom: 16px; }
.mermaid-wrap { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; overflow: auto; user-select: none; -webkit-user-select: none; }
.mermaid { min-height: 200px; }
.key-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 20px; padding-top: 16px; border-top: 1px solid #e2e8f0; }
.key-card { background: #f9fafb; border-radius: 8px; padding: 12px 14px; }
.key-card strong { display: block; margin-bottom: 6px; font-size: 13px; }
.key-card ul { padding-left: 18px; margin: 0; }
.key-card li { font-size: 12px; color: #4a5568; margin-bottom: 3px; }
.blue { color: #1d4ed8; }
.green { color: #047857; }
.amber { color: #b45309; }"""

        logic_items = ''.join('<li>' + i + '</li>' for i in key['logic_items'])
        safety_items = ''.join('<li>' + i + '</li>' for i in key['safety_items'])
        components_items = ''.join('<li>' + i + '</li>' for i in key['components_items'])

        html_top = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>""" + title + """</title>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
window.mermaid = mermaid;
mermaid.initialize({
    startOnLoad: true,
    theme: 'base',
    themeVariables: {
        primaryColor: '#e0e7ff',
        primaryTextColor: '#1a202c',
        secondaryTextColor: '#1a202c',
        tertiaryTextColor: '#1a202c',
        noteTextColor: '#1a202c',
        noteBkgColor: '#fffacd',
        actorBkgColor: '#e0e7ff',
        actorBorderColor: '#a5b4fc',
        actorTextColor: '#1a202c',
        labelBoxBkgColor: '#f0fdf4',
        labelBoxBorderColor: '#86efac',
        labelTextColor: '#1a202c',
        fontFamily: 'Arial, sans-serif',
        fontSize: '15px'
    }
});
</script>
""" + editor_js + """
<style>
""" + css_style + """
</style>
</head>
<body>
<div class="container">
    <div class="badge-row">
        <span class="complexity-badge">""" + key['complexity_label'] + """</span>
        <span class="lang-badge">""" + lang_badge_text + """</span>
    </div>
    <div class="header">
        <h1>""" + title + """</h1>
        <p>""" + key['generated'] + """ <span class="voltage-pill">&#9889; """ + voltage + """</span></p>
    </div>
    <div class="tip-bar">""" + key['tip'] + """</div>
    <div class="mermaid-wrap">
        <div id="mermaid-container">
            <div class="mermaid">
""" + mermaid_code + """
            </div>
        </div>
    </div>
    <div class="code-panel-label">""" + key['code_label'] + """</div>
    <textarea id="mermaid-code-editor" rows="10">""" + mermaid_code + """</textarea>
    <div class="apply-row">
        <button id="apply-code-btn">&#9654; Apply (Ctrl+&#8629;)</button>
        <span class="apply-hint">Ctrl+Enter to apply &bull; diagram edits sync here</span>
    </div>
    <div class="key-grid">
        <div class="key-card">
            <strong class="blue">""" + key['logic_title'] + """</strong>
            <ul>""" + logic_items + """</ul>
        </div>
        <div class="key-card">
            <strong class="green">""" + key['safety_title'] + """</strong>
            <ul>""" + safety_items + """</ul>
        </div>
        <div class="key-card">
            <strong class="amber">""" + key['components_title'] + """</strong>
            <ul>""" + components_items + """</ul>
        </div>
    </div>
</div>
</body>
</html>"""

        return html_top