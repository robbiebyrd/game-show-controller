from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re
import yaml


VALID_RETURN_TARGETS = {"idle", "allow_next"}


@dataclass
class ServiceConfig:
    osc_server_host: str = "0.0.0.0"
    osc_server_port: int = 21601
    dmx_osc_host: str = "localhost"
    dmx_osc_port: int = 21600
    obs_host: str = "localhost"
    obs_port: int = 4455
    obs_password: str = ""
    touchosc_host: str = ""
    touchosc_port: int = 9000


@dataclass
class PlayerConfig:
    id: int
    name: str
    key: str
    enabled: bool = True


@dataclass
class BuzzerConfig:
    players: list[PlayerConfig]
    buzz_timeout_seconds: Optional[float] = 10.0


@dataclass
class StateMachineConfig:
    return_to_after_correct: str = "idle"
    return_to_after_incorrect: str = "idle"
    return_to_after_round_start: str = "idle"
    correct_hold_seconds: float = 2.0
    incorrect_hold_seconds: float = 2.0
    buzz_timeout_hold_seconds: float = 0.5
    round_start_hold_seconds: float = 2.0


@dataclass
class LightingConfig:
    states: dict[str, str] = field(default_factory=dict)


@dataclass
class AudioStateEntry:
    effect: Optional[str] = None
    background: Optional[str] = None


@dataclass
class AudioConfig:
    default_background_volume: float = 0.7
    default_effect_volume: float = 1.0
    states: dict[str, AudioStateEntry] = field(default_factory=dict)


@dataclass
class OBSConfig:
    states: dict[str, str] = field(default_factory=dict)


@dataclass
class OnEnterConfig:
    audio_background: Optional[str] = None
    obs_scene: Optional[str] = None
    lighting: Optional[str] = None


@dataclass
class SceneConfig:
    name: str
    on_enter: OnEnterConfig = field(default_factory=OnEnterConfig)
    _raw_override: dict = field(default_factory=dict, repr=False)


@dataclass
class PressedStyle:
    """Appearance/value overrides applied while a button is held down.

    Every field is optional; only the ones set replace the button's own values
    for the duration of the press, reverting on release. Field names mirror the
    matching ``ButtonConfig`` fields so they layer directly on top of it.
    """
    label: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    text_color: Optional[str] = None
    font_path: Optional[str] = None
    font_size: Optional[int] = None
    fa_icon: Optional[str] = None
    fa_type: Optional[str] = None
    fa_weight: Optional[str] = None
    fa_size: Optional[int] = None
    fa_color: Optional[str] = None
    label_align: Optional[str] = None
    label_wrap: Optional[bool] = None
    label_marquee: Optional[bool] = None


@dataclass
class ButtonConfig:
    type: str
    name: Optional[str] = None           # mapping key from config, for reference/logging
    label: str = ""
    icon: Optional[str] = None
    color: Optional[str] = None          # key background
    text_color: Optional[str] = None     # label color; overrides surface text_color
    font_path: Optional[str] = None      # per-button TTF; overrides surface font_path
    font_size: Optional[int] = None      # per-button size; overrides surface font_size
    fa_icon: Optional[str] = None        # Font Awesome icon name, e.g. "circle-user"
    fa_type: Optional[str] = None        # pro|brands|duotone|sharp|sharp-duotone
    fa_weight: Optional[str] = None      # solid|regular|light|thin (where applicable)
    fa_size: Optional[int] = None        # icon pixel size
    fa_color: Optional[str] = None       # icon color; defaults to the text color
    label_align: Optional[str] = None    # top|center|bottom; overrides surface label_align
    label_wrap: Optional[bool] = None    # word-wrap the label; overrides surface label_wrap
    label_marquee: Optional[bool] = None  # scroll overflowing text; overrides label_marquee
    key: Optional[int] = None            # explicit slot 0-14; otherwise auto-placed
    state: Optional[str] = None          # clear|game_over|round_start|correct|incorrect|allow_next|timed_lockout
    player_id: Optional[int] = None      # buzz
    path: Optional[str] = None           # sound file
    osc: Optional[str] = None            # dmx cue address
    scene: Optional[str] = None          # obs scene name
    target: Optional[object] = None      # scene_goto: name (str) or index (int)
    duration: Optional[float] = None     # timed_lockout / countdown
    action: Optional[str] = None         # countdown: display|toggle|pause|resume|reset|cancel
    request_type: Optional[str] = None   # obs_request
    request_data: Optional[dict] = None  # obs_request payload
    page: Optional["PageConfig"] = None  # page/folder target
    pressed: Optional[PressedStyle] = None  # overrides applied while held down


