import pytest
from unittest.mock import MagicMock, patch, call
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, StateMachineConfig, LightingConfig, AudioConfig, AudioStateEntry, OBSConfig
from gameshow.events import StateChanged, PlayerBuzzed, GameState, ControlCommand
from gameshow.audio import AudioEngine


def make_config(audio_states=None):
    return AppConfig(
        service=ServiceConfig(),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(),
        lighting=LightingConfig(),
        audio=AudioConfig(
            default_background_volume=0.7,
            default_effect_volume=1.0,
            states=audio_states or {
                "player_1_buzz": AudioStateEntry(effect="sounds/buzz.mp3"),
                "correct": AudioStateEntry(effect="sounds/correct.mp3"),
                "round_start": AudioStateEntry(background="music/theme.mp3"),
            }
        ),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_player_buzzed_plays_effect():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_ch = MagicMock()
        mock_pygame.mixer.Channel.return_value = mock_ch
        mock_pygame.mixer.Sound.return_value = MagicMock()
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(PlayerBuzzed(player_id=1, player_name="P1"))
        mock_pygame.mixer.Sound.assert_called_with("sounds/buzz.mp3")
        mock_ch.play.assert_called_once()


@pytest.mark.asyncio
async def test_state_changed_correct_plays_effect():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_ch = MagicMock()
        mock_pygame.mixer.Channel.return_value = mock_ch
        mock_pygame.mixer.Sound.return_value = MagicMock()
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.CORRECT))
        mock_pygame.mixer.Sound.assert_called_with("sounds/correct.mp3")


@pytest.mark.asyncio
async def test_background_stops_before_new_track():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_bg_ch = MagicMock()
        mock_fx_ch = MagicMock()
        mock_pygame.mixer.Channel.side_effect = [mock_bg_ch, mock_fx_ch]
        mock_pygame.mixer.Sound.return_value = MagicMock()
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.ROUND_START))
        mock_bg_ch.stop.assert_called_once()
        mock_bg_ch.play.assert_called_once()


@pytest.mark.asyncio
async def test_audio_bg_stop_command_stops_background():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.audio.pygame") as mock_pygame:
        mock_bg_ch = MagicMock()
        mock_fx_ch = MagicMock()
        mock_pygame.mixer.Channel.side_effect = [mock_bg_ch, mock_fx_ch]
        engine = AudioEngine(bus, lambda: config)
        await bus.publish(ControlCommand(command="audio_bg_stop"))
        mock_bg_ch.stop.assert_called_once()
