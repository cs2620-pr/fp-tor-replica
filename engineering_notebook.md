# Centralized Tor-Inspired Relay Network: Engineering Notebook

*Authors: Mohamed Zidan Cassim, Giovanni D'Antonio, Anaïs Killian, Pranav Ramesh*

## 1. Introduction

This engineering notebook documents our implementation of a simplified Tor-inspired relay network, created as an educational project to demonstrate the core principles of anonymous communication. The system implements a centralized directory service with onion routing through multiple relay nodes, providing anonymity through layered encryption and path indirection.

Unlike the actual Tor network, which uses a decentralized architecture, our system relies on a Central Directory Server (CDS) to coordinate relays and facilitate circuit establishment. This design choice was made to simplify the implementation while still demonstrating the fundamental concepts of onion routing.

This project is a Tor-inspired relay chat system designed to demonstrate the principles of onion routing, secure messaging, and distributed relay management. It features a robust backend for relay and destination server management, a user-friendly frontend for visualization and control, and a modular client for secure communication.

## 2. System Architecture

### 2.1 Overview

Our system consists of five main components:

1. **Central Directory Server (CDS)**: Manages relay registration and provides circuit information to clients
2. **Relay Nodes**: Decrypt one layer of encryption and forward messages to the next node
3. **Client**: Constructs multi-layered encrypted messages and sends them through the relay network
4. **Destination Server**: Receives the final decrypted message and returns a response
5. **Cryptographic Utilities**: Provides shared encryption/decryption functionality
- **Relay Management:** Dynamically start, stop, and monitor relays. Each relay acts as a node in the onion routing network.
- **Destination Server:** Acts as the endpoint for messages traversing the relay chain.
- **Client Messaging:** Users can send messages through a configurable chain of relays, experiencing layered encryption and decryption.
- **Visualization:** The frontend allows users to visualize the relay network, see the relay chain for each message, and step through the encryption/decryption process.
- **User Management:** Supports user registration, login, and chat functionality.

The system operates using the following workflow:

1. Relay nodes generate asymmetric key pairs on startup and register with the CDS
2. A client requests a circuit of relays from the CDS
3. The client encrypts its message in multiple layers ("onion encryption")
4. The message passes through each relay, with one layer of encryption removed at each step
5. The destination server receives the final message and sends a response back through the circuit
6. The response travels back through the relays, with each adding a layer of encryption
7. The client receives and decrypts the response

### Architecture
- **Backend (Flask + Python):**
  - Hosts API endpoints for relay management, user management, and message routing.
  - Uses psutil for robust process discovery and management, allowing relays and the destination server to be started/stopped regardless of how they were launched.
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

### 2.2 Threat Model and Security Goals

Our system aims to address the following privacy threats:

- **Connection Linking**: No single relay can determine both the source and destination
- **Endpoint Identification**: The destination doesn't know the client's identity
- **Traffic Analysis**: Layered encryption prevents message tracing through the network

While our implementation is for educational purposes and lacks many of the security features of real Tor, it demonstrates the core technical principles that enable anonymous communication.

## 3. Component Design and Implementation

### 3.1 Central Directory Server (CDS)

#### 3.1.1 Design

The CDS acts as a centralized registry for all relay nodes in the system. It provides two primary services:

1. **Relay Registration**: Relays register by providing their IP, port, and public key
2. **Client Circuit Establishment**: Clients request three random relays to form a circuit

The CDS is implemented as a multi-threaded server with two listening ports:
- Port 9000: For relay registration
- Port 9001: For client relay requests

#### 3.1.2 Implementation Details

```python
def relay_registration_server(self):
    # Listen on port 9000 for relay registrations
    # Store relay information in self.relays list

def handle_relay_registration(self, conn, addr):
    # Process relay registration requests
    # Store relay IP, port, and public key

def client_request_server(self):
    # Listen on port 9001 for client requests
    # Provide randomly selected relays when requested

def handle_client_request(self, conn, addr):
    # Select 3 random relays and send to client
    # Check if enough relays are registered
```

#### 3.1.3 Design Considerations

1. **Centralization vs. Decentralization**: We opted for a centralized design to simplify implementation, though this creates a single point of failure not present in the real Tor network.

2. **Random Relay Selection**: Our CDS selects relays randomly with random.sample(), which provides basic circuit diversity. A production system would need more sophisticated selection algorithms based on relay performance, geographical distribution, etc.

3. **No Authentication**: For simplicity, the CDS doesn't authenticate relays or clients, which would be essential in a production system.

### 3.2 Relay Nodes

#### 3.2.1 Design

Each relay node is responsible for:

1. Generating and maintaining an RSA key pair
2. Registering with the CDS
3. Accepting incoming connections
4. Decrypting one layer of encryption using its private key
5. Forwarding the message to the next destination

