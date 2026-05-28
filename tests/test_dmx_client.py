import pytest
from unittest.mock import MagicMock, patch
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, PlayerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import StateChanged, PlayerBuzzed, GameState
from gameshow.dmx_client import DMXClient


def make_config(lighting_states=None):
    return AppConfig(
        service=ServiceConfig(dmx_osc_host="localhost", dmx_osc_port=21600),
        buzzers=BuzzerConfig(players=[PlayerConfig(id=1, name="P1", key="1")]),
        state_machine=StateMachineConfig(),
        lighting=LightingConfig(states=lighting_states or {
            "idle": "/palette/Idle/activate",
            "locked": "/palette/Locked/activate",
            "player_1_buzz": "/palette/Buzz_P1/start",
        }),
        audio=AudioConfig(),
        obs=OBSConfig(),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_state_changed_sends_configured_osc():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.dmx_client.SimpleUDPClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        client = DMXClient(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.LOCKED))
        mock_client.send_message.assert_called_once_with("/palette/Locked/activate", [])


@pytest.mark.asyncio
async def test_player_buzzed_sends_player_specific_cue():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.dmx_client.SimpleUDPClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        client = DMXClient(bus, lambda: config)
        await bus.publish(PlayerBuzzed(player_id=1, player_name="P1"))
        mock_client.send_message.assert_called_once_with("/palette/Buzz_P1/start", [])


@pytest.mark.asyncio
async def test_state_with_no_configured_cue_sends_nothing():
    bus = EventBus()
    config = make_config(lighting_states={"idle": "/palette/Idle/activate"})
    with patch("gameshow.dmx_client.SimpleUDPClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        client = DMXClient(bus, lambda: config)
        await bus.publish(StateChanged(new_state=GameState.CORRECT))
        mock_client.send_message.assert_not_called()
