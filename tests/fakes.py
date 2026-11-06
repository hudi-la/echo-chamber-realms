"""测试用假脑子：可编排、可延迟、不花钱。"""
from echo.brain import SILENT, Decision, Rumination, Seed
from echo.clock import Clock


class FakeBrain:
    def __init__(self, decisions: list[Decision] | None = None,
                 rumination: Rumination | None = None,
                 delay: float = 0.0, clock: Clock | None = None, compose_delay: float = 0.0,
                 seed: Seed | None = None) -> None:
        self.decisions = list(decisions or [])
        self.compose_delay = compose_delay
        self._seed = seed
        self.seeds: list[str] = []
        self.rumination = rumination
        self.delay, self.clock = delay, clock
        self.calls: list[tuple[str, str]] = []
        self.ruminations: list[str] = []

    async def decide(self, system: str, situation: str) -> Decision:
        self.calls.append((system, situation))
        if self.delay and self.clock:
            await self.clock.sleep(self.delay)
        # 延迟之后才弹出：木偶因为新事件取消重来时，台词不会被白白吃掉
        return self.decisions.pop(0) if self.decisions else SILENT

    async def compose(self, system: str, situation: str, decision: Decision) -> str:
        """兼容旧脚本格式；获选后才取一条预设台词并模拟 compose 耗时。"""
        self.calls.append((system, situation))
        if self.compose_delay and self.clock:
            await self.clock.sleep(self.compose_delay)
        scripted = self.decisions.pop(0) if self.decisions else SILENT
        return scripted.text if scripted.speak else ""

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        self.ruminations.append(material)
        return self.rumination

    async def seed(self, system: str, material: str) -> Seed | None:
        self.seeds.append(material)
        return self._seed
