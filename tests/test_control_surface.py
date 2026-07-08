import collections
import json
import os
import pytest
from PIL import ImageFont
from gameshow.bus import EventBus
from gameshow.config import (
    AppConfig, ServiceConfig, BuzzerConfig, StateMachineConfig,
    LightingConfig, AudioConfig, OBSConfig,
    ControlSurfaceConfig, PageConfig, ButtonConfig, PressedStyle,
)
from gameshow.events import (
    ControlCommand, BuzzerPressed, StateChanged, SceneChanged,
    CountdownTick, CountdownEnded, ScoreChanged,
)
from gameshow.control_surface import ControlSurface, RETURN_KEY


class FakeDeck:
    """In-memory Stream Deck standing in for the hardware in tests."""

    def __init__(self):
        self.images = {}
        self.image_calls = collections.Counter()
        self.brightness = None
        self.opened = False
        self.closed = False
        self.reset_count = 0
        self.async_callback = None

    # --- lifecycle ---
    def open(self): self.opened = True
    def close(self): self.closed = True
    def reset(self): self.reset_count += 1
    def is_open(self): return self.opened and not self.closed
    def connected(self): return True

    # --- device info ---
    def deck_type(self): return "FakeDeck MK.2"
    def key_count(self): return 15
    def key_layout(self): return (3, 5)
    def is_visual(self): return True
    def get_serial_number(self): return "FAKE123"

    def key_image_format(self):
        return {"size": (72, 72), "format": "JPEG",
                "flip": (True, True), "rotation": 0}

    # --- display ---
    def set_brightness(self, pct): self.brightness = pct

    def set_key_image(self, key, image):
        self.images[key] = image
        self.image_calls[key] += 1

    # --- callbacks ---
    def set_key_callback(self, cb): self.callback = cb
    def set_key_callback_async(self, cb, loop=None): self.async_callback = cb

    # --- mutex context manager ---
    def __enter__(self): return self
    def __exit__(self, *a): return False


def make_config(root_buttons=None, label_align="bottom", label_wrap=False,
                label_marquee=True, font_path=None, fa_path=None,
                color="black", fa_size=None, fa_color=None):
    root = PageConfig(buttons=root_buttons or [])
    return AppConfig(
        service=ServiceConfig(),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(initial="idle"),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
        control_surface=ControlSurfaceConfig(
            brightness=42, root=root, font_path=font_path, fa_path=fa_path,
            label_align=label_align, label_wrap=label_wrap,
            label_marquee=label_marquee, color=color,
            fa_size=fa_size, fa_color=fa_color),
    )


def make_surface(root_buttons=None, decks=None, label_align="bottom",
                 label_wrap=False, label_marquee=True, font_path=None, fa_path=None,
                 color="black", fa_size=None, fa_color=None):
    bus = EventBus()
    config = make_config(root_buttons, label_align=label_align,
                         label_wrap=label_wrap, label_marquee=label_marquee,
                         font_path=font_path, fa_path=fa_path,
                         color=color, fa_size=fa_size, fa_color=fa_color)
    deck = FakeDeck()
    factory = (lambda: (decks if decks is not None else [deck]))
    cs = ControlSurface(bus, lambda: config, deck_factory=factory)
    return bus, cs, deck


# --------------------------------------------------------------------------
# Layout resolution (Step 4)
# --------------------------------------------------------------------------

def test_root_layout_has_no_return_button():
    _, cs, deck = make_surface([
        ButtonConfig(type="state", label="Clear", state="clear"),
        ButtonConfig(type="buzz", label="P1", player_id=1),
    ])
    cs._deck = deck
    layout = cs._resolve_layout(cs._config().control_surface.root, is_subpage=False)
    assert layout[0].type == "state"
    assert layout[1].type == "buzz"
    assert RETURN_KEY not in layout or layout[RETURN_KEY].type != "return"


def test_subpage_layout_reserves_return_at_bottom_left():
    _, cs, deck = make_surface()
    cs._deck = deck
    page = PageConfig(buttons=[ButtonConfig(type="sound", label="A", path="a.mp3")])
    layout = cs._resolve_layout(page, is_subpage=True)
    assert layout[RETURN_KEY].type == "return"
    # first ordinary button skips the reserved return slot
    assert layout[0].type == "sound"