Relays only know their immediate predecessor and successor in the circuit, which is fundamental to the anonymity properties of the system.

#### 3.2.2 Implementation Details

Each relay operates by:

1. **Key Generation**: Creating or loading a persistent RSA key pair
   
```python
def load_or_generate_keys(self):
    # Load keys from file or generate new ones if they don't exist
```

2. **Registration**: Sending its information to the CDS
   
```python
def register_with_cds(self):
    # Send IP, port, and public key to the CDS
```

3. **Message Handling**: Processing incoming messages
   
```python
def handle_message(self, conn, addr):
    # Decrypt session key with private key
    # Use session key to decrypt payload
    # Forward to next hop or destination
    # Handle response on return path
```

4. **Return Path Processing**: Encrypting and returning responses
   
```python
def forward_to_dest(self, payload, session_key, addr, conn):
    # Forward decrypted payload to final destination
    # Encrypt response and send back up the circuit
```

#### 3.2.3 Design Considerations

1. **Persistent Keys**: For simplicity, we save relay key pairs to disk (relay{id}_key.pem). In production, these would require additional security measures.

2. **Error Handling**: Extensive error handling and logging are implemented to aid debugging, which is crucial in a distributed system.

3. **Base64 Encoding**: We use base64 encoding for all data transmitted between components to ensure safe transport of binary data in text-based protocols.

4. **Layered Protocol**: Each message layer contains routing information and an encrypted payload, requiring careful handling of nested structure.

### 3.3 Client

#### 3.3.1 Design

The client component is responsible for:

1. Obtaining relay information from the CDS
2. Generating symmetric keys for each relay
3. Constructing the layered encrypted message
4. Sending the message through the relay network
5. Receiving and decrypting the response

## Major Design Choices
### 1. **Process Management with psutil**
- **Why:** Needed robust, persistent process discovery and management, especially after backend restarts.
- **How:** Backend uses psutil to find, start, and stop relay and destination server processes by port or script name, not relying on in-memory state.
- **Result:** Relays and servers can be managed even if the backend is restarted or run from multiple terminals.

### 2. **Frontend-Backend Synchronization**
- **Why:** The UI must always reflect the true state of relays and servers, regardless of backend restarts or manual process launches.
- **How:** The /api/monitor endpoint dynamically discovers running relays and the destination server using process inspection.
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
  - The demo visualization frontend (demo-frontend) is decoupled from the backend logic.
- **Result:** Easy to extend, maintain, and adapt for new demos or research.

### 6. **Network Accessibility**
- **Why:** To allow clients on different machines to join the relay network.
- **How:**
  - Server and relays can be configured to bind to 0.0.0.0 for LAN/internet access.
  - Client can specify the server's IP address.
- **Result:** Supports distributed, multi-machine demos.

## Notable Implementation Details
- **Persistent Key Management:** Each relay stores its RSA keypair for consistent identity.
- **Dynamic Process Discovery:** Relays/destination are found by inspecting running processes, not just by tracking launches.
- **API-Driven UI:** All relay/server actions are performed via API calls, ensuring clean separation and easy automation/testing.
- **Error Handling:** Backend and frontend provide clear feedback for errors (e.g., trying to start an already-running server).
- **Live Updates:** The UI uses sockets/events to refresh the network view upon relevant changes.

## Challenges and Solutions
- **Process Tracking Across Restarts:** Solved by using psutil for process discovery instead of in-memory state.
- **UI/Backend Sync:** Ensured by always querying the true process state, not cached/in-memory data.
- **Network Access:** Required explicit configuration for multi-machine demos (binding to 0.0.0.0, firewall settings).
- **User Experience:** Iteratively improved UI for clarity, reliability, and educational value.


#### 3.3.2 Implementation Details

The client's operation is divided into several phases:

1. **Relay Acquisition**:
   
```python
def get_relays_from_cds(self):
    # Request and receive relay information from CDS
```

2. **Onion Construction**:
   
```python
def build_onion(self, relays):
    # Generate symmetric keys (K1, K2, K3)
    # Encrypt destination message with K3
    # Add routing layer for relay 3 and encrypt with K2
    # Add routing layer for relay 2 and encrypt with K1
    # Prepare final message for relay 1
```

3. **Message Transmission**:
   
```python
def send_onion(self, onion_msg, relays, keys):
    # Send to first relay
    # Receive response
    # Decrypt through all layers
```

#### 3.3.3 Design Considerations

1. **Key Management**: The client generates three separate AES keys, one for each layer of encryption. Each key is encrypted with the public key of its corresponding relay.

2. **Message Format**: We use JSON for message formatting, which provides a flexible structure for including routing information and payloads.

3. **Encryption Order**: Messages are encrypted from the innermost layer outward, while responses are decrypted in the reverse order.

