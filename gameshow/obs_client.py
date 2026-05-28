from __future__ import annotations
import asyncio
import logging
from typing import Callable, Optional
import simpleobsws
from pythonosc.udp_client import SimpleUDPClient
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import StateChanged, ControlCommand

log = logging.getLogger(__name__)


class OBSClient:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._config = config
        self._connected = False
        svc = config().service
        self._ws = simpleobsws.WebSocketClient(
            url=f"ws://{svc.obs_host}:{svc.obs_port}",
            password=svc.obs_password,
        )
        self._feedback_client = SimpleUDPClient(svc.touchosc_host, svc.touchosc_port) if svc.touchosc_host else None
        bus.subscribe(StateChanged, self._on_state_changed)
        bus.subscribe(ControlCommand, self._on_control_command)

    async def _on_state_changed(self, event: StateChanged) -> None:
        if not self._connected:
            return
        scene_name = self._config().obs.states.get(event.new_state.name.lower())
        if not scene_name:
            return
        try:
            req = simpleobsws.Request("SetCurrentProgramScene", {"sceneName": scene_name})
            await self._ws.call(req)
        except Exception as exc:
            log.warning("OBS scene switch failed: %s", exc)

    async def start(self) -> None:
        asyncio.create_task(self._connect_loop())

    async def _connect_loop(self) -> None:
        delay = 1.0
        while True:
            try:
                await self._ws.connect()
                await self._ws.wait_until_identified()
                self._connected = True
                log.info("OBS connected")
                self._ws.register_event_callback(self._on_obs_event)
                return
            except Exception as exc:
                self._connected = False
                log.info("OBS connection failed (%s); retrying in %.0fs", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def _on_obs_event(self, event: dict) -> None:
        if event.get('eventType') == "CurrentProgramSceneChanged":
            scene_name = event.get('eventData', {}).get("sceneName", "")
            log.debug("OBS scene changed: %s", scene_name)
            if self._feedback_client:
                self._feedback_client.send_message("/feedback/obs/scene", [scene_name])

    async def _on_control_command(self, event: ControlCommand) -> None:
        if event.command == "obs_scene_set" and event.args and self._connected:
            scene_name = str(event.args[0])
            try:
                req = simpleobsws.Request("SetCurrentProgramScene", {"sceneName": scene_name})
                await self._ws.call(req)
            except Exception as exc:
                log.warning("OBS scene set failed: %s", exc)

    async def stop(self) -> None:
        if self._connected:
            self._connected = False
            await self._ws.disconnect()
