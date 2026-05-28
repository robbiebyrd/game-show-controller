from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class GameState(Enum):
    IDLE = auto()
    LOCKED = auto()
    ALLOW_NEXT = auto()
    CORRECT = auto()
    INCORRECT = auto()
    BUZZ_TIMEOUT = auto()
    TIMED_LOCKOUT = auto()
    ROUND_START = auto()
    GAME_OVER = auto()


@dataclass(frozen=True)
class BuzzerPressed:
    player_id: int


@dataclass(frozen=True)
class PlayerBuzzed:
    player_id: int
    player_name: str


@dataclass(frozen=True)
class StateChanged:
    new_state: GameState
    player_id: Optional[int] = None
    duration: Optional[float] = None  # set for TIMED_LOCKOUT; carries duration seconds


@dataclass(frozen=True)
class SceneChanged:
    index: int  # 1-based
    name: str


@dataclass(frozen=True)
class ControlCommand:
    command: str
    args: tuple = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", tuple(self.args))
