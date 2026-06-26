ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# Ash options for safety
SHELL ["/bin/ash", "-o", "pipefail", "-c"]

# Install required Python packages for pymodbus v3.12.1
RUN pip install --no-cache-dir \
    pymodbus==3.12.1 \
    pyserial==3.5 \
    pyserial-asyncio-fast==0.1.2

# Copy application files
COPY run.sh /app/run.sh
COPY bridge.py /app/bridge.py

# Fix Windows CRLF line endings in the shell script and make it executable
RUN sed -i 's/\r$//' /app/run.sh && chmod +x /app/run.sh

WORKDIR /app

# Start the bridge via the shell wrapper
CMD [ "/app/run.sh" ]
