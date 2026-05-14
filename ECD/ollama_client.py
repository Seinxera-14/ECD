# ollama_client.py
import json
import re
import requests


class OllamaClient:
    def __init__(self, model="mistral:7b-instruct", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        system_prompt = f"""You are an expert electrical diagram assistant. Convert the user's description into structured JSON for an electrical distribution diagram.

Return ONLY valid JSON. No explanation. No markdown. No preamble. No text before or after the JSON object.
Start your response with {{ and end with }}. Nothing else.

=== OUTPUT SCHEMA ===
{{
  "components": [
    ["supply", "label"],
    ["maincb", "label"],
    ["rcd", "label"],
    ["bus", "label"],
    ["nbar", "label"],
    ["ebar", "label"],
    ["outcb_1", "label"],
    ["loads", "label"]
  ],
  "flags": {{
    "show_neutral": true,
    "show_earth": true,
    "show_rcd": true,
    "show_protection_notes": false,
    "show_fault_paths": false
  }},
  "voltage": "230V AC",
  "language": "en"
}}

=== ALLOWED COMPONENT IDs ===
supply, maincb, rcd, rcbo, bus, nbar, ebar, loads
outcb_1, outcb_2, outcb_3, outcb_4, outcb_5

=== COMPONENT MEANINGS ===
supply   = incoming mains / grid source
maincb   = main circuit breaker (MCB / MCCB)
rcd      = residual current device (earth fault protection, monitors leakage)
rcbo     = combined RCD + MCB in one unit
bus      = busbar / distribution bar
nbar     = neutral bar / neutral link
ebar     = earth bar / protective earth bar
outcb_N  = outgoing branch circuit breaker (one per named circuit)
loads    = load circuits / consuming devices

=== COMPLEXITY LEVEL IN EFFECT: {complexity} ===

COMPLEXITY RULES:

"Neutral" (prompt-only mode):
  - Include ONLY what the user actually describes. Do not add anything they did not mention.
  - If the user says "supply and a breaker" output only supply + maincb + loads.
  - Do not inject busbar, RCD, neutral bar, earth bar unless the user mentions them.
  - flags must reflect ONLY what the user described.

"Simple":
  - Phase wire only. No neutral, no earth, no RCD, no fault paths.
  - Always include: supply, maincb, loads.
  - show_neutral=false, show_earth=false, show_rcd=false, show_fault_paths=false.
  - Add any extra components the user explicitly names, but never add implicit ones.

"Standard":
  - Default set: supply, maincb, rcd, bus, nbar, ebar, loads.
  - Always include the defaults PLUS anything the user explicitly names.
  - show_neutral=true, show_earth=true, show_rcd=true.
  - show_fault_paths=false unless user asks for fault paths.

"Detailed":
  - Default set: supply, maincb, rcd, bus, nbar, ebar, loads.
  - Always include defaults PLUS every component the user names.
  - For each named circuit add a separate outcb_N with a descriptive label.
  - show_neutral=true, show_earth=true, show_rcd=true, show_fault_paths=true, show_protection_notes=true.

=== EXPLICIT EXCLUSIONS — ALWAYS OVERRIDE COMPLEXITY ===
If the user says "no RCD", "no fault path", "no neutral", "no earth", "simple breaker only":
  Remove that component and set its flag to false. This overrides everything above.

=== INFERENCE RULES ===
1. Voltage: extract from prompt. Format: "230V AC" or "415V AC". Default: "unspecified".
2. Language: Japanese text (hiragana/katakana/kanji) -> "ja". Otherwise -> "en".
3. supply label must include voltage. Example: "Main Supply (230V AC)".
4. rcd label: use "RCD / RCBO" unless user names it differently.
5. outcb_N: only multiple entries if user names distinct circuits. Max 5.
6. "standard distribution panel" with no detail at Standard/Detailed complexity -> include full default set.
"""

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt.strip()}\n\nUSER PROMPT:\n{prompt}\n\nJSON:",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 0.9,
                "num_predict": 1024,
                "num_ctx": 8192,
            }
        }
        print(f'Parsing prompt using {self.model} | complexity={complexity}')
        response = requests.post(self.url, json=payload, timeout=90)
        response.raise_for_status()
        raw = response.json().get("response", "").strip()

        # Try to find JSON in raw text BEFORE stripping think tags
        # (qwen3 sometimes puts the answer inside the think block)
        text = raw

        # First pass: try full text
        json_obj = self._extract_json(text)
        if json_obj:
            return json_obj

        # Second pass: strip think blocks, try again
        text_no_think = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        json_obj = self._extract_json(text_no_think)
        if json_obj:
            return json_obj

        # Third pass: extract from inside think block only
        think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
        if think_match:
            json_obj = self._extract_json(think_match.group(1))
            if json_obj:
                return json_obj

        raise ValueError(f"No JSON found in model output:\n{raw[:500]}")

    def _extract_json(self, text: str) -> dict | None:
        """Try to extract and parse a JSON object from text. Returns dict or None."""
        text = text.strip()
        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find first { ... last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None