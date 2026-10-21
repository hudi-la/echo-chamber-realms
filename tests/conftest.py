import pytest

from echo.clock import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