def test_subpage_button_cannot_override_return_key():
    _, cs, deck = make_surface()
    cs._deck = deck
    page = PageConfig(buttons=[
        ButtonConfig(type="sound", name="button_10", path="a.mp3", key=RETURN_KEY),
    ])
    layout = cs._resolve_layout(page, is_subpage=True)
    assert layout[RETURN_KEY].type == "return"


def test_explicit_key_is_honored():
    _, cs, deck = make_surface([
        ButtonConfig(type="state", label="X", state="clear", key=7),
    ])
    cs._deck = deck
    layout = cs._resolve_layout(cs._config().control_surface.root, is_subpage=False)
    assert 7 in layout and layout[7].state == "clear"


def test_layout_overflow_drops_extra_buttons():
    buttons = [ButtonConfig(type="state", label=str(i), state="clear") for i in range(20)]
    _, cs, deck = make_surface(buttons)
    cs._deck = deck
    layout = cs._resolve_layout(cs._config().control_surface.root, is_subpage=False)
    assert len(layout) <= deck.key_count()


# --------------------------------------------------------------------------
# Press dispatch (Step 4)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("button, expected", [
    (ButtonConfig(type="lighting", osc="/cue/1"), ("dmx_cue", ("/cue/1",))),
    (ButtonConfig(type="sound", path="a.mp3"), ("audio_effect_play", ("a.mp3",))),
    (ButtonConfig(type="reset_buzzer"), ("clear", ())),
    (ButtonConfig(type="state", state="round_start"), ("round_start", ())),
    (ButtonConfig(type="state", state="timed_lockout", duration=5.0), ("timed_lockout", (5.0,))),
    (ButtonConfig(type="scene_advance"), ("scene_advance", ())),
    (ButtonConfig(type="scene_previous"), ("scene_previous", ())),
    (ButtonConfig(type="scene_goto", target="Round 1"), ("scene_goto_name", ("Round 1",))),
    (ButtonConfig(type="scene_goto", target=3), ("scene_goto_index", (3,))),
    (ButtonConfig(type="obs_scene", scene="Intro"), ("obs_scene_set", ("Intro",))),
    (ButtonConfig(type="obs_request", request_type="StartRecord"), ("obs_request", ("StartRecord", None))),
    (ButtonConfig(type="countdown", action="pause"), ("countdown_pause", ())),
    (ButtonConfig(type="countdown", action="reset"), ("countdown_reset", ())),
    (ButtonConfig(type="countdown", action="cancel"), ("countdown_cancel", ())),
    (ButtonConfig(type="set_award", value=200), ("set_award", (200,))),
])
async def test_dispatch_publishes_control_command(button, expected):
    bus, cs, deck = make_surface([button])
    cs._deck = deck
    cs._layout = {0: button}
    published = []

    async def cap(e): published.append(e)
    bus.subscribe(ControlCommand, cap)

    await cs._on_key(deck, 0, True)
    cmd, args = expected
    assert any(e.command == cmd and e.args == args for e in published)


@pytest.mark.asyncio
async def test_score_display_reflects_score_changes():
    button = ButtonConfig(type="score_display", name="scores")
    bus, cs, deck = make_surface([button])
    assert cs._dynamic_value(button) is not None          # renders even with no scores
    await cs._on_score(ScoreChanged(player_id=1, score=300, delta=300))
    await cs._on_score(ScoreChanged(player_id=2, score=150, delta=150))
    text = cs._dynamic_value(button)
    assert "300" in text and "150" in text


@pytest.mark.asyncio
async def test_dispatch_buzz_publishes_buzzer_pressed():
    button = ButtonConfig(type="buzz", player_id=2)
    bus, cs, deck = make_surface([button])
    cs._deck = deck
    cs._layout = {0: button}
    got = []
    async def cap(e): got.append(e)
    bus.subscribe(BuzzerPressed, cap)
    await cs._on_key(deck, 0, True)
    assert got and got[0].player_id == 2


