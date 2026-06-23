#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import sys

# Configure logging to standard output for Home Assistant Add-on logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("modbus_bridge")

# Import PyModbus modules
try:
    from pymodbus import FramerType
    from pymodbus.client import AsyncModbusSerialClient
    from pymodbus.datastore import ModbusServerContext
    from pymodbus.server import StartAsyncTcpServer
    
    # Handle minor import differences across pymodbus v3.x versions (where RemoteDeviceContext is used)
    try:
        from pymodbus.datastore.remote import RemoteDeviceContext
    except ImportError:
        try:
            from pymodbus.datastore.remote import RemoteSlaveContext as RemoteDeviceContext
        except ImportError:
            from pymodbus.datastore import RemoteSlaveContext as RemoteDeviceContext
except ImportError as e:
    logger.critical(f"Failed to import PyModbus modules. Ensure pymodbus v3.x is installed. Error: {e}")
    sys.exit(1)


def load_options():
    """Load configuration options from the Home Assistant Add-on options.json file."""
    options_path = "/data/options.json"
    defaults = {
        "serial_port": "/dev/ttyUSB0",
        "baudrate": 9600,
        "bytesize": 8,
        "stopbits": 1,
        "parity": "N",
        "slave_id": 1,
        "tcp_port": 502
    }
    
    if os.path.exists(options_path):
        try:
            with open(options_path, "r") as f:
                user_options = json.load(f)
                defaults.update(user_options)
                logger.info(f"Loaded configuration options from {options_path}")
        except Exception as e:
            logger.warning(f"Failed to parse {options_path}, using default options. Error: {e}")
    else:
        logger.info(f"Options file {options_path} not found. Operating with default options.")
        
    return defaults


async def run_bridge():
    # Load configuration
    config = load_options()
    
    port = config["serial_port"]
    baudrate = int(config["baudrate"])
    bytesize = int(config["bytesize"])
    stopbits = int(config["stopbits"])
    parity = config["parity"]
    slave_id = int(config["slave_id"])
    tcp_port = int(config["tcp_port"])
    
    logger.info("==========================================")
    logger.info("   Modbus TCP-to-RTU Serial Bridge        ")
    logger.info("==========================================")
    logger.info(f" Serial Port: {port}")
    logger.info(f" Baudrate:    {baudrate}")
    logger.info(f" Data Bits:   {bytesize}")
    logger.info(f" Stop Bits:   {stopbits}")
    logger.info(f" Parity:      {parity}")
    logger.info(f" Slave ID:    {slave_id}")
    logger.info(f" TCP Port:    {tcp_port}")
    logger.info("==========================================")
    
    # Initialize the serial client
    logger.info(f"Connecting to serial port {port}...")
    serial_client = AsyncModbusSerialClient(
        port=port,
        baudrate=baudrate,
        bytesize=bytesize,
        stopbits=stopbits,
        parity=parity,
        framer=FramerType.RTU,
        timeout=2.0
    )
    
    # Test/Open connection
    connected = await serial_client.connect()
    if not connected:
        logger.error(f"Failed to connect to serial port '{port}'.")
        logger.error("Please verify that the USB adapter is plugged in, active, and accessible.")
        sys.exit(1)
        
    logger.info(f"Successfully connected and opened serial port: {port}")
    
    # Initialize RemoteDeviceContext/RemoteSlaveContext to forward requests to the serial client.
    # Fallback to handle signature differences and keyword argument variations.
    store = None
    try:
        # Modern PyModbus v3.x signature (RemoteDeviceContext with device_id)
        store = RemoteDeviceContext(serial_client, device_id=slave_id)
        logger.info(f"Initialized RemoteDeviceContext with device_id={slave_id}")
    except TypeError:
        try:
            # Fallback for RemoteSlaveContext/RemoteDeviceContext with unit=
            store = RemoteDeviceContext(serial_client, unit=slave_id)
            logger.info(f"Initialized RemoteDeviceContext with unit={slave_id}")
        except TypeError:
            try:
                # Fallback for RemoteSlaveContext/RemoteDeviceContext with slave=
                store = RemoteDeviceContext(serial_client, slave=slave_id)
                logger.info(f"Initialized RemoteDeviceContext with slave={slave_id}")
            except TypeError:
                try:
                    # Fallback to positional argument
                    store = RemoteDeviceContext(serial_client, slave_id)
                    logger.info(f"Initialized RemoteDeviceContext with positional unit/device ID: {slave_id}")
                except Exception as context_err:
                    logger.critical(f"Could not instantiate remote device context: {context_err}")
                    await serial_client.close()
                    sys.exit(1)
                
    # Single=True forces all incoming Modbus TCP Unit IDs to map to the single RemoteDeviceContext
    try:
        context = ModbusServerContext(devices=store, single=True)
        logger.info("Initialized ModbusServerContext with devices keyword.")
    except TypeError:
        context = ModbusServerContext(slaves=store, single=True)
        logger.info("Initialized ModbusServerContext with slaves keyword.")
    
    # Start the Modbus TCP Server
    logger.info(f"Starting Modbus TCP server listening on 0.0.0.0:{tcp_port}...")
    try:
        await StartAsyncTcpServer(
            context=context,
            address=("0.0.0.0", tcp_port),
            framer=FramerType.SOCKET
        )
    except Exception as e:
        logger.critical(f"Modbus TCP server failed to start: {e}")
    finally:
        logger.info("Closing serial client connection...")
        await serial_client.close()


def main():
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        logger.info("Bridge execution terminated by user (SIGINT).")
    except Exception as e:
        logger.critical(f"Bridge execution crashed unexpectedly: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
