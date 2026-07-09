# Author: Huang Qijun
# Email: 2692341798@qq.com

import socket
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def block_external_network(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Generator[None, None, None]:
    """Block real sockets in default tests. Author: 2692341798."""
    if request.node.get_closest_marker("live") is not None:
        yield
        return

    def fail_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("Default tests must not open real network connections")

    monkeypatch.setattr(socket.socket, "connect", fail_connection)
    yield
