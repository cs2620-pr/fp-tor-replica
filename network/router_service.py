"""
Router Service for the onion network.
Handles forwarding, encryption/decryption of messages as they pass through the network.
"""

import grpc
import requests
import pickle
import traceback
from concurrent import futures

from network.protos import onion_network_pb2, onion_network_pb2_grpc
from core.crypto_utils import (
    generate_keypair, public_key_to_pem, pem_to_public_key,
    asymmetric_decrypt, symmetric_decrypt, generate_symmetric_key, symmetric_encrypt,
    asymmetric_encrypt
)
from monitoring.status_monitor import StatusMonitor


class RouterServicer(onion_network_pb2_grpc.RouterServicer):
    """
    Implementation of the Router service.
    """
    
    # Node type constants
    ENTRY = 1
    MIDDLE = 2
    EXIT = 3
    
    def __init__(self, address, node_type, registry_address, monitor=None):
        """
        Initialize the RouterServicer.
        
        Args:
            address (str): The address this router is listening on.
            node_type (int): The type of this router (ENTRY, MIDDLE, or EXIT).
            registry_address (str): The address of the registry service.
            monitor (StatusMonitor, optional): Monitor for tracking stats.
        """
        super().__init__()
        self.address = address
        self.node_type = node_type
        self.registry_address = registry_address
        self.monitor = monitor or StatusMonitor()
        
        # Generate RSA key pair for this router
        self.router_public_key, self.router_private_key = generate_keypair(1024)
        self.router_public_key_pem = public_key_to_pem(self.router_public_key)
        
        # Store session information
        # Maps session_id -> client_public_key
        self.sessions = {}
        
        # Store return addresses for backward messages
        # Maps session_id -> return_address
        self.return_addresses = {}
        
        # Register with the registry service
        self._register_with_registry()
        
        # Log the node type for debugging
        node_type_name = {
            self.ENTRY: "ENTRY",
            self.MIDDLE: "MIDDLE",
            self.EXIT: "EXIT"
        }.get(self.node_type, "UNKNOWN")
        self.monitor.log_info(f"Router initialized as {node_type_name} node at {self.address}")
    
    def _register_with_registry(self):
        """
        Register this router with the registry service.
        """
        self.monitor.log_info(f"Registering with registry at {self.registry_address}")
        
        # Try to connect to the registry service
        while True:
            try:
                # Create a channel to the registry service
                with grpc.insecure_channel(self.registry_address) as channel:
                    # Create a stub for the registry service
                    stub = onion_network_pb2_grpc.RegistryStub(channel)
                    
                    # Send a register request
                    request = onion_network_pb2.RegisterNodeRequest(
                        address=self.address,
                        node_type=self.node_type
                    )
                    stub.RegisterNode(request)
                    
                    self.monitor.log_info("Registered with registry")
                    break
            
            except Exception as e:
                self.monitor.log_error(f"Failed to register with registry: {e}")
                import time
                time.sleep(5)  # Wait a bit before retrying
    
    def ExchangeKeys(self, request, context):
        """
        Handle a key exchange request.
        
        Args:
            request (ExchangeKeysRequest): The request message.
            context: The gRPC context.
            
        Returns:
            ExchangeKeysResponse: The response message with router's public key.
        """
        try:
            session_id = request.session_id
            client_public_key_pem = request.public_key
            
            self.monitor.log_info(f"Key exchange for session {session_id}")
            
            # Convert the client's public key from PEM format
            client_public_key = pem_to_public_key(client_public_key_pem)
            
            # Store the client's public key
            self.sessions[session_id] = client_public_key
            
            # Return the router's public key
            return onion_network_pb2.ExchangeKeysResponse(public_key=self.router_public_key_pem)
        
        except Exception as e:
            self.monitor.log_error(f"Error in ExchangeKeys: {e}")
            # Print the full traceback for debugging
            self.monitor.log_error(traceback.format_exc())
            # Still return a valid response to prevent the client from hanging
            return onion_network_pb2.ExchangeKeysResponse(public_key=self.router_public_key_pem)
    
    def RouteMessage(self, request, context):
        """
        Handle a forward message request.
        
        Args:
            request (RouteMessageRequest): The request message.
            context: The gRPC context.
            
        Returns:
            RouteMessageResponse: The response message.
        """
        try:
            # Extract data from the request
            encrypted_message = request.encrypted_message
            encrypted_key = request.encrypted_key
            iv = request.initialization_vector
            session_id = request.session_id.decode('utf-8')
            return_address = request.return_address
            
            self.monitor.log_info(f"Received route message for session {session_id}")
            
            # Store the return address if provided
            if return_address:
                self.return_addresses[session_id] = return_address
                self.monitor.log_info(f"Stored return address {return_address} for session {session_id}")
            
            # Decrypt the symmetric key using the router's private key
            sym_key = asymmetric_decrypt(self.router_private_key, encrypted_key)
            
            # Decrypt the message using the symmetric key
            decrypted_data = symmetric_decrypt(sym_key, iv, encrypted_message)
            
            # Deserialize the message
            message = pickle.loads(decrypted_data)
            
            # Log message info for debugging
            message_action = message.get("action", "unknown")
            self.monitor.log_info(f"Message action: {message_action}, Node type: {self.node_type}")
            
            # Handle the message based on the node type and message action
            if self.node_type == self.EXIT and message_action == "fetch":
                # This is an exit node, fetch the requested URL
                self.monitor.log_info(f"Exit node handling fetch request")
                return self._handle_exit_node_fetch(message, session_id)
            
            elif message_action == "forward":
                # This is an entry or middle node, forward the message
                self.monitor.log_info(f"Forwarding message onward")
                return self._handle_forward(message, session_id)
            
            else:
                # Unexpected message type or action
                self.monitor.log_warning(
                    f"Unexpected message action: {message_action} for node type {self.node_type}"
                )
                return onion_network_pb2.RouteMessageResponse()
        
        except Exception as e:
            self.monitor.log_error(f"Error in RouteMessage: {e}")
            # Print the full traceback for debugging
            self.monitor.log_error(traceback.format_exc())
            return onion_network_pb2.RouteMessageResponse()
    
    def _handle_exit_node_fetch(self, message, session_id):
        """
        Handle a fetch request at an exit node.
        
        Args:
            message (dict): The decrypted message.
            session_id (str): The session ID.
            
        Returns:
            RouteMessageResponse: The response message.
        """
        try:
            # Validate message structure
            if "url" not in message or "method" not in message:
                self.monitor.log_error(f"Missing required fields in exit node message: {message.keys()}")
                error_response = ({"error": "Invalid message format"}, b"")
                return self._send_response_back(error_response, session_id)
            
            url = message["url"].decode('utf-8') if isinstance(message["url"], bytes) else message["url"]
            method = message["method"].decode('utf-8') if isinstance(message["method"], bytes) else message["method"]
            
            self.monitor.log_info(f"Exit node fetching {method} {url} for session {session_id}")
            
            # Fetch the URL with timeout
            try:
                if method == "GET":
                    response = requests.get(url, timeout=15)
                elif method == "POST":
                    response = requests.post(url, timeout=15)
                else:
                    # Default to GET for unsupported methods
                    self.monitor.log_info(f"Unsupported method {method}, using GET instead")
                    response = requests.get(url, timeout=15)
                
                # Extract headers and content
                headers = dict(response.headers)
                content = response.content
                
                self.monitor.log_info(f"Successfully fetched {url}, status: {response.status_code}, content length: {len(content)}")
                
                # Create a response message
                response_data = (headers, content)
                
                # Encrypt and send the response back through the circuit
                return self._send_response_back(response_data, session_id)
            
            except requests.RequestException as req_error:
                self.monitor.log_error(f"Request error fetching {url}: {req_error}")
                error_response = ({"error": str(req_error)}, b"")
                return self._send_response_back(error_response, session_id)
        
        except Exception as e:
            self.monitor.log_error(f"Error in _handle_exit_node_fetch: {e}")
            # Print the full traceback for debugging
            self.monitor.log_error(traceback.format_exc())
            
            # Create an error response
            error_response = ({"error": str(e)}, b"")
            
            # Encrypt and send the error back through the circuit
            return self._send_response_back(error_response, session_id)
    
    def _handle_forward(self, message, session_id):
        """
        Handle a forward request at an entry or middle node.
        
        Args:
            message (dict): The decrypted message.
            session_id (str): The session ID.
            
        Returns:
            RouteMessageResponse: The response message.
        """
        try:
            # Validate message structure
            if "next_hop" not in message or "data" not in message:
                self.monitor.log_error(f"Missing required fields in forward message: {message.keys()}")
                return onion_network_pb2.RouteMessageResponse()
            
            # Decode next_hop if it's bytes
            if isinstance(message["next_hop"], bytes):
                next_hop = message["next_hop"].decode('utf-8')
            else:
                next_hop = message["next_hop"]
            
            data = message["data"]
            
            self.monitor.log_info(f"Forwarding message to {next_hop} for session {session_id}")
            
            # Store the return address if it's an entry node
            if self.node_type == self.ENTRY and "return_address" in message:
                return_address = message["return_address"]
                if isinstance(return_address, bytes):
                    return_address = return_address.decode('utf-8')
                
                self.return_addresses[session_id] = return_address
                self.monitor.log_info(f"Entry node stored return address {return_address} for session {session_id}")
            
            # Validate data structure before forwarding
            if not isinstance(data, dict):
                self.monitor.log_error(f"Invalid data type in message: {type(data)}")
                return onion_network_pb2.RouteMessageResponse()
            
            required_keys = ["message", "key", "iv"]
            if not all(k in data for k in required_keys):
                self.monitor.log_error(f"Missing required keys in data: have {data.keys()}, need {required_keys}")
                return onion_network_pb2.RouteMessageResponse()
            
            try:
                # Create a channel to the next hop with a timeout
                options = [
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50 MB
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024)  # 50 MB
                ]
                with grpc.insecure_channel(next_hop, options=options) as channel:
                    # Create a stub for the router service
                    stub = onion_network_pb2_grpc.RouterStub(channel)
                    
                    # Create a forward request
                    request = onion_network_pb2.RouteMessageRequest(
                        encrypted_message=data["message"],
                        encrypted_key=data["key"],
                        initialization_vector=data["iv"],
                        session_id=session_id.encode('utf-8'),
                        return_address=self.address
                    )
                    
                    # Send the request to the next hop with a timeout
                    response = stub.RouteMessage(request, timeout=15)
                    self.monitor.log_info(f"Successfully forwarded message to {next_hop}")
                    return response
            
            except grpc.RpcError as rpc_error:
                self.monitor.log_error(f"gRPC error forwarding to {next_hop}: {rpc_error.code()}: {rpc_error.details()}")
                return onion_network_pb2.RouteMessageResponse()
        
        except Exception as e:
            self.monitor.log_error(f"Error in _handle_forward: {e}")
            # Print the full traceback for debugging
            self.monitor.log_error(traceback.format_exc())
            
            # Log more detailed information about the message structure
            try:
                self.monitor.log_info(f"Message keys: {message.keys()}")
                if "data" in message:
                    self.monitor.log_info(f"Data type: {type(message['data'])}")
                    if isinstance(message["data"], dict):
                        self.monitor.log_info(f"Data keys: {message['data'].keys()}")
            except Exception as detail_error:
                self.monitor.log_error(f"Error getting message details: {detail_error}")
            
            return onion_network_pb2.RouteMessageResponse()
    
    def _send_response_back(self, response_data, session_id):
        """
        Encrypt and send a response back through the circuit.
        
        Args:
            response_data: The response data to send.
            session_id (str): The session ID.
            
        Returns:
            RouteMessageResponse: The response message.
        """
        try:
            # Get the return address for this session
            return_address = self.return_addresses.get(session_id)
            
            if not return_address:
                self.monitor.log_warning(f"No return address for session {session_id}")
                return onion_network_pb2.RouteMessageResponse()
            
            # Get the client's public key for this session
            client_public_key = self.sessions.get(session_id)
            
            if not client_public_key:
                self.monitor.log_warning(f"No client public key for session {session_id}")
                return onion_network_pb2.RouteMessageResponse()
            
            # Serialize the response data
            response_bytes = pickle.dumps(response_data)
            
            # Generate a symmetric key
            sym_key = generate_symmetric_key()
            
            # Encrypt the response with the symmetric key
            iv, encrypted_response = symmetric_encrypt(sym_key, response_bytes)
            
            # Encrypt the symmetric key with the client's public key
            encrypted_key = asymmetric_encrypt(client_public_key, sym_key)
            
            self.monitor.log_info(f"Sending response back to {return_address} for session {session_id}")
            
            try:
                # Create a channel to the return address with increased message size limits
                options = [
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50 MB
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024)  # 50 MB
                ]
                with grpc.insecure_channel(return_address, options=options) as channel:
                    # If this is sending to a middle node, use the Router service
                    if self.node_type == self.EXIT:
                        # Create a stub for the router service
                        stub = onion_network_pb2_grpc.RouterStub(channel)
                        
                        # Create a backward request
                        request = onion_network_pb2.RouteMessageRequest(
                            encrypted_message=encrypted_response,
                            encrypted_key=encrypted_key,
                            initialization_vector=iv,
                            session_id=session_id.encode('utf-8')
                        )
                        
                        # Send the request with timeout
                        response = stub.RouteBackward(request, timeout=15)
                        self.monitor.log_info(f"Successfully sent response back to {return_address}")
                        return response
                    
                    # If this is an entry node sending to a client
                    elif self.node_type == self.ENTRY:
                        # Create a stub for the terminus service
                        stub = onion_network_pb2_grpc.TerminusStub(channel)
                        
                        # Create a deliver request
                        request = onion_network_pb2.DeliverMessageRequest(
                            encrypted_message=encrypted_response,
                            encrypted_key=encrypted_key,
                            initialization_vector=iv,
                            session_id=session_id.encode('utf-8')
                        )
                        
                        # Send the request with timeout
                        stub.DeliverMessage(request, timeout=15)
                        self.monitor.log_info(f"Successfully sent response to client at {return_address}")
                        return onion_network_pb2.RouteMessageResponse()
                    
                    else:
                        self.monitor.log_warning(f"Unexpected node type {self.node_type} when sending response back")
                        return onion_network_pb2.RouteMessageResponse()
            
            except grpc.RpcError as rpc_error:
                self.monitor.log_error(f"gRPC error sending response back to {return_address}: {rpc_error.code()}: {rpc_error.details()}")
                return onion_network_pb2.RouteMessageResponse()
        
        except Exception as e:
            self.monitor.log_error(f"Error in _send_response_back: {e}")
            # Print the full traceback for debugging
            self.monitor.log_error(traceback.format_exc())
            return onion_network_pb2.RouteMessageResponse()
    
    def RouteBackward(self, request, context):
        """
        Handle a backward message request.
        
        Args:
            request (RouteMessageRequest): The request message.
            context: The gRPC context.
            
        Returns:
            RouteMessageResponse: The response message.
        """
        try:
            # Extract data from the request
            encrypted_message = request.encrypted_message
            encrypted_key = request.encrypted_key
            iv = request.initialization_vector
            session_id = request.session_id.decode('utf-8')
            
            self.monitor.log_info(f"Handling backward message for session {session_id}")
            
            # Get the return address for this session
            return_address = self.return_addresses.get(session_id)
            
            if not return_address:
                self.monitor.log_warning(f"No return address for session {session_id}")
                return onion_network_pb2.RouteMessageResponse()
            
            # Get the client's public key for this session
            client_public_key = self.sessions.get(session_id)
            
            if not client_public_key:
                self.monitor.log_warning(f"No client public key for session {session_id}")
                return onion_network_pb2.RouteMessageResponse()
            
            # Generate a symmetric key
            sym_key = generate_symmetric_key()
            
            # Create a message with the encrypted response
            message = pickle.dumps({
                "data": pickle.dumps((encrypted_message, encrypted_key, iv))
            })
            
            # Encrypt the message with the symmetric key
            new_iv, encrypted_message = symmetric_encrypt(sym_key, message)
            
            # Encrypt the symmetric key with the client's public key
            encrypted_key = asymmetric_encrypt(client_public_key, sym_key)
            
            self.monitor.log_info(f"Forwarding backward message to {return_address} for session {session_id}")
            
            try:
                # Create a channel to the return address with increased message size limits
                options = [
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50 MB
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024)  # 50 MB
                ]
                with grpc.insecure_channel(return_address, options=options) as channel:
                    # If this is an entry node sending to a client
                    if self.node_type == self.ENTRY:
                        # Create a stub for the terminus service
                        stub = onion_network_pb2_grpc.TerminusStub(channel)
                        
                        # Create a deliver request
                        request = onion_network_pb2.DeliverMessageRequest(
                            encrypted_message=encrypted_message,
                            encrypted_key=encrypted_key,
                            initialization_vector=new_iv,
                            session_id=session_id.encode('utf-8')
                        )
                        
                        # Send the request with timeout
                        stub.DeliverMessage(request, timeout=15)
                        self.monitor.log_info(f"Successfully delivered backward message to client")
                    
                    else:  # Middle node sending to entry node
                        # Create a stub for the router service
                        stub = onion_network_pb2_grpc.RouterStub(channel)
                        
                        # Create a backward request
                        request = onion_network_pb2.RouteMessageRequest(
                            encrypted_message=encrypted_message,
                            encrypted_key=encrypted_key,
                            initialization_vector=new_iv,
                            session_id=session_id.encode('utf-8')
                        )
                        
                        # Send the request with timeout
                        stub.RouteBackward(request, timeout=15)
                        self.monitor.log_info(f"Successfully routed backward message to previous node")
                
                return onion_network_pb2.RouteMessageResponse()
            
            except grpc.RpcError as rpc_error:
                self.monitor.log_error(f"gRPC error forwarding backward message to {return_address}: {rpc_error.code()}: {rpc_error.details()}")
                return onion_network_pb2.RouteMessageResponse()
        
        except Exception as e:
            self.monitor.log_error(f"Error in RouteBackward: {e}")
            # Print the full traceback for debugging
            self.monitor.log_error(traceback.format_exc())
            return onion_network_pb2.RouteMessageResponse()
    
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


