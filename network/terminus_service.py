"""
Terminus Service for the onion network.
Provides a service for receiving responses from the network.
"""

import threading
import pickle
import grpc
import traceback
from concurrent import futures
import time

from network.protos import onion_network_pb2, onion_network_pb2_grpc
from core.crypto_utils import asymmetric_decrypt, symmetric_decrypt
from core.message_handler import MessagePackager
from monitoring.status_monitor import StatusMonitor


class TerminusServicer(onion_network_pb2_grpc.TerminusServicer):
    """
    Implementation of the Terminus service.
    """
    
    def __init__(self, terminus_client, monitor=None):
        """
        Initialize the TerminusServicer.
        
        Args:
            terminus_client: The TerminusClient that owns this servicer.
            monitor (StatusMonitor, optional): Monitor for tracking stats.
        """
        super().__init__()
        self.terminus_client = terminus_client
        self.monitor = monitor or StatusMonitor()
    
    def DeliverMessage(self, request, context):
        """
        Handle a message delivery.
        
        Args:
            request (DeliverMessageRequest): The request message.
            context: The gRPC context.
            
        Returns:
            Empty: An empty response.
        """
        try:
            # Extract data from the request
            encrypted_message = request.encrypted_message
            encrypted_key = request.encrypted_key
            iv = request.initialization_vector
            session_id = request.session_id.decode('utf-8')
            
            self.monitor.log_info(f"Received message for session {session_id}")
            
            # Process the message in a separate thread to avoid blocking
            threading.Thread(
                target=self._process_message,
                args=(encrypted_message, encrypted_key, iv, session_id)
            ).start()
            
            # Return an empty response
            return onion_network_pb2.Empty()
        
        except Exception as e:
            self.monitor.log_error(f"Error in DeliverMessage: {e}")
            self.monitor.log_error(traceback.format_exc())
            # Return an empty response even in case of error to prevent RPC failures
            return onion_network_pb2.Empty()
    
    def _process_message(self, encrypted_message, encrypted_key, iv, session_id):
        """
        Process a received message.
        
        Args:
            encrypted_message (bytes): The encrypted message.
            encrypted_key (bytes): The encrypted symmetric key.
            iv (bytes): The initialization vector.
            session_id (str): The session ID.
        """
        try:
            self.monitor.log_info(f"Processing message for session {session_id}")
            
            # Get the private key for the entry node
            private_key = self.terminus_client.get_private_key(0)
            
            if not private_key:
                self.monitor.log_warning(f"No private key for entry node in session {session_id}")
                return
            
            # Decrypt the symmetric key
            sym_key = asymmetric_decrypt(private_key, encrypted_key)
            
            # Decrypt the message
            decrypted_data = symmetric_decrypt(sym_key, iv, encrypted_message)
            
            # Deserialize the message
            message = pickle.loads(decrypted_data)
            
            if "data" not in message:
                self.monitor.log_warning(f"Invalid message format for session {session_id}")
                return
            
            # Extract the encrypted middle layer
            middle_layer = pickle.loads(message["data"])
            
            # Get the private key for the middle node
            private_key = self.terminus_client.get_private_key(1)
            
            if not private_key:
                self.monitor.log_warning(f"No private key for middle node in session {session_id}")
                return
            
            # Decrypt the middle layer
            encrypted_message, encrypted_key, iv = middle_layer
            sym_key = asymmetric_decrypt(private_key, encrypted_key)
            decrypted_data = symmetric_decrypt(sym_key, iv, encrypted_message)
            
            # Deserialize the middle layer
            middle_message = pickle.loads(decrypted_data)
            
            if "data" not in middle_message:
                self.monitor.log_warning(f"Invalid middle layer format for session {session_id}")
                return
            
            # Extract the encrypted exit layer
            exit_layer = pickle.loads(middle_message["data"])
            
            # Get the private key for the exit node
            private_key = self.terminus_client.get_private_key(2)
            
            if not private_key:
                self.monitor.log_warning(f"No private key for exit node in session {session_id}")
                return
            
            # Decrypt the exit layer
            encrypted_message, encrypted_key, iv = exit_layer
            sym_key = asymmetric_decrypt(private_key, encrypted_key)
            decrypted_data = symmetric_decrypt(sym_key, iv, encrypted_message)
            
            # Deserialize the exit layer
            exit_message = pickle.loads(decrypted_data)
            
            # Process the response
            self.monitor.log_info(f"Successfully processed message for session {session_id}")
            
            # Pass the response to the terminus client
            self.terminus_client.handle_response(exit_message, session_id)
        
        except Exception as e:
            self.monitor.log_error(f"Failed to process message for session {session_id}: {e}")
            self.monitor.log_error(traceback.format_exc())
    
    def Ping(self, request, context):
        """
        Handle a ping request.
        
        Args:
            request (Empty): The request message.
            context: The gRPC context.
            
        Returns:
            Empty: An empty response.
        """
        self.monitor.log_info("Received Ping request")
        
        # Return an empty response
        return onion_network_pb2.Empty()


