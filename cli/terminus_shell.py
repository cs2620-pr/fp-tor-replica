"""
Command-line interface for the onion network client.
Provides a shell for interacting with the onion network.
"""

import cmd
import os
import subprocess
import sys
import time
import webbrowser
from network.terminus_service import serve as start_terminus

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.status_monitor import StatusMonitor
from cli.shell_utils import print_logo, print_colored


class OnionShell(cmd.Cmd):
    """
    Interactive shell for the onion network client.
    """
    
    intro = "Welcome to the Onion Network Shell. Type help or ? to list commands.\n"
    prompt = "Onion> "
    
    def __init__(self, client_port=5000, registry_address="localhost:5050"):
        """
        Initialize the OnionShell.
        
        Args:
            client_port (int, optional): Port for the client to listen on.
            registry_address (str, optional): Address of the registry service.
        """
        super(OnionShell, self).__init__()
        
        self.client_port = client_port
        self.client_address = f"localhost:{client_port}"
        self.registry_address = registry_address
        self.client = None
        self.monitor = StatusMonitor()
        
        # Initialize the client
        self.initialize_client()
        
        # Print the logo
        print_logo()
    
    def initialize_client(self):
        """
        Initialize the terminus client.
        """
        self.monitor.log_info("Initializing client...")
        self.client = start_terminus(self.client_address, self.registry_address)
        
        if not self.client:
            self.monitor.log_error("Failed to initialize client")
            print_colored("Failed to initialize client. Exiting...", "red")
            sys.exit(1)
        
        self.monitor.log_info("Client initialized")
    
    def do_fetch(self, arg):
        """
        Fetch a URL through the onion network.
        
        Usage: fetch <url> [method]
        
        Examples:
            fetch https://example.com
            fetch https://example.com POST
        """
        args = arg.split()
        
        if not args:
            print_colored("Please provide a URL to fetch", "yellow")
            return
        
        url = args[0]
        method = args[1].upper() if len(args) > 1 else "GET"
        
        # Validate the method
        valid_methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]
        if method not in valid_methods:
            print_colored(f"Invalid method: {method}", "yellow")
            print_colored(f"Valid methods: {', '.join(valid_methods)}", "yellow")
            return
        
        print_colored(f"Fetching {url} with method {method}...", "blue")
        
        # Build a new circuit for each request
        if not self.client.build_circuit():
            print_colored("Failed to build circuit", "red")
            return
        
        # Send the request
        if not self.client.send_request(url, method):
            print_colored("Failed to send request", "red")
            return
        
        # Wait for a response
        print_colored("Waiting for response...", "blue")
        if not self.client.wait_for_response(timeout=30):
            print_colored("Timed out waiting for response", "red")
            return
        
        print_colored("Response received", "green")
        
        # Try to open the response file in a web browser
        try:
            if os.path.exists("response.html"):
                print_colored("Opening response in web browser...", "blue")
                webbrowser.open(f"file://{os.path.abspath('response.html')}")
            elif os.path.exists("response.txt"):
                # Open text file in a text editor or display it
                print_colored("Response saved to response.txt", "green")
                
                # Try to display the content
                try:
                    with open("response.txt", "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Print the first 1000 characters
                    if len(content) > 1000:
                        print_colored(content[:1000] + "...", "cyan")
                        print_colored("(Response truncated, see response.txt for the full content)", "yellow")
                    else:
                        print_colored(content, "cyan")
                
                except Exception as e:
                    print_colored(f"Failed to display response: {e}", "red")
            
            else:
                print_colored("Response saved to response.bin", "green")
        
        except Exception as e:
            print_colored(f"Failed to open response: {e}", "red")
    
    def do_circuit(self, arg):
        """
        Build a new circuit through the onion network.
        
        Usage: circuit
        """
        print_colored("Building new circuit...", "blue")
        
        if not self.client.build_circuit():
            print_colored("Failed to build circuit", "red")
            return
        
        print_colored("Circuit built successfully", "green")
        print_colored(f"Circuit: {self.client.circuit}", "cyan")
    
    def do_status(self, arg):
        """
        Display status information about the client.
        
        Usage: status
        """
        if not self.client:
            print_colored("Client not initialized", "red")
            return
        
        print_colored("Client Status:", "blue")
        print_colored(f"Client Address: {self.client_address}", "cyan")
        print_colored(f"Registry Address: {self.registry_address}", "cyan")
        
        if self.client.circuit:
            print_colored("Circuit: ", "cyan", end="")
            print_colored(" -> ".join(self.client.circuit), "green")
        else:
            print_colored("No circuit established", "yellow")
    
    def do_shell(self, arg):
        """
        Execute a shell command.
        
        Usage: !<command> or shell <command>
        
        Example:
            !ls -la
            shell ping google.com
        """
        if not arg:
            print_colored("Please provide a command to execute", "yellow")
            return
        
        try:
            # Execute the command
            process = subprocess.run(
                arg, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8"
            )
            
            # Print the output
            if process.stdout:
                print_colored(process.stdout, "cyan")
            
            # Print any errors
            if process.stderr:
                print_colored(process.stderr, "red")
            
            # Print the return code
            print_colored(f"Return code: {process.returncode}", "blue")
        
        except Exception as e:
            print_colored(f"Failed to execute command: {e}", "red")
    
    def do_exit(self, arg):
        """
        Exit the shell.
        
        Usage: exit
        """
        print_colored("Exiting...", "blue")
        
        if self.client:
            self.client.stop_service()
        
        return True
    
    def do_quit(self, arg):
        """
        Exit the shell.
        
        Usage: quit
        """
        return self.do_exit(arg)
    
    def do_help(self, arg):
        """
        Show help for commands.
        
        Usage: help [command]
        """
        if arg:
            # Show help for a specific command
            cmd.Cmd.do_help(self, arg)
        else:
            # Show general help
            print_colored("Available commands:", "blue")
            print_colored("  fetch <url> [method] - Fetch a URL through the onion network", "cyan")
            print_colored("  circuit             - Build a new circuit through the onion network", "cyan")
            print_colored("  status              - Display status information about the client", "cyan")
            print_colored("  shell <command>     - Execute a shell command", "cyan")
            print_colored("  exit, quit          - Exit the shell", "cyan")
            print_colored("  help [command]      - Show help for commands", "cyan")
    
    def default(self, line):
        """
        Handle unknown commands.
        """
        if line.startswith("!"):
            # Treat as a shell command
            return self.do_shell(line[1:])
        
        print_colored(f"Unknown command: {line}", "yellow")
        self.do_help("")
    
    def emptyline(self):
        """
        Handle empty lines.
        """
        # Do nothing
        pass


def main():
    """
    Main entry point for the shell.
    """
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Start the onion network shell")
    parser.add_argument("--port", type=int, default=5000, help="Port for the client to listen on")
    parser.add_argument("--registry", default="localhost:5050", help="Address of the registry service")
    
    args = parser.parse_args()
    
    # Start the shell
    shell = OnionShell(client_port=args.port, registry_address=args.registry)
    
    try:
        shell.cmdloop()
    
    except KeyboardInterrupt:
        print_colored("\nExiting...", "blue")
        
        if shell.client:
            shell.client.stop_service()
    
    except Exception as e:
        print_colored(f"Error: {e}", "red")
        
        if shell.client:
            shell.client.stop_service()


if __name__ == "__main__":
    main()
