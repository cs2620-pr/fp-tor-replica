# Centralized Tor-Inspired Relay Network

**Mohamed Zidan Cassim, Giovanni D'Antonio, Anaïs Killian, Pranav Ramesh**

## 📌 Overview

This project is a simplified version of Tor (“The Onion Router”), designed to demonstrate core principles of anonymous communication using layered encryption and relay routing. A client sends a message through three intermediary relay servers before reaching a destination, ensuring that no single relay knows both the source and destination.

Instead of a decentralized network like Tor, this system uses a Central Directory Server (CDS) to maintain a list of active relays. Each message is encrypted in layers (“onion-style”) such that each relay decrypts one layer and forwards the message to the next.

The system is intended for educational demonstration and not real-world anonymity.

## 🎯 Goals

- Implement a working anonymous message circuit using layered encryption
- Demonstrate correct relay behavior and IP-masking via logging
- Show end-to-end message delivery through three relays
- Submit working code, a design fair poster, and a final written report

## 🧩 System Components

1.  **Central Directory Server (CDS)**

    - Maintains a list of active relays
    - Accepts relay registration (ip, port, public_key)
    - Provides clients with 3 random relays on request

2.  **Relay Node**

    - Generates an RSA keypair on startup
    - Registers with the CDS
    - Listens for incoming TCP messages
    - Decrypts one encryption layer using session key
    - Forwards the remaining payload to the next node

3.  **Client**

    - Queries the CDS for 3 relays
    - Generates 3 symmetric keys (K1, K2, K3)
    - Wraps the payload in 3 encryption layers
    - Sends message to the first relay
    - Receives response and decrypts it layer-by-layer

4.  **Destination Server (for testing)**

    - Simple TCP echo server
    - Accepts final payload, returns a response to verify full round-trip

5.  **Crypto Utilities (shared)**
    - RSA keypair generation
    - RSA encrypt/decrypt for session key exchange
    - AES encrypt/decrypt for message layers

## 🔗 Message Structure

Each message includes:

- Next relay's IP and port
- Encrypted inner payload using AES
- All encrypted layers are base64-encoded and nested

## ✅ Success Criteria

- Relays register with the CDS
- Client sends a message that passes through 3 relays
- Each relay sees only the previous and next hop
- Destination server receives the original message
- Client receives correct response
- Logs verify anonymized routing

## 📎 Deliverables

- Source code for CDS, relays, client, destination server
- Crypto library (RSA, AES)
- CLI demo runner and trace logs
- Poster for SEAS Design Fair
- 6–10 page final report
