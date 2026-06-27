import os
from datetime import date

import pytest

from app.core.config import Settings
from app.providers.deepseek import DeepSeekProvider
from app.schemas.advice import WellnessLog


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_chat_returns_wellness_response() -> None:
    """Smoke-test real DeepSeek chat with a benign wellness message.

    Author: 2692341798
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY is not set in the process environment")

    settings = Settings(_env_file=None, deepseek_api_key=api_key)
    provider = DeepSeekProvider(settings)

    result = await provider.generate_chat(
        message="Give one short general wellness tip.",
        history=[],
    )

    assert isinstance(result.content, str)
    assert len(result.content) > 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_advice_returns_json_wellness_response() -> None:
    """Smoke-test real DeepSeek advice with minimal wellness logs.

    Author: 2692341798
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY is not set in the process environment")

    settings = Settings(_env_file=None, deepseek_api_key=api_key)
    provider = DeepSeekProvider(settings)

    logs = [
        WellnessLog(
            log_date=date(2026, 6, 24),
            sleep_hours=7.5,
            mood_score=4,
            water_cups=6,
            steps=8000,
            exercise_minutes=30,
            note="Felt tired in the afternoon.",
        )
    ]

    result = await provider.generate_advice(logs=logs)

    assert isinstance(result.advice_text, str)
    assert len(result.advice_text) > 0
