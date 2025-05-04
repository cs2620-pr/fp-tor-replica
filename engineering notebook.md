# Engineering Notebook: Tor-Inspired Relay Chat System

## Project Overview
This project is a Tor-inspired relay chat system designed to demonstrate the principles of onion routing, secure messaging, and distributed relay management. It features a robust backend for relay and destination server management, a user-friendly frontend for visualization and control, and a modular client for secure communication.

---

## What the Project Does
- **Relay Management:** Dynamically start, stop, and monitor relays. Each relay acts as a node in the onion routing network.
- **Destination Server:** Acts as the endpoint for messages traversing the relay chain.
- **Client Messaging:** Users can send messages through a configurable chain of relays, experiencing layered encryption and decryption.
- **Visualization:** The frontend allows users to visualize the relay network, see the relay chain for each message, and step through the encryption/decryption process.
- **User Management:** Supports user registration, login, and chat functionality.

---

## How It Works
### Architecture
- **Backend (Flask + Python):**
  - Hosts API endpoints for relay management, user management, and message routing.
  - Uses `psutil` for robust process discovery and management, allowing relays and the destination server to be started/stopped regardless of how they were launched.
  - Maintains a database for users and messages.
- **Relays:**
  - Each relay is a separate process, identified by port and optional ID.
  - Relays register with a central directory server (CDS) and forward encrypted messages.
- **Destination Server:**
  - Receives and decrypts the final message in the chain.
- **Frontend (React + JS/HTML/CSS):**
  - Provides a dashboard for relay/server management and network visualization.
  - Allows users to add relays, start/stop the destination server, and monitor real-time status.
  - Visualizes the relay chain and encryption steps for educational purposes.
- **Client:**
  - Can be run from any computer (with network access to the server) to send messages through the relay chain.

---

## Major Design Choices
### 1. **Process Management with psutil**
- **Why:** Needed robust, persistent process discovery and management, especially after backend restarts.
- **How:** Backend uses `psutil` to find, start, and stop relay and destination server processes by port or script name, not relying on in-memory state.
- **Result:** Relays and servers can be managed even if the backend is restarted or run from multiple terminals.

### 2. **Frontend-Backend Synchronization**
- **Why:** The UI must always reflect the true state of relays and servers, regardless of backend restarts or manual process launches.
- **How:** The `/api/monitor` endpoint dynamically discovers running relays and the destination server using process inspection.
- **Result:** The frontend always shows the correct status, and actions like start/stop are reliable.

### 3. **User-Friendly UI/UX**
- **Why:** To make relay management and onion routing concepts accessible and interactive.
- **How:**
  - Added forms for adding relays with port/ID.
  - Removed unnecessary controls (e.g., only "Stop" is shown for running relays).
  - Column headers and data are always aligned.
  - Visualization of relay chains and encryption steps.
- **Result:** Users can easily manage the network and understand the routing/encryption process.

### 4. **Security and Isolation**
- **Why:** To demonstrate secure, layered encryption and avoid accidental process conflicts.
- **How:**
  - Each relay uses a persistent RSA keypair.
  - Relays and destination server run as isolated processes.
  - All communication is encrypted hop-by-hop.
- **Result:** Simulates real Tor-like security and isolation.

### 5. **Extensibility and Decoupling**
- **Why:** To allow future expansion (e.g., more relay types, new visualizations) and independent development of frontend/backend.
- **How:**
  - The frontend and backend communicate via clean REST APIs.
  - The demo visualization frontend (`demo-frontend`) is decoupled from the backend logic.
- **Result:** Easy to extend, maintain, and adapt for new demos or research.

### 6. **Network Accessibility**
- **Why:** To allow clients on different machines to join the relay network.
- **How:**
  - Server and relays can be configured to bind to `0.0.0.0` for LAN/internet access.
  - Client can specify the server's IP address.
- **Result:** Supports distributed, multi-machine demos.

---

## Notable Implementation Details
- **Persistent Key Management:** Each relay stores its RSA keypair for consistent identity.
- **Dynamic Process Discovery:** Relays/destination are found by inspecting running processes, not just by tracking launches.
- **API-Driven UI:** All relay/server actions are performed via API calls, ensuring clean separation and easy automation/testing.
- **Error Handling:** Backend and frontend provide clear feedback for errors (e.g., trying to start an already-running server).
- **Live Updates:** The UI uses sockets/events to refresh the network view upon relevant changes.

---

## Challenges and Solutions
- **Process Tracking Across Restarts:** Solved by using `psutil` for process discovery instead of in-memory state.
- **UI/Backend Sync:** Ensured by always querying the true process state, not cached/in-memory data.
- **Network Access:** Required explicit configuration for multi-machine demos (binding to `0.0.0.0`, firewall settings).
- **User Experience:** Iteratively improved UI for clarity, reliability, and educational value.

---

## Future Work
- **Enhanced Visualization:** More detailed step-by-step encryption/decryption animations.
- **Security Features:** Add authentication for relay management endpoints.
- **Scalability:** Support for larger relay networks and distributed directory servers.
- **Research Extensions:** Plug in new routing algorithms or relay types for experimentation.

---

## Summary
This project demonstrates a secure, extensible, and user-friendly Tor-inspired relay chat network. Through robust process management, clear UI, and modular architecture, it provides a powerful platform for learning, experimentation, and demonstration of onion routing and secure communication principles.
