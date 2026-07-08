# Author: Huang Qijun
# Email: 2692341798@qq.com

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WellnessLog(BaseModel):
    """One bounded daily wellness observation. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    log_date: date = Field(alias="logDate")
    sleep_hours: float | None = Field(default=None, alias="sleepHours", ge=0, le=24)
    mood_score: int | None = Field(
        default=None,
        alias="moodScore",
        ge=1,
        le=5,
        strict=True,
    )
    water_cups: int | None = Field(default=None, alias="waterCups", ge=0, strict=True)
    steps: int | None = Field(default=None, ge=0, strict=True)
    exercise_minutes: int | None = Field(
        default=None,
        alias="exerciseMinutes",
        ge=0,
        le=1440,
        strict=True,
    )
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("log_date", mode="before")
    @classmethod
    def _require_iso_full_date(cls, value: object) -> object:
        if type(value) is date:
            return value
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                pass
            else:
                if parsed.isoformat() == value:
                    return value
        raise ValueError("logDate must be a YYYY-MM-DD full-date or date instance")

    @field_validator("note", mode="before")
    @classmethod
    def _strip_note(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AdviceRequest(BaseModel):
    """Validated request contract for wellness advice. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId", gt=0, strict=True)
    logs: list[WellnessLog] = Field(default_factory=list, max_length=31)


class AdviceResponse(BaseModel):
    """Public response contract for wellness advice. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    advice_text: str = Field(alias="adviceText", min_length=1)
    request_id: str = Field(alias="requestId")

    @field_validator("advice_text", mode="before")
    @classmethod
    def _strip_advice_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AdvicePayload(BaseModel):
    """Strict JSON payload accepted from the advice provider. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    advice_text: str = Field(alias="adviceText", min_length=1)

    @field_validator("advice_text", mode="before")
    @classmethod
    def _strip_advice_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AdviceProviderResult(BaseModel):
    """Provider-independent parsed advice result. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    advice_text: str = Field(alias="adviceText", min_length=1)
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @field_validator("advice_text", mode="before")
    @classmethod
    def _strip_advice_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
