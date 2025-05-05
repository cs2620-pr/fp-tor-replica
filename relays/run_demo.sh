#!/bin/bash
# Debug Demo runner for Tor-inspired relay network
# Usage: ./run_demo.sh [path_length]

# set -e   # DISABLED for debugging

# Number of relays (default 3)
PATH_LENGTH=${1:-3}

# Ports
CDS_PORT=9000
DEST_PORT=9100
RELAY_BASE_PORT=9101

# Kill any process using demo ports (CDS, Dest, Relays)
echo "[DEBUG] Killing old processes..."
PORTS=($CDS_PORT $DEST_PORT)
for ((i=0;i<$PATH_LENGTH;i++)); do
    PORTS+=("$((RELAY_BASE_PORT + i))")
done
for port in "${PORTS[@]}"; do
    PIDS=$(lsof -ti tcp:$port)
    if [ ! -z "$PIDS" ]; then
        echo "Killing processes on port $port: $PIDS"
        kill -9 $PIDS
    fi
    sleep 0.1
done

echo "[DEBUG] Determining Python executable..."
PYTHON=$(command -v python3 || command -v python || echo "python3")
echo "[DEBUG] Using Python: $PYTHON"

echo "[DEBUG] Starting CDS..."
"$PYTHON" cds.py &
CDS_PID=$!
echo "[DEBUG] Started CDS (PID $CDS_PID, port $CDS_PORT)"
sleep 1

echo "[DEBUG] Starting relays..."
RELAY_PIDS=()
for ((i=1;i<=$PATH_LENGTH;i++)); do
    PORT=$((RELAY_BASE_PORT + i - 1))
    echo "[DEBUG] Starting Relay $i on port $PORT..."
    "$PYTHON" relay.py $i $PORT &
    PID=$!
    RELAY_PIDS+=("$PID")
    echo "[DEBUG] Started Relay $i (PID $PID, port $PORT)"
    sleep 0.5
done

echo "[DEBUG] Waiting for relays to register with CDS..."
sleep 5

echo "[DEBUG] Starting destination server..."
"$PYTHON" dest_server.py &
DEST_PID=$!
echo "[DEBUG] Started Destination Server (PID $DEST_PID, port $DEST_PORT)"
sleep 2

echo "[DEBUG] Running client..."
"$PYTHON" client.py 127.0.0.1 $DEST_PORT '{"msg": "Hello, world!"}' $PATH_LENGTH

# Cleanup

echo "[DEBUG] Cleaning up processes..."
kill $CDS_PID $DEST_PID ${RELAY_PIDS[@]}
echo "[DEBUG] Demo complete."
