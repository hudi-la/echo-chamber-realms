from echo.floor import HUMAN, Floor


async def never_stop() -> str:
    raise AssertionError("不该被调用")


async def test_first_come_first_served():
    floor = Floor()
    assert floor.free
    assert floor.try_acquire("Kaka", never_stop)
    assert not floor.try_acquire("Charlie", never_stop)
    assert floor.holder == "Kaka"


async def test_release_only_by_holder():
    floor = Floor()
    floor.try_acquire("Kaka", never_stop)
    floor.release("Charlie")
    assert floor.holder == "Kaka"
    floor.release("Kaka")
    assert floor.free


async def test_human_seizes_and_cuts_speaker():
    floor = Floor()

    async def stop() -> str:
        return "还用问"

    floor.try_acquire("Kaka", stop)
    cut = await floor.seize_by_human()
    assert cut == ("Kaka", "还用问")
    assert floor.holder == HUMAN
    assert not floor.try_acquire("Lucy", never_stop)
    floor.release_human()
    assert floor.free


async def test_human_seizes_free_floor_without_cut():
    floor = Floor()
    assert await floor.seize_by_human() is None
    assert floor.holder == HUMAN
    assert await floor.seize_by_human() is None  # 再叫一次也不会"打断人"
