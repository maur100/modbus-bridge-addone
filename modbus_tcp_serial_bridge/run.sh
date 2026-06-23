#!/usr/bin/env ash
set -e

echo "=========================================="
echo " Starting Modbus TCP to RTU Bridge Add-on "
echo "=========================================="

# Run the python bridge script
exec python3 /app/bridge.py
