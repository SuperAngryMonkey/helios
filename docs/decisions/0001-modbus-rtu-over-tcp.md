# 0001 — Modbus RTU framed over raw TCP

Date: 2026-06-04 · Status: Accepted

## Context

The Wanderer 30A speaks Modbus RTU on its RS-232 port. To get it onto the
network without buying Renogy's BT-1 dongle (or building an ESP32 +
MAX3232), we use a serial-to-Ethernet gateway in TCP-server mode.

The gateway re-emits the raw serial bytes on a TCP socket. We need to
choose how to talk to it from Python.

## Options considered

1. **Modbus RTU framed over raw TCP** — pymodbus's `ModbusTcpClient` with
   `framer=FramerType.RTU`. The TCP transport carries the Modbus RTU
   frames (including CRC) verbatim, the framer parses them.
2. **Modbus TCP** (the actual standard protocol on port 502 with MBAP
   header). Would require either a Modbus-TCP-capable gateway (this one
   isn't) or a translation layer.
3. **Virtual COM port via vendor utility** — installs a Windows/Linux
   driver that exposes the network gateway as a local `/dev/tty*`.
   Couples helios to a specific platform's userland.
4. **`socat` to bridge TCP to a pseudo-tty**, then `ModbusSerialClient`.
   Adds a userland process to the dependency graph.

## Decision

Option 1: RTU framer over a TCP socket.

## Rationale

- Zero extra moving parts. pymodbus does the framing natively.
- Identical behavior to a real serial port from the Python side — easy
  to swap if the gateway is replaced with a USB-serial dongle later.
- Works with any TCP-server-mode serial gateway, vendor-agnostic.
- One gotcha: the gateway must buffer serial bytes until a full Modbus
  frame is on the wire (inter-character timeout). Without that, frames
  fragment across TCP segments. 50 ms is the safe value.

## Consequences

- Code uses `ModbusTcpClient(framer=FramerType.RTU)`, not the actual
  Modbus TCP framer. Easy to confuse; documented in DESIGN.md.
- pymodbus version matters: 3.13 uses `device_id=`, earlier versions
  used `slave=` or `unit=`. Pinned in `requirements.txt`.
