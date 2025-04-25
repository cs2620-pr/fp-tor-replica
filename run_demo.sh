#!/bin/bash
# Demo runner for Tor-inspired relay network
# Usage: ./run_demo.sh

set -e

PYTHON="/Users/mohamedzidancassim/.pyenv/versions/3.13.2/bin/python3"

# Start CDS
$PYTHON cds.py > cds.log 2>&1 &
CDS_PID=$!
echo "Started CDS (PID $CDS_PID)"
sleep 1

# Start 3 relays
$PYTHON relay.py 1 9101 > relay1.log 2>&1 &
R1_PID=$!
echo "Started Relay 1 (PID $R1_PID, port 9101)"
sleep 0.5
$PYTHON relay.py 2 9102 > relay2.log 2>&1 &
R2_PID=$!
echo "Started Relay 2 (PID $R2_PID, port 9102)"
sleep 0.5
$PYTHON relay.py 3 9103 > relay3.log 2>&1 &
R3_PID=$!
echo "Started Relay 3 (PID $R3_PID, port 9103)"
sleep 1

# Wait for all relays to register with CDS
sleep 3

# Start destination server
$PYTHON dest_server.py > dest.log 2>&1 &
DEST_PID=$!
echo "Started Destination Server (PID $DEST_PID, port 9100)"
sleep 1

# Run client
$PYTHON client.py 127.0.0.1 9100 '{"msg": "Hello, world!"}' | tee client.log

# Cleanup
kill $CDS_PID $R1_PID $R2_PID $R3_PID $DEST_PID
