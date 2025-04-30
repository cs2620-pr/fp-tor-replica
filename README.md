# Onion Network

A Python implementation of an anonymous communication network based on onion routing principles. This implementation provides secure, encrypted communication through a network of relay nodes.

## Overview

The onion network is a privacy-enhancing technology that allows for anonymous communication over a computer network. Data is encapsulated in multiple layers of encryption (like the layers of an onion), and then sent through a series of nodes in the network, with each node removing a single layer of encryption before passing the data to the next node.

This implementation includes:

- A registry service (directory server) that keeps track of available router nodes
- Router nodes of three types:
  - Entry nodes (first hop in the circuit)
  - Middle nodes (intermediate hops)
  - Exit nodes (final hop, interfaces with the internet)
- A client (terminus) that builds circuits and sends requests through the network

## Features

- **Strong Encryption**: Uses RSA for key exchange and AES for symmetric encryption
- **Onion Routing**: Messages are encrypted in multiple layers, with each node peeling off one layer
- **Anonymous Communication**: Source and destination information is protected
- **Circuit-based Design**: Establishes secure circuits through the network for communication
- **Command-line Interface**: Easy to use shell interface for interacting with the network

## Requirements

- Python 3.7 or higher
- Dependencies:
  - grpcio
  - grpcio-tools
  - protobuf
  - requests
  - cryptography
  - psutil

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/onion-network.git
   cd onion-network
   ```

2. Run the setup script:
   ```
   python3 setup.py
   ```

   If you're having issues with package compilation, try the binary-only installation:
   ```
   python3 setup.py --binary-only
   ```

3. The setup script will:
   - Install required dependencies
   - Generate protocol buffer files
   - Create necessary directories
   - Set up the project structure

## Running the Network

### Option 1: Using the Test Script

The easiest way to get started is to use the test script, which launches all components:

```
python scripts/test_onion_network.py
```

This will:
1. Start the registry service
2. Start three router nodes (entry, middle, exit)
3. Start the terminus client
4. Test fetching a URL through the network
5. Allow you to test additional URLs

### Option 2: Running Components Individually

You can also run each component separately:

1. Start the registry service:
   ```
   python scripts/run_registry.py
   ```

2. Start router nodes in separate terminals:
   ```
   python scripts/run_router.py --port 5051 --type 1  # Entry node
   python scripts/run_router.py --port 5052 --type 2  # Middle node
   python scripts/run_router.py --port 5053 --type 3  # Exit node
   ```

3. Start the terminus client:
   ```
   python3 scripts/run_terminus.py
   ```

4. Use the interactive client shell to send requests:
   ```
   Onion> circuit            # Build a circuit through the network
   Onion> fetch example.com  # Fetch a website through the circuit
   Onion> status             # Show status of the client
   Onion> help               # Show available commands
   ```

### Option 3: Using the Demo Script

The project also includes a demo script that sets up all components:

```
python scripts/demo_setup.py
```

This script:
1. Starts the registry service
2. Starts all three router nodes
3. Asks if you want to start the terminus client
4. Provides a summary of all running components

## Project Structure

```
onion_network/
├── core/                  # Core functionality
│   ├── crypto_utils.py    # Encryption/decryption utilities
│   ├── message_handler.py # Message packaging and processing
│   ├── circuit_manager.py # Circuit creation and management
├── network/               # Network components
│   ├── protos/            # Protocol buffer definitions
│   ├── registry_service.py # Directory server implementation
│   ├── router_service.py  # Relay node implementation
│   ├── terminus_service.py # Client service implementation
├── cli/                   # Command-line interface
│   ├── terminus_shell.py  # Interactive shell for the client
│   ├── shell_utils.py     # CLI utilities
├── monitoring/            # Monitoring and error handling
│   ├── status_monitor.py  # Logging and performance monitoring
│   ├── error_handler.py   # Error handling and recovery
├── scripts/               # Scripts for running components
│   ├── run_registry.py    # Script to run the registry service
│   ├── run_router.py      # Script to run a router node
│   ├── run_terminus.py    # Script to run the client
│   ├── demo_setup.py      # Script to set up a complete demo
│   ├── test_onion_network.py # Script to test the network
├── setup.py               # Setup script
├── requirements.txt       # Project dependencies
├── README.md              # Project documentation
```

## How It Works

1. **Circuit Building**:
   - The client requests a list of available router nodes from the registry
   - The client selects one entry node, one middle node, and one exit node
   - The client establishes encrypted connections with each node, exchanging public keys

2. **Message Routing**:
   - The client encrypts a message with multiple layers (like an onion):
     - Inner layer: Encrypted for the exit node
     - Middle layer: Encrypted for the middle node
     - Outer layer: Encrypted for the entry node
   - Each node decrypts one layer and forwards the message to the next node
   - The exit node retrieves the requested content from the internet

3. **Response Handling**:
   - The exit node encrypts the response for the client
   - The response travels back through the circuit
   - Each node adds a layer of encryption as the response travels back
   - The client decrypts all layers to retrieve the original response

## Security Considerations

This project is educational and demonstrates the principles of onion routing. However, it has several limitations compared to production systems like Tor:

- No guard nodes or exit policies
- Limited circuit rotation
- No traffic analysis countermeasures
- Simplified directory service with no consensus
- No hidden services implementation

## Troubleshooting

If you encounter issues with running the network:

1. **Dependency Installation Problems**:
   - Try using binary-only installation: `python setup.py --binary-only`
   - Install dependencies manually: `pip install --only-binary=:all: grpcio grpcio-tools`

2. **Port Conflicts**:
   - Change the ports using command-line arguments if the default ports are in use

3. **Connection Issues**:
   - Ensure all components are running
   - Check that the registry service is accessible to all nodes
   - Try building a new circuit with the `circuit` command

4. **Protocol Buffer Issues**:
   - Regenerate protocol buffer files: `python setup.py --skip-deps`

## Contributing

Contributions are welcome! Here are some areas for improvement:

- Adding guard nodes and exit policies
- Implementing circuit rotation
- Adding hidden services
- Improving error handling and recovery
- Enhancing the user interface
