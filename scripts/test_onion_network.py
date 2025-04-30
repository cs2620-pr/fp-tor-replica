#!/usr/bin/env python3
"""
Test script for the onion network.
This script launches the necessary components and performs a test request.
"""

import os
import sys
import time
import subprocess
import signal
import threading
import webbrowser

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.shell_utils import print_colored, print_logo, clear_screen
from monitoring.status_monitor import StatusMonitor


# Global monitor
monitor = StatusMonitor(name="test_script")

# Global variables to track subprocesses
processes = []
output_locks = {}


def cleanup():
    """
    Cleanup function to terminate all subprocesses.
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


def run_component(cmd, name, color=None):
    """
    Run a component in a subprocess and capture its output.
    
    Args:
        cmd (list): The command to run.
        name (str): The name of the component.
        color (str, optional): The color to use for output.
        
    Returns:
        subprocess.Popen: The subprocess object.
    """
    print_colored(f"Starting {name}...", "blue")
    
    # Create a lock for this component's output
    output_lock = threading.Lock()
    output_locks[name] = output_lock
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Function to handle output
    def handle_output(stream, prefix, component_color):
        for line in stream:
            with output_lock:
                print_colored(f"[{name}] {line.rstrip()}", component_color)
    
    # Start threads to handle stdout and stderr
    threading.Thread(
        target=handle_output,
        args=(proc.stdout, f"[{name}]", color or "cyan"),
        daemon=True
    ).start()
    
    threading.Thread(
        target=handle_output,
        args=(proc.stderr, f"[{name} ERROR]", "red"),
        daemon=True
    ).start()
    
    # Wait a bit for the process to start
    time.sleep(1)
    
    # Check if the process is still running
    if proc.poll() is not None:
        print_colored(f"Failed to start {name}", "red")
        return None
    
    print_colored(f"{name} started with PID {proc.pid}", "green")
    
    # Add the process to the list for cleanup
    processes.append(proc)
    
    return proc


def run_registry(port=5050):
    """
    Start the registry service.
    
    Args:
        port (int, optional): Port to use.
        
    Returns:
        subprocess.Popen: The subprocess object.
    """
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "run_registry.py"),
        "--port", str(port)
    ]
    
    return run_component(cmd, "Registry", "green")


def run_router(port, router_type, registry_port=5050):
    """
    Start a router node.
    
    Args:
        port (int): Port to use.
        router_type (int): Router type (1=entry, 2=middle, 3=exit).
        registry_port (int, optional): Port of the registry service.
        
    Returns:
        subprocess.Popen: The subprocess object.
    """
    type_names = {1: "Entry", 2: "Middle", 3: "Exit"}
    type_name = type_names.get(router_type, "Unknown")
    
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "run_router.py"),
        "--port", str(port),
        "--type", str(router_type),
        "--registry", f"localhost:{registry_port}"
    ]
    
    return run_component(cmd, f"{type_name} Router", "blue")


def run_terminus(port=5000, registry_port=5050):
    """
    Start the terminus client.
    
    Args:
        port (int, optional): Port to use.
        registry_port (int, optional): Port of the registry service.
        
    Returns:
        TerminusClient: The terminus client.
    """
    from network.terminus_service import serve
    
    client_address = f"localhost:{port}"
    registry_address = f"localhost:{registry_port}"
    
    print_colored(f"Starting Terminus Client on {client_address}...", "blue")
    
    # Create and start the terminus client
    client = serve(client_address, registry_address)
    
    if not client:
        print_colored("Failed to start terminus client", "red")
        return None
    
    print_colored(f"Terminus Client started on {client_address}", "green")
    
    return client


def test_fetch(client, url="http://example.com"):
    """
    Test fetching a URL through the onion network.
    
    Args:
        client: The terminus client.
        url (str, optional): The URL to fetch.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    print_colored(f"Testing fetch: {url}", "blue")
    
    # Build a circuit
    print_colored("Building circuit...", "blue")
    if not client.build_circuit():
        print_colored("Failed to build circuit", "red")
        return False
    
    print_colored(f"Circuit built: {client.circuit}", "green")
    
    # Send a request
    print_colored(f"Sending request: GET {url}", "blue")
    if not client.send_request(url, "GET"):
        print_colored("Failed to send request", "red")
        return False
    
    # Wait for a response
    print_colored("Waiting for response...", "blue")
    if not client.wait_for_response(timeout=30):
        print_colored("Timed out waiting for response", "red")
        return False
    
    print_colored("Response received", "green")
    
    # Try to open the response in a browser if it's HTML
    if os.path.exists("response.html"):
        print_colored("Opening response in web browser...", "blue")
        webbrowser.open(f"file://{os.path.abspath('response.html')}")
    elif os.path.exists("response.txt"):
        print_colored("Response saved to response.txt", "green")
        with open("response.txt", "r", encoding="utf-8") as f:
            content = f.read()
        print_colored("Response content:", "cyan")
        print_colored(content[:500] + ("..." if len(content) > 500 else ""), "white")
    elif os.path.exists("response.bin"):
        print_colored("Response saved to response.bin", "green")
    
    return True


