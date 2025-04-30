"""
Message handler for the onion network.
Handles the creation and processing of layered messages.
"""

import pickle
import traceback
from core.crypto_utils import (
    asymmetric_encrypt, asymmetric_decrypt,
    symmetric_encrypt, symmetric_decrypt,
    generate_symmetric_key
)


class MessagePackager:
    """
    Creates and processes layered messages for onion routing.
    """
    
    @staticmethod
    def create_exit_layer(destination, http_method, public_key):
        """
        Create the innermost layer of the onion (exit node).
        
        Args:
            destination (str): Destination URL.
            http_method (str): HTTP method (GET, POST, etc.).
            public_key: Public key of the exit node.
            
        Returns:
            tuple: (encrypted_message, encrypted_key, iv)
        """
        try:
            # Generate a symmetric key for this layer
            sym_key = generate_symmetric_key()
            
            # Create the message with destination and HTTP method
            inner_payload = pickle.dumps({
                "action": "fetch",
                "url": destination.encode('utf-8'),
                "method": http_method.encode('utf-8'),
            })
            
            # Encrypt the message with the symmetric key
            iv, encrypted_message = symmetric_encrypt(sym_key, inner_payload)
            
            # Encrypt the symmetric key with the node's public key
            encrypted_key = asymmetric_encrypt(public_key, sym_key)
            
            return encrypted_message, encrypted_key, iv
        
        except Exception as e:
            print(f"Error creating exit layer: {e}")
            print(traceback.format_exc())
            raise
    
    @staticmethod
    def create_middle_layer(next_node_address, inner_layer, public_key):
        """
        Create a middle layer of the onion.
        
        Args:
            next_node_address (str): Address of the next node.
            inner_layer (tuple): Inner layer (encrypted_message, encrypted_key, iv).
            public_key: Public key of the middle node.
            
        Returns:
            tuple: (encrypted_message, encrypted_key, iv)
        """
        try:
            # Unpack the inner layer
            inner_encrypted_message, inner_encrypted_key, inner_iv = inner_layer
            
            # Generate a symmetric key for this layer
            sym_key = generate_symmetric_key()
            
            # Create the message with next hop and inner layer data
            middle_payload = pickle.dumps({
                "action": "forward",
                "next_hop": next_node_address.encode('utf-8'),
                "data": {
                    "message": inner_encrypted_message,
                    "key": inner_encrypted_key,
                    "iv": inner_iv
                }
            })
            
            # Encrypt the message with the symmetric key
            iv, encrypted_message = symmetric_encrypt(sym_key, middle_payload)
            
            # Encrypt the symmetric key with the node's public key
            encrypted_key = asymmetric_encrypt(public_key, sym_key)
            
            return encrypted_message, encrypted_key, iv
        
        except Exception as e:
            print(f"Error creating middle layer: {e}")
            print(traceback.format_exc())
            raise
    
    @staticmethod
    def create_entry_layer(next_node_address, inner_layer, public_key, return_address):
        """
        Create the outermost layer of the onion (entry node).
        
        Args:
            next_node_address (str): Address of the next node.
            inner_layer (tuple): Inner layer (encrypted_message, encrypted_key, iv).
            public_key: Public key of the entry node.
            return_address (str): Return address for responses.
            
        Returns:
            tuple: (encrypted_message, encrypted_key, iv)
        """
        try:
            # Unpack the inner layer
            inner_encrypted_message, inner_encrypted_key, inner_iv = inner_layer
            
            # Generate a symmetric key for this layer
            sym_key = generate_symmetric_key()
            
            # Create the message with next hop, inner layer data, and return address
            entry_payload = pickle.dumps({
                "action": "forward",
                "next_hop": next_node_address.encode('utf-8'),
                "return_address": return_address.encode('utf-8'),
                "data": {
                    "message": inner_encrypted_message,
                    "key": inner_encrypted_key,
                    "iv": inner_iv
                }
            })
            
            # Encrypt the message with the symmetric key
            iv, encrypted_message = symmetric_encrypt(sym_key, entry_payload)
            
            # Encrypt the symmetric key with the node's public key
            encrypted_key = asymmetric_encrypt(public_key, sym_key)
            
            return encrypted_message, encrypted_key, iv
        
        except Exception as e:
            print(f"Error creating entry layer: {e}")
            print(traceback.format_exc())
            raise
    
    @staticmethod
    def process_layer(encrypted_message, encrypted_key, iv, private_key):
        """
        Process and decrypt a layer of the onion.
        
        Args:
            encrypted_message (bytes): Encrypted message.
            encrypted_key (bytes): Encrypted symmetric key.
            iv (bytes): Initialization vector.
            private_key: Private key to decrypt the symmetric key.
            
        Returns:
            dict: Decrypted message content.
        """
        try:
            # Decrypt the symmetric key
            sym_key = asymmetric_decrypt(private_key, encrypted_key)
            
            # Decrypt the message
            decrypted_data = symmetric_decrypt(sym_key, iv, encrypted_message)
            
            # Deserialize the message
            return pickle.loads(decrypted_data)
        
        except Exception as e:
            print(f"Error processing layer: {e}")
            print(traceback.format_exc())
            raise
    
    @staticmethod
    def create_response_layer(inner_data, public_key):
        """
        Create a layer for the response path.
        
        Args:
            inner_data (bytes or dict): Data to encrypt.
            public_key: Public key of the next node in return path.
            
        Returns:
            tuple: (encrypted_message, encrypted_key, iv)
        """
        try:
            # Generate a symmetric key for this layer
            sym_key = generate_symmetric_key()
            
            # If inner_data is not bytes, serialize it
            if not isinstance(inner_data, bytes):
                inner_data = pickle.dumps(inner_data)
            
            # Create the message with the inner data
            payload = pickle.dumps({
                "action": "response",
                "data": inner_data
            })
            
            # Encrypt the message with the symmetric key
            iv, encrypted_message = symmetric_encrypt(sym_key, payload)
            
            # Encrypt the symmetric key with the node's public key
            encrypted_key = asymmetric_encrypt(public_key, sym_key)
            
            return encrypted_message, encrypted_key, iv
        
        except Exception as e:
            print(f"Error creating response layer: {e}")
            print(traceback.format_exc())
            raise
    
    @staticmethod
    def debug_message_structure(message, depth=0):
        """
        Recursively debug a message structure.
        
        Args:
            message: The message to debug.
            depth (int): Current recursion depth.
            
        Returns:
            str: A string representation of the message structure.
        """
        indent = "  " * depth
        result = []
        
        if isinstance(message, dict):
            result.append(f"{indent}Dict with keys: {list(message.keys())}")
            for key, value in message.items():
                result.append(f"{indent}Key: {key}")
                result.append(MessagePackager.debug_message_structure(value, depth + 1))
        
        elif isinstance(message, (list, tuple)):
            result.append(f"{indent}{type(message).__name__} of length {len(message)}")
            for i, item in enumerate(message):
                result.append(f"{indent}Item {i}:")
                result.append(MessagePackager.debug_message_structure(item, depth + 1))
        
        elif isinstance(message, bytes):
            result.append(f"{indent}Bytes of length {len(message)}")
            
            # Try to deserialize bytes
            try:
                deserialized = pickle.loads(message)
                result.append(f"{indent}Deserialized content:")
                result.append(MessagePackager.debug_message_structure(deserialized, depth + 1))
            except:
                pass
        
        else:
            result.append(f"{indent}{type(message).__name__}: {message}")
        
        return "\n".join(result)


