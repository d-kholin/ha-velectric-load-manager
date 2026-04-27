"""Websocket client for VElectric Load Manager."""

from __future__ import annotations

import asyncio
import logging
import math
import struct
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from .const import PACKET_SIZE, PING_INTERVAL, WS_REQUEST_BYTE

_LOGGER = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class LoadStatus(Enum):
    OFF = "off"
    ON = "on"
    WAIT_OFF = "wait-off"
    WAIT_ON = "wait-on"


@dataclass
class LoadConfig:
    """Configuration for a single load channel"""

    load_breaker: int  # Load breaker rating in amps
    turn_on_delay: int  # Delay before turning on load (seconds for wait-on status)
    turn_off_delay: int  # Delay before turning off load (seconds)


@dataclass
class LoadState:
    """Current state of a load channel"""

    status: LoadStatus
    remaining_time: Optional[int] = None  # Remaining time in seconds for wait states


@dataclass
class Settings:
    """VElectric Load Manager configuration settings"""

    main_supply_breaker: int = 100  # Main supply breaker rating in amps
    loads: list[LoadConfig] = None  # Configuration for each load channel (up to 3)
    active_ch: int = 2  # Number of active channels
    ct_index: int = 0  # Current transformer index
    ct_rating: int = 100  # CT rating in amps
    scale: int = 1  # Scaling factor


@dataclass
class CurrentReadings:
    """Current readings from CT1 and CT2"""

    ct1: float  # CT1 current reading in amps
    ct2: float  # CT2 current reading in amps


