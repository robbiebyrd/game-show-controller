---
status: completed
created: 2026-07-08
validated_at: "2026-07-08T16:04:14.558Z"
updated: "2026-07-08T16:04:49.331Z"
approved_at: "2026-07-08T16:04:18.252Z"
started_at: "2026-07-08T16:04:18.300Z"
completed_at: "2026-07-08T16:04:21.530Z"
archived_at: "2026-07-08T16:04:49.331Z"
---
# Plan: Stream Deck Control Surface

**Created:** 2026-07-07 | **Status:** Complete | **Effort:** L | **Branch:** feat/stream-deck-control-surface

## Summary

Add an in-process `ControlSurface` component that drives an Elgato Stream Deck MK.2 (15 keys, 3×5) from `config.yaml`. Keys publish existing bus commands (lighting, audio, state, buzz, scene, OBS) and navigate nested pages, with live keys reflecting current state, scene, and a buzz-in countdown. Extend `StateMachine` to emit countdown ticks and support pause/resume/reset/cancel of the buzz-in timer.

## Architecture Context

- **Event bus** (`gameshow/bus.py`): `subscribe(EventType, async_handler)` / `await publish(event)`. Handlers isolated by try/except.
- **`ControlCommand(command, args)`** (`events.py`) is the universal command. Existing verbs already cover most buttons: `clear`, `game_over`, `round_start`, `timed_lockout`, `correct`, `incorrect`, `allow_next`, `scene_advance/previous/goto_index/goto_name/current`, `audio_effect_play`, `audio_fx_stop`, `audio_bg_stop`, `obs_scene_set`, `dmx_cue`. `BuzzerPressed(player_id)` = buzz in.
- **Feedback events** the deck consumes for live keys: `StateChanged`, `PlayerBuzzed`, `SceneChanged` (+ new `CountdownTick`/`CountdownEnded`).
- Every component is `Class(bus, config_fn)` with async `start()`/`stop()`, wired in `main.py`. `config_fn()` returns the scene-merged `AppConfig` (`SceneManager.current_config`).
- **StreamDeck lib** (thread-based): callbacks fire on a reader thread → bridge to loop via `deck.set_key_callback_async(coro, loop=loop)`. Render with `PILHelper.create_key_image` → draw → `to_native_key_format` → `set_key_image(key, native)` inside `with deck:`. Keys 72×72 px. Bottom-left of 3×5 = **key index 10**.

## Research Findings

- Package: `streamdeck>=0.9.8` (import `StreamDeck`), needs `pillow`; macOS needs `brew install hidapi` (no Input Monitoring permission required — vendor HID).
- Non-deprecated PILHelper API: `create_key_image(deck, background)`, `create_scaled_key_image(deck, img, margins)`, `to_native_key_format(deck, img)`.
- `DeviceManager(transport='dummy').enumerate()` yields fake decks (real render path, no hardware) — useful for a render smoke test; deterministic logic tests use a hand-written `FakeDeck`.
- `deck` methods our code calls (mockable Protocol surface): `open/close/reset/is_open/connected/deck_type/key_count/key_layout/key_image_format/is_visual/set_brightness/set_key_image/set_key_callback/set_key_callback_async/__enter__/__exit__`.
- Existing tests: `pytest_asyncio` strict mode, `make_config(...)` helpers, patch `simpleobsws.WebSocketClient`, short hold/timeout values (0.05s) for timer tests.
- `parse_config` is re-run on every scene change via merged raw; `control_surface` lives top-level and is unaffected by scene overrides — read it once at `start()`.

## Security Considerations

- None — local hardware control surface, no network input surface added. OSC/OBS targets already configured. `obs_request` forwards config-authored request types only (no external input).

## Performance Considerations

- Countdown ticks at `COUNTDOWN_TICK_SECONDS = 0.25` (4 Hz). Deck only re-encodes/redraws the countdown key when the displayed integer second changes (cache last value) to avoid needless JPEG+USB writes.
- All rendering runs on the asyncio loop thread; `with deck:` mutex guards USB writes against the reader thread.

## Open Questions

### Important (P2)
1. TTF font for labels — bundle one in `gameshow/assets/` or rely on `ImageFont.load_default()`? Default: config-optional `font_path`, fall back to `load_default()`. Visual quality is human-verified.
2. Runtime deck hot-plug/reconnect — out of scope (YAGNI). If no deck at `start()`, log a warning and run inert.