4. **Debugging Support**: Extensive logging helps trace the message's journey through the layers, aiding in development and troubleshooting.

### 3.4 Destination Server

#### 3.4.1 Design

The destination server represents the target website or service in our architecture. For our educational implementation, it's a simple echo server that:

1. Accepts incoming TCP connections
2. Receives messages from the final relay
3. Returns a response (the original message)

#### 3.4.2 Implementation Details

```python
def handle_client(conn, addr):
    # Receive data from final relay
    # Parse message
    # Generate and send response
```

#### 3.4.3 Design Considerations

1. **JSON Response**: The destination server attempts to parse incoming messages as JSON and returns a structured JSON response, demonstrating application-level protocol handling.

2. **Error Handling**: Multiple fallback strategies attempt to decode messages in various formats to handle potential issues in message transmission.

3. **Simplicity**: As an educational component, the destination server is intentionally simple, focusing on demonstrating the communication path rather than complex application logic.

### 3.5 Cryptographic Utilities

#### 3.5.1 Design

The cryptographic utilities module provides essential cryptographic operations for all components:

1. **RSA Key Operations**: Generate key pairs, serialize/deserialize keys, encrypt/decrypt with asymmetric keys
2. **AES Operations**: Generate symmetric keys, encrypt/decrypt with symmetric keys
3. **Key Fingerprinting**: Generate SHA-256 fingerprints of public keys for verification

#### 3.5.2 Implementation Details

```python
# RSA Operations
def generate_rsa_keypair():
    # Generate 2048-bit RSA key pair

def rsa_encrypt(public_key, message):
    # Encrypt using OAEP padding and SHA-256

def rsa_decrypt(private_key, ciphertext):
    # Decrypt using OAEP padding and SHA-256

# AES Operations
def generate_aes_key():
    # Generate 256-bit AES key

def aes_encrypt(key, plaintext):
    # Encrypt using AES-CFB mode with random IV

def aes_decrypt(key, s):
    # Decrypt using AES-CFB mode
```

#### 3.5.3 Design Considerations

1. **Key Sizes**: We use 2048-bit RSA keys and 256-bit AES keys, providing strong security while remaining computationally feasible.

2. **Padding and Modes**: OAEP padding for RSA encryption and CFB mode for AES provide strong security properties.

3. **IV Handling**: Each AES encryption operation uses a random initialization vector (IV) prepended to the ciphertext, ensuring identical plaintexts produce different ciphertexts.

4. **Library Selection**: We use Python's cryptography library, which provides well-tested, high-level cryptographic primitives with secure defaults.

## 4. Protocol Design

### 4.1 Relay Registration Protocol

Relays register with the CDS using a simple TCP-based protocol:

1. Relay connects to CDS on port 9000
2. Relay sends JSON with IP, port, and public key
3. CDS stores relay information and responds with "OK"

### 4.2 Circuit Establishment Protocol

Clients establish circuits through the CDS:

1. Client connects to CDS on port 9001
2. Client sends "REQUEST_RELAYS"
3. CDS returns JSON array with three relay entries (IP, port, public key)

### 4.3 Message Format

Messages are structured in layers, with each layer containing:

1. **next_ip**: IP address of the next relay
2. **next_port**: Port of the next relay
3. **session_key**: RSA-encrypted AES key for this layer
4. **payload**: Base64-encoded, AES-encrypted inner layer

### 4.4 Response Handling

Responses follow the reverse path through the network:

1. Destination server sends a response to the final relay
2. Each relay encrypts the response with the session key used for that layer
3. The client receives the response and decrypts it layer by layer

## 5. Engineering Challenges and Solutions

### 5.1 Debugging Distributed Systems

**Challenge**: Debugging a distributed system with multiple processes communicating across network boundaries is complex.

**Solution**: We implemented extensive logging at each layer, including:
- Detailed trace logging of message contents and states
- Fingerprint logging of cryptographic keys
- Hex dumps of binary data for verification
- Sequential log prefixes to track message paths

### 5.2 Nested Encryption and Decryption

**Challenge**: Managing nested layers of encryption/decryption properly, especially with binary data.

**Solution**:
- Consistent use of base64 encoding for wire transport
- Clear documentation of data formats at each layer
- Explicit type checking and conversion between bytes and strings
- Defensive coding with extensive error handling

### 5.3 Key Management

**Challenge**: Securely managing and distributing cryptographic keys.

**Solution**:
- Persistent key storage for relays
- Public key distribution through the CDS
- Session key encryption with recipient's public key
- Key fingerprinting for verification

### 5.4 Message Format Consistency

**Challenge**: Maintaining consistent message formats across components.

**Solution**:
- JSON as the standard serialization format
- Base64 encoding of binary data
- Structured message objects with consistent field names
- Explicit type conversion at component boundaries

## 6. Performance and Scalability Considerations

