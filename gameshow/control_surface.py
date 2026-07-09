from __future__ import annotations
import asyncio
import dataclasses
import json
import logging
import math
import os
from typing import Callable, Optional
from PIL import ImageDraw, ImageFont
from StreamDeck.ImageHelpers import PILHelper
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ButtonConfig, PageConfig
from gameshow.shows import list_shows
from gameshow.events import (
    ControlCommand, BuzzerPressed, StateChanged, SceneChanged,
    CountdownTick, CountdownEnded, ScoreChanged, CounterChanged, ConfigReloaded,
)

log = logging.getLogger(__name__)

# Bottom-left key on the 3x5 MK.2 layout (row-major); reserved for "return".
RETURN_KEY = 10

# Button types that map 1:1 onto a ControlCommand, with the button attributes
# whose values become the command args (skipping any that are None).
_DIRECT_COMMANDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "lighting": ("dmx_cue", ("osc",)),
    "sound": ("audio_effect_play", ("path",)),
    "reset_buzzer": ("clear", ()),
    "scene_advance": ("scene_advance", ()),
    "scene_previous": ("scene_previous", ()),
    "obs_scene": ("obs_scene_set", ("scene",)),
    "set_award": ("set_award", ("value",)),
}

# Ordered by glyph coverage: broad-Unicode faces first so symbols such as
# ▶ ◀ ✔ ✓ render instead of tofu boxes. Helvetica/Arial (no such glyphs) are
# last-resort only.
_FALLBACK_FONTS = (
    "./fonts/Arial-Unicode.ttf",                                 # bundled with the app, broad coverage
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",    # macOS, very broad
    "/Library/Fonts/Arial Unicode.ttf",                        # macOS (older layout)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",         # Debian/Ubuntu
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",                  # Fedora/Arch
    "DejaVuSans.ttf",
    "/System/Library/Fonts/Menlo.ttc",                         # macOS monospace, full coverage
    "/System/Library/Fonts/Helvetica.ttc",                     # last resort: lacks symbols
    "/Library/Fonts/Arial.ttf",
)

_TITLE_SIZE = 11         # small header on live keys (also caps title size)
_LABEL_MARGIN = 6        # horizontal padding inside a key
_TITLE_Y = 3             # top padding for the live-key title

# Marquee scroll for text that overflows a key.
MARQUEE_INTERVAL = 0.15  # seconds between frames (~7 fps)
MARQUEE_STEP = 4         # pixels advanced per frame
MARQUEE_GAP = 16         # pixel gap between the end and the wrapped-around start

# Font Awesome (v7) npm web-package naming: "fa-<family>-<style>-<num>.woff2"
# (e.g. "fa-sharp-solid-900.woff2"). Classic has no family segment
# ("fa-solid-900.woff2") and brands ships a single Regular weight.
_FA_WEIGHT_TOKEN = {
    "solid": ("solid", "900"), "regular": ("regular", "400"),
    "light": ("light", "300"), "thin": ("thin", "100"),
}
_FA_FAMILY_PREFIX = {
    "pro": "", "classic": "", "free": "",
    "duotone": "duotone", "sharp": "sharp", "sharp-duotone": "sharp-duotone",
}