## Steps

### Step 1: StateMachine countdown ticks + pause/resume/reset/cancel
- **Test:** `tests/test_state_machine.py` — with `buzz_timeout_seconds=1.0`: assert `CountdownTick` events published with decreasing `remaining` and correct `total`; `countdown_pause` freezes `remaining` (no expiry after sleep); `countdown_resume` continues; `countdown_reset` restores `remaining≈total`; `countdown_cancel` publishes `CountdownEnded(reason="cancelled")` and leaves state `LOCKED` (no auto-timeout); natural expiry publishes `CountdownEnded(reason="expired")` then `BUZZ_TIMEOUT`; a host transition (`correct`) publishes `CountdownEnded(reason="superseded")`. Use small `COUNTDOWN_TICK_SECONDS` via monkeypatch for speed.
- **Implement:** `gameshow/events.py` new events; `gameshow/state_machine.py` `Countdown` helper + wiring in `_lock_player` and `_on_control_command`.
- **Code:**
```python
# events.py
@dataclass(frozen=True)
class CountdownTick:
    remaining: float
    total: float
    paused: bool = False

@dataclass(frozen=True)
class CountdownEnded:
    reason: str  # "expired" | "cancelled" | "superseded"

# state_machine.py
COUNTDOWN_TICK_SECONDS = 0.25

class Countdown:
    def __init__(self, total, tick, on_tick, on_expire):
        self.total = total; self.remaining = total; self._tick = tick
        self.paused = False; self._cancelled = False
        self._on_tick = on_tick; self._on_expire = on_expire
        self._task: Optional[asyncio.Task] = None

    def start(self): self._task = asyncio.create_task(self._run())
    def pause(self): self.paused = True
    def resume(self): self.paused = False
    def reset(self): self.remaining = self.total

    def stop(self):  # hard cancel, no callbacks
        self._cancelled = True
        if self._task and not self._task.done(): self._task.cancel()

    async def _run(self):
        try:
            await self._on_tick(self.remaining, self.total, self.paused)
            while self.remaining > 0:
                await asyncio.sleep(self._tick)
                if not self.paused:
                    self.remaining = max(0.0, self.remaining - self._tick)
                await self._on_tick(self.remaining, self.total, self.paused)
            await self._on_expire()
        except asyncio.CancelledError:
            raise
```
- StateMachine: hold `self._countdown: Optional[Countdown]`. `_enter_state` calls `await self._stop_countdown("superseded")` before proceeding. In `_lock_player`, when `buzz_timeout_seconds is not None`, replace the `_buzz_timeout` task with a `Countdown(timeout, COUNTDOWN_TICK_SECONDS, self._emit_tick, self._on_countdown_expire)`.
```python
    async def _emit_tick(self, remaining, total, paused):
        await self._bus.publish(CountdownTick(remaining, total, paused))

    async def _on_countdown_expire(self):
        self._countdown = None
        await self._bus.publish(CountdownEnded(reason="expired"))
        await self._enter_state(GameState.BUZZ_TIMEOUT, self.locked_player_id)

    async def _stop_countdown(self, reason):
        if self._countdown is not None:
            self._countdown.stop(); self._countdown = None
            await self._bus.publish(CountdownEnded(reason=reason))

    # in _on_control_command (handle before the LOCKED gate):
    if cmd == "countdown_pause"  and self._countdown: self._countdown.pause(); return
    if cmd == "countdown_resume" and self._countdown: self._countdown.resume(); return
    if cmd == "countdown_reset"  and self._countdown: self._countdown.reset(); return
    if cmd == "countdown_cancel": await self._stop_countdown("cancelled"); return
```
- **Constraint:** `_enter_state` must stop countdown before publishing new `StateChanged`, so the deck clears the countdown key in the right order. Existing `_cancel_timer()` still handles `_auto_return`/`_buzz_timeout_return`.
- **Validation:** `poetry run pytest tests/test_state_machine.py`

### Step 2: OBSClient generic `obs_request` command
- **Test:** `tests/test_obs_client.py` — publishing `ControlCommand("obs_request", ("SetInputMute", {"inputName": "Mic", "inputMuted": True}))` calls `ws.call` once with a `simpleobsws.Request` for that type/data; ignored when not connected.
- **Implement:** `gameshow/obs_client.py` `_on_control_command`.
- **Code:**
```python
elif event.command == "obs_request" and event.args and self._connected:
    request_type = str(event.args[0])
    data = event.args[1] if len(event.args) > 1 else None
    try:
        await self._ws.call(simpleobsws.Request(request_type, data))
    except Exception as exc:
        log.warning("OBS request %s failed: %s", request_type, exc)
```
- **Validation:** `poetry run pytest tests/test_obs_client.py`