class VElectricWebSocketClient:
    """Websocket client for VElectric Load Manager."""

    def __init__(self, host: str, port: int = 80) -> None:
        """Initialize the websocket client."""
        self._host = host
        self._port = port
        self._ws_url = f"ws://{host}:{port}/ws"
        self._websocket: websockets.WebSocketClientProtocol | None = None
        self._connected = False
        self._ping_task: asyncio.Task | None = None
        self._message_task: asyncio.Task | None = None
        self._latest_readings: dict[str, float] = {"ct1": 0.0, "ct2": 0.0}
        self._lock = asyncio.Lock()

        # Initialize default settings
        default_loads = [
            LoadConfig(load_breaker=60, turn_on_delay=6, turn_off_delay=10),
            LoadConfig(load_breaker=60, turn_on_delay=8, turn_off_delay=8),
            LoadConfig(load_breaker=60, turn_on_delay=10, turn_off_delay=6),
        ]
        self.settings = Settings(loads=default_loads)

        # Current state
        self.current_readings = CurrentReadings(ct1=0.0, ct2=0.0)
        self.load_status = [LoadState(LoadStatus.OFF) for _ in range(3)]
        self.connection_status = ConnectionStatus.DISCONNECTED

        # Event callbacks
        self.on_status_change: Optional[Callable] = None
        self.on_current_reading: Optional[Callable] = None
        self.on_settings_update: Optional[Callable] = None

    async def connect(self) -> None:
        """Connect to the VElectric device."""
        async with self._lock:
            if self._connected:
                return

            try:
                _LOGGER.debug("Connecting to VElectric device at %s", self._ws_url)
                self.connection_status = ConnectionStatus.CONNECTING
                self._notify_status_change()

                self._websocket = await websockets.connect(self._ws_url)
                self._connected = True
                self.connection_status = ConnectionStatus.CONNECTED
                _LOGGER.info("Connected to VElectric device at %s", self._ws_url)
                self._notify_status_change()

                # Send initial command (105) to initialize connection
                await self._send_command(105)

                # Start the ping loop and message handler
                self._ping_task = asyncio.create_task(self._ping_loop())
                self._message_task = asyncio.create_task(self._message_handler())

            except Exception as err:
                _LOGGER.error("Failed to connect to VElectric device: %s", err)
                self._connected = False
                self.connection_status = ConnectionStatus.DISCONNECTED
                self._notify_status_change()
                raise

    async def disconnect(self) -> None:
        """Disconnect from the VElectric device."""
        if not self._connected:
            return

        _LOGGER.debug("Disconnecting from VElectric device")
        self._connected = False

        # Cancel tasks with timeout protection
        tasks_to_cancel = [self._ping_task, self._message_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        self._ping_task = None
        self._message_task = None

        if self._websocket:
            try:
                await asyncio.wait_for(self._websocket.close(), timeout=5.0)
            except asyncio.TimeoutError:
                _LOGGER.warning("WebSocket close timed out")
            finally:
                self._websocket = None

        self.connection_status = ConnectionStatus.DISCONNECTED
        self._notify_status_change()
        _LOGGER.info("Disconnected from VElectric device")

    async def get_readings(self) -> dict[str, float]:
        """Get the latest current readings."""
        if not self._connected:
            raise ConnectionError("Not connected to VElectric device")

        async with self._lock:
            return self._latest_readings.copy()

    def decode_currents(self, packet: bytes) -> dict[str, float]:
        """Decode a 14-byte packet and extract current readings for ct1 and ct2."""
        if len(packet) != PACKET_SIZE:
            _LOGGER.warning(
                "Invalid packet size: %d bytes (expected %d)", len(packet), PACKET_SIZE
            )
            return {"ct1": 0.0, "ct2": 0.0}

        try:
            raw1, raw2 = struct.unpack_from("<HH", packet, 0)
            readings = {
                "ct1": round(math.sqrt(raw1), 1),
                "ct2": round(math.sqrt(raw2), 1),
            }
            _LOGGER.debug("Decoded readings: %s", readings)
            return readings
        except struct.error as err:
            _LOGGER.error("Failed to decode packet: %s", err)
            return {"ct1": 0.0, "ct2": 0.0}

    async def _ping_loop(self) -> None:
        """Send periodic ping requests to get readings."""
        while self._connected and self._websocket:
            try:
                await self._websocket.send(bytes([WS_REQUEST_BYTE]))
                _LOGGER.debug("Sent reading request")
                await asyncio.sleep(PING_INTERVAL)
            except (ConnectionClosed, WebSocketException) as err:
                _LOGGER.warning("Connection lost during ping: %s", err)
                self._connected = False
                break
            except Exception as err:
                _LOGGER.error("Error in ping loop: %s", err)
                self._connected = False
                break

    async def _message_handler(self) -> None:
        """Handle incoming websocket messages."""
        if not self._websocket:
            return

        try:
            async for message in self._websocket:
                if isinstance(message, (bytes, bytearray)):
                    await self._process_binary_message(message)
                else:
                    _LOGGER.debug("Received unexpected message: %s", message)
        except (ConnectionClosed, WebSocketException) as err:
            _LOGGER.warning("Connection lost in message handler: %s", err)
            self._connected = False
            self.connection_status = ConnectionStatus.DISCONNECTED
            self._notify_status_change()
        except Exception as err:
            _LOGGER.error("Error in message handler: %s", err)
            self._connected = False
            self.connection_status = ConnectionStatus.DISCONNECTED
            self._notify_status_change()

    @property
    def is_connected(self) -> bool:
        """Return True if connected to the device."""
        return self._connected

    async def _process_binary_message(self, data: bytes) -> None:
        """
        Process binary messages from VElectric device

        Two types of messages:
        1. Settings/Config (12 bytes) - Contains device configuration
        2. Status/Readings (13+ bytes) - Contains current readings and load status

        Some firmware versions prefix the settings response with the originating
        command byte (105), making it 13 bytes total.
        """
        _LOGGER.debug("Received %d-byte binary message: %s", len(data), data.hex())

        if len(data) == 12:
            # Standard settings/config message
            await self._process_settings_message(data)
        elif len(data) == 13 and data[0] == 105:
            # Settings response prefixed with the init command echo (byte 105)
            _LOGGER.debug("Parsing 13-byte settings echo (prefix byte: %d)", data[0])
            await self._process_settings_message(data[1:])
        else:
            # Current readings and load status message (13+ bytes)
            await self._process_readings_message(data)

    async def _process_settings_message(self, data: bytes) -> None:
        """
        Process 12-byte settings message

        Message format:
        Byte 0: Main supply breaker rating
        Bytes 1-3: Load 1 config (breaker, turn_on_delay, turn_off_delay)
        Bytes 4-6: Load 2 config (breaker, turn_on_delay, turn_off_delay)
        Bytes 7-9: Load 3 config (breaker, turn_on_delay, turn_off_delay)
        Byte 10: Active channels count
        Byte 11: CT index
        """
        # Parse main supply breaker
        main_breaker = data[0] * 1  # Scale factor of 1

        # Parse load configurations
        loads = []
        for i in range(3):
            base_idx = i * 3 + 1
            load_config = LoadConfig(
                load_breaker=data[base_idx] * 1,  # Scale factor of 1
                turn_on_delay=data[base_idx + 1],
                turn_off_delay=data[base_idx + 2],
            )
            loads.append(load_config)

        # Parse other settings
        active_ch = data[10]
        ct_index = data[11]
        ct_rating = 100 * (ct_index + 1)  # CT rating calculation

        # Update settings
        self.settings = Settings(
            main_supply_breaker=main_breaker,
            loads=loads,
            active_ch=active_ch,
            ct_index=ct_index,
            scale=1,
            ct_rating=ct_rating,
        )

        if self.on_settings_update:
            self.on_settings_update(self.settings)

    async def _process_readings_message(self, data: bytes) -> None:
        """
        Process current readings and load status message

        Observed packet layout (bytes 2-3 are a reserved/unknown field, always 0):
          Bytes 0-1:  CT1 raw reading (uint16, little-endian)
          Bytes 2-3:  Reserved (always 0 — not CT2)
          Bytes 4-5:  CT2 raw reading (uint16, little-endian)
          Bytes 6-7:  Load 1 counter (uint16, little-endian)
          Bytes 8-9:  Load 2 counter (uint16, little-endian)
          Byte  10:   Load 1 status (0=off, 1=on, 2=wait-off, 3=wait-on)
          Byte  11:   Load 2 status
          Byte  12:   Load 3 status
          — 15-byte extended variant also carries Load 3 counter at bytes 10-11
            and shifts statuses to bytes 12-14.
        """
        if len(data) < 13:
            _LOGGER.debug("Ignoring short readings packet: %d bytes", len(data))
            return

        # Bytes 2-3 are a reserved field (always 0); CT2 is at bytes 4-5.
        ct1_raw = struct.unpack("<H", data[0:2])[0]
        ct2_raw = struct.unpack("<H", data[4:6])[0]

        ct1_current = math.sqrt(ct1_raw)
        ct2_current = math.sqrt(ct2_raw)

        self.current_readings = CurrentReadings(
            ct1=round(ct1_current, 1), ct2=round(ct2_current, 1)
        )

        async with self._lock:
            self._latest_readings = {
                "ct1": self.current_readings.ct1,
                "ct2": self.current_readings.ct2,
            }

        # 15-byte variant carries all three load counters; 13-14-byte variant
        # carries only Load 1 and Load 2 counters (Load 3 counter absent).
        if len(data) >= 15:
            load_counters = [
                struct.unpack("<H", data[6:8])[0],
                struct.unpack("<H", data[8:10])[0],
                struct.unpack("<H", data[10:12])[0],
            ]
            load_status_bytes = [data[12], data[13], data[14]]
        else:
            load_counters = [
                struct.unpack("<H", data[6:8])[0],
                struct.unpack("<H", data[8:10])[0],
                0,
            ]
            load_status_bytes = [data[10], data[11], data[12]]

        # Get delay settings from current configuration
        turn_on_delays = [load.turn_on_delay for load in self.settings.loads]
        turn_off_delays = [load.turn_off_delay for load in self.settings.loads]

        # Update load status with remaining time calculations
        self.load_status = []
        for i in range(3):
            status_byte = load_status_bytes[i]
            remaining_time = None

            if status_byte == 0:
                status = LoadStatus.OFF
            elif status_byte == 1:
                status = LoadStatus.ON
            elif status_byte == 2:
                # Wait-off: counting down turn_off_delay
                status = LoadStatus.WAIT_OFF
                remaining_time = max(0, turn_off_delays[i] - load_counters[i])
            elif status_byte == 3:
                # Wait-on: counting down turn_on_delay (in minutes, converted to seconds)
                status = LoadStatus.WAIT_ON
                remaining_time = max(0, turn_on_delays[i] * 60 - load_counters[i])
            else:
                status = LoadStatus.OFF

            self.load_status.append(
                LoadState(status=status, remaining_time=remaining_time)
            )

        # Notify callbacks
        if self.on_current_reading:
            self.on_current_reading(self.current_readings, self.load_status)

    async def _send_command(self, command: int) -> None:
        """Send single-byte command to device"""
        if self._websocket and self._connected:
            command_bytes = struct.pack("B", command)
            await self._websocket.send(command_bytes)

    # Configuration modification methods removed for safety
    # This integration is read-only monitoring only

    def _notify_status_change(self) -> None:
        """Notify callback of connection status change"""
        if self.on_status_change:
            self.on_status_change(self.connection_status)

    def get_state_dict(self) -> dict:
        """Get current state as dictionary for serialization"""
        return {
            "connection_status": self.connection_status.value,
            "current_readings": asdict(self.current_readings),
            "load_status": [asdict(load) for load in self.load_status],
            "settings": asdict(self.settings),
            "host": self._host,
            "port": self._port,
        }
