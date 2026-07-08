# Author: Huang Qijun
# Email: 2692341798@qq.com

from app.providers.base import LLMProvider
from tests.fakes import FakeLLMProvider


def test_fake_provider_satisfies_runtime_protocol() -> None:
    """Verify the offline fake conforms to the provider boundary. Author: 2692341798."""
    assert isinstance(FakeLLMProvider(), LLMProvider)
