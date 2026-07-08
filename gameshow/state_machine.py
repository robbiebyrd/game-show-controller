from __future__ import annotations
import asyncio
import logging
from typing import Optional, Callable
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.config import TransitionConfig
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand,
    CountdownTick, CountdownEnded, SceneChanged, ScoreChanged
)

# Countdown controls act on the live countdown rather than driving a transition.
_COUNTDOWN_CONTROLS = {"countdown_pause", "countdown_resume", "countdown_reset", "countdown_cancel"}

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


class StateMachine:
    """Interprets the config-defined transition table and typed behaviors.

    A ``ControlCommand`` (or ``BuzzerPressed``, the ``buzz`` trigger) fires a
    trigger; the current state's ``transitions`` (falling back to ``global``)
    map it to a target state. Entry ``behaviors`` and per-transition ``do``
    lists run the typed side-effects (``ban_current`` / ``clear_bans`` /
    ``clear_player`` / ``countdown``). ``hold``/``then`` drives auto-return.
    """

    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self.state: str = config().state_machine.initial
        self.locked_player_id: Optional[int] = None
        self._banned: set[int] = set()
        self._timer: Optional[asyncio.Task] = None
        self._countdown: Optional[Countdown] = None
        self._scene_key: Optional[tuple] = None  # last scene reset for; guards refreshes
        self.scores: dict[int, float] = {}       # per-player, persists across scenes

    async def start(self) -> None:
        self._bus.subscribe(BuzzerPressed, self._on_buzzer_pressed)
        self._bus.subscribe(ControlCommand, self._on_control_command)
        self._bus.subscribe(SceneChanged, self._on_scene_changed)

    async def _on_scene_changed(self, event: SceneChanged) -> None:
        # Each scene may run a different machine, so reset flow to the new machine's
        # initial state. Ignore refresh publishes for the scene we already reset for
        # (e.g. the scene_current feedback command) so play isn't wiped mid-round.
        key = (event.index, event.name)
        if key == self._scene_key:
            return
        self._scene_key = key
        self._cancel_timer()
        await self._stop_countdown(None)
        self._banned.clear()
        self.locked_player_id = None
        sm = self._config().state_machine
        if sm.reset_scores_on_enter:
            await self._reset_scores()
        self.state = sm.initial
        log.info("Scene → %s; state machine reset to %s", event.name, self.state)

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
        await self._fire("countdown_expire")

    def _start_buzz_countdown(self) -> None:
        timeout = self._config().buzzers.buzz_timeout_seconds
        if timeout is None:
            return
        self._countdown = Countdown(
            timeout, COUNTDOWN_TICK_SECONDS, self._emit_tick, self._on_countdown_expire
        )
        self._countdown.start()

    def _enabled_player_ids(self) -> set[int]:
        return {p.id for p in self._config().buzzers.players if p.enabled}

    def _player_name(self, player_id: int) -> str:
        for p in self._config().buzzers.players:
            if p.id == player_id:
                return p.name
        return str(player_id)

    async def _run_do(self, behaviors: list) -> None:
        """Apply a list of Behavior side-effects, in order."""
        for b in behaviors:
            if b.name == "ban_current":
                if self.locked_player_id is not None:
                    self._banned.add(self.locked_player_id)
            elif b.name == "clear_bans":
                self._banned.clear()
            elif b.name == "clear_player":
                self.locked_player_id = None
            elif b.name == "award":
                await self._adjust_score(self._amount(b, "default_award"))
            elif b.name == "deduct":
                await self._adjust_score(-self._amount(b, "default_deduct"))
            elif b.name == "reset_scores":
                await self._reset_scores()
            # "countdown" is an entry behavior; it has no meaning in a `do` list.

    def _amount(self, behavior, default_attr: str) -> float:
        """Resolve a scoring amount: the behavior's own param, else the machine default."""
        if behavior.param is not None:
            return float(behavior.param)
        scoring = self._config().state_machine.scoring
        return float(getattr(scoring, default_attr)) if scoring is not None else 0.0

    async def _adjust_score(self, delta: float) -> None:
        pid = self.locked_player_id
        if pid is None or delta == 0:
            return
        self.scores[pid] = self.scores.get(pid, 0) + delta
        await self._bus.publish(ScoreChanged(player_id=pid, score=self.scores[pid], delta=delta))

    async def _reset_scores(self) -> None:
        cleared = list(self.scores)
        self.scores.clear()
        for pid in cleared:
            await self._bus.publish(ScoreChanged(player_id=pid, score=0, delta=0))

    async def _resolve_target(self, tr: TransitionConfig) -> str:
        """Run the transition's behaviors and apply the all-banned guard."""
        await self._run_do(tr.do)
        if tr.when_all_banned is not None and self._banned >= self._enabled_player_ids():
            self._banned.clear()
            return tr.when_all_banned
        return tr.to

    async def _fire(self, trigger: str, arg: object = None,
                    player_id: Optional[int] = None) -> None:
        sm = self._config().state_machine
        state = sm.states.get(self.state)
        tr = (state.transitions.get(trigger) if state else None) or sm.global_.get(trigger)
        if tr is None:
            log.debug("Trigger %r not valid in state %s", trigger, self.state)
            return
        if player_id is not None:                # the `buzz` trigger carries a player
            self.locked_player_id = player_id
            log.info("Player %d (%s) buzzed in", player_id, self._player_name(player_id))
            await self._bus.publish(PlayerBuzzed(
                player_id=player_id, player_name=self._player_name(player_id)))
        await self._enter_state(await self._resolve_target(tr), arg=arg)

    async def _enter_state(self, name: str, arg: object = None) -> None:
        self._cancel_timer()
        await self._stop_countdown("superseded")
        cfg = self._config().state_machine.states[name]
        log.info("State → %s%s", name,
                 f" (player {self.locked_player_id})" if self.locked_player_id is not None else "")
        self.state = name

        duration = None
        if cfg.hold_from_arg is not None:
            duration = float(arg) if arg is not None else cfg.hold_from_arg
        await self._bus.publish(StateChanged(
            new_state=name, player_id=self.locked_player_id, duration=duration))

        # Entry behaviors: countdown starts the buzz timer; the rest run as side-effects.
        await self._run_do([b for b in cfg.behaviors if b.name != "countdown"])
        if any(b.name == "countdown" for b in cfg.behaviors):
            self._start_buzz_countdown()

        hold = duration if cfg.hold_from_arg is not None else cfg.hold
        if hold is not None and cfg.then is not None:
            self._timer = asyncio.create_task(self._auto_return(hold, cfg.then))

    async def _auto_return(self, delay: float, tr: TransitionConfig) -> None:
        await asyncio.sleep(delay)
        await self._enter_state(await self._resolve_target(tr))

    async def _on_buzzer_pressed(self, event: BuzzerPressed) -> None:
        pid = event.player_id
        if pid not in self._enabled_player_ids():
            log.debug("Buzzer press from disabled player %d ignored", pid)
            return
        if pid in self._banned:
            return
        state = self._config().state_machine.states.get(self.state)
        if state is None or "buzz" not in state.transitions:
            return
        await self._fire("buzz", player_id=pid)

    async def _on_control_command(self, event: ControlCommand) -> None:
        cmd = event.command
        if cmd in _COUNTDOWN_CONTROLS:
            await self._handle_countdown_control(cmd)
            return
        arg = event.args[0] if event.args else None
        await self._fire(cmd, arg=arg)

    async def _handle_countdown_control(self, cmd: str) -> None:
        if cmd == "countdown_cancel":
            await self._stop_countdown("cancelled")
        elif self._countdown:
            if cmd == "countdown_pause":
                self._countdown.pause()
            elif cmd == "countdown_resume":
                self._countdown.resume()
            elif cmd == "countdown_reset":
                self._countdown.reset()
