---
status: in_progress
approved_at: "2026-07-09T16:46:44.578Z"
updated: "2026-07-09T16:49:51.962Z"
started_at: "2026-07-09T16:49:51.962Z"
---
# Plan: Generate TouchOSC surface from control_surface config (full parity)

**Created:** 2026-07-09 | **Status:** Draft | **Effort:** M | **Branch:** feat/touchosc-from-config

## Summary

Make `tools/generate_touchosc.py` build the `.tosc` layout **from** the `control_surface:`
button/page tree in a show YAML (instead of a hardcoded layout), mirroring the Stream Deck
grid and pages as TouchOSC PAGER tabs. Close the inbound-OSC gap so every button that works on
the Stream Deck also works from TouchOSC. A single shared module (`gameshow/osc_map.py`) is the
one source of truth for button-type → OSC address, consumed by both the generator (emit) and
`osc_server.py` (receive), with a test that proves they can't drift.

## Architecture Context

- Two input doors to the same `EventBus`: Stream Deck (`control_surface.py::_dispatch` publishes
  events directly) and TouchOSC (`osc_server.py::_dispatch` translates OSC → events).
- The gap: `osc_server.py` accepts a *narrower* command set than the Stream Deck can produce.
- Every command needed already has a consumer: triggers → `state_machine.py:348` (`_fire`),
  `dmx_cue` → DMXClient, `obs_scene_set`/`obs_request` → `obs_client.py:68,76`, `set_award` →
  `state_machine.py:344`, `countdown_*` → `state_machine.py:358`. Buzz = `BuzzerPressed`
  (`keyboard.py:32` is the reference producer).
- Config tree: `ControlSurfaceConfig.root` → `PageConfig.buttons` → `ButtonConfig`
  (`config.py:184-242`); sub-pages are `ButtonConfig.page`. Slots via `button.key` (0-14, row-major
  3×5).
- Existing generator (`tools/generate_touchosc.py`) already has all `.tosc` XML plumbing
  (button/label/feedback_label/fader factories, `_osc_send`/`_osc_receive`, zlib packaging) and a
  PAGER/PAGE example in `tools/generate_touchosc_test.py:98-125` — reuse both.

## Research Findings

- `_on_control_command` fires any unknown command as a trigger → one generic `/trigger <name>`
  route covers all `type: state` buttons incl. `three_strikes`. Keep existing `/buzzer/*`
  routes (harmless; used by the current hand-built `.tosc`).
- No `/feedback/countdown` is emitted today → Timer display buttons need a new
  `CountdownTick` → `/feedback/countdown` feedback in `osc_server.py`.
- No `countdown_toggle` command exists (SD resolves toggle client-side via `_last_tick.paused`,
  `control_surface.py:375`). Server must gain a `countdown_toggle` for TouchOSC toggle buttons.
- `obs_request.request_data` is a dict; OSC can't carry a dict. Emit `request_type` as a string
  arg and, if `request_data` is set, a second JSON-string arg the server `json.loads`.
- `generate_touchosc_test.py` is misnamed — it's a diagnostic script with no `test_*` functions
  (pytest collects nothing). Replace with real tests.
- `SimpleUDPClient.send_message` takes a single value or list; per-player score feedback is
  `/feedback/score/<id>` (already emitted).

## Security Considerations

- None of consequence — OSC is trusted LAN input already accepted by the service. New routes add
  no new trust boundary. `/config/reload` path handling is unchanged (still resolved under
  `shows/`). `obs_request` JSON arg: wrap `json.loads` in `try/except (ValueError, TypeError)` and
  log-and-drop on malformed input (no bare except).

## Performance Considerations

- None. Generator is an offline build tool. New feedback subscription (`CountdownTick` →
  `/feedback/countdown`) fires at the existing tick cadence (~already throttled by
  `_last_countdown_text` dedupe in control_surface; add the same string-dedupe in osc_server to
  avoid one UDP packet per tick).

## Design decisions