if __name__ == "__main__":
    # Test the MessagePackager
    from core.crypto_utils import generate_keypair
    
    print("Testing MessagePackager...")
    
    # Generate keys for testing
    exit_pub, exit_priv = generate_keypair(1024)
    mid_pub, mid_priv = generate_keypair(1024)
    entry_pub, entry_priv = generate_keypair(1024)
    
    # Create the exit layer
    exit_layer = MessagePackager.create_exit_layer(
        "https://example.com", "GET", exit_pub
    )
    
    # Create the middle layer
    middle_layer = MessagePackager.create_middle_layer(
        "localhost:5052", exit_layer, mid_pub
    )
    
    # Create the entry layer
    entry_layer = MessagePackager.create_entry_layer(
        "localhost:5051", middle_layer, entry_pub, "localhost:5050"
    )
    
    # Process the entry layer
    entry_message = MessagePackager.process_layer(
        entry_layer[0], entry_layer[1], entry_layer[2], entry_priv
    )
    
    assert entry_message["action"] == "forward"
    print("Entry layer processing: Success")
    
    # Extract and process the middle layer
    middle_data = entry_message["data"]
    middle_message = MessagePackager.process_layer(
        middle_data["message"], middle_data["key"], middle_data["iv"], mid_priv
    )
    
    assert middle_message["action"] == "forward"
    print("Middle layer processing: Success")
    
    # Extract and process the exit layer
    exit_data = middle_message["data"]
    exit_message = MessagePackager.process_layer(
        exit_data["message"], exit_data["key"], exit_data["iv"], exit_priv
    )
    
    assert exit_message["action"] == "fetch"
    assert exit_message["url"].decode('utf-8') == "https://example.com"
    assert exit_message["method"].decode('utf-8') == "GET"
    print("Exit layer processing: Success")
    
    # Debug the message structure
    print("\nMessage Structure Debugging:")
    print(MessagePackager.debug_message_structure(entry_message))