class ControlSurface:
    def __init__(self, bus: EventBus, config: Callable[[], AppConfig],
                 deck_factory: Optional[Callable[[], list]] = None) -> None:
        self._bus = bus
        self._config = config
        self._deck_factory = deck_factory or self._default_factory
        self._deck = None
        self._cs = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stack: list[PageConfig] = []
        self._layout: dict[int, ButtonConfig] = {}
        # Keys currently held down whose button defines `pressed` overrides.
        self._pressed: set[int] = set()
        self._font_cache: dict[tuple, object] = {}
        self._fa_meta: Optional[dict] = None  # lazily loaded Font Awesome metadata
        # Keys whose text overflows and is being marquee-scrolled: key -> state.
        self._marquee: dict[int, dict] = {}
        self._marquee_task: Optional[asyncio.Task] = None
        # Live display state driven by bus events.
        self._last_tick: Optional[CountdownTick] = None
        self._last_countdown_text: Optional[str] = None
        self._last_scene = "—"
        self._last_state = "idle"
        self._scores: dict[int, float] = {}
        self._counters: dict[str, int] = {}

    # ------------------------------------------------------------------ setup
    def _default_factory(self) -> list:
        from StreamDeck.DeviceManager import DeviceManager
        return DeviceManager().enumerate()

    def _load_font(self, path: Optional[str], size: int):
        key = (path, size)
        if key in self._font_cache:
            return self._font_cache[key]
        candidates = ([path] if path else []) + list(_FALLBACK_FONTS)
        font = None
        for candidate in candidates:
            try:
                font = ImageFont.truetype(candidate, size)
                break
            except OSError:
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size)
            except TypeError:  # Pillow < 10 has no size arg
                font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _font_for(self, button: Optional[ButtonConfig], size: int):
        """Resolve a button's font: its own font_path, else the surface default."""
        path = button.font_path if (button and button.font_path) else self._cs.font_path
        return self._load_font(path, size)

    def _font_size(self, button: Optional[ButtonConfig]) -> int:
        """Resolve a button's label size: its own font_size, else the surface default."""
        if button and button.font_size:
            return button.font_size
        return self._cs.font_size

    # ------------------------------------------------------------- font awesome
    @staticmethod
    def _fa_font_candidates(fa_type: str, weight: str) -> list[str]:
        """Candidate webfont filenames for a Font Awesome family + weight."""
        if fa_type == "brands":
            return ["fa-brands-400.woff2"]
        prefix = _FA_FAMILY_PREFIX.get(fa_type, "")
        style, num = _FA_WEIGHT_TOKEN.get(weight, ("solid", "900"))
        segments = [seg for seg in (prefix, style) if seg]
        names = ["-".join(["fa", *segments, num]) + ".woff2"]
        # Duotone's solid weight drops the style word ("fa-duotone-900.woff2").
        if fa_type == "duotone" and style == "solid":
            names.append(f"fa-{prefix}-{num}.woff2")
        return names

    def _fa_meta_map(self) -> dict:
        if self._fa_meta is None:
            self._fa_meta = {}
            if self._cs and self._cs.fa_path:
                path = os.path.join(self._cs.fa_path, "metadata",
                                    "icon-families.json")
                try:
                    with open(path) as f:
                        self._fa_meta = json.load(f)
                except (OSError, ValueError) as exc:
                    log.warning("Font Awesome metadata unavailable at %s (%s)", path, exc)
        return self._fa_meta

    def _fa_codepoint(self, name: str) -> Optional[str]:
        entry = self._fa_meta_map().get(name)
        if not entry or "unicode" not in entry:
            return None
        try:
            return chr(int(entry["unicode"], 16))
        except (ValueError, TypeError):
            return None

    def _fa_font(self, button: ButtonConfig, size: int):
        if not (self._cs and self._cs.fa_path):
            return None
        fa_type = button.fa_type or self._cs.fa_type
        weight = button.fa_weight or self._cs.fa_weight
        font_dir = os.path.join(self._cs.fa_path, "webfonts")
        for fname in self._fa_font_candidates(fa_type, weight):
            path = os.path.join(font_dir, fname)
            if os.path.exists(path):
                return self._load_font(path, size)
        return None

    def _fa_glyph(self, button: ButtonConfig, size: int):
        char = self._fa_codepoint(button.fa_icon)
        if char is None:
            return None
        font = self._fa_font(button, size)
        if font is None:
            return None
        return char, font

    def _draw_fa_icon(self, draw, image, button: ButtonConfig) -> bool:
        """Draw a Font Awesome icon; return False (to fall back) if unavailable."""
        label = button.label
        icon_size = self._fa_size(button, bool(label))
        glyph = self._fa_glyph(button, icon_size)
        if glyph is None:
            log.warning("Font Awesome icon %r unavailable; falling back to label",
                        button.fa_icon)
            return False
        char, font = glyph
        color = self._fa_color(button)
        if label:
            draw.text((image.width / 2, image.height * 0.40), char,
                      font=font, anchor="mm", fill=color)
            small = self._font_for(button, min(_TITLE_SIZE, self._font_size(button)))
            draw.text((image.width / 2, image.height - 4), label,
                      font=small, anchor="ms", fill=self._text_color(button))
        else:
            draw.text((image.width / 2, image.height / 2), char,
                      font=font, anchor="mm", fill=color)
        return True

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        cs = self._config().control_surface
        if not cs or not cs.enabled:
            log.info("Control surface disabled or unconfigured")
            return

        # Acquiring the device touches native USB/HID; any failure here
        # (missing hidapi backend, deck grabbed by the Elgato app, disconnect)
        # must leave the rest of the service running rather than crash it.
        try:
            decks = self._deck_factory()
        except Exception as exc:
            log.warning("Stream Deck backend unavailable; control surface is "
                        "inert (%s). Is 'hidapi' installed (brew install hidapi)?", exc)
            return

        deck = next((d for d in decks
                     if cs.serial is None or d.get_serial_number() == cs.serial), None)
        if deck is None:
            log.warning("No Stream Deck found; control surface is inert")
            return

        try:
            deck.open()
            deck.reset()
            deck.set_brightness(cs.brightness)
            deck.set_key_callback_async(self._on_key, loop=self._loop)
        except Exception as exc:
            log.warning("Failed to initialise Stream Deck; control surface is inert (%s)", exc)
            return

        self._deck = deck
        self._cs = cs

        self._bus.subscribe(CountdownTick, self._on_tick)
        self._bus.subscribe(CountdownEnded, self._on_end)
        self._bus.subscribe(SceneChanged, self._on_scene)
        self._bus.subscribe(StateChanged, self._on_state)
        self._bus.subscribe(ScoreChanged, self._on_score)
        self._bus.subscribe(CounterChanged, self._on_counter)
        self._bus.subscribe(ConfigReloaded, self._on_config_reloaded)

        await self._render()
        self._marquee_task = asyncio.create_task(self._marquee_loop())
        log.info("Control surface started on %s", deck.deck_type())

    async def stop(self) -> None:
        if self._marquee_task is not None:
            self._marquee_task.cancel()
            try:
                await self._marquee_task
            except asyncio.CancelledError:
                pass
            self._marquee_task = None
        if self._deck is not None:
            try:
                with self._deck:
                    self._deck.reset()
                    self._deck.close()
            except Exception as exc:
                log.warning("Error closing Stream Deck: %s", exc)
            self._deck = None

    # -------------------------------------------------------------- layout
    def _resolve_layout(self, page: PageConfig, is_subpage: bool) -> dict[int, ButtonConfig]:
        layout: dict[int, ButtonConfig] = {}
        reserved: set[int] = set()
        if is_subpage:
            layout[RETURN_KEY] = ButtonConfig(type="return", fa_icon="caret-large-left", font_size=56)
            reserved.add(RETURN_KEY)

        for button in page.buttons:
            if button.key is not None:
                if button.key in reserved:
                    log.warning("Button %r wants reserved key %d; skipped",
                                button.name or button.label, button.key)
                    continue
                layout[button.key] = button

        free = (k for k in range(self._deck.key_count())
                if k not in layout and k not in reserved)
        for button in (b for b in page.buttons if b.key is None):
            key = next(free, None)
            if key is None:
                log.warning("Control surface page overflow; dropping button %r",
                            button.name or button.label)
                continue
            layout[key] = button
        return layout

    def _key_of(self, button: ButtonConfig) -> int:
        for key, candidate in self._layout.items():
            if candidate is button:
                return key
        raise KeyError(button)

    @staticmethod
    def _apply_pressed(button: ButtonConfig) -> ButtonConfig:
        """Overlay a button's `pressed` overrides, yielding an effective button
        that the normal render path draws exactly as if those were its values."""
        overrides = {k: v for k, v in vars(button.pressed).items() if v is not None}
        return dataclasses.replace(button, **overrides)

    # -------------------------------------------------------------- dispatch
    async def _on_key(self, deck, key: int, state: bool) -> None:
        button = self._layout.get(key)
        # Apply/revert the pressed appearance before dispatch so held-down
        # feedback shows immediately (and reverts the moment the key is released).
        if button is not None and button.pressed is not None:
            self._pressed.add(key) if state else self._pressed.discard(key)
            self._render_key(key, button)
        if not state:
            return
        log.info("IN  DECK key %d press → %s", key,
                 (button.name or button.type) if button else "unbound")
        if button is not None:
            await self._dispatch(button)

    async def _dispatch(self, button: ButtonConfig) -> None:
        t = button.type

        if t == "page" and button.page is not None:
            self._stack.append(button.page)
            await self._render()
            return
        if t == "return":
            if self._stack:
                self._stack.pop()
            await self._render()
            return
        if t == "stop_sounds":
            await self._bus.publish(ControlCommand(command="audio_fx_stop"))
            await self._bus.publish(ControlCommand(command="audio_bg_stop"))
            return
        if t == "buzz" and button.player_id is not None:
            await self._bus.publish(BuzzerPressed(player_id=button.player_id))
            return
        if t == "state" and button.state:
            args = (button.duration,) if button.state == "timed_lockout" and button.duration else ()
            await self._bus.publish(ControlCommand(command=button.state, args=args))
            return
        if t == "scene_goto" and button.target is not None:
            cmd = "scene_goto_index" if isinstance(button.target, int) else "scene_goto_name"
            await self._bus.publish(ControlCommand(command=cmd, args=(button.target,)))
            return
        if t == "obs_request" and button.request_type:
            await self._bus.publish(ControlCommand(
                command="obs_request", args=(button.request_type, button.request_data)))
            return
        if t == "config_reload":
            args = (button.config,) if button.config else ()
            await self._bus.publish(ControlCommand(command="config_reload", args=args))
            return
        if t == "show_browser":
            self._stack.append(self._build_shows_page())
            await self._render()
            return
        if t == "countdown":
            action = button.action or "display"
            if action == "toggle":
                action = "resume" if (self._last_tick and self._last_tick.paused) else "pause"
            if action in ("pause", "resume", "reset", "cancel"):
                await self._bus.publish(ControlCommand(command=f"countdown_{action}"))
            return  # "display" is a live readout; pressing it does nothing
        if t in _DIRECT_COMMANDS:
            cmd, attrs = _DIRECT_COMMANDS[t]
            args = tuple(getattr(button, a) for a in attrs if getattr(button, a) is not None)
            await self._bus.publish(ControlCommand(command=cmd, args=args))
            return
        # "scene_current" / "state_display" are display-only → no action on press

    def _build_shows_page(self, entries=None) -> PageConfig:
        """Build a (paginated) page listing every show in shows/ as a
        config_reload button labelled by show name.

        When shows overflow one deck page, a Next button chains to the following
        page; the reserved return key (key 10) steps back through them.
        """
        entries = list_shows() if entries is None else entries
        key_count = self._deck.key_count()
        # Every sub-page reserves the return key; a page with a successor also
        # reserves one slot for its Next button.
        fits_one_page = len(entries) <= key_count - 1
        page_size = (key_count - 1) if fits_one_page else (key_count - 2)
        chunks = [entries[i:i + page_size]
                  for i in range(0, len(entries), page_size)] or [[]]

        # Built back-to-front so each page's Next can link to the one after it.
        page: Optional[PageConfig] = None
        for chunk in reversed(chunks):
            buttons = [ButtonConfig(type="config_reload", label=e.name, config=e.filename)
                       for e in chunk]
            if page is not None:
                buttons.append(ButtonConfig(type="page", label="Next ▶", page=page))
            page = PageConfig(buttons=buttons)
        return page

    # -------------------------------------------------------------- rendering
    async def _render(self) -> None:
        if self._deck is None:
            return
        cs = self._config().control_surface
        page = self._stack[-1] if self._stack else cs.root
        self._layout = self._resolve_layout(page, is_subpage=bool(self._stack))
        # A fresh layout can't have any keys "still held"; drop stale press state.
        self._pressed.clear()
        for key in range(self._deck.key_count()):
            self._render_key(key, self._layout.get(key))

    def _render_key(self, key: int, button: Optional[ButtonConfig]) -> None:
        if button is None:
            self._marquee.pop(key, None)
            self._blit(key, self._new_image("black"))
            return

        if key in self._pressed and button.pressed is not None:
            button = self._apply_pressed(button)

        background = self._bg_color(button)
        image = self._new_image(background)
        draw = ImageDraw.Draw(image)

        # A Font Awesome icon takes over the key; a label (if any) sits beneath it.
        if button.fa_icon and self._draw_fa_icon(draw, image, button):
            self._marquee.pop(key, None)
            self._blit(key, image)
            return

        title, body = self._key_texts(button)
        size = self._font_size(button)
        body_font = self._font_for(button, size)
        title_font = self._font_for(button, min(_TITLE_SIZE, size))
        top = 0
        if title:
            draw.text((image.width / 2, _TITLE_Y), title,
                      font=title_font, anchor="ma", fill="#AAAAAA")
            top = self._title_band(title_font)
        # Live values sit centred in the remaining space; static labels honour align.
        body_align = "center" if title else self._label_align(button)
        fill = self._text_color(button)

        max_width = image.width - 2 * _LABEL_MARGIN
        line_h = self._line_height(body_font)
        mode, lines = self._plan_body(body, self._label_wrap(button),
                                      max_width, image.height - top, line_h, body_font)

        if mode == "overflow" and self._label_marquee(button):
            self._marquee[key] = {
                "background": background, "title": title, "title_font": title_font,
                "text": body, "font": body_font, "align": body_align,
                "fill": fill, "top": top, "offset": 0,
            }
            self._draw_marquee(draw, image, body, body_font, 0, body_align, top, fill)
        else:
            self._marquee.pop(key, None)
            self._draw_body(draw, image, lines, body_font, body_align, top, fill)

        self._blit(key, image)

    def _key_texts(self, button: ButtonConfig) -> tuple[Optional[str], str]:
        """Return (title, body): live keys show a small title + dynamic value."""
        value = self._dynamic_value(button)
        if value is not None:
            return (button.label or None, value)
        return (None, button.label)

    def _label_align(self, button: ButtonConfig) -> str:
        return button.label_align or self._cs.label_align

    def _label_wrap(self, button: ButtonConfig) -> bool:
        return button.label_wrap if button.label_wrap is not None else self._cs.label_wrap

    def _label_marquee(self, button: ButtonConfig) -> bool:
        if button.label_marquee is not None:
            return button.label_marquee
        return self._cs.label_marquee

    def _text_color(self, button: ButtonConfig) -> str:
        return button.text_color or self._cs.text_color

    def _bg_color(self, button: ButtonConfig) -> str:
        return button.color or self._cs.color

    def _fa_color(self, button: ButtonConfig) -> str:
        return button.fa_color or self._cs.fa_color or self._text_color(button)

    def _fa_size(self, button: ButtonConfig, has_label: bool) -> int:
        if button.fa_size:
            return button.fa_size
        if self._cs.fa_size:
            return self._cs.fa_size
        return 30 if has_label else 42

    def _plan_body(self, text: str, wrap: bool, max_width: float,
                   avail_height: float, line_h: float, font) -> tuple[str, list[str]]:
        """Decide how a body string is laid out: static, wrapped, or overflow."""
        if font.getlength(text) <= max_width:
            return ("static", [text])
        if wrap:
            lines = self._wrap_text(text, font, max_width)
            fits = (all(font.getlength(ln) <= max_width for ln in lines)
                    and line_h * len(lines) <= avail_height)
            if len(lines) > 1 and fits:
                return ("wrapped", lines)
        return ("overflow", [text])

    @staticmethod
    def _wrap_text(text: str, font, max_width: float) -> list[str]:
        """Greedily wrap text into lines that fit within max_width pixels."""
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.getlength(trial) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    @staticmethod
    def _line_height(font) -> int:
        ascent, descent = font.getmetrics()
        return ascent + descent + 2

    @staticmethod
    def _title_band(font) -> int:
        ascent, descent = font.getmetrics()
        return _TITLE_Y + ascent + descent + 2

    def _draw_body(self, draw, image, lines: list[str], font, align: str,
                   top: int, fill: str = "white") -> None:
        ascent, descent = font.getmetrics()
        line_h = ascent + descent + 2
        block_h = line_h * len(lines)
        region = image.height - top
        if align == "top":
            baseline = top + 4 + ascent
        elif align == "center":
            baseline = top + (region - block_h) / 2 + ascent
        else:  # bottom
            baseline = image.height - block_h - 2 + ascent
        for line in lines:
            draw.text((image.width / 2, baseline), line,
                      font=font, anchor="ms", fill=fill)
            baseline += line_h

    def _draw_marquee(self, draw, image, text: str, font, offset: int,
                      align: str, top: int, fill: str = "white") -> None:
        ascent, descent = font.getmetrics()
        line_h = ascent + descent
        region = image.height - top
        if align == "top":
            baseline = top + 4 + ascent
        elif align == "center":
            baseline = top + (region - line_h) / 2 + ascent
        else:  # bottom
            baseline = image.height - descent - 4
        period = font.getlength(text) + MARQUEE_GAP
        x = _LABEL_MARGIN - (offset % period)
        # Draw twice so the tail wraps seamlessly back to the start.
        draw.text((x, baseline), text, font=font, anchor="ls", fill=fill)
        draw.text((x + period, baseline), text, font=font, anchor="ls", fill=fill)

    def _new_image(self, background: str):
        return PILHelper.create_key_image(self._deck, background=background)

    def _blit(self, key: int, image) -> None:
        native = PILHelper.to_native_key_format(self._deck, image)
        with self._deck:
            self._deck.set_key_image(key, native)

    def _render_marquee_frame(self, key: int) -> None:
        st = self._marquee.get(key)
        if st is None or self._deck is None:
            return
        image = self._new_image(st["background"])
        draw = ImageDraw.Draw(image)
        if st["title"]:
            draw.text((image.width / 2, _TITLE_Y), st["title"],
                      font=st["title_font"], anchor="ma", fill="#AAAAAA")
        self._draw_marquee(draw, image, st["text"], st["font"],
                           st["offset"], st["align"], st["top"], st["fill"])
        self._blit(key, image)

    async def _marquee_loop(self) -> None:
        while True:
            await asyncio.sleep(MARQUEE_INTERVAL)
            self._marquee_step()

    def _marquee_step(self) -> None:
        for key, st in list(self._marquee.items()):
            st["offset"] += MARQUEE_STEP
            self._render_marquee_frame(key)

    def _dynamic_value(self, button: ButtonConfig) -> Optional[str]:
        if button.type == "countdown" and (button.action or "display") == "display":
            return self._countdown_text()
        if button.type == "scene_current":
            return self._last_scene
        if button.type == "state_display":
            return self._last_state
        if button.type == "score_display":
            return self._score_text()
        if button.type == "counter_display":
            return str(self._counters.get(button.counter, 0))
        return None

    def _score_text(self) -> str:
        if not self._scores:
            return "—"
        return "  ".join(f"P{pid}:{int(score)}"
                         for pid, score in sorted(self._scores.items()))

    def _countdown_text(self) -> str:
        if self._last_tick is None:
            return "--"
        return str(math.ceil(self._last_tick.remaining))

    def _refresh_type(self, *types: str) -> None:
        if self._deck is None:
            return
        for key, button in self._layout.items():
            if button is not None and button.type in types:
                self._render_key(key, button)

    # --------------------------------------------------------- live handlers
    async def _on_tick(self, event: CountdownTick) -> None:
        self._last_tick = event
        text = self._countdown_text()
        if text != self._last_countdown_text:
            self._last_countdown_text = text
            self._refresh_type("countdown")

    async def _on_end(self, event: CountdownEnded) -> None:
        self._last_tick = None
        self._last_countdown_text = None
        self._refresh_type("countdown")

    async def _on_scene(self, event: SceneChanged) -> None:
        self._last_scene = f"{event.index}:{event.name}" if event.name else "—"
        self._refresh_type("scene_current")

    async def _on_state(self, event: StateChanged) -> None:
        self._last_state = event.new_state
        self._refresh_type("state_display")

    async def _on_score(self, event: ScoreChanged) -> None:
        self._scores[event.player_id] = event.score
        self._refresh_type("score_display")

    async def _on_counter(self, event: CounterChanged) -> None:
        self._counters[event.name] = event.value
        self._refresh_type("counter_display")

    async def _on_config_reloaded(self, event: ConfigReloaded) -> None:
        # A reloaded config brings a fresh surface layout and defaults: refresh the
        # cached surface, drop caches keyed to the old config, wipe live readouts,
        # and redraw from the new root page.
        cs = self._config().control_surface
        if cs is None:
            return
        self._cs = cs
        self._stack.clear()
        self._font_cache.clear()
        self._fa_meta = None
        self._scores.clear()
        self._counters.clear()
        self._last_scene = "—"
        self._last_state = "idle"
        if self._deck is not None:
            self._deck.set_brightness(cs.brightness)
        await self._render()