### Step 3: Config schema for `control_surface`
- **Test:** `tests/test_config.py` — parse a raw dict with `control_surface.root.buttons` including a nested `page` button; assert `AppConfig.control_surface` is a `ControlSurfaceConfig` with `enabled`, `brightness`, `font_path`, and a `PageConfig` tree; nested page buttons parsed recursively; unknown/absent section → `control_surface is None`.
- **Implement:** `gameshow/config.py` dataclasses + `_parse_control_surface`, add field to `AppConfig`.
- **Code:**
```python
@dataclass
class ButtonConfig:
    type: str
    label: str = ""
    icon: Optional[str] = None
    color: Optional[str] = None
    key: Optional[int] = None            # explicit slot 0-14
    # action params (only the relevant ones per type are used)
    state: Optional[str] = None          # clear|game_over|round_start|correct|incorrect|allow_next
    player_id: Optional[int] = None
    path: Optional[str] = None           # sound file
    osc: Optional[str] = None            # dmx cue address
    scene: Optional[str] = None          # obs scene name
    target: Optional[object] = None      # scene name(str) or index(int) for scene_goto
    duration: Optional[float] = None     # timed_lockout / countdown
    action: Optional[str] = None         # countdown: display|toggle|pause|resume|reset|cancel
    request_type: Optional[str] = None   # obs_request
    request_data: Optional[dict] = None
    page: Optional["PageConfig"] = None

@dataclass
class PageConfig:
    buttons: list[ButtonConfig] = field(default_factory=list)

@dataclass
class ControlSurfaceConfig:
    enabled: bool = True
    brightness: int = 60
    serial: Optional[str] = None
    font_path: Optional[str] = None
    root: PageConfig = field(default_factory=PageConfig)

def _parse_page(raw: dict) -> PageConfig:
    return PageConfig(buttons=[_parse_button(b) for b in raw.get("buttons", [])])

def _parse_button(raw: dict) -> ButtonConfig:
    page = _parse_page(raw["page"]) if isinstance(raw.get("page"), dict) else None
    fields = {k: v for k, v in raw.items()
              if k in ButtonConfig.__dataclass_fields__ and k != "page"}
    return ButtonConfig(page=page, **fields)
```
- `parse_config`: `cs = raw.get("control_surface"); control_surface = _parse_control_surface(cs) if cs else None`, add to `AppConfig(..., control_surface=control_surface)` (default `None`). **Update every `AppConfig(...)` call site in tests' `make_config` is unnecessary** since the new field has a default.
- **Validation:** `poetry run pytest tests/test_config.py`

### Step 4: ControlSurface layout resolution + press dispatch (logic, no pixels)
- **Test:** `tests/test_control_surface.py` — with a `FakeDeck` (key_count 15, layout (3,5), image format dict) and a two-level config:
  - `_resolve_layout(root)` places buttons at explicit `key`s and auto-fills the rest in order; on a **sub-page**, key 10 is reserved for an injected `return` button; root page has no return button.
  - Auto-placement skips reserved slot and warns+truncates when buttons exceed free keys.
  - Press dispatch (call `await cs._on_key(deck, key, True)`) publishes the right event per type: `lighting`→`dmx_cue`, `sound`→`audio_effect_play`, `stop_sounds`→both `audio_fx_stop`+`audio_bg_stop`, `state`→that command (`timed_lockout` carries `duration`), `buzz`→`BuzzerPressed`, `reset_buzzer`→`clear`, `scene_advance/previous`, `scene_goto`→index or name, `obs_scene`→`obs_scene_set`, `obs_request`→`obs_request`, `countdown` action→`countdown_*` (display/toggle logic), `page`→pushes stack (no bus event), `return`→pops stack.
  - Key release (`state=False`) publishes nothing.
