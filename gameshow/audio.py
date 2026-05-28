from __future__ import annotations
from typing import Callable
import pygame
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from pythonosc.udp_client import SimpleUDPClient
from gameshow.events import StateChanged, PlayerBuzzed, ControlCommand

_BG_CHANNEL = 0
_FX_CHANNEL = 1


class AudioEngine:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._config = config
        pygame.mixer.init()
        self._bg = pygame.mixer.Channel(_BG_CHANNEL)
        self._fx = pygame.mixer.Channel(_FX_CHANNEL)
        svc = config().service
        self._feedback_client = SimpleUDPClient(svc.touchosc_host, svc.touchosc_port) if svc.touchosc_host else None
        bus.subscribe(StateChanged, self._on_state_changed)
        bus.subscribe(PlayerBuzzed, self._on_player_buzzed)
        bus.subscribe(ControlCommand, self._on_control_command)

    def _feedback(self, address: str, *args) -> None:
        if self._feedback_client:
            self._feedback_client.send_message(address, list(args))

    def _play_effect(self, path: str) -> None:
        sound = pygame.mixer.Sound(path)
        cfg = self._config().audio
        self._fx.set_volume(cfg.default_effect_volume)
        self._fx.play(sound)
        self._feedback("/feedback/audio/effect/state", "playing")
        self._feedback("/feedback/audio/effect/track", path)

    def _play_background(self, path: str) -> None:
        sound = pygame.mixer.Sound(path)
        cfg = self._config().audio
        self._bg.stop()
        self._bg.set_volume(cfg.default_background_volume)
        self._bg.play(sound, loops=-1)
        self._feedback("/feedback/audio/background/state", "playing")
        self._feedback("/feedback/audio/background/track", path)

    def _handle_audio_state(self, state_key: str) -> None:
        entry = self._config().audio.states.get(state_key)
        if not entry:
            return
        if entry.effect:
            self._play_effect(entry.effect)
        if entry.background:
            self._play_background(entry.background)

    async def _on_state_changed(self, event: StateChanged) -> None:
        self._handle_audio_state(event.new_state.name.lower())

    async def _on_player_buzzed(self, event: PlayerBuzzed) -> None:
        self._handle_audio_state(f"player_{event.player_id}_buzz")

    async def _on_control_command(self, event: ControlCommand) -> None:
        if event.command == "audio_bg_stop":
            self._bg.stop()
            self._feedback("/feedback/audio/background/state", "stopped")
        elif event.command == "audio_fx_stop":
            self._fx.stop()
            self._feedback("/feedback/audio/effect/state", "stopped")
        elif event.command == "audio_background_play" and event.args:
            self._play_background(str(event.args[0]))
        elif event.command == "audio_effect_play" and event.args:
            self._play_effect(str(event.args[0]))
        elif event.command == "audio_background_volume" and event.args:
            self._bg.set_volume(float(event.args[0]))
        elif event.command == "audio_effect_volume" and event.args:
            self._fx.set_volume(float(event.args[0]))
