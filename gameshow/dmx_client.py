from __future__ import annotations
import logging
from typing import Callable
from pythonosc.udp_client import SimpleUDPClient
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import StateChanged, PlayerBuzzed, ControlCommand

log = logging.getLogger(__name__)


class DMXClient:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._config = config
        svc = config().service
        self._client = SimpleUDPClient(svc.dmx_osc_host, svc.dmx_osc_port)
        bus.subscribe(StateChanged, self._on_state_changed)
        bus.subscribe(PlayerBuzzed, self._on_player_buzzed)
        bus.subscribe(ControlCommand, self._on_control_command)

    def _send(self, address: str) -> None:
        log.info("OUT DMX %s", address)
        self._client.send_message(address, [])

    async def _on_state_changed(self, event: StateChanged) -> None:
        states = self._config().lighting.states
        cue = states.get(event.new_state.name.lower())
        if cue:
            self._send(cue)

    async def _on_player_buzzed(self, event: PlayerBuzzed) -> None:
        states = self._config().lighting.states
        key = f"player_{event.player_id}_buzz"
        cue = states.get(key)
        if cue:
            self._send(cue)

    async def _on_control_command(self, event: ControlCommand) -> None:
        if event.command == "dmx_cue" and event.args:
            self._send(str(event.args[0]))