While our implementation focuses on educational clarity rather than performance, we considered several performance aspects:

### 6.1 Network Overhead

The layered encryption approach increases message size at each hop. A message grows by:
- RSA-encrypted session key: ~256 bytes
- Base64 encoding overhead: ~33% size increase
- AES encryption IV: 16 bytes per layer

### 6.2 Computational Overhead

Each relay performs:
- One RSA decryption (computationally expensive)
- One AES decryption (relatively inexpensive)
- One AES encryption for the return path

### 6.3 Scalability Limitations

Our centralized design has several scalability limitations:

1. **CDS Bottleneck**: All relay registrations and client requests go through a single server
2. **No Relay Load Balancing**: Random relay selection doesn't account for relay capacity
3. **Single-Threaded Relays**: Each relay processes messages sequentially

### 6.4 Potential Improvements

For a more scalable system, we would consider:
- Distributed directory service
- Relay performance metrics and intelligent circuit selection
- Connection pooling and asynchronous processing
- Persistent circuits for session continuity

## 7. Security Analysis

### 7.1 Strengths

1. **Layered Encryption**: Each relay only sees encrypted data for subsequent hops
2. **Path Indirection**: No single relay knows both the source and destination
3. **Strong Cryptography**: Industry-standard RSA and AES implementations

### 7.2 Limitations

1. **Centralized Directory**: The CDS is a single point of failure and potential surveillance point
2. **No Traffic Padding**: Message sizes change at each hop, enabling size correlation attacks
3. **No Timing Protection**: Vulnerable to timing correlation attacks
4. **Limited Circuit Diversity**: Small relay pool limits anonymity set

### 7.3 Threat Analysis

1. **Malicious Relay**: A compromised relay can only observe traffic to/from adjacent nodes
2. **Network Observer**: Can observe encrypted traffic but not contents
3. **Compromised CDS**: Could potentially manipulate circuit construction
4. **End-to-End Correlation**: Timing patterns could potentially be correlated

## 8. Testing Strategy

Our testing approach encompassed:

### 8.1 Component Testing

Individual testing of:
- Cryptographic operations
- Message construction/parsing
- Relay handling logic

### 8.2 Integration Testing

- Relay registration with CDS
- Client circuit establishment
- Multi-hop message routing

### 8.3 End-to-End Testing

The run_demo.sh script provides an automated end-to-end test of the entire system:
1. Starts the CDS
2. Launches three relay nodes
3. Starts the destination server
4. Runs a client to send a message through the network

### 8.4 Logging and Verification

Each component writes to its own log file:
- cds.log: Central Directory Server logs
- relay1.log, relay2.log, relay3.log: Relay node logs
- dest.log: Destination server logs
- client.log: Client output

These logs allow verification of the message path and encryption/decryption operations.

## 9. Lessons Learned

### 9.1 Architectural Insights

1. **Modularity Benefits**: Separating components allowed parallel development and clear interfaces
2. **Protocol Design Importance**: Clear data formats and protocols simplified integration
3. **Centralization Trade-offs**: Centralized design simplified implementation but created bottlenecks

### 9.2 Implementation Challenges

1. **Binary Data Handling**: Consistent handling of binary data required careful attention
2. **Error Propagation**: Errors in distributed systems require comprehensive handling
3. **Debugging Complexity**: Distributed systems debugging requires systematic logging

### 9.3 Future Improvements

1. **Relay Authentication**: Add relay authentication to prevent malicious relay registration
2. **Circuit Rotation**: Implement periodic circuit rotation for improved security
3. **Padding and Timing Defenses**: Add traffic padding and timing obfuscation
4. **Directory Distribution**: Move to a distributed directory service
5. **Enhanced Visualization:** More detailed step-by-step encryption/decryption animations.
6. **Security Features:** Add authentication for relay management endpoints.
7. **Scalability:** Support for larger relay networks and distributed directory servers.
8. **Research Extensions:** Plug in new routing algorithms or relay types for experimentation.

## 10. Conclusion

This project successfully demonstrates the core principles of onion routing in a simplified, educational context. Through layered encryption and multi-hop routing, we've created a system that preserves the fundamental anonymity property: no single relay knows both the source and destination of a message.

While our implementation lacks many of the advanced features and security protections of the actual Tor network, it provides a clear demonstration of the architectural and cryptographic foundations that make anonymous communication possible. The trade-offs we've made prioritize educational clarity over production-level security, allowing for easier understanding of the underlying concepts.

The modular design and extensive documentation make this system a valuable educational tool for understanding anonymous communication networks and the practical application of cryptographic principles in distributed systems.

Overall, our project demonstrates a secure, extensible, and user-friendly Tor-inspired relay chat network. Through robust process management, clear UI, and modular architecture, it provides a powerful platform for learning, experimentation, and demonstration of onion routing and secure communication principles.
