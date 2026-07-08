import asyncio
import pytest
from gameshow.bus import EventBus
from gameshow.events import (
    BuzzerPressed, PlayerBuzzed, StateChanged, ControlCommand,
    CountdownTick, CountdownEnded, SceneChanged, ScoreChanged, AwardChanged
)
from gameshow import state_machine as sm_module
from gameshow.state_machine import StateMachine
from gameshow.config import (
    AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig,
    StateMachineConfig, StateConfig, TransitionConfig,
    LightingConfig, AudioConfig, OBSConfig, ScoringConfig, Behavior
)


def _enable_scoring(cfg, default_award=100, default_deduct=50):
    """Attach scoring config + award/deduct behaviors to a make_config() machine."""
    sm = cfg.state_machine
    sm.scoring = ScoringConfig(default_award=default_award, default_deduct=default_deduct)
    sm.states["locked"].transitions["correct"].do.append(Behavior("award"))
    sm.states["locked"].transitions["incorrect"].do.append(Behavior("deduct"))
    sm.global_["clear"].do.append(Behavior("reset_scores"))
    return cfg


def _t(to, do=None, when_all_banned=None):
    return TransitionConfig(to=to, do=do or [], when_all_banned=when_all_banned)


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
    states = {
        "idle": StateConfig(transitions={"buzz": _t("locked")}),
        "locked": StateConfig(
            behaviors=["countdown"],
            transitions={
                "countdown_expire": _t("buzz_timeout"),
                "correct": _t("correct"),
                "incorrect": _t("incorrect", do=["ban_current"]),
                "allow_next": _t("allow_next", do=["ban_current", "clear_player"],
                                 when_all_banned="idle"),
            },
        ),
        "correct": StateConfig(hold=correct_hold, then=_t(return_correct)),
        "incorrect": StateConfig(hold=incorrect_hold, then=_t(return_incorrect),
                                 transitions={"buzz": _t("locked")}),
        "allow_next": StateConfig(transitions={"buzz": _t("locked")}),
        "buzz_timeout": StateConfig(
            hold=buzz_timeout_hold,
            then=_t("allow_next", do=["ban_current", "clear_player"], when_all_banned="idle"),
        ),
        "timed_lockout": StateConfig(hold_from_arg=5.0, then=_t("idle")),
        "round_start": StateConfig(hold=round_start_hold, then=_t(return_round_start)),
        "game_over": StateConfig(),
    }
    global_ = {
        "clear": _t("idle", do=["clear_bans", "clear_player"]),
        "game_over": _t("game_over", do=["clear_bans", "clear_player"]),
        "round_start": _t("round_start"),
        "timed_lockout": _t("timed_lockout"),
    }
    return AppConfig(
        service=ServiceConfig(),
        buzzers=BuzzerConfig(players=players, buzz_timeout_seconds=buzz_timeout_seconds),
        state_machine=StateMachineConfig(initial="idle", states=states, global_=global_),
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
    assert any(isinstance(e, StateChanged) and e.new_state == "locked" for e in published)
    assert sm.state == "locked"

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
    assert sm.state == "locked"

    await sm.stop()


@pytest.mark.asyncio
async def test_correct_from_locked_transitions_and_auto_returns():
    bus = EventBus()
    config = make_config(correct_hold=0.05, return_correct="idle")
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == "correct"

    await asyncio.sleep(0.15)
    assert sm.state == "idle"

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
    assert sm.state == "idle"

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_from_locked_bans_player_and_allows_others():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="allow_next"))
    assert sm.state == "allow_next"

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "allow_next"  # still banned

    await bus.publish(BuzzerPressed(player_id=2))
    assert sm.state == "locked"
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

    assert sm.state == "idle"

    await sm.stop()


@pytest.mark.asyncio
async def test_allow_next_outside_locked_is_ignored():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    assert sm.state == "idle"
    await bus.publish(ControlCommand(command="allow_next"))
    assert sm.state == "idle"

    await sm.stop()


