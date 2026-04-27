# VElectric Load Manager — HA Integration

## What This Is

A read-only Home Assistant HACS integration that connects to a VElectric electrical load manager over a local WebSocket and exposes real-time readings as HA sensors. The device manages up to 3 controllable loads (e.g. EV charger, hot tub) based on whole-house current draw from two CTs installed on the main panel legs (L1 and L2).

## Core Value

Both CT1 and CT2 current readings are accurate, so total household power consumption and all derived sensors (power, energy) reflect reality.

## Requirements

### Validated

- ✓ CT1 current sensor reports correct amps — existing
- ✓ Power calculation sensors (current × configured voltage) — existing
- ✓ Energy accumulation sensors with HA state restoration across restarts — existing
- ✓ WebSocket auto-reconnect with exponential backoff — existing
- ✓ Config flow (UI setup: host, port, voltage, scan interval) — existing
- ✓ Load status sensors for 3 channels (off / on / wait-off / wait-on) — existing
- ✓ Load remaining-time sensors (countdown during wait states) — existing
- ✓ Device settings sensors (breaker ratings, CT rating, delays) — existing
- ✓ Connection status sensor — existing
- ✓ Binary sensor for connected/disconnected state — existing
- ✓ HACS-compatible structure (hacs.json, manifest.json, config_flow) — existing

### Active

- [ ] CT2 current reads correctly (non-zero) from the second main leg
- [ ] Raw packet hex logging so byte-layout problems are immediately visible in HA logs
- [ ] Total current / power / energy sensors accurate once CT2 is fixed (CT1 + CT2)

### Out of Scope

- Writing settings back to device — explicitly removed for safety; device has its own UI
- Multiple simultaneous device instances — single-device support covers current use case
- MQTT bridge / cloud relay — local-only is the design intent

## Context

The device communicates over `ws://{host}/ws`. Sending byte `103` triggers a response. The integration currently handles two response types:

- **12-byte**: settings/config message (breaker ratings, delays, CT index)
- **13+ byte**: readings message (CT raw values + load status)

CT1 and CT2 raw values are `uint16 little-endian`; actual current = `sqrt(raw_value)`. CT1 always reports correctly; CT2 always reports `0.0 A`. Since CT2 is on the second main leg and should never read zero in a live household, this is a parsing bug — the raw `uint16` at bytes 2–3 is coming back as `0`. Root cause is unknown until raw packet bytes are logged and inspected.

There is also a dead-code path in `_process_readings_message`: the fallback for "legacy 14-byte" packets (`len(data) == PACKET_SIZE`) sits unreachably inside an `if len(data) < 13:` guard. The device packet size needs to be confirmed from diagnostics.

## Constraints

- **Read-only**: Integration must not write configuration to the device
- **HA compatibility**: Must work with current Home Assistant core (DataUpdateCoordinator, CoordinatorEntity patterns)
- **HACS**: Must remain HACS-installable (`hacs.json` present, versioned via `version.py`)
- **Python async**: All I/O must be non-blocking (asyncio + websockets library)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Add raw hex packet logging before fixing CT2 | Can't fix what we can't see — diagnostics first | — Pending |
| Keep total sensors (CT1+CT2) | Represents true whole-house L1+L2 consumption | — Pending |
| Read-only integration | Safety — device controls high-current loads | ✓ Good |

---
*Last updated: 2026-04-27 after initialization*