@pytest.mark.asyncio
async def test_dispatch_stop_sounds_stops_both_channels():
    button = ButtonConfig(type="stop_sounds")
    bus, cs, deck = make_surface([button])
    cs._deck = deck
    cs._layout = {0: button}
    cmds = []
    async def cap(e): cmds.append(e.command)
    bus.subscribe(ControlCommand, cap)
    await cs._on_key(deck, 0, True)
    assert "audio_fx_stop" in cmds and "audio_bg_stop" in cmds


@pytest.mark.asyncio
async def test_key_release_publishes_nothing():
    button = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([button])
    cs._deck = deck
    cs._layout = {0: button}
    cmds = []
    async def cap(e): cmds.append(e)
    bus.subscribe(ControlCommand, cap)
    await cs._on_key(deck, 0, False)
    assert cmds == []


@pytest.mark.asyncio
async def test_page_button_pushes_and_return_pops():
    sub = PageConfig(buttons=[ButtonConfig(type="sound", path="a.mp3")])
    page_btn = ButtonConfig(type="page", label="Folder", page=sub)
    bus, cs, deck = make_surface([page_btn])
    await cs.start()

    await cs._on_key(deck, cs._key_of(page_btn), True)
    assert cs._stack == [sub]

    await cs._on_key(deck, RETURN_KEY, True)
    assert cs._stack == []

    await cs.stop()


# --------------------------------------------------------------------------
# Rendering, live updates, lifecycle (Step 5)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_opens_resets_brightness_and_renders():
    buttons = [ButtonConfig(type="state", label="Clear", state="clear")]
    bus, cs, deck = make_surface(buttons)
    await cs.start()
    assert deck.opened
    assert deck.reset_count >= 1
    assert deck.brightness == 42
    assert deck.async_callback is not None
    assert deck.images.get(0) is not None  # button key rendered
    await cs.stop()


@pytest.mark.asyncio
async def test_deck_backend_error_is_inert():
    bus = EventBus()
    config = make_config([ButtonConfig(type="state", state="clear")])

    def exploding_factory():
        raise RuntimeError("Probe failed to find any functional HID backend.")

    cs = ControlSurface(bus, lambda: config, deck_factory=exploding_factory)
    await cs.start()  # must not raise
    assert cs._deck is None
    # events must not raise either
    await bus.publish(StateChanged(new_state="locked"))
    await cs.stop()


@pytest.mark.asyncio
async def test_deck_open_error_is_inert():
    bus = EventBus()
    config = make_config([ButtonConfig(type="state", state="clear")])
    deck = FakeDeck()

    def boom():
        raise OSError("device is grabbed by another process")
    deck.open = boom

    cs = ControlSurface(bus, lambda: config, deck_factory=lambda: [deck])
    await cs.start()  # must not raise
    assert cs._deck is None
    await cs.stop()


@pytest.mark.asyncio
async def test_no_deck_is_inert():
    bus, cs, _ = make_surface([ButtonConfig(type="state", state="clear")], decks=[])
    await cs.start()
    assert cs._deck is None
    # events must not raise
    await bus.publish(CountdownTick(remaining=3.0, total=5.0))
    await bus.publish(SceneChanged(index=1, name="Intro"))
    await bus.publish(StateChanged(new_state="locked"))
    await cs.stop()


@pytest.mark.asyncio
async def test_countdown_tick_updates_display_only_on_second_change():
    btn = ButtonConfig(type="countdown", action="display", label="Timer")
    bus, cs, deck = make_surface([btn])
    await cs.start()
    key = cs._key_of(btn)
    base = deck.image_calls[key]

    await bus.publish(CountdownTick(remaining=5.0, total=5.0))
    after_first = deck.image_calls[key]
    assert after_first == base + 1

    await bus.publish(CountdownTick(remaining=4.9, total=5.0))  # same ceil second
    assert deck.image_calls[key] == after_first

    await bus.publish(CountdownTick(remaining=3.9, total=5.0))  # new second
    assert deck.image_calls[key] == after_first + 1

    await cs.stop()


