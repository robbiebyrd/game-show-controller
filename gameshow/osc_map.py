"""Single source of truth for the button ↔ OSC address mapping.

Both the TouchOSC generator (``tools/generate_touchosc.py``) and the OSC server
(``gameshow/osc_server.py``) import this module, so a TouchOSC control and the
server route it triggers can never drift apart:

- ``button_to_osc`` — emit side: what OSC message(s) a Stream Deck button sends.
- ``command_for``   — receive side: the bus event an inbound OSC message becomes.

Keeping both directions here guarantees every address the generator can emit is
an address the server knows how to handle (asserted by tests/test_osc_parity).
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Optional
from gameshow.config import ButtonConfig
from gameshow.events import ControlCommand, BuzzerPressed

log = logging.getLogger(__name__)

# ── Inbound OSC addresses (TouchOSC → server) ──────────────────────────────
ADDR_BUZZ = "/buzzer/press"
ADDR_CLEAR = "/buzzer/clear"
ADDR_TIMED_LOCKOUT = "/buzzer/timed_lockout"
ADDR_TRIGGER = "/trigger"                    # arg: any state-machine trigger name
ADDR_SCENE_ADVANCE = "/show/advance"
ADDR_SCENE_PREVIOUS = "/show/previous"
ADDR_SCENE_GOTO = "/show/goto"               # arg: scene name (str) or index (int)
ADDR_EFFECT_PLAY = "/audio/effect/play"
ADDR_EFFECT_STOP = "/audio/effect/stop"
ADDR_BG_STOP = "/audio/background/stop"
ADDR_LIGHTING = "/lighting/cue"              # arg: DMX cue OSC address
ADDR_OBS_SCENE = "/obs/scene"
ADDR_OBS_REQUEST = "/obs/request"            # args: request type [, JSON data]
ADDR_AWARD_SET = "/award/set"
ADDR_CONFIG_RELOAD = "/config/reload"

_COUNTDOWN_ACTIONS = ("pause", "resume", "reset", "cancel", "toggle")
COUNTDOWN_ADDRS = {a: f"/countdown/{a}" for a in _COUNTDOWN_ACTIONS}

# Argument-type tokens for the .tosc <arguments> partial.
FLOAT, INT, STRING = "FLOAT", "INT", "STRING"

# Every inbound address the server must register a handler for.
INBOUND_ADDRESSES = (
    ADDR_BUZZ, ADDR_CLEAR, ADDR_TIMED_LOCKOUT, ADDR_TRIGGER,
    ADDR_SCENE_ADVANCE, ADDR_SCENE_PREVIOUS, ADDR_SCENE_GOTO,
    ADDR_EFFECT_PLAY, ADDR_EFFECT_STOP, ADDR_BG_STOP,
    ADDR_LIGHTING, ADDR_OBS_SCENE, ADDR_OBS_REQUEST,
    ADDR_AWARD_SET, ADDR_CONFIG_RELOAD,
) + tuple(COUNTDOWN_ADDRS.values())


@dataclass(frozen=True)
class OscSend:
    """One OSC message a button sends. ``arg=None`` means a plain trigger button
    (the .tosc emits a constant ``1``); otherwise ``arg`` is sent as ``arg_type``."""
    address: str
    arg: Optional[object] = None
    arg_type: str = FLOAT


def button_to_osc(button: ButtonConfig) -> list[OscSend]:
    """The OSC message(s) a Stream Deck button would send from TouchOSC.

    Returns ``[]`` for display-only and navigation buttons (countdown/scene/
    state/score/counter displays, page, return), which carry no outbound OSC."""
    t = button.type
    if t == "reset_buzzer":
        return [OscSend(ADDR_CLEAR)]
    if t == "buzz" and button.player_id is not None:
        return [OscSend(ADDR_BUZZ, button.player_id, INT)]
    if t == "state" and button.state:
        if button.state == "timed_lockout" and button.duration:
            return [OscSend(ADDR_TIMED_LOCKOUT, float(button.duration), FLOAT)]
        return [OscSend(ADDR_TRIGGER, button.state, STRING)]
    if t == "scene_advance":
        return [OscSend(ADDR_SCENE_ADVANCE)]
    if t == "scene_previous":
        return [OscSend(ADDR_SCENE_PREVIOUS)]
    if t == "scene_goto" and button.target is not None:
        arg_type = INT if isinstance(button.target, int) else STRING
        return [OscSend(ADDR_SCENE_GOTO, button.target, arg_type)]
    if t == "sound" and button.path:
        return [OscSend(ADDR_EFFECT_PLAY, button.path, STRING)]
    if t == "stop_sounds":
        return [OscSend(ADDR_EFFECT_STOP), OscSend(ADDR_BG_STOP)]
    if t == "lighting" and button.osc:
        return [OscSend(ADDR_LIGHTING, button.osc, STRING)]
    if t == "obs_scene" and button.scene:
        return [OscSend(ADDR_OBS_SCENE, button.scene, STRING)]
    if t == "obs_request" and button.request_type:
        return [OscSend(ADDR_OBS_REQUEST, button.request_type, STRING)]
    if t == "set_award" and button.value is not None:
        return [OscSend(ADDR_AWARD_SET, float(button.value), FLOAT)]
    if t == "config_reload" and button.config:
        return [OscSend(ADDR_CONFIG_RELOAD, button.config, STRING)]
    if t == "countdown":
        action = button.action or "display"
        if action in COUNTDOWN_ADDRS:
            return [OscSend(COUNTDOWN_ADDRS[action])]
    return []


def _parse_obs_data(raw: object) -> Optional[dict]:
    """Decode the optional JSON payload of an /obs/request; drop it if malformed."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        log.warning("Ignoring malformed /obs/request JSON data: %r", raw)
        return None
    return data if isinstance(data, dict) else None


