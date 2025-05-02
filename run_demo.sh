#!/bin/bash
# Demo runner for Tor-inspired relay network
# Usage: ./run_demo.sh

set -e

PYTHON="$(which python3)"

# Cleanup any existing processes first
echo "Cleaning up any existing processes..."
pkill -f "python.*cds.py" || true
pkill -f "python.*relay.py" || true
pkill -f "python.*dest_server.py" || true
sleep 1

# Start CDS
echo "Starting CDS..."
$PYTHON cds.py >cds.log 2>&1 &
CDS_PID=$!
echo "Started CDS (PID $CDS_PID)"
sleep 2  # Increased sleep time to ensure CDS is ready

# Start 3 relays
echo "Starting Relay 1..."
$PYTHON relay.py 1 9101 >relay1.log 2>&1 &
R1_PID=$!
echo "Started Relay 1 (PID $R1_PID, port 9101)"
sleep 1  # Increased sleep time between relay starts

echo "Starting Relay 2..."
$PYTHON relay.py 2 9102 >relay2.log 2>&1 &
R2_PID=$!
echo "Started Relay 2 (PID $R2_PID, port 9102)"
sleep 1  # Increased sleep time between relay starts

echo "Starting Relay 3..."
$PYTHON relay.py 3 9103 >relay3.log 2>&1 &
R3_PID=$!
echo "Started Relay 3 (PID $R3_PID, port 9103)"
sleep 1

# Wait for all relays to register with CDS
echo "Waiting for relays to register with CDS..."
sleep 5  # Increased wait time to ensure all relays register

# Start destination server
echo "Starting Destination Server..."
$PYTHON dest_server.py >dest.log 2>&1 &
DEST_PID=$!
echo "Started Destination Server (PID $DEST_PID, port 9100)"
sleep 2  # Increased sleep time to ensure destination server is ready

# Run client
echo "Running client..."
$PYTHON client.py 127.0.0.1 9100 '{"msg": "Hello, world!"}' | tee client.log
CLIENT_EXIT=$?

# Cleanup
echo "Cleaning up processes..."
kill $CDS_PID $R1_PID $R2_PID $R3_PID $DEST_PID 2>/dev/null || true

# Make sure we clean up no matter what
cleanup() {
  echo "Ensuring all processes are terminated..."
  pkill -f "python.*cds.py" || true
  pkill -f "python.*relay.py" || true
  pkill -f "python.*dest_server.py" || true
}

# Register cleanup function
trap cleanup EXIT

exit $CLIENT_EXIT
