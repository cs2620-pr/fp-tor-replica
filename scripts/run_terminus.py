#!/usr/bin/env python3
"""
Script to run the terminus client for the onion network.
"""

import os
import sys
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.terminus_shell import OnionShell
from cli.shell_utils import print_colored


def main():
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the onion network terminus client")
    parser.add_argument("--host", default="localhost", help="Host to bind the service to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind the service to")
    parser.add_argument("--registry", default="localhost:5050",
                        help="Address of the registry service")
    
    args = parser.parse_args()
    
    # Construct the address
    address = f"{args.host}:{args.port}"
    
    # Print startup banner
    print_colored("=" * 80, "blue")
    print_colored(f"Starting Onion Network Terminus Client on {address}", "green")
    print_colored(f"Registry: {args.registry}", "green")
    print_colored("=" * 80, "blue")
    
    # Start the shell
    shell = OnionShell(client_port=args.port, registry_address=args.registry)
    
    try:
        # Start the interactive shell
        shell.cmdloop()
    
    except KeyboardInterrupt:
        # Stop the client
        print_colored("\nStopping terminus client...", "yellow")
        
        if shell.client:
            shell.client.stop_service()
        
        print_colored("Terminus client stopped", "green")


if __name__ == "__main__":
    main()
