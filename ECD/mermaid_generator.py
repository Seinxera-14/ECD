import re
from constants import COMPLEXITY_LEVELS



class MermaidGenerator:
    def __init__(self):
        self.components_map = {
            "main incoming supply": {"en": "Main Incoming Supply<br/>(230V / 415V)", "ja": "主電源<br/>(230V / 415V)"},
            "main breaker": {"en": "Main Breaker<br/>(MCB/MCCB)", "ja": "主遮断器<br/>(MCB/MCCB)"},
            "rcd": {"en": "RCD<br/>(Earth Fault Protection)", "ja": "漏電遮断器<br/>(RCD/RCBO)"},
            "busbar": {"en": "Busbar<br/>(Distribution)", "ja": "母線<br/>(配電)"},
            "neutral bar": {"en": "Neutral Bar", "ja": "中性線バー"},
            "earth bar": {"en": "Earth Bar", "ja": "接地バー"},
            "outgoing mcbs": {"en": "Outgoing MCBs", "ja": "出力MCB"},
            "load circuits": {"en": "Load Circuits<br/>(Lights, Sockets)", "ja": "負荷回路<br/>(照明、コンセント)"},
        }
        self.keywords_map = {
            "incoming": {
                "en": [
                    "incoming", "supply", "source", "230v", "415v", "mains", "grid", "utility", "infeed", "line in",
                    "three-phase", "3-phase", "three phase", "3phase", "ryb", "ryw", "rst", "uvw",
                    "single-phase", "1-phase", "single phase",
                ],
                "ja": [
                    "主電源", "受電", "電源", "入力電源",
                    "三相", "単相", "系統",
                ],
            },            
            "breaker": {
                "en": [
                    "breaker", "mcb", "mccb", "protection", "circuit breaker", "main cb", "main breaker",
                    "isolator", "isolating switch", "main switch", "elcb",
                    "fuse", "fuse switch", "switch fuse", "acb", "vcb", "contactor",
                ],
                "ja": [
                    "遮断器", "ブレーカー", "ブレーカ",
                    "主開閉器", "漏電遮断器", "配線用遮断器",
                    "ヒューズ", "開閉器",
                ],
            },

            "rcd": {
                "en": ["rcd", "rcbo", "elcb", "residual current", "earth fault", "leakage",
                    "earth leakage", "ground fault", "residual", "30ma", "100ma", "300ma"],
                "ja": ["漏電遮断器", "漏電ブレーカー", "漏電", "地絡", "残留電流"],
            },

            "busbar": {
                "en": [
                    "busbar", "distribution", "panel", "bus bar", "bus-bar", "copper bar", "copper strip", 
                    "db", "distribution board", "distribution box", "switchboard", "switchgear", "mdb", "pcc", "mcc",                                 
                ],
                "ja": [
                    "母線", "バスバー", "配電盤", "分電盤",
                    "銅バー", "主幹", "盤",
                ],
            },            
            
            "neutral": {
                "en": [
                    "neutral", "return",
                    "neutral bar", "n bar", "n-bar",
                    "neutral link", "neutral terminal",
                    "neutral bus", "common neutral",
                    "neutral return", "return path",
                    # three-phase star point terms
                    "star point", "centre point",
                ],
                "ja": [
                    "中性線", "ニュートラル", "零線", "N線",
                    "中性点", "中性線バー",
                ],
            },            

            "earth": {
                "en": [
                    "earth", "ground", "safety",
                    "earth bar", "e bar", "e-bar",
                    "earthing", "grounding",
                    "protective earth", "pe",
                    "cpc", "safety earth", "protective conductor",
                    "bonding", "equipotential bonding",
                    "earth terminal", "earth bus",
                    "chassis earth", "frame earth",
                ],
                "ja": [
                    "接地", "アース", "グラウンド", "地線",
                    "保護接地", "接地バー", "PE線",
                ],
            }, 

            "outgoing": {
                "en": [
                    "outgoing", "branch", "circuit",
                    "sub breaker", "sub-breaker", "sub mcb",
                    "outgoing mcb", "outgoing breaker",
                    "final circuit", "branch circuit",
                    "feeder", "sub feeder",
                    "downstream breaker", "individual breaker",
                    "motor breaker", "lighting breaker",
                ],
                "ja": [
                    "出力", "分岐", "回路",
                    "分岐ブレーカー", "出力MCB", "子ブレーカー",
                ],
            },

           
            "load": {
                "en": [
                    "load", "circuit", "light", "socket", "appliance",
                    # common load descriptions users write
                    "lighting", "lights", "lamps", "luminaire",
                    "power socket", "outlet", "plug point",
                    "motor", "pump", "fan", "hvac", "air conditioning",
                    "equipment", "machine", "device", "consumer",
                    "balanced load", "unbalanced load",
                    "three-phase load", "single-phase load",
                ],
                "ja": [
                    "負荷", "回路", "照明", "コンセント",
                    "モーター", "ポンプ", "機器", "電気機器",
                ],
            },
        }
        self.diagram_labels = {
            "section_incoming":     {"en": "Incoming Source",               "ja": "入力電源"},
            "section_distribution": {"en": "Distribution Panel Components", "ja": "分電盤部品"},
            "section_load":         {"en": "Load Side",                     "ja": "負荷側"},
            "note_power_entry":     {"en": "1. INCOMING POWER ENTRY",       "ja": "1. 受電"},
            "note_internal":        {"en": "2. INTERNAL DISTRIBUTION",      "ja": "2. 内部配電"},
            "note_outgoing":        {"en": "3. OUTGOING CIRCUITS",          "ja": "3. 出力回路"},
            "note_fault":           {"en": "4. FAULT CURRENT PATH (E)",     "ja": "4. 故障電流経路 (E)"},            
            "wire_phase":           {"en": "Phase/Line Wire (L)",           "ja": "相線/ラインワイヤ (L)"},
            "wire_neutral":         {"en": "Neutral Wire (N)",              "ja": "中性線 (N)"},
            "wire_earth":           {"en": "Earth Wire (E)",                "ja": "接地線 (E)"},
            "action_energize":      {"en": "Energize Busbar (L)",           "ja": "母線を励磁 (L)"},
            "action_protection":    {"en": "Protection: Overload/Short",    "ja": "保護: 過負荷/短絡"},
            "action_rcd_monitor":   {"en": "Current Monitoring (RCD)",      "ja": "電流監視 (RCD)"},
            "action_rcd_pass":      {"en": "Protected Distribution (L)",    "ja": "保護配電 (L)"},
            "action_rcd_note":      {"en": "RCD: Residual Current\nTrip", "ja": "RCD: 漏電検知\n30mA以下でトリップ"},
            "action_distribute":    {"en": "Distribute to Branch Breakers", "ja": "分岐ブレーカーに配電"},
            "action_feed":          {"en": "Line (L) - Protected Feed",     "ja": "ライン (L) - 保護給電"},
            "action_return":        {"en": "Neutral (N) - Return Path",     "ja": "中性線 (N) - 帰路"},
            "action_safety":        {"en": "Earth (E) - Safety Grounding",  "ja": "接地 (E) - 安全接地"},
            "action_fault":         {"en": "Fault Current Detected (E)",    "ja": "故障電流検知 (E)"},
            "action_fault_return":  {"en": "Fault Return Path to Source",         "ja": "故障電流帰路 (電源へ)"},
            "action_rcd_isolate":   {"en": "Open Contacts — Isolate Circuit",     "ja": "接点開放 — 回路遮断"},
            "action_rcd_trip":      {"en": "RCD Trip Signal",               "ja": "RCDトリップ信号"},
            "action_cb_open":       {"en": "Circuit Open — Supply Isolated", "ja": "回路開放 — 電源遮断"},
        }
        
    def detect_language(self, text):
        if re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]').search(text):
            return "ja"
        return "en"


    

    def parse_prompt(self, prompt_text, complexity_level="Neutral"):
        print('parsing prompt with hardcoded rules')
        if not prompt_text or not isinstance(prompt_text, str):
            return {"components": self.get_default_components("en", "230V / 415V", "Standard"),
                    "voltage": "230V / 415V", "language": "en", "complexity": complexity_level}

        exclusions = {
            "rcd":  ["no rcd", "no residual", "no earth fault"],
            "nbar": ["no neutral"],
            "ebar": ["no earth", "no ground"],
            "bus":  ["no busbar", "no bus"],
        }
        prompt_lower = prompt_text.lower()

        # ✅ Assign BEFORE use
        language = self.detect_language(prompt_text)
        voltage_text = "230V / 415V"

        try:
            for pattern in [r'(\d+)\s*[Vv]\s*[/／]?\s*(\d+)\s*[Vv]', r'(\d+)\s*[Vv]', r'(\d+)\s*volts?']:
                m = re.search(pattern, prompt_text)
                if m:
                    voltage_text = f"{m.group(1)}V / {m.group(2)}V" if len(m.groups()) >= 2 else f"{m.group(1)}V"
                    break
        except Exception:
            pass

        # ✅ For Neutral mode, keyword-detect from prompt instead of using empty allowed list
        if complexity_level == "Neutral":
            KEYWORD_TO_COMPONENT = {
                "supply":  ["supply", "mains", "source", "incoming", "grid"],
                "maincb":  ["breaker", "mcb", "mccb", "circuit breaker", "main cb"],
                "rcd":     ["rcd", "rcbo", "residual", "earth fault"],
                "bus":     ["busbar", "bus bar", "bus-bar", "distribution"],
                "nbar":    ["neutral bar", "neutral link", "n bar"],
                "ebar":    ["earth bar", "earth terminal", "e bar"],
                "loads":   ["load", "loads", "lighting", "socket", "appliance", "circuit"],
            }
            all_possible = self.get_default_components(language, voltage_text, "Standard")
            all_possible_dict = dict(all_possible)

            found_ids = []
            for cid, keywords in KEYWORD_TO_COMPONENT.items():
                if any(kw in prompt_lower for kw in keywords):
                    if cid not in [ex for ex in exclusions if any(ex_kw in prompt_lower for ex_kw in exclusions.get(cid, []))]:
                        found_ids.append(cid)

            # Always ensure supply and loads if detected; fallback to supply+maincb+loads minimum
            if not found_ids:
                found_ids = ["supply", "maincb", "loads"]

            found_components = [
                (cid, all_possible_dict[cid]) for cid in found_ids
                if cid in all_possible_dict
                and not any(ex in prompt_lower for ex in exclusions.get(cid, []))
            ]
        else:
            # Non-Neutral: use the complexity level's allowed list
            found_components = self.get_default_components(language, voltage_text, complexity_level)
            comp_dict = dict(found_components)
            if "supply" in comp_dict:
                comp_dict["supply"] = self.components_map["main incoming supply"][language].replace(
                    "230V / 415V", voltage_text
                )
            found_components = [
                (cid, lbl) for cid, lbl in comp_dict.items()
                if not any(ex in prompt_lower for ex in exclusions.get(cid, []))
            ]

        return {"components": found_components, "voltage": voltage_text,
                "language": language, "complexity": complexity_level}

    def get_default_components(self, language, voltage_text="230V / 415V", complexity_level="Standard"):
        level_cfg = COMPLEXITY_LEVELS[complexity_level]
        allowed_ids = level_cfg["components"]  # outcb_N no longer in here for Detailed

        # allowed_ids = COMPLEXITY_LEVELS[complexity_level]["components"]
        all_defaults = [
            ("supply", self.components_map["main incoming supply"][language].replace("230V / 415V", voltage_text)),
            ("maincb", self.components_map["main breaker"][language]),
            ("rcd",    self.components_map["rcd"][language]),
            ("bus",    self.components_map["busbar"][language]),
            ("nbar",   self.components_map["neutral bar"][language]),
            ("ebar",   self.components_map["earth bar"][language]),
            ("loads",  self.components_map["load circuits"][language]),
        ]

        return [(cid, lbl) for cid, lbl in all_defaults if cid in allowed_ids]

    def generate_mermaid_code(self, parsed_data):
        components = parsed_data["components"]
        language   = parsed_data.get("language", "en")
        complexity = parsed_data.get("complexity", "Neutral")
        comp_map   = {cid: lbl for cid, lbl in components}
        L          = self.diagram_labels

        # ── Merge flags ───────────────────────────────────────────────────────────────────
        # Complexity defaults WIN when they require True.
        # The LLM can add True flags (e.g. user asked for fault paths on Standard),
        # but must NOT suppress flags that the complexity level mandates.
        # This fixes Detailed mode where Mistral often returns show_fault_paths=false.
        complexity_cfg = COMPLEXITY_LEVELS.get(complexity, COMPLEXITY_LEVELS["Neutral"])
        llm_flags = parsed_data.get("flags", {})

        # def _merge_flag(key):
        #     complexity_val = complexity_cfg[key]
        #     llm_val = llm_flags.get(key, None)
        #     # OR: if complexity requires it, keep it; LLM can only add True
        #     # return complexity_val or llm_val
        #     if llm_val is not None:
        #         return llm_val
        #     return complexity_val

        prompt_text = parsed_data.get("prompt", "")

        EXPLICIT_ENABLE_KEYWORDS = {
            "show_fault_paths":       ["fault path", "fault current", "earth fault path"],
            "show_neutral":           ["neutral wire", "show neutral", "include neutral"],
            "show_earth":             ["earth wire", "show earth", "include earth"],
            "show_rcd":               ["rcd", "residual current", "earth fault protection"],
            "show_protection_notes":  ["protection note", "show notes", "annotation"],
        }

        def _prompt_explicitly_enables(key, text):
            t = text.lower()
            return any(kw in t for kw in EXPLICIT_ENABLE_KEYWORDS.get(key, []))

        def _merge_flag(key):
            complexity_val = complexity_cfg[key]
            llm_val = llm_flags.get(key, None)

            # If complexity REQUIRES False (e.g. Simple hides fault paths),
            # only override if the prompt explicitly asks for it
            if complexity_val is False:
                # Only allow True if LLM was explicitly instructed by prompt
                # (prompt_text is stored in parsed_data["prompt"])
                prompt_explicitly_requests = _prompt_explicitly_enables(key, prompt_text)
                return True if prompt_explicitly_requests else False

            # If complexity requires True, LLM cannot suppress it
            if complexity_val is True:
                return True

            # Neutral / unset — LLM decides
            return llm_val if llm_val is not None else complexity_val


        cfg = {
            "show_neutral":          _merge_flag("show_neutral"),
            "show_earth":            _merge_flag("show_earth"),
            "show_rcd":              _merge_flag("show_rcd"),
            "show_protection_notes": _merge_flag("show_protection_notes"),
            "show_fault_paths":      _merge_flag("show_fault_paths"),
        }

        voltage_str = parsed_data.get("voltage", "")
        prompt_text = parsed_data.get("prompt", "")   # see note below about storing prompt

        THREE_PHASE_TERMS = ["415", "three-phase", "3-phase", "3phase", "ryb", "ryw", "rst", "uvw", "three phase"]
        is_three_phase = any(t in voltage_str.lower() for t in THREE_PHASE_TERMS)

        def clean_label(lbl):
            return re.sub(r'<br\s*/?>', ' ', lbl).strip()

        # ── Build participant ID map — handle dynamic outcb_1..5 ──────────────────
        pid = {
            "supply": "Supply",
            "maincb": "MainCB",
            "rcd":    "RCD",
            "rcbo":   "RCD",
            "bus":    "Bus",
            "nbar":   "NBar",
            "ebar":   "EBar",
            "outcb":  "OutCB",
            "loads":  "Loads",
        }
        # Add dynamic outcb_N entries
        for cid, _ in components:
            if cid.startswith("outcb_"):
                pid[cid] = cid.replace("outcb_", "OutCB")

        outcb_ids = [cid for cid, _ in components if cid.startswith("outcb_")]
        # Also support legacy single "outcb"
        if "outcb" in comp_map and not outcb_ids:
            outcb_ids = ["outcb"]

        lines = ["sequenceDiagram",  ""]

        # ── Box: Incoming Source ──────────────────────────────────────────────────
        lines.append(f'    box rgb(238,242,255) "{L["section_incoming"][language]}"')
        if "supply" in comp_map:
            lines.append(f'        participant {pid["supply"]} as {clean_label(comp_map["supply"])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Distribution Panel ───────────────────────────────────────────────
        lines.append(f'    box rgb(240,253,244) "{L["section_distribution"][language]}"')
        dist_order = ["maincb", "rcd", "rcbo", "bus", "nbar", "ebar"] + outcb_ids
        for cid in dist_order:
            if cid in comp_map:
                lines.append(f'        participant {pid[cid]} as {clean_label(comp_map[cid])}')
        lines.append("    end")
        lines.append("")

        # ── Box: Load Side ────────────────────────────────────────────────────────
        lines.append(f'    box rgb(255,247,237) "{L["section_load"][language]}"')
        if "loads" in comp_map:
            lines.append(f'        participant {pid["loads"]} as {clean_label(comp_map["loads"])}')
        lines.append("    end")
        lines.append("")

        lines.append("   autonumber")
        lines.append("")

        # ── Section 1: Incoming Power Entry ──────────────────────────────────────
        if "supply" in comp_map:
            note_right_order = ["loads", "ebar", "nbar"] + list(reversed(outcb_ids)) + ["bus", "rcd", "maincb"]
            # note_right = next((pid[c] for c in note_right_order if c in comp_map), pid["supply"])
            # lines.append(f'    Note over {pid["supply"]},{note_right}: {L["note_power_entry"][language]}')
            all_pids_in_order = [pid[c] for c in note_right_order if c in comp_map]
            # lines.append(f'    Note over {all_pids_in_order[0]},{all_pids_in_order[-1]}: ...')
            if len(all_pids_in_order) >= 2:
                lines.append(f'    Note over {all_pids_in_order[0]},{all_pids_in_order[-1]}: {L["note_power_entry"][language]}')
            else:
                lines.append(f'    Note over {pid["supply"]}: {L["note_power_entry"][language]}')

            # Phase wire: supply → maincb (or directly to rcd if no maincb — shouldn't happen)
            if "maincb" in comp_map:
                # lines.append(f'    {pid["supply"]}->>{pid["maincb"]}: {L["wire_phase"][language]}')
                phase_label = L["wire_phase"][language]
                if is_three_phase:
                    phase_label = f"3-Phase Supply (L1/L2/L3) — {voltage_str}" if language == "en" else f"三相電源 (L1/L2/L3) — {voltage_str}"
                lines.append(f'    {pid["supply"]}->>{pid["maincb"]}: {phase_label}')
            # Neutral: supply → nbar (direct, parallel path)
            if cfg["show_neutral"] and "nbar" in comp_map:
                lines.append(f'    {pid["supply"]}->>{pid["nbar"]}: {L["wire_neutral"][language]}')
            # Earth: supply → ebar (direct, safety path)
            if cfg["show_earth"] and "ebar" in comp_map:
                lines.append(f'    {pid["supply"]}-->>{pid["ebar"]}: {L["wire_earth"][language]}')
            lines.append("")

            

        # ── Section 2: Internal Distribution ─────────────────────────────────────
        if "maincb" in comp_map:
            # dist_right_order = (outcb_ids or []) + ["ebar", "nbar", "bus", "rcd"]
            # In Section 2, replace the Note over maincb,dist_right line with:
            dist_pids = [pid[c] for c in ["maincb", "rcd", "bus", "nbar", "ebar"] + outcb_ids if c in comp_map]
            if len(dist_pids) >= 2:
                lines.append(f'    Note over {dist_pids[0]},{dist_pids[-1]}: {L["note_internal"][language]}')
            elif dist_pids:
                lines.append(f'    Note over {dist_pids[0]}: {L["note_internal"][language]}')           
           # Lines 648-649 — protection notes block
            if cfg["show_protection_notes"]:
                lines.append(f'    Note right of {pid["maincb"]}: {"Overcurrent / Short Circuit Protection" if language == "en" else "過電流/短絡保護"}')
                if cfg["show_rcd"] and "rcd" in comp_map:
                    lines.append(f'    Note right of {pid["rcd"]}: {"Earth Fault / Residual Current Protection" if language == "en" else "地絡/残留電流保護"}')

            # maincb → rcd (if RCD present)
            if cfg["show_rcd"] and "rcd" in comp_map:
                lines.append(f'    {pid["maincb"]}->>{pid["rcd"]}: {L["action_rcd_monitor"][language]}')
                
                # rcd → bus (or directly to outcb if no bus)
                if "bus" in comp_map:
                    lines.append(f'    {pid["rcd"]}->>{pid["bus"]}: {L["action_rcd_pass"][language]}')
                elif outcb_ids:
                    for oid in outcb_ids:
                        lines.append(f'    {pid["rcd"]}->>{pid[oid]}: {L["action_distribute"][language]}')
            else:
                # No RCD — maincb → bus or outcb directly
                if "bus" in comp_map:
                    lines.append(f'    {pid["maincb"]}->>{pid["bus"]}: {L["action_energize"][language]}')
                elif outcb_ids:
                    for oid in outcb_ids:
                        lines.append(f'    {pid["maincb"]}->>{pid[oid]}: {L["action_distribute"][language]}')

            # bus → outcb_N
            if "bus" in comp_map and outcb_ids:
                for oid in outcb_ids:
                    lines.append(f'    {pid["bus"]}->>{pid[oid]}: {L["action_distribute"][language]}')

            lines.append("")

        # ── Section 3: Outgoing Circuits ──────────────────────────────────────────
        if "loads" in comp_map:
            load_src_order = outcb_ids + ["bus", "rcd", "maincb"]
            load_src_cid = next((c for c in load_src_order if c in comp_map), None)

            if load_src_cid is None:
                lines.append(f'    Note over {pid["loads"]}: ⚠ WARNING: No upstream protection found')
            else:
                if load_src_cid != "loads":
                    lines.append(f'    Note over {pid[load_src_cid]},{pid["loads"]}: {L["note_outgoing"][language]}')
                else:
                    lines.append(f'    Note over {pid["loads"]}: {L["note_outgoing"][language]}')

                # ── NEW: outcb → Loads feed arrows ───────────────────────────────
                if outcb_ids:
                    feed_label = "Protected Feed (L)" if language == "en" else "保護給電 (L)"
                    for oid in outcb_ids:
                        lines.append(f'    {pid[oid]}->>{pid["loads"]}: {feed_label}')
                elif load_src_cid and load_src_cid != "loads":
                    # No outcbs — draw direct feed from whatever upstream exists
                    lines.append(f'    {pid[load_src_cid]}->>{pid["loads"]}: {L["action_feed"][language]}')

                # Neutral return and earth (unchanged)
                if cfg["show_neutral"] and "nbar" in comp_map:
                    lines.append(f'    {pid["loads"]}->>{pid["nbar"]}: {L["action_return"][language]}')
                if cfg["show_earth"] and "ebar" in comp_map:
                    lines.append(f'    {pid["ebar"]}-->>{pid["loads"]}: {L["action_safety"][language]}')

            lines.append("")


        # ── Section 4: Fault Protection Paths ─────────────────────────────────
        if cfg["show_fault_paths"] and "ebar" in comp_map and "loads" in comp_map:
            L = self.diagram_labels
            language = parsed_data.get("language", "en")

            lines.append("")
            # Note over must span left-to-right in participant order: EBar is left of Loads
            lines.append(f'    Note over {pid["ebar"]},{pid["loads"]}: {L["note_fault"][language]}')

            # Step 1: Fault current flows from load (motor casing) through CPC to Earth Bar
            lines.append(f'    {pid["loads"]}-->>{pid["ebar"]}: {L["action_fault"][language]}')

            # Step 2: Fault return path travels from Earth Bar back to supply source
            # (via main earth terminal / transformer star-point bond)
            if "supply" in comp_map:
                lines.append(f'    {pid["ebar"]}-->>{pid["supply"]}: {L["action_fault_return"][language]}')

            # Step 3: RCD monitors live vs neutral — shown as a note, not an arrow
            # because RCD is a sensing device; fault current does NOT flow through it
            if cfg["show_rcd"] and "rcd" in comp_map:
                lines.append(f'    Note over {pid["rcd"]}: {"Monitors L vs N current | Trips on imbalance ≥ 30mA" if language == "en" else "L線とN線の電流を監視 | 30mA以上の不平衡でトリップ"}')

                # Step 4: RCD opens contacts to isolate the faulted circuit (not the whole panel)
                # Target is the load/motor circuit, not MainCB
                lines.append(f'    {pid["rcd"]}-->>{pid["loads"]}: {L["action_rcd_isolate"][language]}')
        return "\n".join(lines)

    def generate_display_html(self, mermaid_code, parsed_data, title=None, enable_editing=True):
        language = parsed_data.get("language", "en")
        voltage = parsed_data.get("voltage", "230V / 415V")
        complexity = parsed_data.get("complexity", "Standard")

        if title is None:
            title = "電力配電盤図" if language == "ja" else "Power Distribution Panel Diagram"

        complexity_badge_colors = {"Neutral":  "#f59e0b", "Simple": "#10b981", "Standard": "#3b82f6", "Detailed": "#8b5cf6"}
        complexity_color = complexity_badge_colors.get(complexity, "#f59e0b")

        key_texts = {
            "en": {
                "logic_title": "Key Logic:",
                "logic_items": ["Line (L) passes through Breakers", "Neutral (N) goes direct to Neutral Bar", "Earth (E) goes direct to Earth Bar"],
                "safety_title": "Safety:",
                "safety_items": ["Main Breaker isolates entire panel", "RCD monitors L/N current imbalance — trips faulted circuit at ≥30mA", "Outgoing MCBs protect individual circuits", "Earth (CPC) carries fault current to source — RCD senses the imbalance",],
                "components_title": "Components:",
                "components_items": ["<strong>MCCB:</strong> Molded Case Circuit Breaker", "<strong>MCB:</strong> Miniature Circuit Breaker", "<strong>RCD/RCBO:</strong> Residual Current Device", "<strong>Busbar:</strong> Copper strip for distribution"],
                "generated": "Generated from prompt description",
                "tip": "Tip: Drag any box to move it. Double-click any text to edit it. Edit code below to update diagram.",
                "code_label": "Mermaid Code (edit to update diagram →)",
                "complexity_label": f"Mode: {complexity}",
            },
            "ja": {
                "logic_title": "主要ロジック:",
                "logic_items": ["相線(L)は遮断器を通過", "中性線(N)は中性線バーへ直接接続", "接地線(E)は接地バーへ直接接続"],
                "safety_title": "安全機能:",
                "safety_items": ["主遮断器は全盤を絶縁",  "RCDはL/N電流の不平衡を監視し30mA以上で該当回路を遮断", "出力MCBは個々の回路を保護", "CPC(接地線)が故障電流を電源に帰還させRCDが不平衡を検知",],
                "components_items": ["<strong>MCCB:</strong> モールドケース遮断器", "<strong>MCB:</strong> 配線用遮断器", "<strong>Busbar:</strong> 銅製配電用導体"],
                "generated": "プロンプトから生成",
                "tip": "ヒント: ボックスをドラッグして移動。ダブルクリックでテキストを編集。コードを編集して図を更新。",
                "code_label": "Mermaidコード (編集で図を更新 →)",
                "complexity_label": f"モード: {complexity}",
            }
        }
        key = key_texts.get(language, key_texts["en"])

        # escaped_mermaid = mermaid_code.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

        import html as _html
        html_safe_mermaid = _html.escape(mermaid_code)

        editor_js = """
<script>
class EnhancedMermaidEditor {
    constructor() {
        this.dragState   = null;
        this.lineDrag    = null;
        this.editState   = null;
        this.svgEl       = null;
        this.resizeState = null;   
        this._waitForSVG();
    }

    _waitForSVG() {
        const iv = setInterval(() => {
            const svg = document.querySelector('.mermaid svg');
            if (svg) {
                clearInterval(iv);
                setTimeout(() => this._init(svg), 300);
            }
        }, 100);
    }

    _init(svg) {
        this.svgEl = svg;
        this._fixAllText(svg);
        this._groupActorBoxes(svg);
        this._attachSVGListeners(svg);
    }

    _fixAllText(svg) {
        svg.querySelectorAll('text, tspan').forEach(el => {
            const f = el.getAttribute('fill');
            if (!f || f === 'currentColor' || f === 'inherit' ||
                f === '#ffffff' || f === '#fff' || f === 'white') {
                el.setAttribute('fill', '#1a202c');
            }
        });
    }


    _onNoteResizeStart(e, g, rect, side) {
        const pt = this._screenToSVG(e.clientX, e.clientY);
        this.resizeState = {
            g,
            rect,
            side,                                           // 'left' or 'right'
            startX:    pt.x,
            origX:     parseFloat(rect.getAttribute('x')),
            origWidth: parseFloat(rect.getAttribute('width')),
        };
        rect.style.outline = '2px dashed #f59e0b';         // visual feedback
    }

    _groupActorBoxes(svg) {
        const seen = new Set();
        // After the existing note-grouping loop, add:
        svg.querySelectorAll('rect.actor, rect[class*="actor"]').forEach((rect, idx) => {
            if (seen.has(rect)) return;
            seen.add(rect);

            const rBBox = rect.getBoundingClientRect();
            if (rBBox.width < 4 || rBBox.height < 4) return;

            // Find text labels that overlap this actor rect
            const matchedTexts = Array.from(svg.querySelectorAll('text')).filter(t => {
                if (seen.has(t)) return false;
                const tBBox = t.getBoundingClientRect();
                const tCx = tBBox.left + tBBox.width / 2;
                const tCy = tBBox.top + tBBox.height / 2;
                const tol = 8;
                return (tCx >= rBBox.left - tol && tCx <= rBBox.right + tol &&
                        tCy >= rBBox.top - tol && tCy <= rBBox.bottom + tol);
            });
            matchedTexts.forEach(t => seen.add(t));

            // Also grab the actor LINE (vertical lifeline) associated with this box
            // Mermaid draws lifelines as <line class="actor-line"> sharing the same x center
            const rectCenterX = rBBox.left + rBBox.width / 2;
            const matchedLines = Array.from(svg.querySelectorAll('line.actor-line, line[class*="actor"]')).filter(line => {
                const svgPt = svg.createSVGPoint();
                const lx1 = parseFloat(line.getAttribute('x1'));
                const svgRect = svg.getBoundingClientRect();
                const scaleX = svgRect.width / parseFloat(svg.getAttribute('viewBox')?.split(' ')[2] || svgRect.width);
                const lineScreenX = svgRect.left + lx1 * scaleX;
                return Math.abs(lineScreenX - rectCenterX) < 10;
            });

            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('data-actor-group', `actor-${idx}`);
            g.setAttribute('data-draggable', `actor-${idx}`);
            g.setAttribute('data-tx', '0');
            g.setAttribute('data-ty', '0');
            g.setAttribute('data-actor-lines', JSON.stringify(
                matchedLines.map((_, i) => `actor-line-ref-${idx}-${i}`)
            ));
            g.style.cursor = 'grab';

            rect.parentNode.insertBefore(g, rect);
            g.appendChild(rect);
            matchedTexts.forEach(t => g.appendChild(t));
            // Store line refs but keep lines in DOM (don't move them with box)
            g._actorLines = matchedLines;

            g.addEventListener('mousedown', e => this._onBoxMouseDown(e, g));
            // ... hover effects same as note boxes


                        // After building the note group `g`:
            const toggle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            toggle.textContent = '▲';
            toggle.setAttribute('font-size', '10');
            toggle.setAttribute('fill', '#92400e');
            toggle.setAttribute('cursor', 'pointer');
            toggle.setAttribute('data-collapsed', 'false');

            // Position at top-right corner of the note rect
            const rX = parseFloat(rect.getAttribute('x') || 0);
            const rY = parseFloat(rect.getAttribute('y') || 0);
            const rW = parseFloat(rect.getAttribute('width') || 60);
            toggle.setAttribute('x', rX + rW - 14);
            toggle.setAttribute('y', rY + 12);

            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const collapsed = toggle.getAttribute('data-collapsed') === 'true';
                const noteTexts = g.querySelectorAll('text:not([data-toggle])');
                const noteRect  = g.querySelector('rect');
                
                if (!collapsed) {
                    // Minimize: shrink rect height, hide text
                    noteRect._fullHeight = noteRect.getAttribute('height');
                    noteRect.setAttribute('height', '16');
                    noteTexts.forEach(t => { t._prevVis = t.style.display; t.style.display = 'none'; });
                    toggle.textContent = '▼';
                    toggle.setAttribute('data-collapsed', 'true');
                } else {
                    // Restore
                    if (noteRect._fullHeight) noteRect.setAttribute('height', noteRect._fullHeight);
                    noteTexts.forEach(t => { t.style.display = t._prevVis || ''; });
                    toggle.textContent = '▲';
                    toggle.setAttribute('data-collapsed', 'false');
                }
            });

            toggle.setAttribute('data-toggle', 'true');
            g.appendChild(toggle);
            // After g.appendChild(rect) and texts, add resize handles:
            const MIN_NOTE_WIDTH = 60; // minimum enforced width in SVG units

            ['left', 'right'].forEach(side => {
                const handle = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                const rX = parseFloat(rect.getAttribute('x') || 0);
                const rY = parseFloat(rect.getAttribute('y') || 0);
                const rH = parseFloat(rect.getAttribute('height') || 30);
                const rW = parseFloat(rect.getAttribute('width') || 100);

                handle.setAttribute('x', side === 'left' ? rX - 4 : rX + rW - 4);
                handle.setAttribute('y', rY);
                handle.setAttribute('width', '8');
                handle.setAttribute('height', rH);
                handle.setAttribute('fill', 'transparent');
                handle.setAttribute('cursor', 'ew-resize');
                handle.setAttribute('data-resize-handle', side);
                handle.style.cursor = 'ew-resize';

                handle.addEventListener('mousedown', e => {
                    e.stopPropagation(); // prevent box drag from firing
                    this._onNoteResizeStart(e, g, rect, side);
                });

                g.appendChild(handle);
                // Store handle refs on the group for later repositioning
                if (!g._resizeHandles) g._resizeHandles = {};
                g._resizeHandles[side] = handle;
            });
        });
    }

    _attachSVGListeners(svg) {
        svg.addEventListener('mousemove', e => this._onMouseMove(e));
        svg.addEventListener('mouseup', e => this._onMouseUp(e));
        svg.addEventListener('mouseleave', e => this._onMouseUp(e));
        svg.addEventListener('touchmove', e => this._onTouchMove(e), {passive: false});
        svg.addEventListener('touchend', e => this._onTouchEnd(e), {passive: false});
        svg.addEventListener('mousedown', e => this._onMouseDown(e));
        svg.addEventListener('dblclick', e => this._onDblClick(e));
        window.addEventListener('mousemove', e => this._onMouseMove(e));
        window.addEventListener('mouseup', e => this._onMouseUp(e));
    }

    _screenToSVG(x, y) {
        const pt = this.svgEl.createSVGPoint();
        pt.x = x; pt.y = y;
        return pt.matrixTransform(this.svgEl.getScreenCTM().inverse());
    }

    _onBoxMouseDown(e, g) {
        if (e.target.getAttribute('data-resize-handle')) return;
        e.stopPropagation()
        e.stopPropagation();
        const pt = this._screenToSVG(e.clientX, e.clientY);
        this.dragState = {g, startX: pt.x, startY: pt.y,
            tx: parseFloat(g.getAttribute('data-tx')),
            ty: parseFloat(g.getAttribute('data-ty'))};
        g.style.cursor = 'grabbing';
        g.style.opacity = '0.85';
    }

    _onBoxTouchStart(e, g) {
        e.preventDefault();
        const t = e.touches[0];
        const pt = this._screenToSVG(t.clientX, t.clientY);
        this.dragState = {g, startX: pt.x, startY: pt.y,
            tx: parseFloat(g.getAttribute('data-tx')),
            ty: parseFloat(g.getAttribute('data-ty'))};
    }

    _onMouseDown(e) {
        if (!this._isLineEl(e.target)) return;
        const pt = this._screenToSVG(e.clientX, e.clientY);
        const el = e.target;
        let mode = 'move';
        if (el.tagName.toLowerCase() === 'line') {
            const hit = this._getLineEndpointHit(el, pt);
            if (hit) mode = hit;
        }
        // this.pendingLineDrag = {el, sx: pt.x, sy: pt.y, mode};
    }

    _onMouseMove(e) {
        if (this.resizeState) {
            const pt = this._screenToSVG(e.clientX, e.clientY);
            const dx = pt.x - this.resizeState.startX;
            const { rect, side, origX, origWidth, g } = this.resizeState;
            const MIN_NOTE_WIDTH = 60;

            let newX     = origX;
            let newWidth = origWidth;

            if (side === 'right') {
                // Drag right edge: only width changes, x stays
                newWidth = Math.max(MIN_NOTE_WIDTH, origWidth + dx);
            } else {
                // Drag left edge: x moves right, width shrinks (or x moves left, width grows)
                const proposed = origWidth - dx;
                if (proposed >= MIN_NOTE_WIDTH) {
                    newX     = origX + dx;
                    newWidth = proposed;
                } else {
                    // Clamp to minimum: pin right edge
                    newX     = origX + origWidth - MIN_NOTE_WIDTH;
                    newWidth = MIN_NOTE_WIDTH;
                }
            }

            // Check overlap with sibling note groups before applying
            const wouldOverlap = this._checkNoteOverlap(g, newX, newWidth);
            if (!wouldOverlap) {
                rect.setAttribute('x', newX);
                rect.setAttribute('width', newWidth);
                this._repositionNoteContents(g, rect, newX, newWidth);
                this._repositionHandles(g, rect, newX, newWidth);
            }
            return;
        }

        if (this.dragState) {
            const pt = this._screenToSVG(e.clientX, e.clientY);
            const dx = pt.x - this.dragState.startX;
            let dy = pt.y - this.dragState.startY;

            // Actor boxes: horizontal reposition only (lock Y)
            const isActor = this.dragState.g.getAttribute('data-actor-group')?.startsWith('actor-');
            if (isActor) dy = 0;

            const newTx = this.dragState.tx + dx;
            const newTy = this.dragState.ty + (isActor ? 0 : dy);         
            this.dragState.g.setAttribute('transform', `translate(${newTx},${newTy})`);
            this.dragState.g.setAttribute('data-tx', newTx);
            this.dragState.g.setAttribute('data-ty', newTy);
            return;
        }
        if (this.lineDrag) {
            this._updateLineDrag(e.clientX, e.clientY);
            return;
        }
        if (!this.pendingLineDrag) return;
        const cur = this._screenToSVG(e.clientX, e.clientY);
        const dx = cur.x - this.pendingLineDrag.sx;
        const dy = cur.y - this.pendingLineDrag.sy;
        if (Math.hypot(dx, dy) < 3) return;
        this.lineDrag = {el: this.pendingLineDrag.el, pvx: this.pendingLineDrag.sx, pvy: this.pendingLineDrag.sy, mode: this.pendingLineDrag.mode};
        this.pendingLineDrag = null;
    }

    _onTouchMove(e) {
        e.preventDefault();
        const t = e.touches[0];
        if (this.dragState) {
            const fakeEv = {clientX: t.clientX, clientY: t.clientY};
            this._onMouseMove(fakeEv);
        } else if (this.lineDrag) {
            this._updateLineDrag(t.clientX, t.clientY);
        }
    }

    _repositionNoteContents(g, rect, newX, newWidth) {
        const centerX = newX + newWidth / 2;
        g.querySelectorAll('text').forEach(t => {
            // Only reposition text that isn't a resize handle label
            if (t.getAttribute('data-resize-handle')) return;
            t.setAttribute('x', centerX);
            t.querySelectorAll('tspan').forEach(ts => ts.setAttribute('x', centerX));
        });
    }

    _repositionHandles(g, rect, newX, newWidth) {
        if (!g._resizeHandles) return;
        const rY = parseFloat(rect.getAttribute('y') || 0);
        const rH = parseFloat(rect.getAttribute('height') || 30);

        const lh = g._resizeHandles['left'];
        const rh = g._resizeHandles['right'];

        if (lh) { lh.setAttribute('x', newX - 4);              lh.setAttribute('y', rY); lh.setAttribute('height', rH); }
        if (rh) { rh.setAttribute('x', newX + newWidth - 4);   rh.setAttribute('y', rY); rh.setAttribute('height', rH); }
    }

    _checkNoteOverlap(currentGroup, proposedX, proposedWidth) {
        const proposedRight = proposedX + proposedWidth;
        const allNoteGroups = Array.from(
            this.svgEl.querySelectorAll('[data-actor-group^="note-"]')
        );

        return allNoteGroups.some(g => {
            if (g === currentGroup) return false;
            const r = g.querySelector('rect');
            if (!r) return false;
            const otherX     = parseFloat(r.getAttribute('x'));
            const otherWidth = parseFloat(r.getAttribute('width'));
            const otherRight = otherX + otherWidth;
            const GAP = 4; // minimum gap between boxes in SVG units
            // Overlap if proposed range intersects other range
            return proposedX < otherRight + GAP && proposedRight > otherX - GAP;
        });
    }    

    


    _onMouseUp(e) {
        if (this.dragState) {
            const g = this.dragState.g;
            g.style.cursor = 'grab';
            g.style.opacity = '1';

            // If this was an actor box, reattach vertical lifeline
            if (g._actorLines && g._actorLines.length > 0) {
                const rect = g.querySelector('rect');
                if (rect) {
                    const rBBox = rect.getBoundingClientRect();
                    const svgRect = this.svgEl.getBoundingClientRect();
                    const viewBox = this.svgEl.viewBox.baseVal;
                    const scaleX = viewBox.width / svgRect.width;
                    const newCenterX = (rBBox.left + rBBox.width / 2 - svgRect.left) * scaleX;

                    g._actorLines.forEach(line => {
                        line.setAttribute('x1', newCenterX);
                        line.setAttribute('x2', newCenterX);
                    });
                }
            }

            // Store position for external use
            const tx = parseFloat(g.getAttribute('data-tx'));
            const ty = parseFloat(g.getAttribute('data-ty'));
            g.setAttribute('data-final-x', tx);
            g.setAttribute('data-final-y', ty);

            this.dragState = null;
        }
        if (this.dragState) {
            this.dragState.g.style.cursor = 'grab';
            this.dragState.g.style.opacity = '1';
            this.dragState = null;
        }
    /*    if (this.lineDrag) this._finishLineDrag();
        this.pendingLineDrag = null; */

        if (window.qtBridge && window.qtBridge.onElementEdited) {
            window.qtBridge.onElementEdited(
                g.getAttribute('data-actor-group'),  // element_id
                'actor',                              // element_type
                '',                                   // new_text (empty = position update)
                parseFloat(g.getAttribute('data-tx')),
                parseFloat(g.getAttribute('data-ty'))
            );
        }
        if (this.resizeState) {
            this.resizeState.rect.style.outline = '';   // remove visual feedback
            // Snap to nearest 10px grid (optional but clean)
            const rect  = this.resizeState.rect;
            const snapW = Math.round(parseFloat(rect.getAttribute('width'))  / 10) * 10;
            const snapX = Math.round(parseFloat(rect.getAttribute('x'))      / 10) * 10;
            rect.setAttribute('width', snapW);
            rect.setAttribute('x',     snapX);
            this._repositionNoteContents(this.resizeState.g, rect, snapX, snapW);
            this._repositionHandles(this.resizeState.g, rect, snapX, snapW);
            this.resizeState = null;
        }
    }

    _onTouchEnd(e) {
        if (this.dragState) {
            this.dragState.g.style.opacity = '1';
            this.dragState = null;
        }
        if (this.lineDrag) this._finishLineDrag();
    }

    _getLineEndpointHit(el, pt, tol = 6) {
        const x1 = parseFloat(el.getAttribute('x1'));
        const y1 = parseFloat(el.getAttribute('y1'));
        const x2 = parseFloat(el.getAttribute('x2'));
        const y2 = parseFloat(el.getAttribute('y2'));
        if (Math.hypot(pt.x - x1, pt.y - y1) <= tol) return 'start';
        if (Math.hypot(pt.x - x2, pt.y - y2) <= tol) return 'end';
        return null;
    }

    _isLineEl(el) {
        if (!el) return false;
        const tag = el.tagName.toLowerCase();
        const cls = el.getAttribute('class') || '';
        if (!['line', 'path', 'polyline'].includes(tag)) return false;
        if (!el.getAttribute('stroke')) return false;
        if (cls.includes('actor') || cls.includes('note') || cls.includes('label')) return false;
        if (tag === 'line') {
            const x1 = parseFloat(el.getAttribute('x1') || 0);
            const x2 = parseFloat(el.getAttribute('x2') || 0);
            if (Math.abs(x1 - x2) < 3) return false;
        }
        return true;
    }

    _updateLineDrag(cx, cy) {
        const cur = this._screenToSVG(cx, cy);
        const dx = cur.x - this.lineDrag.pvx;
        const dy = cur.y - this.lineDrag.pvy;
        this.lineDrag.pvx = cur.x;
        this.lineDrag.pvy = cur.y;
        if (this.lineDrag.mode === 'move') this._shiftLineEl(this.lineDrag.el, dx, dy);
        else this._extendLineEl(this.lineDrag.el, dx, dy, this.lineDrag.mode);
    }

    _finishLineDrag() {
        if (!this.lineDrag) return;
        const el = this.lineDrag.el;
        el.style.stroke = '';
        el.style.strokeWidth = '';
        el.style.strokeDasharray = '';
        this.lineDrag = null;
    }

    _extendLineEl(el, dx, dy, which) {
        if (el.tagName.toLowerCase() !== 'line') return;
        if (which === 'start') {
            el.setAttribute('x1', parseFloat(el.getAttribute('x1')) + dx);
            el.setAttribute('y1', parseFloat(el.getAttribute('y1')) + dy);
        }
        if (which === 'end') {
            el.setAttribute('x2', parseFloat(el.getAttribute('x2')) + dx);
            el.setAttribute('y2', parseFloat(el.getAttribute('y2')) + dy);
        }
    }

    _shiftLineEl(el, dx, dy) {
        const tag = el.tagName;
        if (tag === 'line') {
            ['x1','x2'].forEach(a => el.setAttribute(a, parseFloat(el.getAttribute(a)) + dx));
            ['y1','y2'].forEach(a => el.setAttribute(a, parseFloat(el.getAttribute(a)) + dy));
        } else if (tag === 'polyline') {
            const pts = el.getAttribute('points').trim().split(/\s+/).map(p => {
                const [x, y] = p.split(',').map(parseFloat);
                return `${x + dx},${y + dy}`;
            });
            el.setAttribute('points', pts.join(' '));
        } else if (tag === 'path') {
            const d = el.getAttribute('d').replace(
                /([ML])\s*([\d.+-]+)[,\s]+([\d.+-]+)/gi,
                (_, cmd, x, y) => `${cmd}${parseFloat(x)+dx},${parseFloat(y)+dy}`
            );
            el.setAttribute('d', d);
        }
    }

    _onDblClick(e) {
        if (this.lineDrag) return;
        let textEl = null;
        if (e.target.tagName === 'text')  textEl = e.target;
        if (e.target.tagName === 'tspan') textEl = e.target.parentElement;
        if (!textEl) return;
        const current = this._getTextContent(textEl);
        if (!current.trim()) return;
        this._openTextEditor(textEl, current);
    }

    _getTextContent(el) {
        const spans = el.querySelectorAll('tspan');
        if (spans.length) return Array.from(spans).map(s => s.textContent).join('\\n');
        return el.textContent || '';
    }

    _openTextEditor(textEl, current) {
        const rect = textEl.getBoundingClientRect();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = current;
        Object.assign(input.style, {
            position: 'fixed',
            left: rect.left + 'px',
            top: rect.top + 'px',
            width: Math.max(rect.width + 24, 160) + 'px',
            height: rect.height + 10 + 'px',
            zIndex: '10000',
            padding: '3px 8px',
            border: '2px solid #4299e1',
            borderRadius: '4px',
            fontSize: window.getComputedStyle(textEl).fontSize,
            fontFamily: window.getComputedStyle(textEl).fontFamily,
            fontWeight: window.getComputedStyle(textEl).fontWeight,
            color: '#000',
            backgroundColor: '#fff',
            boxShadow: '0 4px 12px rgba(0,0,0,0.18)',
            outline: 'none',
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

        input.addEventListener('keydown', e => {
            if (e.key === 'Enter')  { e.preventDefault(); done(true); }
            if (e.key === 'Escape') { e.preventDefault(); done(false); }
        });
        input.addEventListener('blur', () => done(true));
    }

    _applyTextEdit(textEl, newVal) {
        const spans = textEl.querySelectorAll('tspan');
        const lines = newVal.split('\\n');
        if (spans.length) {
            spans.forEach((s, i) => { if (i < lines.length) s.textContent = lines[i]; });
        } else {
            textEl.textContent = newVal;
        }
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
                return spans.length
                    ? Array.from(spans).map(s => s.textContent).join('<br/>')
                    : t.textContent;
            }).join('<br/>').trim();

            if (!newLabel) return;

            code = code.replace(
                /(participant\s+\w+\s+as\s+).+/,
                (match, prefix) => prefix + newLabel
            );
        });

        codeArea.value = code;
        if (window.qtBridge && window.qtBridge.onDiagramTextChanged) {
            window.qtBridge.onDiagramTextChanged(code);
        }
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
                setTimeout(() => {
                    window.mermaidEditor = new EnhancedMermaidEditor();
                }, 400);
            });
        } catch(e) {
            console.error('Mermaid render error:', e);
            container.innerHTML = '<p style="color:red;padding:12px;">⚠ Mermaid syntax error. Check the code and try again.</p>';
        }
    }

    if (window.qtBridge && window.qtBridge.onDiagramTextChanged) {
        window.qtBridge.onDiagramTextChanged(code);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { window.mermaidEditor = new EnhancedMermaidEditor(); }, 400);

    const applyBtn = document.getElementById('apply-code-btn');
    if (applyBtn) applyBtn.addEventListener('click', applyCodeToDiagram);

    const codeArea = document.getElementById('mermaid-code-editor');
    if (codeArea) {
        codeArea.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                applyCodeToDiagram();
            }
        });
    }
});
</script>
<style>
.mermaid svg text,
.mermaid svg tspan { fill: #1a202c !important; }
[data-actor-group], [data-draggable] { cursor: grab; }
[data-actor-group]:active, [data-draggable]:active { cursor: grabbing; }
[data-actor-group]:hover rect,
[data-draggable]:hover rect {
    filter: drop-shadow(0 0 5px rgba(66,153,225,0.6));
}
[data-actor-group], [data-draggable] { transition: opacity 0.1s ease; }
.mermaid svg line:hover,
.mermaid svg path:hover,
.mermaid svg polyline:hover {
    stroke-width: 3px !important;
    cursor: move !important;
}
#mermaid-code-editor {
    width: 100%;
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
    color: #1a202c;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s;
}
#mermaid-code-editor:focus {
    border-color: #4299e1;
    box-shadow: 0 0 0 3px rgba(66,153,225,0.15);
}
#apply-code-btn {
    background: #2c5282;
    color: #fff;
    border: none;
    border-radius: 5px;
    padding: 7px 18px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 6px;
    transition: background 0.15s;
}
#apply-code-btn:hover { background: #2a4365; }
.code-panel-label {
    font-size: 11px;
    font-weight: 600;
    color: #718096;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 4px;
    margin-top: 14px;
}
.apply-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 6px;
}
.apply-hint {
    font-size: 11px;
    color: #a0aec0;
}
</style>
"""

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
window.mermaid = mermaid;
mermaid.initialize({{
    startOnLoad: true,
    theme: 'base',
    themeVariables: {{
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
    }}
}});
</script>
{"" if not enable_editing else editor_js}
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f4f8;
    padding: 20px;
    min-height: 100vh;
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
    background: #fff;
    border-radius: 14px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
    padding: 28px 32px 24px;
    position: relative;
}}
.badge-row {{
    position: absolute;
    top: 16px; right: 20px;
    display: flex; gap: 6px; align-items: center;
}}
.lang-badge {{
    background: {'#3b82f6' if language == 'en' else '#ef4444'};
    color: #fff;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
.complexity-badge {{
    background: {complexity_color};
    color: #fff;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
.header {{ text-align: center; margin-bottom: 20px; }}
.header h1 {{ font-size: 26px; font-weight: 700; color: #1a202c; margin-bottom: 6px; }}
.header p  {{ color: #718096; font-size: 13px; }}
.voltage-pill {{
    display: inline-block;
    background: #edf2f7; padding: 3px 12px;
    border-radius: 20px; font-size: 12px; color: #4a5568;
    margin-left: 8px;
}}
.tip-bar {{
    background: #fefce8; border: 1px solid #fde68a;
    border-radius: 8px; padding: 8px 14px;
    font-size: 12px; color: #92400e;
    text-align: center; margin-bottom: 16px;
}}
.mermaid-wrap {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    overflow: auto;
    user-select: none;
    -webkit-user-select: none;
}}
.mermaid {{ min-height: 200px; }}
.key-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #e2e8f0;
}}
.key-card {{
    background: #f9fafb;
    border-radius: 8px;
    padding: 12px 14px;
}}
.key-card strong {{ display: block; margin-bottom: 6px; font-size: 13px; }}
.key-card ul {{ padding-left: 18px; margin: 0; }}
.key-card li {{ font-size: 12px; color: #4a5568; margin-bottom: 3px; }}
.blue  {{ color: #1d4ed8; }}
.green {{ color: #047857; }}
.amber {{ color: #b45309; }}
</style>
</head>
<body>
<div class="container">
    <div class="badge-row">
        <span class="complexity-badge">{key['complexity_label']}</span>
        <span class="lang-badge">{'English' if language == 'en' else '日本語'}</span>
    </div>
    <div class="header">
        <h1>{title}</h1>
        <p>{key['generated']} <span class="voltage-pill">⚡ {voltage}</span></p>
    </div>
    <div class="tip-bar">{key['tip']}</div>
    <div class="mermaid-wrap" id="diagram-root">
        <div id="mermaid-container">
            <div class="mermaid">
{html_safe_mermaid}
            </div>
        </div>
    </div>

    <div class="code-panel-label">{key['code_label']}</div>
    <textarea id="mermaid-code-editor" rows="10">{html_safe_mermaid}</textarea>
    <div class="apply-row">
        <button id="apply-code-btn">▶ Apply (Ctrl+↵)</button>
        <span class="apply-hint">Ctrl+Enter to apply • diagram edits sync here</span>
    </div>

    <div class="key-grid">
        <div class="key-card">
            <strong class="blue">{key['logic_title']}</strong>
            <ul>{''.join(f'<li>{i}</li>' for i in key['logic_items'])}</ul>
        </div>
        <div class="key-card">
            <strong class="green">{key['safety_title']}</strong>
            <ul>{''.join(f'<li>{i}</li>' for i in key['safety_items'])}</ul>
        </div>
        <div class="key-card">
            <strong class="amber">{key['components_title']}</strong>
            <ul>{''.join(f'<li>{i}</li>' for i in key['components_items'])}</ul>
        </div>
    </div>
</div>
</body>
</html>'''
        return html