# Changelog

## 1.1.5
- **Fix**: Adjusted the default baudrate from `9600` to `115200` to match Duravolt specification.

## 1.1.4
- **Fix**: Changed the hardcoded test register from `5` to `32104` (SoC) in the diagnostic loop to avoid `ILLEGAL DATA ADDRESS` errors.

## 1.1.3
- **Fix**: Passed `count` as a keyword argument in `safe_client_call` to satisfy PyModbus 3.x keyword-only parameters.

## 1.1.2
- **Fix**: Added support for PyModbus 3.12.x's `device_id=` keyword parameter in `safe_client_call`.

## 1.1.1
- **Fix**: Resolved `TypeError: got an unexpected keyword argument 'slave'` in older PyModbus versions by dynamically falling back to `unit=`.

## 1.1.0
- **Add**: Added a background diagnostic loop that queries holding register 5 (SoC) every 3 seconds to check if physical wiring (A+/B-) is correct, printing clear warnings/errors.
- **Fix**: Resolved `AttributeError: 'coroutine' object has no attribute 'isError'` crash when forwarding requests through the TCP server by introducing `AsyncRemoteDeviceContext`.
- **Feature**: Changed serial port configuration from text input to `device(subsystem=tty)` dropdown selector for easier USB device mapping in the Home Assistant UI.

## 1.0.0
- Initial release of the Modbus TCP to Serial Bridge add-on.
