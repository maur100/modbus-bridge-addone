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


async def safe_client_call(client, method_name, *args, slave_id, **kwargs):
    method = getattr(client, method_name)
    
    # Try with 'slave' keyword argument
    try:
        return await method(*args, slave=slave_id, **kwargs)
    except TypeError as e:
        if "unexpected keyword argument 'slave'" not in str(e):
            raise e
            
    # Try with 'device_id' keyword argument (used in PyModbus 3.12.x)
    try:
        return await method(*args, device_id=slave_id, **kwargs)
    except TypeError as e:
        if "unexpected keyword argument 'device_id'" not in str(e):
            raise e
            
    # Try with 'unit' keyword argument (used in older PyModbus versions)
    try:
        return await method(*args, unit=slave_id, **kwargs)
    except TypeError as e:
        if "unexpected keyword argument 'unit'" not in str(e):
            raise e
            
    raise TypeError(f"Could not find a valid slave/device_id/unit parameter name for {method_name}")


class AsyncRemoteDeviceContext(RemoteDeviceContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = args[0] if args else kwargs.get("client")
        self.slave_id = (
            kwargs.get("device_id")
            or kwargs.get("unit")
            or kwargs.get("slave")
            or (args[1] if len(args) > 1 else 1)
        )

    async def async_getValues(self, func_code, address, count=1):
        try:
            if func_code in (1, 2):
                if func_code == 1:
                    result = await safe_client_call(self.client, "read_coils", address, count=count, slave_id=self.slave_id)
                else:
                    result = await safe_client_call(self.client, "read_discrete_inputs", address, count=count, slave_id=self.slave_id)
                if result.isError():
                    logger.error(f"Error reading coils/inputs: {result}")
                    return [False] * count
                return result.bits[:count]
            elif func_code in (3, 4):
                if func_code == 3:
                    result = await safe_client_call(self.client, "read_holding_registers", address, count=count, slave_id=self.slave_id)
                else:
                    result = await safe_client_call(self.client, "read_input_registers", address, count=count, slave_id=self.slave_id)
                if result.isError():
                    logger.error(f"Error reading registers: {result}")
                    return [0] * count
                return result.registers[:count]
        except Exception as e:
            logger.error(f"Exception during async_getValues: {e}")
        return []

    async def async_setValues(self, func_code, address, values):
        try:
            if func_code == 5:
                await safe_client_call(self.client, "write_coil", address, values[0], slave_id=self.slave_id)
            elif func_code == 15:
                await safe_client_call(self.client, "write_coils", address, values, slave_id=self.slave_id)
            elif func_code == 6:
                await safe_client_call(self.client, "write_register", address, values[0], slave_id=self.slave_id)
            elif func_code == 16:
                await safe_client_call(self.client, "write_registers", address, values, slave_id=self.slave_id)
        except Exception as e:
            logger.error(f"Exception during async_setValues: {e}")


def load_options():
    """Load configuration options from the Home Assistant Add-on options.json file."""
    options_path = "/data/options.json"
    defaults = {
        "serial_port": "/dev/ttyUSB0",
        "baudrate": 115200,
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


async def diagnose_loop(client, slave_id):
    logger.info("==========================================")
    logger.info("🎯 DIAGNOSTISCHE TEST-LOOP GESTART 🎯")
    logger.info(f" Probeert elke 3 seconden Modbus register 32104 (SoC) te lezen van Slave ID: {slave_id}...")
    logger.info("==========================================")
    await asyncio.sleep(2.0)  # Wacht 2 seconden om de verbinding te stabiliseren
    
    while True:
        try:
            # Lees register 32104 (SoC) met safe_client_call om versie-incompatibiliteit te voorkomen
            response = await safe_client_call(client, "read_holding_registers", 32104, count=1, slave_id=slave_id)
            
            if response.isError():
                err_str = str(response)
                err_lower = err_str.lower()
                if "crc" in err_lower:
                    logger.error(
                        "🛑 CRC ERROR: Er is corrupte data ontvangen! De draden maken fysiek contact, "
                        "maar er is ruis, de baudrate/parity is onjuist of er ontbreekt een 120-ohm afsluitweerstand.\n"
                        f"   Details: {err_str}"
                    )
                elif "timeout" in err_lower or "no response" in err_lower or "modbusioexception" in err_lower:
                    logger.warning(
                        "⚠️ TIMEOUT/GEEN ANTWOORD: De batterij reageert helemaal niet.\n"
                        "   Dit betekent meestal dat de A+ en B- draden omgedraaid zijn, "
                        f"de Waveshare adapter niet goed is aangesloten, of Slave ID {slave_id} onjuist is.\n"
                        f"   Details: {err_str}"
                    )
                else:
                    logger.error(f"❌ MODBUS FOUT: {err_str}")
            else:
                registers = response.registers
                logger.info(
                    "✨✨✨ SUCCES! Communicatie werkt! De draden zitten goed! ✨✨✨\n"
                    f"   Gelezen waarde op register 32104 (SoC): {registers[0]}%"
                )
                logger.info("🎯 Diagnose-loop succesvol afgerond en gestopt. De bridge blijft actief voor Home Assistant!")
                return
        except Exception as e:
            err_str = str(e)
            err_lower = err_str.lower()
            if "crc" in err_lower:
                logger.error(
                    "🛑 CRC ERROR (Exception): Er is corrupte data ontvangen!\n"
                    f"   Details: {err_str}"
                )
            elif "timeout" in err_lower or "no response" in err_lower:
                logger.warning(
                    "⚠️ TIMEOUT/GEEN ANTWOORD (Exception): De batterij reageert niet. Controleer A+/B- bedrading.\n"
                    f"   Details: {err_str}"
                )
            else:
                logger.error(f"💥 INTERNE DIAGNOSE FOUT: {err_str}")
                
        await asyncio.sleep(3.0)


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
    
    # Start the diagnostics task in the background
    asyncio.create_task(diagnose_loop(serial_client, slave_id))
    
    # Initialize AsyncRemoteDeviceContext (our custom async-aware context) to forward requests.
    # Fallback to handle signature differences and keyword argument variations of the base class.
    store = None
    try:
        # Modern PyModbus v3.x signature (RemoteDeviceContext with device_id)
        store = AsyncRemoteDeviceContext(serial_client, device_id=slave_id)
        logger.info(f"Initialized AsyncRemoteDeviceContext with device_id={slave_id}")
    except TypeError:
        try:
            # Fallback for RemoteSlaveContext/RemoteDeviceContext with unit=
            store = AsyncRemoteDeviceContext(serial_client, unit=slave_id)
            logger.info(f"Initialized AsyncRemoteDeviceContext with unit={slave_id}")
        except TypeError:
            try:
                # Fallback for RemoteSlaveContext/RemoteDeviceContext with slave=
                store = AsyncRemoteDeviceContext(serial_client, slave=slave_id)
                logger.info(f"Initialized AsyncRemoteDeviceContext with slave={slave_id}")
            except TypeError:
                try:
                    # Fallback to positional argument
                    store = AsyncRemoteDeviceContext(serial_client, slave_id)
                    logger.info(f"Initialized AsyncRemoteDeviceContext with positional unit/device ID: {slave_id}")
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
