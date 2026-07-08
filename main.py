import asyncio
import logging
import os
import signal
from gameshow.config import load_config
from gameshow.bus import EventBus
from gameshow.state_machine import StateMachine
from gameshow.scene_manager import SceneManager
from gameshow.keyboard import KeyboardListener
from gameshow.osc_server import OSCServer
from gameshow.dmx_client import DMXClient
from gameshow.audio import AudioEngine
from gameshow.obs_client import OBSClient
from gameshow.control_surface import ControlSurface
from gameshow.events import ControlCommand, SceneChanged, ConfigReloaded

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

CONFIG_PATH = "config.yaml"
SHOWS_DIR = "shows"  # bare show names in a reload command resolve here


def resolve_show_path(arg: str) -> str:
    """Resolve a reload target: an absolute or already-existing path is used
    as-is; a bare name is looked up under ``shows/``."""
    if os.path.isabs(arg) or os.path.exists(arg):
        return arg
    return os.path.join(SHOWS_DIR, arg)


async def main() -> None:
    base_raw, base_config = load_config(CONFIG_PATH)
    bus = EventBus()

    scene_manager = SceneManager(bus, base_raw, base_config, CONFIG_PATH)
    def config_fn():
        return scene_manager.current_config

    state_machine = StateMachine(bus, config_fn)
    keyboard = KeyboardListener(bus, config_fn)
    osc_server = OSCServer(bus, config_fn)
    DMXClient(bus, config_fn)
    AudioEngine(bus, config_fn)
    obs_client = OBSClient(bus, config_fn)
    control_surface = ControlSurface(bus, config_fn)

    # Wire on_enter actions when a scene activates.
    # DMXClient handles "dmx_cue"; OBSClient handles "obs_scene_set".
    async def on_scene_changed(event: SceneChanged) -> None:
        scene = next((s for s in scene_manager.current_config.scenes
                      if s.name == event.name), None)
        if not scene or not scene.on_enter:
            return
        oe = scene.on_enter
        if oe.audio_background:
            await bus.publish(ControlCommand(command="audio_background_play", args=(oe.audio_background,)))
        if oe.obs_scene:
            await bus.publish(ControlCommand(command="obs_scene_set", args=(oe.obs_scene,)))
        if oe.lighting:
            await bus.publish(ControlCommand(command="dmx_cue", args=(oe.lighting,)))

    bus.subscribe(SceneChanged, on_scene_changed)

    # Wire scene commands from OSC to SceneManager
    async def on_control(event: ControlCommand) -> None:
        if event.command == "scene_advance":
            await scene_manager.advance()
        elif event.command == "scene_previous":
            await scene_manager.previous()
        elif event.command == "scene_goto_index" and event.args:
            await scene_manager.goto_index(int(event.args[0]))
        elif event.command == "scene_goto_name" and event.args:
            await scene_manager.goto_name(str(event.args[0]))
        elif event.command == "scene_current":
            await bus.publish(SceneChanged(
                index=scene_manager.current_index,
                name=scene_manager.current_scene_name or "",
            ))
        elif event.command == "config_reload":
            target = str(event.args[0]) if event.args else scene_manager.config_path
            path = resolve_show_path(target)
            if scene_manager.reload(path):
                await bus.publish(ConfigReloaded(path=path))

    bus.subscribe(ControlCommand, on_control)

    await state_machine.start()
    await keyboard.start()
    await osc_server.start()
    await obs_client.start()
    await control_surface.start()

    log.info("Game show control service running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()

    log.info("Shutting down...")
    await keyboard.stop()
    await state_machine.stop()
    await osc_server.stop()
    await obs_client.stop()
    await control_surface.stop()


if __name__ == "__main__":
    asyncio.run(main())
