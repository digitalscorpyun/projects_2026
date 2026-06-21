import json
import re
from watsonx_client import WatsonXClient


class CTXGrokProto:
    """
    Minimal interpretive agent for prototype synapse flow.
    Ensures watsonx output resolves to clean JSON, no markdown,
    no multiple blocks, no stray text.
    """

    def __init__(self):
        self.client = WatsonXClient()

    # ------------------------------------------------------
    # CLEANER: strip markdown, extract single JSON object
    # ------------------------------------------------------
    def _extract_json(self, text: str) -> dict:
        # 1. Remove markdown fences
        text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

        # 2. Extract JSON block (first {...} encountered)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError(f"CTX-GROK-PROTO: No JSON found in model output:\n{text}")

        json_str = match.group(0)

        # 3. Attempt strict parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 4. Attempt recovery by removing trailing commas, bad escapes, etc.
            cleaned = re.sub(r",\s*}", "}", json_str)  # trailing commas
            cleaned = re.sub(r",\s*\]", "]", cleaned)
            return json.loads(cleaned)

    # ------------------------------------------------------
    # AGENT RUN
    # ------------------------------------------------------
    def run(self, text: str, task: str = "structured_summary") -> dict:
        prompt = (
            "Summarize the following text as structured JSON ONLY. "
            "No markdown, no explanation, no multiple objects. "
            "Return exactly ONE JSON object.\n\n"
            f"TEXT:\n{text}\n"
        )

        raw = self.client.ask(prompt)
        parsed = self._extract_json(raw)

        return {
            "task": task,
            "agent": "ctx_grok_proto",
            "output": parsed,
        }