@pytest.mark.asyncio
async def test_countdown_ended_clears_display():
    btn = ButtonConfig(type="countdown", action="display", label="Timer")
    bus, cs, deck = make_surface([btn])
    await cs.start()
    key = cs._key_of(btn)
    await bus.publish(CountdownTick(remaining=5.0, total=5.0))
    calls = deck.image_calls[key]
    await bus.publish(CountdownEnded(reason="expired"))
    assert deck.image_calls[key] == calls + 1
    assert cs._last_tick is None
    await cs.stop()


@pytest.mark.asyncio
async def test_scene_changed_updates_scene_current_key():
    btn = ButtonConfig(type="scene_current", label="Scene")
    bus, cs, deck = make_surface([btn])
    await cs.start()
    key = cs._key_of(btn)
    calls = deck.image_calls[key]
    await bus.publish(SceneChanged(index=2, name="Face Off"))
    assert deck.image_calls[key] == calls + 1
    await cs.stop()


@pytest.mark.asyncio
async def test_state_changed_updates_state_display_key():
    btn = ButtonConfig(type="state_display", label="State")
    bus, cs, deck = make_surface([btn])
    await cs.start()
    key = cs._key_of(btn)
    calls = deck.image_calls[key]
    await bus.publish(StateChanged(new_state="locked"))
    assert deck.image_calls[key] == calls + 1
    await cs.stop()


def test_wrap_text_splits_long_label():
    font = ImageFont.load_default()
    lines = ControlSurface._wrap_text("Start The Next Round Right Now Please", font, 40)
    assert len(lines) > 1
    assert all(line for line in lines)


def test_wrap_text_keeps_short_label_single_line():
    font = ImageFont.load_default()
    assert ControlSurface._wrap_text("Go", font, 200) == ["Go"]


def test_wrap_text_empty_label():
    font = ImageFont.load_default()
    assert ControlSurface._wrap_text("", font, 100) == [""]


@pytest.mark.asyncio
async def test_label_align_resolution_button_overrides_global():
    override = ButtonConfig(type="state", state="clear", label_align="center")
    default = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, default], label_align="bottom")
    await cs.start()
    assert cs._label_align(cs._layout[0]) == "center"   # per-button override
    assert cs._label_align(cs._layout[1]) == "bottom"    # falls back to global
    await cs.stop()


@pytest.mark.asyncio
async def test_label_wrap_resolution_button_overrides_global():
    override = ButtonConfig(type="state", state="clear", label_wrap=True)
    default = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, default], label_wrap=False)
    await cs.start()
    assert cs._label_wrap(cs._layout[0]) is True         # per-button override
    assert cs._label_wrap(cs._layout[1]) is False         # falls back to global
    await cs.stop()


@pytest.mark.asyncio
async def test_label_marquee_resolution_button_overrides_global():
    override = ButtonConfig(type="state", state="clear", label_marquee=False)
    default = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, default], label_marquee=True)
    await cs.start()
    assert cs._label_marquee(cs._layout[0]) is False     # per-button override
    assert cs._label_marquee(cs._layout[1]) is True       # falls back to global
    await cs.stop()


@pytest.mark.asyncio
async def test_centered_wrapped_label_renders_without_error():
    btn = ButtonConfig(type="state", label="Start The Next Round", state="round_start")
    bus, cs, deck = make_surface([btn], label_align="center", label_wrap=True)
    await cs.start()
    assert deck.images.get(0) is not None
    await cs.stop()


# --------------------------------------------------------------------------
# Marquee scrolling + per-button fonts
# --------------------------------------------------------------------------

_LONG = "This label is far too long to fit on one key"


def test_plan_body_static_for_short_text():
    font = ImageFont.load_default()
    bus, cs, deck = make_surface()
    mode, lines = cs._plan_body("Hi", wrap=False, max_width=1000,
                                avail_height=72, line_h=14, font=font)
    assert mode == "static"
    assert lines == ["Hi"]


def test_plan_body_overflow_when_too_wide_without_wrap():
    font = ImageFont.load_default()
    bus, cs, deck = make_surface()
    mode, _ = cs._plan_body(_LONG, wrap=False, max_width=60,
                            avail_height=72, line_h=14, font=font)
    assert mode == "overflow"