@pytest.mark.asyncio
async def test_clear_from_any_state_goes_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "locked"
    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == "idle"

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
    assert sm.state == "allow_next"
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
    assert sm.state == "allow_next"

    # Timed-out player is banned
    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "allow_next"

    # Other player can buzz in
    await bus.publish(BuzzerPressed(player_id=2))
    assert sm.state == "locked"
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
    assert sm.state == "idle"
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
    assert sm.state == "correct"  # not BUZZ_TIMEOUT

    await sm.stop()


@pytest.mark.asyncio
async def test_any_transition_cancels_transient_timer():
    bus = EventBus()
    config = make_config(correct_hold=1.0)  # long hold
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.state == "correct"

    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == "idle"

    await asyncio.sleep(0.1)
    assert sm.state == "idle"  # no ghost timer

    await sm.stop()


@pytest.mark.asyncio
async def test_timed_lockout_auto_returns_to_idle():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(ControlCommand(command="timed_lockout", args=(0.05,)))
    assert sm.state == "timed_lockout"
    await asyncio.sleep(0.15)
    assert sm.state == "idle"

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
    assert sm.state == "idle"

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
    assert sm.state == "locked"
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
    assert sm.state == "locked"  # paused, no expiry
    await bus.publish(ControlCommand(command="countdown_resume"))
    await asyncio.sleep(0.3)
    assert sm.state == "idle"  # resumed → expired → exhausted

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
    assert sm.state == "locked"  # no auto-timeout after cancel
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
    assert sm.state == "correct"

    await sm.stop()


@pytest.mark.asyncio
async def test_award_increases_locked_player_score_and_emits_event():
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_award=100)
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()

    events = []
    async def capture(e): events.append(e)
    bus.subscribe(ScoreChanged, capture)

    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))

    assert sm.scores[1] == 100
    assert any(isinstance(e, ScoreChanged) and e.player_id == 1
               and e.score == 100 and e.delta == 100 for e in events)
    await sm.stop()


@pytest.mark.asyncio
async def test_award_uses_explicit_param_over_default():
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_award=100)
    # Override: correct awards 500, not the default 100.
    cfg.state_machine.states["locked"].transitions["correct"].do = [Behavior("award", 500)]
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 500
    await sm.stop()


@pytest.mark.asyncio
async def test_deduct_decreases_score():
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_deduct=50)
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="incorrect"))
    assert sm.scores[1] == -50
    await sm.stop()


@pytest.mark.asyncio
async def test_reset_scores_clears_all():
    bus = EventBus()
    cfg = _enable_scoring(make_config())
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 100
    await bus.publish(ControlCommand(command="clear"))   # global clear includes reset_scores
    assert sm.scores.get(1, 0) == 0
    await sm.stop()


@pytest.mark.asyncio
async def test_scores_persist_across_scene_change_by_default():
    holder = {"cfg": _enable_scoring(make_config())}
    bus = EventBus()
    sm = StateMachine(bus, lambda: holder["cfg"])
    await sm.start()
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 100

    holder["cfg"] = _enable_scoring(make_config())   # new scene, default persistence
    await bus.publish(SceneChanged(index=2, name="Round 2"))
    assert sm.scores[1] == 100                        # carried over
    await sm.stop()


@pytest.mark.asyncio
async def test_reset_scores_on_enter_clears_on_scene_change():
    holder = {"cfg": _enable_scoring(make_config())}
    bus = EventBus()
    sm = StateMachine(bus, lambda: holder["cfg"])
    await sm.start()
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 100

    fresh = _enable_scoring(make_config())
    fresh.state_machine.reset_scores_on_enter = True
    holder["cfg"] = fresh
    await bus.publish(SceneChanged(index=2, name="Round 2"))
    assert sm.scores.get(1, 0) == 0                   # reset on enter
    await sm.stop()


