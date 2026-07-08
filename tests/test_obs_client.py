import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from gameshow.bus import EventBus
from gameshow.config import AppConfig, ServiceConfig, BuzzerConfig, StateMachineConfig, LightingConfig, AudioConfig, OBSConfig
from gameshow.events import StateChanged, ControlCommand
from gameshow.obs_client import OBSClient


def make_config(obs_states=None):
    return AppConfig(
        service=ServiceConfig(obs_host="localhost", obs_port=4455, obs_password=""),
        buzzers=BuzzerConfig(players=[]),
        state_machine=StateMachineConfig(initial="idle"),
        lighting=LightingConfig(),
        audio=AudioConfig(),
        obs=OBSConfig(states=obs_states or {
            "idle": "Idle",
            "locked": "Buzz_Locked",
            "correct": "Correct",
        }),
        scenes=[],
    )


@pytest.mark.asyncio
async def test_state_changed_calls_obs_switch():
    bus = EventBus()
    config = make_config()
    mock_ws = AsyncMock()
    mock_ws.call = AsyncMock(return_value=MagicMock())

    with patch("gameshow.obs_client.simpleobsws.WebSocketClient", return_value=mock_ws):
        client = OBSClient(bus, lambda: config)
        client._ws = mock_ws
        client._connected = True
        await bus.publish(StateChanged(new_state="locked"))
        mock_ws.call.assert_called_once()
        args = mock_ws.call.call_args
        assert "Buzz_Locked" in str(args)


@pytest.mark.asyncio
async def test_state_with_no_obs_mapping_sends_nothing():
    bus = EventBus()
    config = make_config(obs_states={"idle": "Idle"})
    mock_ws = AsyncMock()

    with patch("gameshow.obs_client.simpleobsws.WebSocketClient", return_value=mock_ws):
        client = OBSClient(bus, lambda: config)
        client._ws = mock_ws
        client._connected = True
        await bus.publish(StateChanged(new_state="correct"))
        mock_ws.call.assert_not_called()


@pytest.mark.asyncio
async def test_obs_request_calls_ws_with_request_type_and_data():
    bus = EventBus()
    config = make_config()
    mock_ws = AsyncMock()
    mock_ws.call = AsyncMock(return_value=MagicMock())

    with patch("gameshow.obs_client.simpleobsws.WebSocketClient", return_value=mock_ws):
        client = OBSClient(bus, lambda: config)
        client._ws = mock_ws
        client._connected = True
        await bus.publish(ControlCommand(
            command="obs_request",
            args=("SetInputMute", {"inputName": "Mic", "inputMuted": True}),
        ))
        mock_ws.call.assert_called_once()
        assert "SetInputMute" in str(mock_ws.call.call_args)


@pytest.mark.asyncio
async def test_obs_request_not_connected_does_not_call():
    bus = EventBus()
    config = make_config()
    mock_ws = AsyncMock()
    with patch("gameshow.obs_client.simpleobsws.WebSocketClient", return_value=mock_ws):
        client = OBSClient(bus, lambda: config)
        client._connected = False
        await bus.publish(ControlCommand(command="obs_request", args=("StartRecord",)))
        mock_ws.call.assert_not_called()


@pytest.mark.asyncio
async def test_obs_not_connected_does_not_raise():
    bus = EventBus()
    config = make_config()
    with patch("gameshow.obs_client.simpleobsws.WebSocketClient"):
        client = OBSClient(bus, lambda: config)
        client._connected = False
        await bus.publish(StateChanged(new_state="locked"))
        # no exception