def test_plan_body_wraps_multiword_that_fits():
    font = ImageFont.load_default()
    bus, cs, deck = make_surface()
    single = font.getlength("aa")
    both = font.getlength("aa aa")
    mid = (single + both) / 2      # fits one word, not two
    mode, lines = cs._plan_body("aa aa", wrap=True, max_width=mid,
                                avail_height=72, line_h=14, font=font)
    assert mode == "wrapped"
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_overflowing_label_registers_marquee_and_scrolls():
    btn = ButtonConfig(type="state", label=_LONG, state="clear", label_wrap=False)
    bus, cs, deck = make_surface([btn], label_marquee=True)
    await cs.start()
    assert 0 in cs._marquee                       # registered for scrolling
    offset0 = cs._marquee[0]["offset"]
    calls0 = deck.image_calls[0]
    cs._marquee_step()                            # advance one frame
    assert cs._marquee[0]["offset"] > offset0
    assert deck.image_calls[0] > calls0           # key was re-rendered
    await cs.stop()


@pytest.mark.asyncio
async def test_short_label_does_not_marquee():
    bus, cs, deck = make_surface([ButtonConfig(type="state", label="OK", state="clear")])
    await cs.start()
    assert cs._marquee == {}
    await cs.stop()


@pytest.mark.asyncio
async def test_marquee_can_be_disabled_globally():
    btn = ButtonConfig(type="state", label=_LONG, state="clear", label_wrap=False)
    bus, cs, deck = make_surface([btn], label_marquee=False)
    await cs.start()
    assert cs._marquee == {}       # overflow, but scrolling disabled
    await cs.stop()


@pytest.mark.asyncio
async def test_stop_cancels_marquee_task():
    btn = ButtonConfig(type="state", label=_LONG, state="clear")
    bus, cs, deck = make_surface([btn])
    await cs.start()
    assert cs._marquee_task is not None
    await cs.stop()
    assert cs._marquee_task is None


@pytest.mark.asyncio
async def test_button_font_overrides_surface_default():
    btn = ButtonConfig(type="state", label="X", state="clear",
                       font_path="/no/such/font.ttf")
    bus, cs, deck = make_surface([btn], font_path=None)
    await cs.start()
    # Per-button font_path is resolved (falls back to a default face if the
    # path can't be loaded) without raising.
    font = cs._font_for(cs._layout[0], 16)
    assert font is not None
    await cs.stop()


@pytest.mark.asyncio
async def test_font_size_resolution_button_overrides_global():
    override = ButtonConfig(type="state", state="clear", font_size=28)
    default = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, default])
    await cs.start()
    assert cs._font_size(cs._layout[0]) == 28   # per-button override
    assert cs._font_size(cs._layout[1]) == 16    # surface default
    await cs.stop()


@pytest.mark.asyncio
async def test_larger_font_size_renders_without_error():
    btn = ButtonConfig(type="state", label="Big", state="clear", font_size=32)
    bus, cs, deck = make_surface([btn])
    await cs.start()
    assert deck.images.get(0) is not None
    await cs.stop()


def _is_tofu(font, ch):
    # A missing glyph renders as .notdef — identical to a private-use codepoint.
    return bytes(font.getmask(ch)) == bytes(font.getmask(""))


def test_default_font_covers_symbol_glyphs():
    bus, cs, deck = make_surface()
    font = cs._load_font(None, 18)
    if not isinstance(font, ImageFont.FreeTypeFont):
        pytest.skip("no TrueType font available on this system")
    for ch in ("▶", "◀", "✔", "✓"):
        assert not _is_tofu(font, ch), f"default font lacks glyph {ch!r}"


@pytest.mark.asyncio
async def test_text_color_resolution_button_overrides_global():
    override = ButtonConfig(type="state", state="clear", text_color="#FF0000")
    default = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, default])
    await cs.start()
    assert cs._text_color(cs._layout[0]) == "#FF0000"   # per-button override
    assert cs._text_color(cs._layout[1]) == "white"      # surface default
    await cs.stop()


