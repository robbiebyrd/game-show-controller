from __future__ import annotations
import asyncio
import logging
from typing import Optional, Callable
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand, GameState
)

log = logging.getLogger(__name__)

_TRANSIENT_HOLD_MAP = {
    GameState.CORRECT: lambda sm: sm._config().state_machine.correct_hold_seconds,
    GameState.INCORRECT: lambda sm: sm._config().state_machine.incorrect_hold_seconds,
    GameState.ROUND_START: lambda sm: sm._config().state_machine.round_start_hold_seconds,
}

_RETURN_TO_MAP = {
    GameState.CORRECT: lambda sm: sm._config().state_machine.return_to_after_correct,
    GameState.INCORRECT: lambda sm: sm._config().state_machine.return_to_after_incorrect,
    GameState.ROUND_START: lambda sm: sm._config().state_machine.return_to_after_round_start,
}

_STATE_NAME_TO_ENUM = {s.name.lower(): s for s in GameState}


class StateMachine:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self.state = GameState.IDLE
        self.locked_player_id: Optional[int] = None
        self._banned: set[int] = set()
        self._timer: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._bus.subscribe(BuzzerPressed, self._on_buzzer_pressed)
        self._bus.subscribe(ControlCommand, self._on_control_command)

    async def stop(self) -> None:
        self._cancel_timer()

    def _cancel_timer(self) -> None:
        if self._timer and not self._timer.done():
            self._timer.cancel()
        self._timer = None

    def _enabled_player_ids(self) -> set[int]:
        return {p.id for p in self._config().buzzers.players if p.enabled}

    def _player_name(self, player_id: int) -> str:
        for p in self._config().buzzers.players:
            if p.id == player_id:
                return p.name
        return str(player_id)

    async def _enter_state(self, new_state: GameState, player_id: Optional[int] = None) -> None:
        self._cancel_timer()
        log.info("State → %s%s", new_state.name, f" (player {player_id})" if player_id is not None else "")
        self.state = new_state

        await self._bus.publish(StateChanged(new_state=new_state, player_id=player_id))

        if new_state == GameState.BUZZ_TIMEOUT:
            hold = self._config().state_machine.buzz_timeout_hold_seconds
            self._timer = asyncio.create_task(self._buzz_timeout_return(player_id, hold))
        elif new_state in _TRANSIENT_HOLD_MAP:
            hold = _TRANSIENT_HOLD_MAP[new_state](self)
            return_to = _RETURN_TO_MAP[new_state](self)
            self._timer = asyncio.create_task(self._auto_return(hold, return_to))

    async def _buzz_timeout_return(self, player_id: Optional[int], hold: float) -> None:
        await asyncio.sleep(hold)
        if player_id is not None:
            self._banned.add(player_id)
        self.locked_player_id = None
        enabled = self._enabled_player_ids()
        if self._banned >= enabled:
            self._banned.clear()
            await self._enter_state(GameState.IDLE)
        else:
            await self._enter_state(GameState.ALLOW_NEXT)

    async def _auto_return(self, delay: float, return_to: str) -> None:
        await asyncio.sleep(delay)
        target = _STATE_NAME_TO_ENUM.get(return_to, GameState.IDLE)
        await self._enter_state(target)

    async def _on_buzzer_pressed(self, event: BuzzerPressed) -> None:
        pid = event.player_id
        enabled = self._enabled_player_ids()
        if pid not in enabled:
            log.debug("Buzzer press from disabled player %d ignored", pid)
            return

        if self.state == GameState.IDLE and pid not in self._banned:
            await self._lock_player(pid)
        elif self.state in (GameState.ALLOW_NEXT, GameState.INCORRECT) and pid not in self._banned:
            await self._lock_player(pid)

    async def _lock_player(self, player_id: int) -> None:
        self._cancel_timer()
        log.info("Player %d (%s) buzzed in", player_id, self._player_name(player_id))
        self.locked_player_id = player_id
        await self._bus.publish(PlayerBuzzed(
            player_id=player_id, player_name=self._player_name(player_id)
        ))

        cfg = self._config()
        if cfg.buzzers.buzz_timeout_seconds is not None:
            timeout = cfg.buzzers.buzz_timeout_seconds
            self._cancel_timer()
            self.state = GameState.LOCKED
            await self._bus.publish(StateChanged(new_state=GameState.LOCKED, player_id=player_id))
            self._timer = asyncio.create_task(self._buzz_timeout(timeout))
        else:
            self.state = GameState.LOCKED
            await self._bus.publish(StateChanged(new_state=GameState.LOCKED, player_id=player_id))

    async def _buzz_timeout(self, delay: float) -> None:
        await asyncio.sleep(delay)
        await self._enter_state(GameState.BUZZ_TIMEOUT, self.locked_player_id)

    async def _on_control_command(self, event: ControlCommand) -> None:
        cmd = event.command

        if cmd == "clear":
            self._banned.clear()
            self.locked_player_id = None
            await self._enter_state(GameState.IDLE)
            return

        if cmd == "game_over":
            self._banned.clear()
            self.locked_player_id = None
            await self._enter_state(GameState.GAME_OVER)
            return

        if cmd == "round_start":
            await self._enter_state(GameState.ROUND_START)
            return

        if cmd == "timed_lockout":
            duration = float(event.args[0]) if event.args else 5.0
            self._cancel_timer()
            self.state = GameState.TIMED_LOCKOUT
            await self._bus.publish(StateChanged(new_state=GameState.TIMED_LOCKOUT, duration=duration))
            self._timer = asyncio.create_task(self._auto_return(duration, "idle"))
            return

        if self.state == GameState.GAME_OVER:
            log.debug("Command %r ignored in GAME_OVER", cmd)
            return

        if self.state != GameState.LOCKED:
            log.debug("Command %r ignored outside LOCKED (state=%s)", cmd, self.state.name)
            return

        if cmd == "correct":
            await self._enter_state(GameState.CORRECT, self.locked_player_id)
        elif cmd == "incorrect":
            self._banned.add(self.locked_player_id)
            await self._enter_state(GameState.INCORRECT, self.locked_player_id)
        elif cmd == "allow_next":
            self._banned.add(self.locked_player_id)
            enabled = self._enabled_player_ids()
            if self._banned >= enabled:
                self._banned.clear()
                self.locked_player_id = None
                await self._enter_state(GameState.IDLE)
            else:
                self.locked_player_id = None
                await self._enter_state(GameState.ALLOW_NEXT)
