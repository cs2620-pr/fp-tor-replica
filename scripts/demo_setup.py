#!/usr/bin/env python3
"""
Script to set up a complete onion network demo environment.
Launches the registry, multiple router nodes, and a client.
"""

import os
import sys
import argparse
import subprocess
import time
import signal
import atexit

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.shell_utils import print_colored, print_logo, clear_screen


# Global variables to track subprocesses
processes = []


def cleanup():
    """
    Cleanup function to terminate all subprocesses when exiting.
    """
    print_colored("\nCleaning up...", "yellow")
    
    for proc in processes:
        try:
            # Try to terminate the process gracefully
            proc.terminate()
            proc.wait(timeout=2)
        except:
            # If termination fails, force kill
            try:
                proc.kill()
            except:
                pass
    
    print_colored("All processes terminated", "green")


def start_registry(host="localhost", port=5050):
    """
    Start the registry service.
    
    Args:
        host (str, optional): Host to bind the service to.
        port (int, optional): Port to bind the service to.
        
    Returns:
        subprocess.Popen: The subprocess object.
    """
    print_colored(f"Starting registry service on {host}:{port}...", "blue")
    
    # Build the command
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "run_registry.py"),
        "--host", host,
        "--port", str(port)
    ]
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Wait a bit for the service to start
    time.sleep(1)
    
    # Check if the process is still running
    if proc.poll() is not None:
        print_colored("Failed to start registry service", "red")
        stdout, stderr = proc.communicate()
        print_colored("STDOUT:", "yellow")
        print(stdout)
        print_colored("STDERR:", "red")
        print(stderr)
        sys.exit(1)
    
    print_colored(f"Registry service started with PID {proc.pid}", "green")
    
    # Add the process to the list for cleanup
    processes.append(proc)
    
    return proc


def start_router(host="localhost", port=None, router_type=None, registry="localhost:5050"):
    """
    Start a router node.
    
    Args:
        host (str, optional): Host to bind the service to.
        port (int, optional): Port to bind the service to.
        router_type (int, optional): Router type (1=entry, 2=middle, 3=exit).
        registry (str, optional): Address of the registry service.
        
    Returns:
        subprocess.Popen: The subprocess object.
    """
    # Set default port based on router type if not specified
    if port is None:
        if router_type == 1:
            port = 5051
        elif router_type == 2:
            port = 5052
        elif router_type == 3:
            port = 5053
        else:
            print_colored("Invalid router type", "red")
            sys.exit(1)
    
    # Get router type name
    router_type_name = {
        1: "ENTRY",
        2: "MIDDLE",
        3: "EXIT"
    }.get(router_type, "UNKNOWN")
    
    print_colored(f"Starting {router_type_name} router on {host}:{port}...", "blue")
    
    # Build the command
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "run_router.py"),
        "--host", host,
        "--port", str(port),
        "--type", str(router_type),
        "--registry", registry
    ]
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Wait a bit for the service to start
    time.sleep(1)
    
    # Check if the process is still running
    if proc.poll() is not None:
        print_colored(f"Failed to start {router_type_name} router", "red")
        stdout, stderr = proc.communicate()
        print_colored("STDOUT:", "yellow")
        print(stdout)
        print_colored("STDERR:", "red")
        print(stderr)
        sys.exit(1)
    
    print_colored(f"{router_type_name} router started with PID {proc.pid}", "green")
    
    # Add the process to the list for cleanup
    processes.append(proc)
    
    return proc


def start_terminus(host="localhost", port=5000, registry="localhost:5050"):
    """
    Start the terminus client.
    
    Args:
        host (str, optional): Host to bind the service to.
        port (int, optional): Port to bind the service to.
        registry (str, optional): Address of the registry service.
        
    Returns:
        subprocess.Popen: The subprocess object.
    """
    print_colored(f"Starting terminus client on {host}:{port}...", "blue")
    
    # Build the command
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "run_terminus.py"),
        "--host", host,
        "--port", str(port),
        "--registry", registry
    ]
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Wait a bit for the service to start
    time.sleep(1)
    
    # Check if the process is still running
    if proc.poll() is not None:
        print_colored("Failed to start terminus client", "red")
        stdout, stderr = proc.communicate()
        print_colored("STDOUT:", "yellow")
        print(stdout)
        print_colored("STDERR:", "red")
        print(stderr)
        sys.exit(1)
    
    print_colored(f"Terminus client started with PID {proc.pid}", "green")
    
    # Add the process to the list for cleanup
    processes.append(proc)
    
    return proc


def main():
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Set up an onion network demo environment")
    parser.add_argument("--registry-port", type=int, default=5050,
                        help="Port for the registry service")
    parser.add_argument("--entry-port", type=int, default=5051,
                        help="Port for the entry router")
    parser.add_argument("--middle-port", type=int, default=5052,
                        help="Port for the middle router")
    parser.add_argument("--exit-port", type=int, default=5053,
                        help="Port for the exit router")
    parser.add_argument("--client-port", type=int, default=5000,
                        help="Port for the terminus client")
    parser.add_argument("--host", default="localhost",
                        help="Host to bind all services to")
    
    args = parser.parse_args()
    
    # Clear the screen and print the logo
    clear_screen()
    print_logo()
    
    # Register the cleanup function to be called on exit
    atexit.register(cleanup)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
    
    # Start the registry
    registry_proc = start_registry(host=args.host, port=args.registry_port)
    registry_address = f"{args.host}:{args.registry_port}"
    
    # Wait a bit for the registry to start
    time.sleep(2)
    
    # Start the router nodes
    entry_proc = start_router(host=args.host, port=args.entry_port, router_type=1, registry=registry_address)
    time.sleep(1)
    
    middle_proc = start_router(host=args.host, port=args.middle_port, router_type=2, registry=registry_address)
    time.sleep(1)
    
    exit_proc = start_router(host=args.host, port=args.exit_port, router_type=3, registry=registry_address)
    time.sleep(1)
    
    # Print a summary of the running services
    print_colored("\nOnion Network Demo Environment", "green")
    print_colored("----------------------------", "green")
    print_colored(f"Registry: {args.host}:{args.registry_port} (PID: {registry_proc.pid})", "cyan")
    print_colored(f"Entry Router: {args.host}:{args.entry_port} (PID: {entry_proc.pid})", "cyan")
    print_colored(f"Middle Router: {args.host}:{args.middle_port} (PID: {middle_proc.pid})", "cyan")
    print_colored(f"Exit Router: {args.host}:{args.exit_port} (PID: {exit_proc.pid})", "cyan")
    
    # Ask if the user wants to start the client
    print_colored("\nDo you want to start the terminus client? (y/n)", "yellow")
    choice = input().strip().lower()
    
    if choice in ["y", "yes"]:
        # Start the terminus client
        terminus_proc = start_terminus(host=args.host, port=args.client_port, registry=registry_address)
        
        # Wait for the client to exit
        terminus_proc.wait()
    else:
        print_colored("\nTerminus client not started. Demo environment is running in the background.", "yellow")
        print_colored("Press Ctrl+C to stop all services.", "yellow")
        
        # Keep the script running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
