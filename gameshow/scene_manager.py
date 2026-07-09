from __future__ import annotations
import logging
from typing import Optional
import yaml
from gameshow.bus import EventBus
from gameshow.config import (
    AppConfig, SceneConfig, parse_config, apply_scene_override, load_show,
)
from gameshow.events import SceneChanged

log = logging.getLogger(__name__)


class SceneManager:
    def __init__(self, bus: EventBus, base_raw: dict, base_config: AppConfig,
                 config_path: str, service_raw: dict | None = None) -> None:
        self._bus = bus
        self._base_raw = base_raw
        self._base_config = base_config
        self.config_path = config_path  # currently-loaded config file
        self.current_index: int = 0  # 0 = no scene selected
        self._scenes: list[SceneConfig] = base_config.scenes
        self.current_config: AppConfig = base_config
        self._service_raw = service_raw or {}

    def reload(self, path: str) -> bool:
        """Hot-load a new show file, resetting to a clean (no-scene) state.

        On any load/parse failure the current config is kept untouched and
        ``False`` is returned, so a bad file can never take the service down.
        """
        try:
            base_raw, base_config = load_show(path, self._service_raw)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            log.error("Config reload from %s failed; keeping current config (%s)", path, exc)
            return False
        self._base_raw = base_raw
        self._base_config = base_config
        self._scenes = base_config.scenes
        self.current_config = base_config
        self.current_index = 0
        self.config_path = path
        log.info("Config reloaded from %s", path)
        return True

    @property
    def current_scene_name(self) -> Optional[str]:
        if self.current_index == 0:
            return None
        return self._scenes[self.current_index - 1].name

    async def advance(self) -> None:
        if self.current_index >= len(self._scenes):
            log.warning("Already at last scene; advance ignored")
            return
        await self.goto_index(self.current_index + 1)

    async def previous(self) -> None:
        if self.current_index <= 1:
            log.warning("No scene active or already at first scene; previous ignored")
            return
        await self.goto_index(self.current_index - 1)

    async def goto_index(self, index: int) -> None:
        if index < 1 or index > len(self._scenes):
            log.warning("Scene index %d out of range (1–%d); ignored", index, len(self._scenes))
            return
        self.current_index = index
        scene = self._scenes[index - 1]
        self._apply(scene)
        await self._bus.publish(SceneChanged(index=index, name=scene.name))

    async def goto_name(self, name: str) -> None:
        for i, scene in enumerate(self._scenes, start=1):
            if scene.name == name:
                await self.goto_index(i)
                return
        log.warning("Scene name %r not found; ignored", name)

    def _apply(self, scene: SceneConfig) -> None:
        merged_raw = apply_scene_override(self._base_raw, scene._raw_override)
        self.current_config = parse_config(merged_raw)
