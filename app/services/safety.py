import unicodedata
from collections.abc import Sequence

CRISIS_RESPONSE = (
    "If you may be in immediate danger or are thinking about harming yourself, contact your "
    "local emergency services or a qualified crisis professional now. If possible, stay with "
    "someone you trust. This service cannot provide emergency or medical care."
)

_CRISIS_PHRASES = (
    "kill myself",
    "suicide",
    "self-harm",
    "cannot breathe",
    "chest pain",
    "overdose",
)


class SafetyPolicy:
    """Apply deterministic crisis escalation before provider use. Author: 2692341798."""

    def evaluate(self, texts: Sequence[str]) -> str | None:
        """Return the fixed escalation for an explicit crisis phrase. Author: 2692341798."""
        text = "\n".join(texts)
        normalized_text = unicodedata.normalize("NFKC", text).lower()
        if any(phrase in normalized_text for phrase in _CRISIS_PHRASES):
            return CRISIS_RESPONSE
        return None
