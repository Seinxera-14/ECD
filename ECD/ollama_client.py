# ollama_client.py
import json
import re
import requests


class OllamaClient:
    def __init__(self, model="qwen2.5:1.5b", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def prompt_to_structured_data(self, prompt: str) -> dict:
        system_prompt = """
You are an assistant that converts user descriptions of electrical diagrams
into structured JSON.

Return ONLY valid JSON.
Do NOT include explanations or markdown.
/no_think

Schema:
{
  "components": [["id","label"]],
  "layout": "horizontal|vertical",
  "voltage": "string",
  "language": "en|ja"
}

Allowed component ids:
supply, maincb, bus, nbar, ebar, outcb, loads
"""
        payload = {
            "model": self.model,
            "prompt": f"{system_prompt.strip()}\n\nUser:\n{prompt}",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 0.9,
                "num_predict": 2048,
                "num_ctx": 4096,
            }
        }
        print('parsed prompt using qwen1.5b')
        response = requests.post(self.url, json=payload, timeout=60)
        response.raise_for_status()
        text = response.json().get("response", "").strip()

        # Strip <think> blocks (qwen3 reasoning models)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                raise ValueError(f"No JSON found in model output:\n{text}")
            return json.loads(text[start:end])