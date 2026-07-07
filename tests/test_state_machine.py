import asyncio
import pytest
from gameshow.bus import EventBus
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand, GameState,
    CountdownTick, CountdownEnded
)
from gameshow import state_machine as sm_module
from gameshow.state_machine import StateMachine
from gameshow.config import (
    AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig,
    StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
)


def make_config(
    buzz_timeout_seconds=None,
    correct_hold=0.05,
    incorrect_hold=0.05,
    buzz_timeout_hold=0.05,
    round_start_hold=0.05,
    return_correct="idle",
    return_incorrect="idle",
    return_round_start="idle",
    players=None,
):
    if players is None:
        players = [
            PlayerConfig(id=1, name="P1", key="1", enabled=True),
            PlayerConfig(id=2, name="P2", key="2", enabled=True),
        ]
    return AppConfig(
        service=ServiceConfig(),
        buzzers=BuzzerConfig(players=players, buzz_timeout_seconds=buzz_timeout_seconds),
        state_machine=StateMachineConfig(
            correct_hold_seconds=correct_hold,
            incorrect_hold_seconds=incorrect_hold,
            buzz_timeout_hold_seconds=buzz_timeout_hold,
            round_start_hold_seconds=round_start_hold,
            return_to_after_correct=return_correct,
            return_to_after_incorrect=return_incorrect,
            return_to_after_round_start=return_round_start,
        ),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_idle_buzz_emits_player_buzzed_and_state_changed_locked():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    published = []
    async def capture(e): published.append(e)
    bus.subscribe(PlayerBuzzed, capture)
    bus.subscribe(StateChanged, capture)

    await bus.publish(BuzzerPressed(player_id=1))

    assert any(isinstance(e, PlayerBuzzed) and e.player_id == 1 for e in published)
    assert any(isinstance(e, StateChanged) and e.new_state == GameState.LOCKED for e in published)
    assert sm.state == GameState.LOCKED

    await sm.stop()


@pytest.mark.asyncio
async def test_second_buzz_in_locked_is_ignored():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    published = []
    async def capture(e): published.append(e)
    bus.subscribe(StateChanged, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    published.clear()
    await bus.publish(BuzzerPressed(player_id=2))

    assert len(published) == 0
    assert sm.state == GameState.LOCKED

    await sm.stop()


@pytest.mark.asyncio
async def test_correct_from_locked_transitions_and_auto_returns():
    bus = EventBus()
    config = make_config(correct_hold=0.05, return_correct="idle")
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == GameState.CORRECT

    await asyncio.sleep(0.15)
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_incorrect_from_locked_auto_returns():
    bus = EventBus()
    config = make_config(incorrect_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="incorrect"))
    await asyncio.sleep(0.15)
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_from_locked_bans_player_and_allows_others():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="allow_next"))
    assert sm.state == GameState.ALLOW_NEXT

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.ALLOW_NEXT  # still banned

    await bus.publish(BuzzerPressed(player_id=2))
    assert sm.state == GameState.LOCKED
    assert sm.locked_player_id == 2

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_exhaustion_returns_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="allow_next"))
    await bus.publish(BuzzerPressed(player_id=2))
    await bus.publish(ControlCommand(command="allow_next"))

    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_outside_locked_is_ignored():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    assert sm.state == GameState.IDLE
    await bus.publish(ControlCommand(command="allow_next"))
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_clear_from_any_state_goes_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.LOCKED
    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_buzz_timeout_fires_after_delay():
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.05, buzz_timeout_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.2)
    # P1 timed out and is banned; P2 still available → ALLOW_NEXT
    assert sm.state == GameState.ALLOW_NEXT
    assert 1 in sm._banned

    await sm.stop()


@pytest.mark.asyncio
async def test_buzz_timeout_allows_other_players_to_buzz():
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.05, buzz_timeout_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.2)
    assert sm.state == GameState.ALLOW_NEXT

    # Timed-out player is banned
    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.ALLOW_NEXT

    # Other player can buzz in
    await bus.publish(BuzzerPressed(player_id=2))
    assert sm.state == GameState.LOCKED
    assert sm.locked_player_id == 2

    await sm.stop()


@pytest.mark.asyncio
async def test_buzz_timeout_all_players_exhausted_returns_to_idle():
    bus = EventBus()
    players = [PlayerConfig(id=1, name="P1", key="1", enabled=True)]
    config = make_config(buzz_timeout_seconds=0.05, buzz_timeout_hold=0.05, players=players)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.2)
    # Only one player, they timed out → all exhausted → IDLE with ban cleared
    assert sm.state == GameState.IDLE
    assert len(sm._banned) == 0

    await sm.stop()


