from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
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
class AppConfig:
    service: ServiceConfig
    buzzers: BuzzerConfig
    state_machine: StateMachineConfig
    lighting: LightingConfig
    audio: AudioConfig
    obs: OBSConfig
    scenes: list[SceneConfig] = field(default_factory=list)


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

    return AppConfig(
        service=service, buzzers=buzzers, state_machine=state_machine,
        lighting=lighting, audio=audio, obs=obs, scenes=scenes,
    )


def load_config(path: str) -> tuple[dict, AppConfig]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw, parse_config(raw)