def serve(address, node_type, registry_address, max_workers=10):
    """
    Start the router service.
    
    Args:
        address (str): The address to bind the service to.
        node_type (int): The type of this router (ENTRY, MIDDLE, or EXIT).
        registry_address (str): The address of the registry service.
        max_workers (int, optional): Maximum number of worker threads.
        
    Returns:
        tuple: (grpc.Server, RouterServicer)
    """
    monitor = StatusMonitor()
    
    # Set gRPC options for large messages
    options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50 MB
        ('grpc.max_receive_message_length', 50 * 1024 * 1024)  # 50 MB
    ]
    
    # Create the server
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=options
    )
    
    # Add the servicer to the server
    router_servicer = RouterServicer(address, node_type, registry_address, monitor=monitor)
    onion_network_pb2_grpc.add_RouterServicer_to_server(router_servicer, server)
    
    # Bind the server to the address
    server.add_insecure_port(address)
    
    # Start the server
    node_type_name = {
        1: "ENTRY",
        2: "MIDDLE",
        3: "EXIT"
    }.get(node_type, "UNKNOWN")
    
    monitor.log_info(f"Starting {node_type_name} router on {address}")
    server.start()
    
    return server, router_servicer


if __name__ == "__main__":
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Start a router node")
    parser.add_argument("port", help="Port to listen on")
    parser.add_argument("type", type=int, choices=[1, 2, 3],
                        help="Node type: 1 (entry), 2 (middle), or 3 (exit)")
    parser.add_argument("--registry", default="localhost:5050",
                        help="Address of the registry service")
    
    args = parser.parse_args()
    
    # Start the router on localhost with the specified port
    address = f"localhost:{args.port}"
    server, servicer = serve(address, args.type, args.registry)
    
    try:
        # Keep the main thread alive
        import time
        while True:
            time.sleep(86400)  # Sleep for a day
    
    except KeyboardInterrupt:
        # Stop the server
        server.stop(grace=0)
