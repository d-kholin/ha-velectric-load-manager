"""Constants for VElectric Load Manager integration."""

from typing import Final

DOMAIN: Final = "velectric_load_manager"

# Configuration keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_NAME: Final = "name"
CONF_VOLTAGE: Final = "voltage"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_PORT: Final = 80
DEFAULT_SCAN_INTERVAL: Final = 5  # seconds (reduced from 2s to be less aggressive)
DEFAULT_VOLTAGE: Final = 120  # Voltage per leg (split-phase: each CT measures one 120V leg)

# Device info
MANUFACTURER: Final = "VElectric"
MODEL: Final = "Load Manager"

# Websocket protocol
WS_REQUEST_BYTE: Final = 103  # 'g' command for readings
PACKET_SIZE: Final = 14  # Expected packet size in bytes
PING_INTERVAL: Final = 2.0  # Seconds between pings

# Sensor keys
SENSOR_CT1_CURRENT: Final = "ct1_current"
SENSOR_CT2_CURRENT: Final = "ct2_current"
SENSOR_CT1_POWER: Final = "ct1_power"
SENSOR_CT2_POWER: Final = "ct2_power"
SENSOR_CT1_ENERGY: Final = "ct1_energy"
SENSOR_CT2_ENERGY: Final = "ct2_energy"
SENSOR_TOTAL_CURRENT: Final = "total_current"
SENSOR_TOTAL_POWER: Final = "total_power"
SENSOR_TOTAL_ENERGY: Final = "total_energy"
SENSOR_CONNECTION_STATUS: Final = "connection_status"

# Load sensor keys
SENSOR_LOAD1_STATUS: Final = "load1_status"
SENSOR_LOAD2_STATUS: Final = "load2_status"
SENSOR_LOAD3_STATUS: Final = "load3_status"
SENSOR_LOAD1_REMAINING_TIME: Final = "load1_remaining_time"
SENSOR_LOAD2_REMAINING_TIME: Final = "load2_remaining_time"
SENSOR_LOAD3_REMAINING_TIME: Final = "load3_remaining_time"

# Settings sensor keys
SENSOR_MAIN_BREAKER: Final = "main_supply_breaker"
SENSOR_ACTIVE_CHANNELS: Final = "active_channels"
SENSOR_CT_RATING: Final = "ct_rating"
SENSOR_CT_INDEX: Final = "ct_index"
SENSOR_LOAD1_BREAKER: Final = "load1_breaker"
SENSOR_LOAD2_BREAKER: Final = "load2_breaker"
SENSOR_LOAD3_BREAKER: Final = "load3_breaker"
SENSOR_LOAD1_TURN_ON_DELAY: Final = "load1_turn_on_delay"
SENSOR_LOAD2_TURN_ON_DELAY: Final = "load2_turn_on_delay"
SENSOR_LOAD3_TURN_ON_DELAY: Final = "load3_turn_on_delay"
SENSOR_LOAD1_TURN_OFF_DELAY: Final = "load1_turn_off_delay"
SENSOR_LOAD2_TURN_OFF_DELAY: Final = "load2_turn_off_delay"
SENSOR_LOAD3_TURN_OFF_DELAY: Final = "load3_turn_off_delay"

# Sensor names
SENSOR_NAMES = {
    SENSOR_CT1_CURRENT: "CT1 Current",
    SENSOR_CT2_CURRENT: "CT2 Current",
    SENSOR_CT1_POWER: "CT1 Power",
    SENSOR_CT2_POWER: "CT2 Power",
    SENSOR_CT1_ENERGY: "CT1 Energy",
    SENSOR_CT2_ENERGY: "CT2 Energy",
    SENSOR_TOTAL_CURRENT: "Total Current",
    SENSOR_TOTAL_POWER: "Total Power",
    SENSOR_TOTAL_ENERGY: "Total Energy",
    SENSOR_CONNECTION_STATUS: "Connection Status",
    SENSOR_LOAD1_STATUS: "Load 1 Status",
    SENSOR_LOAD2_STATUS: "Load 2 Status",
    SENSOR_LOAD3_STATUS: "Load 3 Status",
    SENSOR_LOAD1_REMAINING_TIME: "Load 1 Remaining Time",
    SENSOR_LOAD2_REMAINING_TIME: "Load 2 Remaining Time",
    SENSOR_LOAD3_REMAINING_TIME: "Load 3 Remaining Time",
    SENSOR_MAIN_BREAKER: "Main Supply Breaker",
    SENSOR_ACTIVE_CHANNELS: "Active Channels",
    SENSOR_CT_RATING: "CT Rating",
    SENSOR_CT_INDEX: "CT Index",
    SENSOR_LOAD1_BREAKER: "Load 1 Breaker Rating",
    SENSOR_LOAD2_BREAKER: "Load 2 Breaker Rating",
    SENSOR_LOAD3_BREAKER: "Load 3 Breaker Rating",
    SENSOR_LOAD1_TURN_ON_DELAY: "Load 1 Turn On Delay",
    SENSOR_LOAD2_TURN_ON_DELAY: "Load 2 Turn On Delay",
    SENSOR_LOAD3_TURN_ON_DELAY: "Load 3 Turn On Delay",
    SENSOR_LOAD1_TURN_OFF_DELAY: "Load 1 Turn Off Delay",
    SENSOR_LOAD2_TURN_OFF_DELAY: "Load 2 Turn Off Delay",
    SENSOR_LOAD3_TURN_OFF_DELAY: "Load 3 Turn Off Delay",
}
