from __future__ import annotations
import asyncio
import logging
from typing import Callable, Optional
from pynput import keyboard
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.events import BuzzerPressed

log = logging.getLogger(__name__)


class KeyboardListener:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._listener: Optional[keyboard.Listener] = None

    def _build_key_map(self) -> dict[str, int]:
        return {
            p.key: p.id
            for p in self._config().buzzers.players
            if p.enabled
        }

    async def _on_key(self, key_char: str) -> None:
        key_map = self._build_key_map()
        player_id = key_map.get(key_char)
        if player_id is not None:
            log.debug("Key %r → player %d buzzer", key_char, player_id)
            await self._bus.publish(BuzzerPressed(player_id=player_id))

    def _handle_key(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        try:
            char = key.char
        except AttributeError:
            return
        if char and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_key(char), self._loop)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._listener = keyboard.Listener(on_press=self._handle_key)
        self._listener.start()
        log.info("Keyboard listener started")

    async def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            log.info("Keyboard listener stopped")
