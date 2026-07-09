from __future__ import annotations
import asyncio
import logging
import math
from typing import Any, Callable
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from gameshow.bus import EventBus
from gameshow.config import AppConfig
from gameshow.osc_map import command_for, INBOUND_ADDRESSES
from gameshow.shows import list_shows
from gameshow.events import (
    ControlCommand, SceneChanged, StateChanged, PlayerBuzzed,
    ScoreChanged, AwardChanged, CounterChanged, ConfigReloaded, CountdownTick,
)

# States after which the on-screen player label is cleared (the round's result
# is in, so nobody is "buzzed in" anymore). These are conventional state names;
# renaming them in config simply means the label won't auto-clear on them.
_PLAYER_RESET_STATES = {"correct", "incorrect", "idle"}

log = logging.getLogger(__name__)

_SIMPLE_COMMANDS = {
    "/buzzer/clear": "clear",
    "/buzzer/allow_next": "allow_next",
    "/buzzer/correct": "correct",
    "/buzzer/incorrect": "incorrect",
    "/buzzer/round_start": "round_start",
    "/buzzer/game_over": "game_over",
    "/show/advance": "scene_advance",
    "/show/previous": "scene_previous",
    "/show/current": "scene_current",
    "/audio/background/stop": "audio_bg_stop",
    "/audio/background/pause": "audio_bg_pause",
    "/audio/background/resume": "audio_bg_resume",
    "/audio/effect/stop": "audio_fx_stop",
}


class OSCServer:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig]) -> None:
        self._bus = bus
        self._config = config
        self._loop: asyncio.AbstractEventLoop | None = None
        self._transport = None
        self._protocol = None
        self._feedback_client: SimpleUDPClient | None = None
        self._last_countdown_text: str | None = None
        self._setup_feedback()
        self._setup_feedback_subscriptions()

    def _setup_feedback(self) -> None:
        svc = self._config().service
        if svc.touchosc_host:
            self._feedback_client = SimpleUDPClient(svc.touchosc_host, svc.touchosc_port)
            log.info("OSC feedback client → %s:%d", svc.touchosc_host, svc.touchosc_port)

    def _feedback(self, address: str, *args: Any) -> None:
        if self._feedback_client:
            log.info("OUT OSC %s %s", address, list(args))
            self._feedback_client.send_message(address, list(args))

    def _setup_feedback_subscriptions(self) -> None:
        self._bus.subscribe(StateChanged, self._on_state_changed)
        self._bus.subscribe(PlayerBuzzed, self._on_player_buzzed)
        self._bus.subscribe(SceneChanged, self._on_scene_changed)
        self._bus.subscribe(ScoreChanged, self._on_score_changed)
        self._bus.subscribe(AwardChanged, self._on_award_changed)
        self._bus.subscribe(CounterChanged, self._on_counter_changed)
        self._bus.subscribe(ConfigReloaded, self._on_config_reloaded)
        self._bus.subscribe(CountdownTick, self._on_tick)

    async def _on_state_changed(self, event: StateChanged) -> None:
        self._feedback("/feedback/state", event.new_state)
        if event.duration is not None:
            self._feedback("/feedback/timed_lockout/duration", event.duration)
        if event.new_state in _PLAYER_RESET_STATES:
            self._feedback("/feedback/player", "None")

    async def _on_player_buzzed(self, event: PlayerBuzzed) -> None:
        self._feedback("/feedback/player", f"{event.player_id}: {event.player_name}")

    async def _on_scene_changed(self, event: SceneChanged) -> None:
        self._feedback("/feedback/scene", f"{event.index}: {event.name}")

    async def _on_score_changed(self, event: ScoreChanged) -> None:
        self._feedback(f"/feedback/score/{event.player_id}", event.score)

    async def _on_award_changed(self, event: AwardChanged) -> None:
        self._feedback("/feedback/award", event.value if event.value is not None else "None")

    async def _on_counter_changed(self, event: CounterChanged) -> None:
        self._feedback(f"/feedback/counter/{event.name}", event.value)

    async def _on_tick(self, event: CountdownTick) -> None:
        # CountdownTick fires ~4×/sec; only send when the whole-second readout
        # actually changes so a bound label isn't flooded with duplicate packets.
        text = str(math.ceil(event.remaining))
        if text != self._last_countdown_text:
            self._last_countdown_text = text
            self._feedback("/feedback/countdown", text)

    async def _on_config_reloaded(self, event: ConfigReloaded) -> None:
        show = self._config().show
        self._feedback("/feedback/show/name", show.name or "")
        self._feedback("/feedback/show/description", show.description or "")

    async def _dispatch(self, address: str, args: list[Any]) -> None:
        log.info("IN  OSC %s %s", address, args)
        # Routes shared with the Stream Deck live in osc_map (the single source
        # of truth for button↔OSC); everything below is server-only.
        event = command_for(address, args)
        if event is not None:
            await self._bus.publish(event)
            return

        if address in _SIMPLE_COMMANDS:
            await self._bus.publish(ControlCommand(command=_SIMPLE_COMMANDS[address]))
            return

        if address == "/config/list":
            self._emit_show_list()
            return

        if address == "/config/load":
            await self._load_show_by_index(args)
            return

        if address in ("/audio/background/play", "/audio/background/volume",
                       "/audio/effect/volume"):
            arg = args[0] if args else None
            cmd = address.lstrip("/").replace("/", "_")
            await self._bus.publish(ControlCommand(command=cmd, args=(arg,) if arg is not None else ()))
            return

    def _emit_show_list(self) -> None:
        """Publish the shows/ listing as feedback so a surface can build a menu."""
        entries = list_shows()
        self._feedback("/feedback/shows/count", len(entries))
        for index, entry in enumerate(entries):
            self._feedback("/feedback/shows/item", index, entry.filename, entry.name)

    async def _load_show_by_index(self, args: list[Any]) -> None:
        """Load the Nth show from the shows/ listing (as shown by /config/list)."""
        try:
            index = int(args[0])
        except (IndexError, TypeError, ValueError):
            log.warning("IN OSC /config/load ignored: expected an integer index, got %s", args)
            return
        entries = list_shows()
        if not 0 <= index < len(entries):
            log.warning("IN OSC /config/load index %d out of range (0-%d)",
                        index, len(entries) - 1)
            return
        await self._bus.publish(
            ControlCommand(command="config_reload", args=(entries[index].filename,)))

    def _make_handler(self, address: str) -> Callable:
        def handler(addr: str, *args: Any) -> None:
            self._loop.create_task(self._dispatch(address, list(args)))
        return handler

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        cfg = self._config().service
        dispatcher = Dispatcher()
        addresses = set(_SIMPLE_COMMANDS) | set(INBOUND_ADDRESSES) | {
            "/config/list", "/config/load",
            "/audio/background/play", "/audio/background/volume",
            "/audio/effect/volume",
        }
        for address in sorted(addresses):
            dispatcher.map(address, self._make_handler(address))

        server = AsyncIOOSCUDPServer(
            (cfg.osc_server_host, cfg.osc_server_port), dispatcher, self._loop
        )
        self._transport, self._protocol = await server.create_serve_endpoint()
        log.info("OSC server listening on %s:%d", cfg.osc_server_host, cfg.osc_server_port)

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
            log.info("OSC server stopped")