@dataclass
class PageConfig:
    buttons: list[ButtonConfig] = field(default_factory=list)


@dataclass
class ControlSurfaceConfig:
    enabled: bool = True
    brightness: int = 60
    serial: Optional[str] = None
    color: str = "black"                 # default key background (per-button wins)
    text_color: str = "white"            # default label color (per-button wins)
    font_path: Optional[str] = None      # default TTF for all buttons
    font_size: int = 16                  # default label size (per-button wins)
    fa_path: Optional[str] = None        # Font Awesome asset dir (webfonts/ + metadata/icon-families.json)
    fa_type: str = "pro"                 # default icon family (per-button wins)
    fa_weight: str = "solid"             # default icon weight (per-button wins)
    fa_size: Optional[int] = None        # default icon size (per-button wins)
    fa_color: Optional[str] = None       # default icon color (per-button wins)
    label_align: str = "bottom"          # top|center|bottom (per-button wins)
    label_wrap: bool = False             # word-wrap labels (per-button wins)
    label_marquee: bool = True           # scroll overflowing labels (per-button wins)
    root: PageConfig = field(default_factory=PageConfig)


@dataclass
class AppConfig:
    service: ServiceConfig
    buzzers: BuzzerConfig
    state_machine: StateMachineConfig
    lighting: LightingConfig
    audio: AudioConfig
    obs: OBSConfig
    scenes: list[SceneConfig] = field(default_factory=list)
    control_surface: Optional[ControlSurfaceConfig] = None


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key == "players" and isinstance(value, list):
            base_players = {p["id"]: dict(p) for p in result.get("players", [])}
            for player_override in value:
                pid = player_override["id"]
                if pid in base_players:
                    base_players[pid].update(player_override)
                else:
                    base_players[pid] = dict(player_override)
            result["players"] = list(base_players.values())
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def apply_scene_override(base_raw: dict, scene_raw: dict) -> dict:
    override = {k: v for k, v in scene_raw.items() if k not in ("name", "on_enter")}
    if "buzzers" in override:
        buzzers = dict(override["buzzers"])
        if "all_enabled" in buzzers:
            all_enabled = buzzers.pop("all_enabled")
            base_players = base_raw.get("buzzers", {}).get("players", [])
            shorthand = [{"id": p["id"], "enabled": all_enabled} for p in base_players]
            existing_ids = {p["id"] for p in buzzers.get("players", [])}
            extra = [p for p in shorthand if p["id"] not in existing_ids]
            buzzers["players"] = extra + buzzers.get("players", [])
        override["buzzers"] = buzzers
    return deep_merge(base_raw, override)


def _validate_return_targets(sm: StateMachineConfig) -> None:
    for attr in ("return_to_after_correct", "return_to_after_incorrect",
                 "return_to_after_round_start"):
        value = getattr(sm, attr)
        if value not in VALID_RETURN_TARGETS:
            raise ValueError(
                f"{attr}='{value}' is not valid; must be one of {sorted(VALID_RETURN_TARGETS)}"
            )


_BUTTON_KEY_RE = re.compile(r"button_(\d+)$")


def _key_from_name(name: str) -> Optional[int]:
    """Derive a key slot from a ``button_<N>`` name, else None."""
    match = _BUTTON_KEY_RE.match(name or "")
    return int(match.group(1)) if match else None


def _parse_pressed(raw: dict) -> PressedStyle:
    return PressedStyle(**{k: v for k, v in raw.items()
                           if k in PressedStyle.__dataclass_fields__})


