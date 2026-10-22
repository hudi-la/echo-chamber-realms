"""房间里会发生的事。全部不可变；at 是 Clock.now() 的秒数。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    at: float


@dataclass(frozen=True)
class HumanStarted(Event):
    pass


@dataclass(frozen=True)
class HumanSaid(Event):
    text: str


@dataclass(frozen=True)
class PuppetStarted(Event):
    name: str
    text: str = ""  # 它打算说的整句。只给监控台看；木偶们要等说完（PuppetSaid）才"听到"


@dataclass(frozen=True)
class PuppetSaid(Event):
    name: str
    text: str


@dataclass(frozen=True)
class PuppetCut(Event):
    name: str
    spoken: str


@dataclass(frozen=True)
class Quiet(Event):
    seconds: float


@dataclass(frozen=True)
class VisitorArrived(Event):
    pass


@dataclass(frozen=True)
class VisitorLeft(Event):
    session_id: str


@dataclass(frozen=True)
class WokeUp(Event):
    day: int
