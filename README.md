# Tor-Inspired Relay Chat System

## Overview
This project demonstrates a Tor-inspired relay chat system with onion routing, secure messaging, and a user-friendly frontend for relay and message visualization.

---

## Quick Start Guide

### 1. Clone the Repository
```bash
git clone <repo-url>
cd fp-tor-replica
```

### 2. Set Up Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Requirements
```bash
pip install -r requirements.txt
```

### 4. Set Up and Start the Frontend
```bash
cd chat-frontend
npm install
npm start
```
- The frontend will run on [http://localhost:3000](http://localhost:3000) by default. If using a different port, adjust accordingly, but note that for connecting to the flask server, we are using a proxy anyways (5050).
- To access the relay/server monitor, visit [http://localhost:3000/monitor](http://localhost:3000/monitor)

### 5. Start the Backend API Server
In a new terminal (with the virtual environment activated):
```bash
cd fp-tor-replica
python3 api_server.py
```
- The backend runs on [http://localhost:5050](http://localhost:5050)

### 6. Workflow: Using the Monitor
1. **Start the CDS (Central Directory Server):**
   - Use the Start button in the Monitor UI to launch the CDS.
2. **Start the Destination Server:**
   - Use the Start button in the Monitor UI for the destination server.
3. **Add Relays:**
   - Use the Add Relay form in the Monitor to spin up as many relays as you want (specify port and optional ID). Note that relays will be automatically registered with the CDS.
4. **Register and Login:**
   - Create a user account and log in via the frontend. You will probably want to start a new frontend in a different terminal to see both the monitor and the chat pages of different clients at the same time.
5. **Send Messages:**
   - Select how many relays to use for each message (dropdown in chat UI).
   - Messages will traverse the selected number of relays with layered encryption, and this can be seen from the Monitor UI.

### 7. Stopping Components
- You can stop the CDS and destination server from the Monitor UI.
- Relays can be stopped individually.

### 8. Resetting the Database
To clear all users and messages (but keep the structure):
```bash
sqlite3 chat.db "DELETE FROM users; DELETE FROM messages;"
```

---

## Requirements
- Python 3.8+
- Node.js & npm (for frontend)

### Python dependencies (see requirements.txt):
- Flask
- Flask-SocketIO
- cryptography
- psutil
- sqlite3 (Python built-in)

### Frontend dependencies (see chat-frontend/package.json):
- react
- react-dom
- react-router-dom
- react-scripts
- socket.io-client

---

## Notes
- For multi-machine demos, ensure all servers are bound to `0.0.0.0` and firewall allows the relevant ports.
- If you change ports, update the proxy in `chat-frontend/package.json` and backend settings as needed.

---

## Troubleshooting
- If you see 404 errors for API endpoints, make sure the backend has been restarted after any code changes.
- If relays or servers fail to start, check for port conflicts or already-running processes.
- For further help, see the engineering notebook or contact the project maintainers.