@pytest.mark.asyncio
async def test_host_input_cancels_buzz_timeout():
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.2)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.05)
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == GameState.CORRECT  # not BUZZ_TIMEOUT

    await sm.stop()


@pytest.mark.asyncio
async def test_any_transition_cancels_transient_timer():
    bus = EventBus()
    config = make_config(correct_hold=1.0)  # long hold
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == GameState.CORRECT

    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == GameState.IDLE

    await asyncio.sleep(0.1)
    assert sm.state == GameState.IDLE  # no ghost timer

    await sm.stop()


@pytest.mark.asyncio
async def test_timed_lockout_auto_returns_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(ControlCommand(command="timed_lockout", args=(0.05,)))
    assert sm.state == GameState.TIMED_LOCKOUT
    await asyncio.sleep(0.15)
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.fixture
def fast_tick(monkeypatch):
    monkeypatch.setattr(sm_module, "COUNTDOWN_TICK_SECONDS", 0.02)


@pytest.mark.asyncio
async def test_countdown_emits_ticks_during_buzz_in(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.2)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    ticks = []
    async def capture(e): ticks.append(e)
    bus.subscribe(CountdownTick, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.1)

    assert len(ticks) >= 2
    assert ticks[0].total == 0.2
    assert ticks[0].remaining >= ticks[-1].remaining
    assert all(t.paused is False for t in ticks)

    await sm.stop()


@pytest.mark.asyncio
async def test_countdown_expiry_ends_and_reaches_buzz_timeout(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.1, buzz_timeout_hold=0.05,
                         players=[PlayerConfig(id=1, name="P1", key="1", enabled=True)])
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    ended = []
    async def capture(e): ended.append(e)
    bus.subscribe(CountdownEnded, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.35)

    assert any(e.reason == "expired" for e in ended)
    # single-player config → all exhausted after timeout → IDLE
    assert sm.state == GameState.IDLE

    await sm.stop()


@pytest.mark.asyncio
async def test_countdown_pause_freezes_and_prevents_expiry(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.15)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.04)
    await bus.publish(ControlCommand(command="countdown_pause"))

    ticks = []
    async def capture(e): ticks.append(e)
    bus.subscribe(CountdownTick, capture)

    await asyncio.sleep(0.25)
    # Still locked (no expiry) and paused ticks report frozen remaining
    assert sm.state == GameState.LOCKED
    assert ticks, "paused countdown should still emit ticks"
    assert all(t.paused for t in ticks)
    assert ticks[0].remaining == ticks[-1].remaining

    await sm.stop()


@pytest.mark.asyncio
async def test_countdown_resume_continues_to_expiry(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.1, buzz_timeout_hold=0.05,
                         players=[PlayerConfig(id=1, name="P1", key="1", enabled=True)])
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="countdown_pause"))
    await asyncio.sleep(0.15)
    assert sm.state == GameState.LOCKED  # paused, no expiry
    await bus.publish(ControlCommand(command="countdown_resume"))
    await asyncio.sleep(0.3)
    assert sm.state == GameState.IDLE  # resumed → expired → exhausted

    await sm.stop()


@pytest.mark.asyncio
async def test_countdown_reset_restores_remaining(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.3)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.12)

    ticks = []
    async def capture(e): ticks.append(e)
    bus.subscribe(CountdownTick, capture)

    await bus.publish(ControlCommand(command="countdown_reset"))
    await asyncio.sleep(0.05)
    assert ticks
    assert ticks[0].remaining > 0.25  # bumped back near total

    await sm.stop()


@pytest.mark.asyncio
async def test_countdown_cancel_stops_timer_but_stays_locked(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.1, buzz_timeout_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    ended = []
    async def capture(e): ended.append(e)
    bus.subscribe(CountdownEnded, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="countdown_cancel"))
    await asyncio.sleep(0.25)

    assert any(e.reason == "cancelled" for e in ended)
    assert sm.state == GameState.LOCKED  # no auto-timeout after cancel
    assert sm.locked_player_id == 1

    await sm.stop()


@pytest.mark.asyncio
async def test_host_transition_supersedes_countdown(fast_tick):
    bus = EventBus()
    config = make_config(buzz_timeout_seconds=0.3, correct_hold=0.05)
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    ended = []
    async def capture(e): ended.append(e)
    bus.subscribe(CountdownEnded, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    await asyncio.sleep(0.04)
    await bus.publish(ControlCommand(command="correct"))

    assert any(e.reason == "superseded" for e in ended)
    assert sm.state == GameState.CORRECT

    await sm.stop()


@pytest.mark.asyncio
async def test_game_over_only_exits_via_clear():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(ControlCommand(command="game_over"))
    assert sm.state == GameState.GAME_OVER

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == GameState.GAME_OVER  # buzz does nothing

    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == GameState.IDLE

    await sm.stop()