def main():
    """
    Main entry point for the script.
    """
    # Clear the screen and print the logo
    clear_screen()
    print_logo()
    
    print_colored("Onion Network Test", "green")
    print_colored("-" * 80, "blue")
    
    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
    
    # Register cleanup function
    import atexit
    atexit.register(cleanup)
    
    try:
        # Define ports
        registry_port = 5050
        entry_port = 5051
        middle_port = 5052
        exit_port = 5053
        client_port = 5000
        
        # Start the registry
        registry_proc = run_registry(registry_port)
        if not registry_proc:
            print_colored("Failed to start registry, aborting test", "red")
            return 1
        
        # Give the registry time to start
        time.sleep(2)
        
        # Start the router nodes
        entry_proc = run_router(entry_port, 1, registry_port)
        if not entry_proc:
            print_colored("Failed to start entry router, aborting test", "red")
            return 1
        
        time.sleep(1)
        
        middle_proc = run_router(middle_port, 2, registry_port)
        if not middle_proc:
            print_colored("Failed to start middle router, aborting test", "red")
            return 1
        
        time.sleep(1)
        
        exit_proc = run_router(exit_port, 3, registry_port)
        if not exit_proc:
            print_colored("Failed to start exit router, aborting test", "red")
            return 1
        
        time.sleep(1)
        
        # Start the terminus client
        client = run_terminus(client_port, registry_port)
        if not client:
            print_colored("Failed to start terminus client, aborting test", "red")
            return 1
        
        time.sleep(1)
        
        # Print summary of running components
        print_colored("\nTest Environment Setup", "green")
        print_colored("-" * 80, "blue")
        print_colored(f"Registry: localhost:{registry_port}", "cyan")
        print_colored(f"Entry Router: localhost:{entry_port}", "cyan")
        print_colored(f"Middle Router: localhost:{middle_port}", "cyan")
        print_colored(f"Exit Router: localhost:{exit_port}", "cyan")
        print_colored(f"Terminus Client: localhost:{client_port}", "cyan")
        print_colored("-" * 80, "blue")
        
        # Test fetching a URL
        print_colored("\nRunning test...", "green")
        success = test_fetch(client, "http://example.com")
        
        if success:
            print_colored("\nTest PASSED!", "green")
        else:
            print_colored("\nTest FAILED!", "red")
        
        # Ask if user wants to run more tests
        print_colored("\nDo you want to run more tests? (y/n)", "yellow")
        choice = input().strip().lower()
        
        while choice in ["y", "yes"]:
            print_colored("\nEnter a URL to fetch:", "yellow")
            url = input().strip()
            
            if url:
                success = test_fetch(client, url)
                
                if success:
                    print_colored("Test PASSED!", "green")
                else:
                    print_colored("Test FAILED!", "red")
            
            print_colored("\nDo you want to run more tests? (y/n)", "yellow")
            choice = input().strip().lower()
        
        print_colored("\nTests completed. Press Ctrl+C to exit.", "yellow")
        
        # Keep the program running until explicitly terminated
        while True:
            time.sleep(1)
        
        return 0
    
    except Exception as e:
        print_colored(f"Error in test script: {e}", "red")
        import traceback
        print_colored(traceback.format_exc(), "red")
        return 1


if __name__ == "__main__":
    sys.exit(main())
