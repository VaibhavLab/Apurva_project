import re


class SafetyService:
    """Conservative English pattern screening for a demo; not clinical triage."""
    PATTERNS = [
        r"\bi\s+(?:(?:really|just)\s+)?(?:want to|need to|plan to|intend to|will|might|may|am going to|am about to|am planning to|am ready to|feel like i might)\s+(?:kill myself|hurt myself|harm myself|end my life|take my (?:own )?life|commit suicide|die|self[- ]harm)\b",
        r"\bi(?:'m| am)\s+(?:going to|about to|planning to|ready to)\s+(?:kill myself|hurt myself|harm myself|end my life|take my (?:own )?life|commit suicide|die|self[- ]harm)\b",
        r"\b(?:kill myself|end my life|hurt myself|commit suicide)\s+(?:now|tonight|today)\b",
        r"\bi\s+(?:don't|do not)\s+want to\s+(?:live|be alive|exist)\b",
        r"\bi\s+(?:wish i (?:was|were) dead|cannot keep myself safe|can't keep myself safe)\b",
        r"\bi(?:'m| am)\s+(?:suicidal|thinking (?:about|of) (?:suicide|killing myself|ending my life))\b",
        r"\bi\s+(?:have |just |already )?(?:overdosed|taken an overdose|took an overdose)\b",
    ]

    def analyze(self, text: str) -> dict:
        normalized = re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()
        high = any(re.search(pattern, normalized) for pattern in self.PATTERNS)
        return {"risk_level": "high" if high else "normal"}
