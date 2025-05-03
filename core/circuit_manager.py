"""
Circuit Manager for the onion network.
Handles the creation and management of circuits through the network.
"""

import uuid
import concurrent.futures
import grpc

from core.crypto_utils import (
    generate_keypair, public_key_to_pem, pem_to_public_key
)
from network.protos import onion_network_pb2, onion_network_pb2_grpc


class CircuitManager:
    """
    Manages the creation and maintenance of circuits through the onion network.
    """
    
    def __init__(self, registry_address):
        """
        Initialize the CircuitManager.
        
        Args:
            registry_address (str): Address of the registry service.
        """
        self.registry_address = registry_address
        self.session_id = str(uuid.uuid4())
        self.node_keys = {}  # Public keys of nodes
        self.client_keys = {}  # Client key pairs for each node
        self.node_channels = {}  # gRPC channels to nodes
        self.node_stubs = {}  # gRPC stubs for nodes
        self.circuit = []  # Ordered list of node addresses in the circuit
        
    def get_available_nodes(self):
        """
        Fetch available nodes from the registry service.
        
        Returns:
            list: List of node addresses.
        """
        # Create a channel to the registry service
        with grpc.insecure_channel(self.registry_address) as channel:
            # Create a stub for the registry service
            stub = onion_network_pb2_grpc.RegistryStub(channel)
            
            # Request the list of available nodes
            response = stub.GetNodes(onion_network_pb2.GetNodesRequest())
            
            # Extract and return the node addresses
            return [(node.address, node.node_type) for node in response.nodes]
    
    def select_circuit_nodes(self):
        """
        Select nodes for the circuit.
        
        Returns:
            list: List of node addresses in order (entry, middle, exit).
        """
        # Get all available nodes
        available_nodes = self.get_available_nodes()
        
        # Group nodes by type
        entry_nodes = [node[0] for node in available_nodes if node[1] == onion_network_pb2.NodeType.ENTRY]
        middle_nodes = [node[0] for node in available_nodes if node[1] == onion_network_pb2.NodeType.MIDDLE]
        exit_nodes = [node[0] for node in available_nodes if node[1] == onion_network_pb2.NodeType.EXIT]
        
        # Select one node of each type
        # In a real implementation, this would involve more sophisticated selection
        # based on node performance, reliability, etc.
        if not entry_nodes or not middle_nodes or not exit_nodes:
            raise ValueError("Not enough nodes available to build a circuit")
        
        # For this example, just take the first of each type
        selected_circuit = [entry_nodes[0], middle_nodes[0], exit_nodes[0]]
        return selected_circuit
    
    def establish_circuit(self):
        """
        Establish a circuit through the network by selecting nodes and
        exchanging keys with each node.
        
        Returns:
            bool: True if circuit was successfully established, False otherwise.
        """
        try:
            # Select nodes for the circuit
            self.circuit = self.select_circuit_nodes()
            
            # Create channels and stubs for each node
            for node_address in self.circuit:
                self.node_channels[node_address] = grpc.insecure_channel(node_address)
                self.node_stubs[node_address] = onion_network_pb2_grpc.RouterStub(
                    self.node_channels[node_address]
                )
            
            # Generate key pairs for each node concurrently
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Generate a 1024-bit key pair for each node
                futures = {
                    node_address: executor.submit(generate_keypair, 1024)
                    for node_address in self.circuit
                }
                
                # Collect the results
                for node_address, future in futures.items():
                    public_key, private_key = future.result()
                    self.client_keys[node_address] = (public_key, private_key)
            
            # Exchange keys with each node
            for node_address in self.circuit:
                # Get the client's public key for this node
                client_public_key, _ = self.client_keys[node_address]
                
                # Convert the public key to PEM format
                pem_public_key = public_key_to_pem(client_public_key)
                
                # Create the exchange keys request
                request = onion_network_pb2.ExchangeKeysRequest(
                    session_id=self.session_id,
                    public_key=pem_public_key
                )
                
                # Send the request to the node
                response = self.node_stubs[node_address].ExchangeKeys(request)
                
                # Convert the node's public key from PEM format
                node_public_key = pem_to_public_key(response.public_key)
                
                # Store the node's public key
                self.node_keys[node_address] = node_public_key
            
            return True
        
        except Exception as e:
            print(f"Failed to establish circuit: {e}")
            self.teardown_circuit()
            return False
    
    def teardown_circuit(self):
        """
        Tear down the circuit by closing all channels.
        """
        # Close all channels
        for channel in self.node_channels.values():
            channel.close()
        
        # Clear all circuit data
        self.node_keys.clear()
        self.client_keys.clear()
        self.node_channels.clear()
        self.node_stubs.clear()
        self.circuit.clear()
    
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
    
    def get_node_keys(self):
        """
        Get the public keys of all nodes in the circuit.
        
        Returns:
            dict: Node addresses mapped to their public keys.
        """
        return self.node_keys
    
    def get_client_keys(self):
        """
        Get the client key pairs for all nodes in the circuit.
        
        Returns:
            dict: Node addresses mapped to (public_key, private_key) tuples.
        """
        return self.client_keys
    
    def get_node_stubs(self):
        """
        Get the gRPC stubs for all nodes in the circuit.
        
        Returns:
            dict: Node addresses mapped to their gRPC stubs.
        """
        return self.node_stubs


if __name__ == "__main__":
    # Test the CircuitManager
    # This won't actually work without a running registry service
    # and router nodes, but it demonstrates the usage
    
    print("CircuitManager test")
    
    # Create a CircuitManager
    manager = CircuitManager("localhost:5050")
    
    # Establish a circuit
    # This would fail without actual services running
    try:
        success = manager.establish_circuit()
        if success:
            print("Circuit established successfully")
            
            # Get circuit info
            circuit_info = manager.get_circuit_info()
            print(f"Circuit: {circuit_info}")
            
            # Tear down the circuit
            manager.teardown_circuit()
            print("Circuit torn down")
        else:
            print("Failed to establish circuit")
    
    except Exception as e:
        print(f"Test failed: {e}")