- **Implement:** `gameshow/control_surface.py` — `StreamDeckProtocol`, `FakeDeck` lives in the test file, layout + dispatch methods.
- **Code:**
```python
RETURN_KEY = 10  # bottom-left on 3x5

class ControlSurface:
    def __init__(self, bus, config, deck_factory=None):
        self._bus = bus; self._config = config
        self._deck_factory = deck_factory or self._default_factory
        self._deck = None; self._loop = None
        self._stack: list[PageConfig] = []
        self._layout: dict[int, ButtonConfig] = {}
        self._last_tick: Optional[CountdownTick] = None
        self._last_scene = "—"; self._last_state = "idle"

    def _resolve_layout(self, page, is_subpage):
        layout: dict[int, ButtonConfig] = {}
        reserved = {RETURN_KEY} if is_subpage else set()
        if is_subpage:
            layout[RETURN_KEY] = ButtonConfig(type="return", label="Back")
        explicit = {b.key: b for b in page.buttons if b.key is not None}
        layout.update(explicit)
        free = (k for k in range(self._deck.key_count())
                if k not in layout and k not in reserved)
        for b in (b for b in page.buttons if b.key is None):
            k = next(free, None)
            if k is None:
                log.warning("Control surface page overflow; button %r dropped", b.label); continue
            layout[k] = b
        return layout

    _DIRECT = {  # type -> (command, arg_attrs) simple 1:1 command buttons
        "lighting": ("dmx_cue", ("osc",)),
        "sound": ("audio_effect_play", ("path",)),
        "reset_buzzer": ("clear", ()),
        "scene_advance": ("scene_advance", ()),
        "scene_previous": ("scene_previous", ()),
        "obs_scene": ("obs_scene_set", ("scene",)),
    }

    async def _dispatch(self, b: ButtonConfig):
        t = b.type
        if t == "page" and b.page is not None:
            self._stack.append(b.page); await self._render(); return
        if t == "return":
            if self._stack: self._stack.pop()
            await self._render(); return
        if t == "stop_sounds":
            await self._bus.publish(ControlCommand("audio_fx_stop"))
            await self._bus.publish(ControlCommand("audio_bg_stop")); return
        if t == "buzz" and b.player_id is not None:
            await self._bus.publish(BuzzerPressed(player_id=b.player_id)); return
        if t == "state" and b.state:
            args = (b.duration,) if b.state == "timed_lockout" and b.duration else ()
            await self._bus.publish(ControlCommand(b.state, args)); return
        if t == "scene_goto" and b.target is not None:
            cmd = "scene_goto_index" if isinstance(b.target, int) else "scene_goto_name"
            await self._bus.publish(ControlCommand(cmd, (b.target,))); return
        if t == "obs_request" and b.request_type:
            await self._bus.publish(ControlCommand("obs_request", (b.request_type, b.request_data))); return
        if t == "countdown":
            act = b.action or "display"
            if act == "toggle":
                act = "resume" if (self._last_tick and self._last_tick.paused) else "pause"
            if act in ("pause", "resume", "reset", "cancel"):
                await self._bus.publish(ControlCommand(f"countdown_{act}"))
            return  # "display" = no-op on press
        if t in self._DIRECT:
            cmd, attrs = self._DIRECT[t]
            args = tuple(getattr(b, a) for a in attrs)
            await self._bus.publish(ControlCommand(cmd, args)); return
        # types "scene_current", "state_display" are display-only → no-op

    async def _on_key(self, deck, key, state):
        if not state: return
        b = self._layout.get(key)
        if b is not None:
            await self._dispatch(b)
```
- **Validation:** `poetry run pytest tests/test_control_surface.py`

### Step 5: ControlSurface rendering, live updates, and lifecycle
- **Test:** `tests/test_control_surface.py` (same file, new cases) with `FakeDeck` recording `set_key_image(key, bytes)`:
  - `start()` opens deck, resets, sets brightness from config, registers async callback, and renders the root page (every non-empty key gets a non-None image).
  - `CountdownTick` re-renders `countdown` display keys (assert `set_key_image` called for that key; only when integer second changes — second identical tick is a no-op); `CountdownEnded` clears them.
  - `SceneChanged` updates `scene_current` keys; `StateChanged` updates `state_display` keys.
  - `stop()` resets and closes the deck.
  - No deck from factory → `start()` logs warning, `self._deck is None`, later events no-op (no crash).