@pytest.mark.asyncio
async def test_bg_color_resolution_button_overrides_global():
    override = ButtonConfig(type="state", state="clear", color="#111111")
    default = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, default], color="#222222")
    await cs.start()
    assert cs._bg_color(cs._layout[0]) == "#111111"   # per-button override
    assert cs._bg_color(cs._layout[1]) == "#222222"    # surface default
    await cs.stop()


@pytest.mark.asyncio
async def test_fa_color_resolution_and_text_fallback():
    override = ButtonConfig(type="state", state="clear", fa_color="#FF0000")
    from_surface = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, from_surface], fa_color="#00FF00")
    await cs.start()
    assert cs._fa_color(cs._layout[0]) == "#FF0000"   # per-button override
    assert cs._fa_color(cs._layout[1]) == "#00FF00"    # surface default
    await cs.stop()

    # With no fa_color anywhere, it falls back to the text color.
    bus2, cs2, deck2 = make_surface([ButtonConfig(type="state", state="clear")])
    await cs2.start()
    assert cs2._fa_color(cs2._layout[0]) == "white"
    await cs2.stop()


@pytest.mark.asyncio
async def test_fa_size_resolution_and_default():
    override = ButtonConfig(type="state", state="clear", fa_size=50)
    from_surface = ButtonConfig(type="state", state="clear")
    bus, cs, deck = make_surface([override, from_surface], fa_size=28)
    await cs.start()
    assert cs._fa_size(cs._layout[0], has_label=False) == 50   # per-button
    assert cs._fa_size(cs._layout[1], has_label=False) == 28    # surface default
    await cs.stop()

    # No fa_size anywhere → computed default depends on whether a label is shown.
    bus2, cs2, deck2 = make_surface([ButtonConfig(type="state", state="clear")])
    await cs2.start()
    assert cs2._fa_size(cs2._layout[0], has_label=True) == 30
    assert cs2._fa_size(cs2._layout[0], has_label=False) == 42
    await cs2.stop()


# --------------------------------------------------------------------------
# Font Awesome icons
# --------------------------------------------------------------------------

def test_fa_font_candidates_classic():
    assert ControlSurface._fa_font_candidates("pro", "solid") == [
        "fa-solid-900.woff2"]
    assert ControlSurface._fa_font_candidates("classic", "light") == [
        "fa-light-300.woff2"]


def test_fa_font_candidates_brands_ignores_weight():
    assert ControlSurface._fa_font_candidates("brands", "thin") == [
        "fa-brands-400.woff2"]


def test_fa_font_candidates_sharp_and_sharp_duotone():
    assert ControlSurface._fa_font_candidates("sharp", "solid") == [
        "fa-sharp-solid-900.woff2"]
    assert ControlSurface._fa_font_candidates("sharp-duotone", "thin") == [
        "fa-sharp-duotone-thin-100.woff2"]


def test_fa_font_candidates_duotone_solid_drops_style_word():
    # Duotone light keeps the style word; duotone solid is "fa-duotone-900".
    assert ControlSurface._fa_font_candidates("duotone", "light") == [
        "fa-duotone-light-300.woff2"]
    assert ControlSurface._fa_font_candidates("duotone", "solid") == [
        "fa-duotone-solid-900.woff2", "fa-duotone-900.woff2"]


@pytest.mark.asyncio
async def test_fa_codepoint_resolved_from_metadata(tmp_path):
    meta = tmp_path / "metadata"
    meta.mkdir()
    (meta / "icon-families.json").write_text(json.dumps({
        "file": {"unicode": "f15b", "label": "File"},
    }))
    bus, cs, deck = make_surface(fa_path=str(tmp_path))
    await cs.start()
    assert cs._fa_codepoint("file") == chr(0xF15B)
    assert cs._fa_codepoint("does-not-exist") is None
    await cs.stop()


@pytest.mark.asyncio
async def test_fa_icon_without_font_falls_back_to_label(tmp_path):
    # Metadata present, but no font files → icon can't render → label fallback.
    meta = tmp_path / "metadata"
    meta.mkdir()
    (meta / "icon-families.json").write_text(
        json.dumps({"file": {"unicode": "f15b"}}))
    btn = ButtonConfig(type="state", state="clear", label="File", fa_icon="file")
    bus, cs, deck = make_surface([btn], fa_path=str(tmp_path))
    await cs.start()
    assert deck.images.get(0) is not None   # rendered (as a label) without error
    await cs.stop()


