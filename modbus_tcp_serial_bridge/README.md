# Modbus TCP to Serial Bridge Add-on

A Home Assistant local Add-on to bridge Modbus TCP traffic (port 502) to a Modbus RTU serial interface (e.g. `/dev/ttyUSB0` at 9600 8N1) specifically for Marstek home battery systems.

## Features
- Fully asynchronous TCP server and RTU serial client using PyModbus 3.x.
- Configuration options via the Home Assistant user interface.
- Automatic container watchdogs and restarts via Home Assistant Supervisor.

## Configuration Options
Configure these settings on the **Configuration** tab in the Home Assistant UI:
- `serial_port`: The path to your USB-to-RS485 adapter (default: `/dev/ttyUSB0`).
- `baudrate`: Serial baudrate (default: `9600`).
- `bytesize`: Data bits (default: `8`).
- `stopbits`: Stop bits (default: `1`).
- `parity`: Parity choice `N` (None), `E` (Even), or `O` (Odd).
- `slave_id`: The Modbus Slave/Unit ID of your Marstek battery (default: `1`).
- `tcp_port`: Local port to bind the Modbus TCP server (default: `502`).