def command_for(address: str, args: list) -> Optional[object]:
    """Translate an inbound OSC ``(address, args)`` into the bus event to publish,
    or ``None`` if this module does not own the address (server handles it)."""
    a0 = args[0] if args else None
    if address == ADDR_BUZZ:
        return BuzzerPressed(player_id=int(a0))
    if address == ADDR_CLEAR:
        return ControlCommand(command="clear")
    if address == ADDR_TIMED_LOCKOUT:
        return ControlCommand(command="timed_lockout",
                              args=(float(a0),) if a0 is not None else ())
    if address == ADDR_TRIGGER and a0 is not None:
        return ControlCommand(command=str(a0))
    if address == ADDR_SCENE_ADVANCE:
        return ControlCommand(command="scene_advance")
    if address == ADDR_SCENE_PREVIOUS:
        return ControlCommand(command="scene_previous")
    if address == ADDR_SCENE_GOTO and a0 is not None:
        cmd = "scene_goto_index" if isinstance(a0, int) else "scene_goto_name"
        return ControlCommand(command=cmd, args=(a0,))
    if address == ADDR_EFFECT_PLAY and a0 is not None:
        return ControlCommand(command="audio_effect_play", args=(a0,))
    if address == ADDR_EFFECT_STOP:
        return ControlCommand(command="audio_fx_stop")
    if address == ADDR_BG_STOP:
        return ControlCommand(command="audio_bg_stop")
    if address == ADDR_LIGHTING and a0 is not None:
        return ControlCommand(command="dmx_cue", args=(a0,))
    if address == ADDR_OBS_SCENE and a0 is not None:
        return ControlCommand(command="obs_scene_set", args=(a0,))
    if address == ADDR_OBS_REQUEST and a0 is not None:
        data = _parse_obs_data(args[1]) if len(args) > 1 else None
        return ControlCommand(command="obs_request",
                              args=(a0, data) if data is not None else (a0,))
    if address == ADDR_AWARD_SET and a0 is not None:
        return ControlCommand(command="set_award", args=(float(a0),))
    if address == ADDR_CONFIG_RELOAD:
        return ControlCommand(command="config_reload",
                              args=(str(a0),) if a0 is not None else ())
    for action, addr in COUNTDOWN_ADDRS.items():
        if address == addr:
            return ControlCommand(command=f"countdown_{action}")
    return None
