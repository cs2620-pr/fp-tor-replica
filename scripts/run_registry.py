#!/usr/bin/env python3
"""
Script to run the registry service for the onion network.
"""

import os
import sys
import argparse
import time
import threading

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.registry_service import serve
from monitoring.status_monitor import StatusMonitor
from cli.shell_utils import print_colored


def main():
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the onion network registry service")
    parser.add_argument("--host", default="localhost", help="Host to bind the service to")
    parser.add_argument("--port", type=int, default=5050, help="Port to bind the service to")
    
    args = parser.parse_args()
    
    # Construct the address
    address = f"{args.host}:{args.port}"
    
    # Print startup banner
    print_colored("=" * 80, "blue")
    print_colored(f"Starting Onion Network Registry Service on {address}", "green")
    print_colored("=" * 80, "blue")
    
    # Start the registry service
    server, servicer = serve(address)
    
    # Create a status monitor
    monitor = StatusMonitor(name="registry")
    
    # Set up a function to print status periodically
    def print_status():
        while True:
            time.sleep(10)
            node_count = len(servicer.nodes)
            print_colored(f"Registry is tracking {node_count} router nodes", "cyan")
    
    # Start the status thread
    status_thread = threading.Thread(target=print_status, daemon=True)
    status_thread.start()
    
    try:
        # Keep the main thread alive
        print_colored("Registry service is running. Press Ctrl+C to stop.", "yellow")
        while True:
            time.sleep(3600)  # Sleep for an hour
    
    except KeyboardInterrupt:
        # Stop the server
        print_colored("\nStopping registry service...", "yellow")
        servicer.stop()
        server.stop(grace=0)
        print_colored("Registry service stopped", "green")


if __name__ == "__main__":
    main()
