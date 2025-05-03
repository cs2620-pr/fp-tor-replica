"""
Registry Service for the onion network.
Acts as a directory service that maintains a list of available router nodes.
"""

import threading
import time
import grpc
from concurrent import futures

from network.protos import onion_network_pb2, onion_network_pb2_grpc
from monitoring.status_monitor import StatusMonitor


class RegistryServicer(onion_network_pb2_grpc.RegistryServicer):
    """
    Implementation of the Registry service.
    """
    
    def __init__(self, monitor=None):
        """
        Initialize the RegistryServicer.
        
        Args:
            monitor (StatusMonitor, optional): Monitor for tracking stats.
        """
        super().__init__()
        self.nodes = []  # List of (address, node_type) tuples
        self.monitor = monitor or StatusMonitor()
        
        # Start a thread to periodically ping nodes
        self.running = True
        self.ping_thread = threading.Thread(target=self._ping_nodes)
        self.ping_thread.daemon = True
        self.ping_thread.start()
        
    def GetNodes(self, request, context):
        """
        Handle a request for available router nodes.
        
        Args:
            request (GetNodesRequest): The request message.
            context: The gRPC context.
            
        Returns:
            GetNodesResponse: The response message with available nodes.
        """
        self.monitor.log_info("Received GetNodes request")
        
        # Create a list of Node messages from the stored nodes
        node_messages = [
            onion_network_pb2.Node(address=address, node_type=node_type)
            for address, node_type in self.nodes
        ]
        
        self.monitor.log_info(f"Returning {len(node_messages)} nodes")
        
        # Return the response with the list of nodes
        return onion_network_pb2.GetNodesResponse(nodes=node_messages)
    
    def RegisterNode(self, request, context):
        """
        Handle a request to register a router node.
        
        Args:
            request (RegisterNodeRequest): The request message.
            context: The gRPC context.
            
        Returns:
            Empty: An empty response.
        """
        address = request.address
        node_type = request.node_type
        
        self.monitor.log_info(f"Registering node {address} as type {node_type}")
        
        # Add the node to the list
        self.nodes.append((address, node_type))
        
        # Return an empty response
        return onion_network_pb2.Empty()
    
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
    
    def _ping_nodes(self):
        """
        Periodically ping all registered nodes to check if they are still alive.
        Remove any nodes that do not respond.
        """
        while self.running:
            # Sleep for a while
            time.sleep(10)
            
            if not self.nodes:
                continue
            
            self.monitor.log_info("Pinging registered nodes")
            
            alive_nodes = []
            
            # Ping each node
            for address, node_type in self.nodes:
                try:
                    # Create a channel to the node
                    with grpc.insecure_channel(address) as channel:
                        # Create a stub for the router service
                        stub = onion_network_pb2_grpc.RouterStub(channel)
                        
                        # Send a ping request with a 2 second timeout
                        stub.Ping(onion_network_pb2.Empty(), timeout=2)
                        
                        # If we get here, the node is alive
                        alive_nodes.append((address, node_type))
                        self.monitor.log_info(f"Node {address} is alive")
                
                except Exception as e:
                    # If the ping fails, the node is considered dead
                    self.monitor.log_warning(f"Node {address} is not responding: {e}")
            
            # Update the list of nodes
            self.nodes = alive_nodes
    
    def stop(self):
        """
        Stop the ping thread.
        """
        self.running = False
        if self.ping_thread.is_alive():
            self.ping_thread.join(timeout=1)


def serve(address, max_workers=10):
    """
    Start the registry service.
    
    Args:
        address (str): The address to bind the service to.
        max_workers (int, optional): Maximum number of worker threads.
        
    Returns:
        grpc.Server: The gRPC server.
    """
    monitor = StatusMonitor()
    
    # Create the server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    
    # Add the servicer to the server
    registry_servicer = RegistryServicer(monitor=monitor)
    onion_network_pb2_grpc.add_RegistryServicer_to_server(registry_servicer, server)
    
    # Bind the server to the address
    server.add_insecure_port(address)
    
    # Start the server
    monitor.log_info(f"Starting registry service on {address}")
    server.start()
    
    return server, registry_servicer


if __name__ == "__main__":
    # Start the registry service on localhost:5050
    server, servicer = serve("localhost:5050")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(86400)  # Sleep for a day
    
    except KeyboardInterrupt:
        # Stop the server
        servicer.stop()
        server.stop(grace=0)