class TerminusClient:
    """
    Client for the onion network.
    """
    
    def __init__(self, client_address, registry_address, monitor=None):
        """
        Initialize the TerminusClient.
        
        Args:
            client_address (str): The address this client is listening on.
            registry_address (str): The address of the registry service.
            monitor (StatusMonitor, optional): Monitor for tracking stats.
        """
        self.client_address = client_address
        self.registry_address = registry_address
        self.monitor = monitor or StatusMonitor()
        
        # Circuit management
        self.session_id = None
        self.circuit = None
        self.private_keys = {}  # Index -> private_key
        self.response_handlers = {}  # session_id -> handler function
        self.response_received = False
        
        # Start the terminus service
        self.server = None
        self.servicer = None
    
    def start_service(self, max_workers=10):
        """
        Start the terminus service.
        
        Args:
            max_workers (int, optional): Maximum number of worker threads.
            
        Returns:
            bool: True if started successfully, False otherwise.
        """
        try:
            # Create the server with options for large messages
            options = [
                ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50 MB
                ('grpc.max_receive_message_length', 50 * 1024 * 1024)  # 50 MB
            ]
            self.server = grpc.server(
                futures.ThreadPoolExecutor(max_workers=max_workers),
                options=options
            )
            
            # Add the servicer to the server
            self.servicer = TerminusServicer(self, monitor=self.monitor)
            onion_network_pb2_grpc.add_TerminusServicer_to_server(self.servicer, self.server)
            
            # Bind the server to the client address
            self.server.add_insecure_port(self.client_address)
            
            # Start the server
            self.monitor.log_info(f"Starting terminus service on {self.client_address}")
            self.server.start()
            
            return True
        
        except Exception as e:
            self.monitor.log_error(f"Failed to start terminus service: {e}")
            self.monitor.log_error(traceback.format_exc())
            return False
    
    def stop_service(self):
        """
        Stop the terminus service.
        """
        if self.server:
            self.server.stop(grace=0)
            self.server = None
            self.servicer = None
    
    def build_circuit(self):
        """
        Build a circuit through the onion network.
        
        Returns:
            bool: True if the circuit was built successfully, False otherwise.
        """
        from core.circuit_manager import CircuitManager
        
        try:
            # Create a circuit manager
            circuit_manager = CircuitManager(self.registry_address)
            
            # Establish a circuit
            if not circuit_manager.establish_circuit():
                self.monitor.log_error("Failed to establish circuit")
                return False
            
            # Store the circuit information
            self.session_id = circuit_manager.session_id
            self.circuit = circuit_manager.circuit
            
            # Store the private keys
            for i, node_address in enumerate(self.circuit):
                _, private_key = circuit_manager.client_keys[node_address]
                self.private_keys[i] = private_key
            
            self.monitor.log_info(f"Built circuit: {self.circuit}")
            
            return True
        
        except Exception as e:
            self.monitor.log_error(f"Exception building circuit: {e}")
            self.monitor.log_error(traceback.format_exc())
            return False
    
    def send_request(self, url, method="GET", handler=None):
        """
        Send a request through the onion network.
        
        Args:
            url (str): The URL to request.
            method (str, optional): The HTTP method to use.
            handler (callable, optional): Function to call with the response.
            
        Returns:
            bool: True if the request was sent successfully, False otherwise.
        """
        # Reset the response flag
        self.response_received = False
        
        # Ensure we have a circuit
        if not self.circuit:
            self.monitor.log_info("No circuit established, building one...")
            if not self.build_circuit():
                return False
        
        # If a handler is provided, store it
        if handler:
            self.response_handlers[self.session_id] = handler
        
        try:
            self.monitor.log_info(f"Preparing to send {method} request to {url}")
            
            # Import the MessagePackager
            from core.message_handler import MessagePackager
            
            # Get the node keys from the circuit
            from core.circuit_manager import CircuitManager
            circuit_manager = CircuitManager(self.registry_address)
            circuit_manager.session_id = self.session_id
            circuit_manager.circuit = self.circuit
            
            # Rebuild connections to nodes
            for i, node_address in enumerate(self.circuit):
                # Setup gRPC options for large messages
                options = [
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50 MB
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024)  # 50 MB
                ]
                circuit_manager.node_channels[node_address] = grpc.insecure_channel(
                    node_address, options=options
                )
                circuit_manager.node_stubs[node_address] = onion_network_pb2_grpc.RouterStub(
                    circuit_manager.node_channels[node_address]
                )
            
            # Get the nodes and their public keys
            exit_node = self.circuit[2]
            middle_node = self.circuit[1]
            entry_node = self.circuit[0]
            
            # Create the exit layer
            self.monitor.log_info("Creating exit layer")
            exit_layer = MessagePackager.create_exit_layer(
                url, method, circuit_manager.node_keys[exit_node]
            )
            
            # Create the middle layer
            self.monitor.log_info("Creating middle layer")
            middle_layer = MessagePackager.create_middle_layer(
                exit_node, exit_layer, circuit_manager.node_keys[middle_node]
            )
            
            # Create the entry layer
            self.monitor.log_info("Creating entry layer")
            entry_layer = MessagePackager.create_entry_layer(
                middle_node, middle_layer, circuit_manager.node_keys[entry_node],
                self.client_address
            )
            
            # Send the request to the entry node
            self.monitor.log_info(f"Sending request to entry node at {entry_node}")
            
            # Create a forward request
            request = onion_network_pb2.RouteMessageRequest(
                encrypted_message=entry_layer[0],
                encrypted_key=entry_layer[1],
                initialization_vector=entry_layer[2],
                session_id=self.session_id.encode('utf-8'),
                return_address=self.client_address
            )
            
            # Send the request with a timeout
            response = circuit_manager.node_stubs[entry_node].RouteMessage(
                request, timeout=15
            )
            
            self.monitor.log_info("Request sent successfully")
            return True
        
        except grpc.RpcError as rpc_error:
            self.monitor.log_error(f"gRPC error sending request: {rpc_error.code()}: {rpc_error.details()}")
            return False
        
        except Exception as e:
            self.monitor.log_error(f"Failed to send request: {e}")
            self.monitor.log_error(traceback.format_exc())
            return False
    
    def handle_response(self, response, session_id):
        """
        Handle a response from the onion network.
        
        Args:
            response: The response data.
            session_id (str): The session ID.
        """
        try:
            # Mark that we received a response
            self.response_received = True
            
            # If there's a handler for this session, call it
            handler = self.response_handlers.get(session_id)
            if handler:
                handler(response)
                # Remove the handler after use
                del self.response_handlers[session_id]
            
            # Process the response
            headers, content = response
            
            # Log response info
            self.monitor.log_info(f"Received response with headers: {list(headers.keys())}")
            if content:
                self.monitor.log_info(f"Response content length: {len(content)} bytes")
            
            # Write the content to a file based on content type
            if content and isinstance(content, bytes):
                content_type = headers.get("Content-Type", "")
                
                if "html" in content_type.lower():
                    with open("response.html", "wb") as f:
                        f.write(content)
                    self.monitor.log_info("Saved HTML response to response.html")
                
                elif "text" in content_type.lower():
                    text_content = content.decode("utf-8", errors="replace")
                    with open("response.txt", "w", encoding="utf-8") as f:
                        f.write(text_content)
                    self.monitor.log_info("Saved text response to response.txt")
                
                else:
                    with open("response.bin", "wb") as f:
                        f.write(content)
                    self.monitor.log_info("Saved binary response to response.bin")
        
        except Exception as e:
            self.monitor.log_error(f"Error handling response: {e}")
            self.monitor.log_error(traceback.format_exc())
    
    def get_private_key(self, index):
        """
        Get a private key by index.
        
        Args:
            index (int): The index of the private key to get.
            
        Returns:
            The private key or None if not found.
        """
        return self.private_keys.get(index)
    
    def wait_for_response(self, timeout=30):
        """
        Wait for a response from the onion network.
        
        Args:
            timeout (int, optional): Maximum time to wait in seconds.
            
        Returns:
            bool: True if a response was received, False otherwise.
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.response_received:
                return True
            time.sleep(0.1)
        
        return False
    
    def get_circuit_info(self):
        """
        Get information about the current circuit.
        
        Returns:
            dict: Information about the circuit.
        """
        if not self.circuit:
            return {"status": "not_established"}
        
        return {
            "status": "established",
            "session_id": self.session_id,
            "nodes": self.circuit,
            "entry_node": self.circuit[0] if self.circuit else None,
            "middle_node": self.circuit[1] if len(self.circuit) > 1 else None,
            "exit_node": self.circuit[2] if len(self.circuit) > 2 else None
        }
    
    def reset_circuit(self):
        """
        Reset the current circuit.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        self.session_id = None
        self.circuit = None
        self.private_keys.clear()
        self.response_handlers.clear()
        self.response_received = False
        
        return True


def serve(client_address, registry_address="localhost:5050"):
    """
    Start the terminus client and service.
    
    Args:
        client_address (str): The address for the client to listen on.
        registry_address (str, optional): The address of the registry service.
        
    Returns:
        TerminusClient: The terminus client.
    """
    monitor = StatusMonitor()
    
    # Create the terminus client
    client = TerminusClient(client_address, registry_address, monitor=monitor)
    
    # Start the service
    if not client.start_service():
        monitor.log_error("Failed to start terminus service")
        return None
    
    return client


if __name__ == "__main__":
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Start a terminus client")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", default="5000", help="Port to listen on")
    parser.add_argument("--registry", default="localhost:5050",
                        help="Address of the registry service")
    
    args = parser.parse_args()
    
    # Start the terminus client on localhost with the specified port
    client_address = f"{args.host}:{args.port}"
    client = serve(client_address, args.registry)
    
    if not client:
        print("Failed to start terminus client")
        import sys
        sys.exit(1)
    
    # Keep the client running
    try:
        import time
        while True:
            time.sleep(86400)  # Sleep for a day
    
    except KeyboardInterrupt:
        # Stop the client
        client.stop_service()
