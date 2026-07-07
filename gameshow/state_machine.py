from __future__ import annotations
import asyncio
import logging
from typing import Optional, Callable
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand, GameState,
    CountdownTick, CountdownEnded
)

log = logging.getLogger(__name__)

COUNTDOWN_TICK_SECONDS = 0.25


class Countdown:
    """A pausable, resettable countdown that emits ticks until it expires.

    ``on_tick(remaining, total, paused)`` fires every tick; ``on_expire()``
    fires once when the remaining time naturally reaches zero. A hard
    ``stop()`` cancels the task without firing either callback.
    """

    def __init__(self, total: float, tick: float,
                 on_tick: Callable[[float, float, bool], "asyncio.Future"],
                 on_expire: Callable[[], "asyncio.Future"]) -> None:
        self.total = total
        self.remaining = total
        self._tick = tick
        self.paused = False
        self._on_tick = on_tick
        self._on_expire = on_expire
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def reset(self) -> None:
        self.remaining = self.total

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        await self._on_tick(self.remaining, self.total, self.paused)
        while self.remaining > 0:
            step = self._tick if self.paused else min(self._tick, self.remaining)
            await asyncio.sleep(step)
            if not self.paused:
                self.remaining = max(0.0, self.remaining - step)
            await self._on_tick(self.remaining, self.total, self.paused)
        await self._on_expire()


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
        self._countdown: Optional[Countdown] = None

    async def start(self) -> None:
        self._bus.subscribe(BuzzerPressed, self._on_buzzer_pressed)
        self._bus.subscribe(ControlCommand, self._on_control_command)

    async def stop(self) -> None:
        self._cancel_timer()
        await self._stop_countdown(None)

    def _cancel_timer(self) -> None:
        if self._timer and not self._timer.done():
            self._timer.cancel()
        self._timer = None

    async def _stop_countdown(self, reason: Optional[str]) -> None:
        """Stop the active countdown, optionally announcing why it ended."""
        if self._countdown is not None:
            self._countdown.stop()
            self._countdown = None
            if reason is not None:
                await self._bus.publish(CountdownEnded(reason=reason))

    async def _emit_tick(self, remaining: float, total: float, paused: bool) -> None:
        await self._bus.publish(CountdownTick(remaining=remaining, total=total, paused=paused))

    async def _on_countdown_expire(self) -> None:
        self._countdown = None
        await self._bus.publish(CountdownEnded(reason="expired"))
        await self._enter_state(GameState.BUZZ_TIMEOUT, self.locked_player_id)

    def _enabled_player_ids(self) -> set[int]:
        return {p.id for p in self._config().buzzers.players if p.enabled}

    def _player_name(self, player_id: int) -> str:
        for p in self._config().buzzers.players:
            if p.id == player_id:
                return p.name
        return str(player_id)

    async def _enter_state(self, new_state: GameState, player_id: Optional[int] = None) -> None:
        self._cancel_timer()
        await self._stop_countdown("superseded")
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
        await self._stop_countdown(None)
        log.info("Player %d (%s) buzzed in", player_id, self._player_name(player_id))
        self.locked_player_id = player_id
        await self._bus.publish(PlayerBuzzed(
            player_id=player_id, player_name=self._player_name(player_id)
        ))

        self.state = GameState.LOCKED
        await self._bus.publish(StateChanged(new_state=GameState.LOCKED, player_id=player_id))

        timeout = self._config().buzzers.buzz_timeout_seconds
        if timeout is not None:
            self._countdown = Countdown(
                timeout, COUNTDOWN_TICK_SECONDS, self._emit_tick, self._on_countdown_expire
            )
            self._countdown.start()

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

        if cmd == "countdown_pause":
            if self._countdown:
                self._countdown.pause()
            return
        if cmd == "countdown_resume":
            if self._countdown:
                self._countdown.resume()
            return
        if cmd == "countdown_reset":
            if self._countdown:
                self._countdown.reset()
            return
        if cmd == "countdown_cancel":
            await self._stop_countdown("cancelled")
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
