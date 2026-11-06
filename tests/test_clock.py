import asyncio

from echo.clock import FakeClock


async def test_fake_clock_wakes_sleepers_in_order():
    clock = FakeClock()
    order = []

    async def sleeper(tag, seconds):
        await clock.sleep(seconds)
        order.append(tag)

    asyncio.create_task(sleeper("b", 5))
    asyncio.create_task(sleeper("a", 2))
    await asyncio.sleep(0)

    await clock.advance(3)
    assert order == ["a"]
    assert clock.now() == 3

    await clock.advance(3)
    assert order == ["a", "b"]
    assert clock.now() == 6


async def test_fake_clock_sleep_zero_returns_immediately():
    clock = FakeClock()
    await clock.sleep(0)
    assert clock.now() == 0


async def test_fake_clock_cancelled_sleeper_is_forgotten():
    clock = FakeClock()
    task = asyncio.create_task(clock.sleep(10))
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    await clock.advance(20)  # 不应该因为被取消的 future 报错
    assert clock.now() == 20


def test_fake_clock_today_and_wall():
    clock = FakeClock(start=42, today="2026-09-05")
    assert clock.today() == "2026-09-05"
    assert clock.wall().startswith("2026-09-05")
    clock.set_today("2026-09-06")
    assert clock.today() == "2026-09-06"