_FA_PRO = "node_modules/@fortawesome/fontawesome-pro"


@pytest.mark.skipif(not os.path.isdir(f"{_FA_PRO}/webfonts"),
                    reason="Font Awesome Pro assets not installed (run `mise run install`)")
@pytest.mark.asyncio
async def test_fa_icon_renders_with_real_assets():
    btn = ButtonConfig(type="state", state="clear", fa_icon="circle-user",
                       fa_type="pro", fa_weight="solid")
    bus, cs, deck = make_surface([btn], fa_path=_FA_PRO)
    await cs.start()
    assert cs._fa_glyph(btn, 40) is not None
    assert deck.images.get(0) is not None
    await cs.stop()


# --------------------------------------------------------------------------
# Pressed-state overrides
# --------------------------------------------------------------------------

def test_apply_pressed_overlays_only_set_fields():
    btn = ButtonConfig(type="state", state="clear", label="Go", color="#111111",
                       text_color="white",
                       pressed=PressedStyle(color="#00FF00", label="Held"))
    eff = ControlSurface._apply_pressed(btn)
    assert eff.color == "#00FF00"        # overridden
    assert eff.label == "Held"            # overridden
    assert eff.text_color == "white"      # untouched appearance field
    assert eff.state == "clear"           # non-appearance field preserved
    # the original button is not mutated
    assert btn.color == "#111111"
    assert btn.label == "Go"


@pytest.mark.asyncio
async def test_pressed_style_renders_on_press_and_reverts_on_release():
    btn = ButtonConfig(type="buzz", player_id=1, label="P1", color="#111111",
                       pressed=PressedStyle(color="#00FF00", label="IN"))
    bus, cs, deck = make_surface([btn])
    await cs.start()
    key = cs._key_of(btn)
    base = deck.image_calls[key]

    await cs._on_key(deck, key, True)     # press
    assert key in cs._pressed
    assert deck.image_calls[key] == base + 1

    await cs._on_key(deck, key, False)    # release
    assert key not in cs._pressed
    assert deck.image_calls[key] == base + 2
    await cs.stop()


@pytest.mark.asyncio
async def test_pressed_button_still_dispatches_on_press():
    btn = ButtonConfig(type="buzz", player_id=3, label="P3",
                       pressed=PressedStyle(color="#00FF00"))
    bus, cs, deck = make_surface([btn])
    await cs.start()
    got = []
    async def cap(e): got.append(e)
    bus.subscribe(BuzzerPressed, cap)
    await cs._on_key(deck, cs._key_of(btn), True)
    assert got and got[0].player_id == 3
    await cs.stop()


@pytest.mark.asyncio
async def test_press_without_pressed_style_does_not_rerender_key():
    btn = ButtonConfig(type="buzz", player_id=1, label="P1")
    bus, cs, deck = make_surface([btn])
    await cs.start()
    key = cs._key_of(btn)
    base = deck.image_calls[key]
    await cs._on_key(deck, key, True)    # dispatch only, no visual change
    await cs._on_key(deck, key, False)
    assert deck.image_calls[key] == base
    assert cs._pressed == set()
    await cs.stop()


@pytest.mark.asyncio
async def test_render_clears_stale_pressed_state():
    sub = PageConfig(buttons=[ButtonConfig(type="sound", path="a.mp3")])
    page_btn = ButtonConfig(type="page", label="Folder", page=sub,
                            pressed=PressedStyle(color="#00FF00"))
    bus, cs, deck = make_surface([page_btn])
    await cs.start()
    key = cs._key_of(page_btn)
    await cs._on_key(deck, key, True)    # press pushes the sub-page (full re-render)
    assert cs._stack == [sub]
    assert cs._pressed == set()          # navigation dropped the held-key state
    await cs.stop()


@pytest.mark.asyncio
async def test_stop_resets_and_closes():
    bus, cs, deck = make_surface([ButtonConfig(type="state", state="clear")])
    await cs.start()
    await cs.stop()
    assert deck.closed
    assert cs._deck is None
