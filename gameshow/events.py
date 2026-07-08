from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class BuzzerPressed:
    player_id: int


@dataclass(frozen=True)
class PlayerBuzzed:
    player_id: int
    player_name: str


@dataclass(frozen=True)
class StateChanged:
    new_state: str  # config state key, e.g. "locked"
    player_id: Optional[int] = None
    duration: Optional[float] = None  # set when entering a hold_from_arg state (e.g. timed_lockout)


@dataclass(frozen=True)
class SceneChanged:
    index: int  # 1-based
    name: str


@dataclass(frozen=True)
class CountdownTick:
    remaining: float
    total: float
    paused: bool = False


@dataclass(frozen=True)
class CountdownEnded:
    reason: str  # "expired" | "cancelled" | "superseded"


@dataclass(frozen=True)
class ControlCommand:
    command: str
    args: tuple = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", tuple(self.args))