- **Implement:** `gameshow/control_surface.py` rendering (`_render`, `_render_key`, `_render_live_keys`), event subscriptions, `start`/`stop`, `_default_factory`.
- **Code:**
```python
    def _default_factory(self):
        from StreamDeck.DeviceManager import DeviceManager
        return DeviceManager().enumerate()

    async def start(self):
        self._loop = asyncio.get_running_loop()
        cs = self._config().control_surface
        if not cs or not cs.enabled:
            log.info("Control surface disabled"); return
        decks = self._deck_factory()
        deck = next((d for d in decks
                     if cs.serial is None or d.get_serial_number() == cs.serial), None)
        if deck is None:
            log.warning("No Stream Deck found; control surface inert"); return
        self._deck = deck
        self._font = self._load_font(cs.font_path)
        deck.open(); deck.reset(); deck.set_brightness(cs.brightness)
        deck.set_key_callback_async(self._on_key, loop=self._loop)
        for et, h in ((CountdownTick, self._on_tick), (CountdownEnded, self._on_end),
                      (SceneChanged, self._on_scene), (StateChanged, self._on_state)):
            self._bus.subscribe(et, h)
        await self._render()

    async def _render(self):
        if self._deck is None: return
        page = self._stack[-1] if self._stack else self._config().control_surface.root
        self._layout = self._resolve_layout(page, is_subpage=bool(self._stack))
        for key in range(self._deck.key_count()):
            self._render_key(key, self._layout.get(key))

    def _render_key(self, key, button):
        img = PILHelper.create_key_image(self._deck, background=(button.color if button and button.color else "black"))
        if button is not None:
            ImageDraw.Draw(img).text((img.width/2, img.height-5),
                self._label_for(button), font=self._font, anchor="ms", fill="white")
        with self._deck:
            self._deck.set_key_image(key, PILHelper.to_native_key_format(self._deck, img))

    async def stop(self):
        if self._deck is not None:
            with self._deck:
                self._deck.reset(); self._deck.close()
            self._deck = None
```
- `_label_for(button)`: live types compute text — `countdown`→`ceil(remaining)`s from `_last_tick` (or "--"), `scene_current`→`_last_scene`, `state_display`→`_last_state`, else `button.label`. `_on_tick` stores tick, redraws countdown keys only if `ceil(remaining)` changed; `_on_end` clears `_last_tick` and redraws; `_on_scene`/`_on_state` store value and redraw matching keys.
- **Constraint:** all handlers run on the loop thread; wrap `set_key_image` in `with self._deck:`. Guard every handler with `if self._deck is None: return`.
- **Visual — requires human verification:** label legibility, font size, icon scaling, colors on physical hardware.
- **Validation:** `poetry run pytest tests/test_control_surface.py`

### Step 6: Wire into main.py + deps + example config + docs
- **Implement:** `main.py`, `pyproject.toml`, `config.yaml`, `docs/`.
- **Code:**
```python
# main.py
from gameshow.control_surface import ControlSurface
control_surface = ControlSurface(bus, config_fn)
# ...after obs_client.start():
await control_surface.start()
# ...in shutdown:
await control_surface.stop()
```
- `pyproject.toml` deps: add `streamdeck>=0.9.8`, `pillow>=10.0`. Run `poetry lock && poetry install`.
- Add a `control_surface:` section to `config.yaml` exercising every button type incl. a nested page (return auto-added).
- Document macOS `brew install hidapi` prerequisite + config reference in `docs/`.
- **Validation:** `poetry run pytest` (full suite green); `poetry run python -c "import gameshow.control_surface"`; manual: run `main.py` with deck attached, verify pages/live keys/countdown.

## Acceptance Criteria

- [x] All existing tests still pass; new tests for Steps 1–5 pass. (150 passed)
- [x] StateMachine emits `CountdownTick` during buzz-in and supports pause/resume/reset/cancel; expiry still reaches `BUZZ_TIMEOUT`.
- [x] Each configured button type publishes the correct bus event; `stop_sounds` stops both channels.
- [x] Sub-pages always show a working return button at key 10; root has none.
- [x] Live keys (countdown, current scene, current state) update from bus events.
- [x] No physical device required for the test suite (FakeDeck / injected factory).
- [x] Missing deck at startup logs a warning and leaves the rest of the app running.

## Checklist (non-TDD cleanup)

- [ ] `poetry run flake8 gameshow/control_surface.py` clean; type hints on public methods. (Type hints present; 45 `E501` line-length warnings remain — project-wide, no flake8 config sets `max-line-length`.)
- [x] `config.yaml` example documents every button type.
- [x] `docs/` notes `brew install hidapi` and the `control_surface` schema.
- [x] No bare `except:` (use `except Exception`); handlers log on failure.