- **Layout:** flatten root + every descendant page into ONE PAGER tab bar (root tab = "Main";
  each nested `page:` becomes its own tab labelled by the page button's `label`). Simpler and more
  tablet-friendly than nested PAGERs; `return` is unneeded (tabs replace back-nav). Buttons placed
  on a 3×5 grid from `button.key` (`row = key // 5`, `col = key % 5`).
- **Single source of truth:** `osc_map.py` owns address constants + `button_to_osc()` (emit side)
  + `command_for()` (receive side). `osc_server.py` keeps its bespoke handlers (`/config/list`,
  `/config/load`, `/show/goto` type-dispatch, audio play/volume). Anti-drift test asserts every
  address `button_to_osc` can emit is handled by `command_for`.

## Steps

### Step 1: `gameshow/osc_map.py` — shared address map (emit + receive)
- **Test:** `tools/osc_map_test.py` — `button_to_osc` returns the right `(address, arg, arg_type)`
  for each type (buzz→`/buzzer/press` INT; state→`/trigger` STRING; state=timed_lockout→
  `/buzzer/timed_lockout` FLOAT; lighting→`/lighting/cue`; obs_scene→`/obs/scene`; set_award→
  `/award/set`; countdown pause/resume/reset/cancel/toggle→`/countdown/<action>`; stop_sounds→two
  sends; display/page/return→`[]`). `command_for` maps each address+args back to the right bus
  event (`BuzzerPressed` for `/buzzer/press`, else `ControlCommand`).
- **Implement:** `gameshow/osc_map.py`.
- **Code:**
```python
from dataclasses import dataclass
from gameshow.config import ButtonConfig
from gameshow.events import ControlCommand, BuzzerPressed

ADDR_TRIGGER, ADDR_BUZZ, ADDR_LIGHTING = "/trigger", "/buzzer/press", "/lighting/cue"
ADDR_OBS_SCENE, ADDR_AWARD = "/obs/scene", "/award/set"

@dataclass(frozen=True)
class OscSend:
    address: str
    arg: object | None = None      # None -> plain trigger button (const "1", FLOAT)
    arg_type: str = "FLOAT"        # FLOAT|INT|STRING for the .tosc <arguments> partial

def button_to_osc(b: ButtonConfig) -> list[OscSend]:
    t = b.type
    if t == "buzz" and b.player_id is not None:
        return [OscSend(ADDR_BUZZ, b.player_id, "INT")]
    if t == "state" and b.state:
        if b.state == "timed_lockout" and b.duration:
            return [OscSend("/buzzer/timed_lockout", float(b.duration), "FLOAT")]
        return [OscSend(ADDR_TRIGGER, b.state, "STRING")]
    if t == "countdown" and b.action in {"pause", "resume", "reset", "cancel", "toggle"}:
        return [OscSend(f"/countdown/{b.action}")]
    # ... reset_buzzer, scene_*, sound, stop_sounds(2), lighting, obs_scene,
    #     set_award, config_reload; display/page/return -> []
    return []

def command_for(address: str, args: list) -> object | None:
    if address == ADDR_BUZZ:
        return BuzzerPressed(player_id=int(args[0]))
    if address == ADDR_TRIGGER:
        return ControlCommand(command=str(args[0]))
    # ... map remaining addresses -> ControlCommand(command, args)
    return None
```
- **Validation:** `poetry run pytest tools/osc_map_test.py`

### Step 2: extend `osc_server.py` — register osc_map routes + new feedback
- **Test:** `tests/osc_server_test.py` — sending `/trigger three_strikes`, `/buzzer/press 2`,
  `/lighting/cue /x`, `/obs/scene S`, `/award/set 50`, `/countdown/pause`, `/countdown/toggle`
  each publishes the expected bus event; `CountdownTick` publishes `/feedback/countdown`.
- **Implement:** in `start()`, register every address from `osc_map` and dispatch via
  `command_for`; add `CountdownTick` subscription; keep bespoke handlers. Add `countdown_toggle`
  to `state_machine.py` `_COUNTDOWN_CONTROLS` + `_handle_countdown_control` (toggle on
  `self._countdown.paused`).
- **Code:**
```python
async def _dispatch(self, address, args):
    event = command_for(address, args)
    if event is not None:
        await self._bus.publish(event); return
    # ... existing bespoke branches (config/list, config/load, goto, audio) unchanged

async def _on_tick(self, event: CountdownTick) -> None:
    text = str(math.ceil(event.remaining))
    if text != self._last_countdown_text:      # dedupe: one packet per second
        self._last_countdown_text = text
        self._feedback("/feedback/countdown", text)
```
- **Depends on:** Step 1
- **Constraint:** `obs_request` JSON arg parsed with `try/except (ValueError, TypeError)`.
- **Validation:** `poetry run pytest tests/osc_server_test.py`

### Step 3: anti-drift test (emit ⊆ receive)
- **Test:** `tests/osc_parity_test.py` — load `shows/family_feud.yaml` via `gameshow.config`,
  walk `control_surface.root` + all nested pages, collect every `OscSend.address` from
  `button_to_osc`, assert `command_for(address, dummy_args)` is not None for each (i.e. the server
  handles everything the generator emits).
- **Implement:** none (test only) — reuse the page-walk helper from Step 4.
- **Depends on:** Step 1
- **Validation:** `poetry run pytest tests/osc_parity_test.py`

### Step 4: config-driven generator
- **Test:** `tools/generate_touchosc_test.py` (replace diagnostic script) — build from
  `shows/family_feud.yaml`; assert: output is valid zlib→XML `lexml`; one PAGER; a PAGE per page
  (Main, Sounds, More, Timer, OBS, Lights); buzz/state/lighting/obs buttons carry the addresses
  from `button_to_osc`; display buttons carry `_osc_receive` on the right `/feedback/*`.
- **Implement:** rewrite `tools/generate_touchosc.py`: `load_show()` → walk pages
  (root + descendants via `button.page`) into a flat list; for each page add a PAGE; place buttons
  on a 3×5 grid by `button.key`; emit `button_to_osc` sends (or `feedback_label` for
  `*_display`/countdown-display, mapped type→`/feedback/*`). CLI:
  `generate_touchosc.py [show.yaml] [out.tosc]` (defaults: config.yaml's `default_show`,
  `gameshow-control.tosc`). Reuse existing factories + PAGER/PAGE from the old test script.
- **Code:**
```python
GRID_COLS = 5
def _slot_xy(key, cell_w, cell_h, x0, y0):
    return x0 + (key % GRID_COLS) * cell_w, y0 + (key // GRID_COLS) * cell_h

_FEEDBACK = {"state_display": "/feedback/state", "scene_current": "/feedback/scene",
             "countdown": "/feedback/countdown", "score_display": "/feedback/score/1",
             "counter_display": None}  # counter_display -> f"/feedback/counter/{b.counter}"

def emit_button(page_ch, b, x, y, w, h):
    if b.type in _FEEDBACK or (b.type == "countdown" and (b.action or "display") == "display"):
        feedback_label(page_ch, x, y, w, h, _feedback_addr(b)); return
    sends = button_to_osc(b)
    if not sends:  # page/return handled by the PAGER tab bar
        return
    grp = button(page_ch, x, y, w, h, b.label or b.name or "", sends[0].address,
                 arg_val=_arg(sends[0]))
    for extra in sends[1:]:
        _osc_send(_ms(...), extra.address, ...)   # stop_sounds' 2nd address
```
- **Depends on:** Step 1
- **Validation:** `poetry run pytest tools/generate_touchosc_test.py` and
  `poetry run python tools/generate_touchosc.py && python -c "import zlib;
  zlib.decompress(open('gameshow-control.tosc','rb').read())"`

## Acceptance Criteria

- [ ] `generate_touchosc.py <show.yaml>` produces a `.tosc` whose tabs/buttons mirror that show's
      `control_surface:` tree (verified against `family_feud.yaml`).
- [ ] Every Stream Deck button type has a working TouchOSC equivalent (buzz, arbitrary state,
      lighting, obs_scene, obs_request, set_award, countdown controls) — no dead buttons.
- [ ] Timer/state/scene/counter display labels update from `/feedback/*` (incl. new
      `/feedback/countdown`).
- [ ] Anti-drift test passes: generator emits no address the server can't handle.
- [ ] All tests passing; flake8 clean.

## Checklist (non-TDD cleanup)

- [ ] flake8 clean (type hints, no bare except)
- [ ] Update the OSC address reference comment block in `shows/family_feud.yaml` with the new
      inbound routes (`/trigger`, `/buzzer/press`, `/lighting/cue`, `/obs/scene`, `/award/set`,
      `/countdown/*`, `/feedback/countdown`)
- [ ] Remove stale `test1/2/3-*.tosc` artifacts if regenerated