@pytest.mark.asyncio
async def test_set_award_overrides_default():
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_award=100)
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    await bus.publish(ControlCommand(command="set_award", args=(500,)))
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 500
    await sm.stop()


@pytest.mark.asyncio
async def test_award_falls_back_to_default_without_override():
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_award=100)
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 100
    await sm.stop()


@pytest.mark.asyncio
async def test_pending_award_clears_after_use():
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_award=100)
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    await bus.publish(ControlCommand(command="set_award", args=(500,)))
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 500
    await asyncio.sleep(0.1)   # let CORRECT auto-return to idle
    assert sm.state == "idle"
    # Next question: no override → default is used (pending was cleared).
    await bus.publish(BuzzerPressed(player_id=1))
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 600
    await sm.stop()


@pytest.mark.asyncio
async def test_set_award_emits_award_changed():
    bus = EventBus()
    cfg = _enable_scoring(make_config())
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()
    events = []
    async def capture(e): events.append(e)
    bus.subscribe(AwardChanged, capture)
    await bus.publish(ControlCommand(command="set_award", args=(300,)))
    assert any(isinstance(e, AwardChanged) and e.value == 300 for e in events)
    await sm.stop()


@pytest.mark.asyncio
async def test_award_override_timeout_commits_default(monkeypatch):
    bus = EventBus()
    cfg = _enable_scoring(make_config(), default_award=100)
    cfg.state_machine.scoring.award_override_timeout = 0.05
    # 'locked' becomes the "question live" state that opens the override window.
    cfg.state_machine.states["locked"].behaviors.append(Behavior("await_award"))
    sm = StateMachine(bus, lambda: cfg)
    await sm.start()

    events = []
    async def capture(e): events.append(e)
    bus.subscribe(AwardChanged, capture)

    await bus.publish(BuzzerPressed(player_id=1))   # enters locked → arms window
    await asyncio.sleep(0.15)                        # window expires → commit default
    assert any(isinstance(e, AwardChanged) and e.value == 100 for e in events)
    await bus.publish(ControlCommand(command="correct"))
    assert sm.scores[1] == 100
    await sm.stop()


@pytest.mark.asyncio
async def test_scene_change_resets_to_new_machine_initial():
    holder = {"cfg": make_config()}
    bus = EventBus()
    sm = StateMachine(bus, lambda: holder["cfg"])
    await sm.start()

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "locked"

    # Swap to a different machine whose initial state is 'ready'.
    cfgB = make_config()
    cfgB.state_machine.initial = "ready"
    cfgB.state_machine.states["ready"] = StateConfig(transitions={"buzz": _t("locked")})
    holder["cfg"] = cfgB

    await bus.publish(SceneChanged(index=2, name="Round 2"))
    assert sm.state == "ready"           # reset to the new machine's initial
    assert sm.locked_player_id is None
    assert sm._banned == set()

    # Buzzing drives the NEW machine.
    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "locked"

    await sm.stop()


@pytest.mark.asyncio
async def test_repeated_scene_changed_same_scene_does_not_reset():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(SceneChanged(index=1, name="R1"))
    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "locked"

    # A refresh publish for the SAME scene (e.g. scene_current) must not reset play.
    await bus.publish(SceneChanged(index=1, name="R1"))
    assert sm.state == "locked"
    assert sm.locked_player_id == 1

    await sm.stop()


@pytest.mark.asyncio
async def test_game_over_only_exits_via_clear():
    bus = EventBus()
    config = make_config()
    sm = StateMachine(bus, lambda: config)
    await sm.start()

    await bus.publish(ControlCommand(command="game_over"))
    assert sm.state == "game_over"

    await bus.publish(BuzzerPressed(player_id=1))
    assert sm.state == "game_over"  # buzz does nothing

    await bus.publish(ControlCommand(command="clear"))
    assert sm.state == "idle"

    await sm.stop()
