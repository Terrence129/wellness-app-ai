import pytest

from app.services.safety import SafetyPolicy

EXPECTED_CRISIS_RESPONSE = (
    "If you may be in immediate danger or are thinking about harming yourself, contact your "
    "local emergency services or a qualified crisis professional now. If possible, stay with "
    "someone you trust. This service cannot provide emergency or medical care."
)


@pytest.mark.parametrize(
    "message",
    [
        "I want to kill myself",
        "I am thinking about SUICIDE",
        "I have thoughts of self-harm",
        "I cannot breathe",
        "I have chest pain",
        "I may have taken an overdose",
        "I have ＣＨＥＳＴ ＰＡＩＮ",
    ],
)
def test_returns_fixed_crisis_response_for_explicit_phrase(message: str) -> None:
    """Escalate normalized explicit crisis phrases. Author: 2692341798."""
    assert SafetyPolicy().evaluate([message]) == EXPECTED_CRISIS_RESPONSE


def test_returns_fixed_crisis_response_for_history_phrase() -> None:
    """Escalate an explicit phrase found in conversation history. Author: 2692341798."""
    assert SafetyPolicy().evaluate(
        ["I feel calmer now", "Earlier I had chest pain"]
    ) == EXPECTED_CRISIS_RESPONSE


@pytest.mark.parametrize("text", ["I am stressed", "improve sleep", "healthy diet"])
def test_allows_non_crisis_wellness_text(text: str) -> None:
    """Allow ordinary wellness text without an explicit phrase. Author: 2692341798."""
    assert SafetyPolicy().evaluate([text]) is None
