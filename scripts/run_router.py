#!/usr/bin/env python3
"""
Script to run a router node for the onion network.
"""

import os
import sys
import argparse
import time
import threading

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.router_service import serve
from network.protos import onion_network_pb2
from monitoring.status_monitor import StatusMonitor
from cli.shell_utils import print_colored


def main():
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run an onion network router node")
    parser.add_argument("--host", default="localhost", help="Host to bind the service to")
    parser.add_argument("--port", type=int, required=True, help="Port to bind the service to")
    parser.add_argument("--type", type=int, required=True, choices=[1, 2, 3],
                        help="Router type: 1 (entry), 2 (middle), or 3 (exit)")
    parser.add_argument("--registry", default="localhost:5050",
                        help="Address of the registry service")
    
    args = parser.parse_args()
    
    # Construct the address
    address = f"{args.host}:{args.port}"
    
    # Get the router type name
    router_type_name = {
        1: "ENTRY",
        2: "MIDDLE",
        3: "EXIT"
    }.get(args.type, "UNKNOWN")
    
    # Print startup banner
    print_colored("=" * 80, "blue")
    print_colored(f"Starting Onion Network {router_type_name} Router on {address}", "green")
    print_colored(f"Registry: {args.registry}", "green")
    print_colored("=" * 80, "blue")
    
    # Start the router service
    server, router_servicer = serve(address, args.type, args.registry)
    
    # Create a status monitor
    monitor = StatusMonitor(name=f"router_{args.port}")
    
    # Set up a function to print status periodically
    def print_status():
        while True:
            time.sleep(10)
            session_count = len(router_servicer.sessions)
            print_colored(f"Router has {session_count} active sessions", "cyan")
    
    # Start the status thread
    status_thread = threading.Thread(target=print_status, daemon=True)
    status_thread.start()
    
    try:
        # Keep the main thread alive
        print_colored("Router service is running. Press Ctrl+C to stop.", "yellow")
        while True:
            time.sleep(3600)  # Sleep for an hour
    
    except KeyboardInterrupt:
        # Stop the server
        print_colored("\nStopping router service...", "yellow")
        server.stop(grace=0)
        print_colored("Router service stopped", "green")


if __name__ == "__main__":
    main()
