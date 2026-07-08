# Author: Huang Qijun
# Email: 2692341798@qq.com

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.advice import (
    AdvicePayload,
    AdviceProviderResult,
    AdviceRequest,
    AdviceResponse,
    WellnessLog,
)


def _log(**overrides: object) -> dict[str, object]:
    """Build a valid wellness log for boundary tests. Author: 2692341798."""
    return {"logDate": "2026-06-24", **overrides}


def test_advice_request_accepts_empty_and_thirty_one_logs() -> None:
    """Accept the supported wellness-log range. Author: 2692341798."""
    assert AdviceRequest(userId=1, logs=[]).logs == []
    assert len(AdviceRequest(userId=1, logs=[_log()] * 31).logs) == 31


def test_advice_request_rejects_thirty_two_logs() -> None:
    """Reject oversized wellness history. Author: 2692341798."""
    with pytest.raises(ValidationError):
        AdviceRequest(userId=1, logs=[_log()] * 32)


def test_advice_request_requires_positive_user_id() -> None:
    """Reject a non-positive user identifier. Author: 2692341798."""
    with pytest.raises(ValidationError):
        AdviceRequest(userId=0, logs=[])


@pytest.mark.parametrize("user_id", [True, "1", 1.0])
def test_advice_request_rejects_non_strict_integer_user_id(user_id: object) -> None:
    """Reject coercible non-integer user identifiers. Author: 2692341798."""
    with pytest.raises(ValidationError):
        AdviceRequest(userId=user_id, logs=[])


def test_wellness_log_parses_iso_date_and_rejects_invalid_date() -> None:
    """Parse only valid ISO calendar dates. Author: 2692341798."""
    assert WellnessLog(**_log()).log_date == date(2026, 6, 24)
    assert WellnessLog(logDate=date(2026, 6, 24)).log_date == date(2026, 6, 24)
    with pytest.raises(ValidationError):
        WellnessLog(**_log(logDate="2026-02-30"))


@pytest.mark.parametrize("log_date", [0, 1_700_000_000, "2026-06-24T00:00:00"])
def test_wellness_log_rejects_non_full_date_inputs(log_date: object) -> None:
    """Reject timestamps and datetime strings as log dates. Author: 2692341798."""
    with pytest.raises(ValidationError):
        WellnessLog(logDate=log_date)


@pytest.mark.parametrize(
    ("field", "minimum", "maximum"),
    [
        ("sleepHours", 0, 24),
        ("moodScore", 1, 5),
        ("waterCups", 0, 100),
        ("steps", 0, 100),
        ("exerciseMinutes", 0, 1440),
    ],
)
def test_wellness_measurements_accept_boundaries(
    field: str, minimum: int, maximum: int
) -> None:
    """Accept numeric values at each documented boundary. Author: 2692341798."""
    assert getattr(WellnessLog(**_log(**{field: minimum})), _python_name(field)) == minimum
    assert getattr(WellnessLog(**_log(**{field: maximum})), _python_name(field)) == maximum


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("sleepHours", -0.1),
        ("sleepHours", 24.1),
        ("moodScore", 0),
        ("moodScore", 6),
        ("waterCups", -1),
        ("steps", -1),
        ("exerciseMinutes", -1),
        ("exerciseMinutes", 1441),
    ],
)
def test_wellness_measurements_reject_out_of_range_values(field: str, invalid: object) -> None:
    """Reject measurements outside documented limits. Author: 2692341798."""
    with pytest.raises(ValidationError):
        WellnessLog(**_log(**{field: invalid}))


@pytest.mark.parametrize(
    "field",
    ["moodScore", "waterCups", "steps", "exerciseMinutes"],
)
@pytest.mark.parametrize("invalid", [True, "1", 1.0])
def test_integer_wellness_measurements_reject_coercible_values(
    field: str, invalid: object
) -> None:
    """Reject booleans and coercible non-integers for count fields. Author: 2692341798."""
    with pytest.raises(ValidationError):
        WellnessLog(**_log(**{field: invalid}))


def _python_name(alias: str) -> str:
    """Map test aliases to model attribute names. Author: 2692341798."""
    names = {
        "sleepHours": "sleep_hours",
        "moodScore": "mood_score",
        "waterCups": "water_cups",
        "exerciseMinutes": "exercise_minutes",
    }
    return names.get(alias, alias)


def test_wellness_log_leaves_absent_measurements_as_none() -> None:
    """Preserve the distinction between absent and zero. Author: 2692341798."""
    log = WellnessLog(log_date=date(2026, 6, 24))

    assert log.sleep_hours is None
    assert log.mood_score is None
    assert log.water_cups is None
    assert log.steps is None
    assert log.exercise_minutes is None
    assert log.note is None


def test_wellness_note_strips_and_enforces_maximum_length() -> None:
    """Normalize optional notes and enforce their limit. Author: 2692341798."""
    assert WellnessLog(**_log(note="  felt well  ")).note == "felt well"
    assert WellnessLog(**_log(note="n" * 1000)).note == "n" * 1000
    with pytest.raises(ValidationError):
        WellnessLog(**_log(note="n" * 1001))


def test_advice_models_serialize_camel_case_aliases() -> None:
    """Serialize advice contracts with camel-case aliases. Author: 2692341798."""
    request = AdviceRequest(user_id=7, logs=[WellnessLog(log_date=date(2026, 6, 24))])
    response = AdviceResponse(advice_text="  Rest consistently.  ", request_id="request-2")

    assert request.model_dump(by_alias=True) == {
        "userId": 7,
        "logs": [
            {
                "logDate": date(2026, 6, 24),
                "sleepHours": None,
                "moodScore": None,
                "waterCups": None,
                "steps": None,
                "exerciseMinutes": None,
                "note": None,
            }
        ],
    }
    assert response.advice_text == "Rest consistently."
    assert response.model_dump(by_alias=True) == {
        "adviceText": "Rest consistently.",
        "requestId": "request-2",
    }


def test_advice_payload_strips_text_and_rejects_blank_or_extra_fields() -> None:
    """Validate the provider JSON envelope strictly. Author: 2692341798."""
    assert AdvicePayload(adviceText="  Drink water.  ").advice_text == "Drink water."
    with pytest.raises(ValidationError):
        AdvicePayload(adviceText="   ")
    with pytest.raises(ValidationError):
        AdvicePayload(adviceText="Drink water.", explanation="extra")


def test_advice_provider_result_retains_usage() -> None:
    """Represent parsed provider output and optional usage. Author: 2692341798."""
    result = AdviceProviderResult(
        advice_text="Take a walk.",
        model="deepseek-v4-flash",
        prompt_tokens=None,
        completion_tokens=8,
    )

    assert result.advice_text == "Take a walk."
    assert result.completion_tokens == 8