def _parse_button(name: str, raw: dict) -> ButtonConfig:
    page = _parse_page(raw["page"]) if isinstance(raw.get("page"), dict) else None
    pressed = _parse_pressed(raw["pressed"]) if isinstance(raw.get("pressed"), dict) else None
    nested = ("page", "pressed")
    fields = {k: v for k, v in raw.items()
              if k in ButtonConfig.__dataclass_fields__ and k not in nested}
    fields.setdefault("name", name)
    # The slot is derived from a "button_<N>" name; an explicit `key` wins.
    if "key" not in fields:
        derived = _key_from_name(name)
        if derived is not None:
            fields["key"] = derived
    return ButtonConfig(page=page, pressed=pressed, **fields)


def _parse_page(raw: dict) -> PageConfig:
    # ``buttons`` is a mapping of name -> button spec; iteration preserves the
    # YAML declaration order, which drives auto-placement.
    buttons_raw = raw.get("buttons", {}) or {}
    return PageConfig(buttons=[_parse_button(name, spec)
                               for name, spec in buttons_raw.items()])


def _parse_control_surface(raw: dict) -> ControlSurfaceConfig:
    return ControlSurfaceConfig(
        enabled=raw.get("enabled", True),
        brightness=raw.get("brightness", 60),
        serial=raw.get("serial"),
        color=raw.get("color", "black"),
        text_color=raw.get("text_color", "white"),
        font_path=raw.get("font_path"),
        font_size=raw.get("font_size", 16),
        fa_path=raw.get("fa_path"),
        fa_type=raw.get("fa_type", "pro"),
        fa_weight=raw.get("fa_weight", "solid"),
        fa_size=raw.get("fa_size"),
        fa_color=raw.get("fa_color"),
        label_align=raw.get("label_align", "bottom"),
        label_wrap=raw.get("label_wrap", False),
        label_marquee=raw.get("label_marquee", True),
        root=_parse_page(raw.get("root", {})),
    )


def parse_config(raw: dict) -> AppConfig:
    svc_raw = raw.get("service", {})
    service = ServiceConfig(**{k: v for k, v in svc_raw.items()
                               if k in ServiceConfig.__dataclass_fields__})

    bz_raw = raw.get("buzzers", {})
    players = [PlayerConfig(**{k: v for k, v in p.items()
                               if k in PlayerConfig.__dataclass_fields__})
               for p in bz_raw.get("players", [])]
    buzzers = BuzzerConfig(
        players=players,
        buzz_timeout_seconds=bz_raw.get("buzz_timeout_seconds", 10.0),
    )

    sm_raw = raw.get("state_machine", {})
    state_machine = StateMachineConfig(**{k: v for k, v in sm_raw.items()
                                         if k in StateMachineConfig.__dataclass_fields__})
    _validate_return_targets(state_machine)

    lighting = LightingConfig(states=raw.get("lighting", {}).get("states", {}))

    audio_raw = raw.get("audio", {})
    audio_states = {
        k: AudioStateEntry(effect=v.get("effect"), background=v.get("background"))
        for k, v in audio_raw.get("states", {}).items()
    }
    audio = AudioConfig(
        default_background_volume=audio_raw.get("default_background_volume", 0.7),
        default_effect_volume=audio_raw.get("default_effect_volume", 1.0),
        states=audio_states,
    )

    obs = OBSConfig(states=raw.get("obs", {}).get("states", {}))

    scenes = []
    for s in raw.get("show", {}).get("scenes", []):
        on_enter_raw = s.get("on_enter", {})
        on_enter = OnEnterConfig(
            audio_background=on_enter_raw.get("audio_background"),
            obs_scene=on_enter_raw.get("obs_scene"),
            lighting=on_enter_raw.get("lighting"),
        )
        raw_override = {k: v for k, v in s.items() if k != "name"}
        scenes.append(SceneConfig(name=s["name"], on_enter=on_enter,
                                  _raw_override=raw_override))

    cs_raw = raw.get("control_surface")
    control_surface = _parse_control_surface(cs_raw) if cs_raw is not None else None

    return AppConfig(
        service=service, buzzers=buzzers, state_machine=state_machine,
        lighting=lighting, audio=audio, obs=obs, scenes=scenes,
        control_surface=control_surface,
    )


def load_config(path: str) -> tuple[dict, AppConfig]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw, parse_config(raw)
