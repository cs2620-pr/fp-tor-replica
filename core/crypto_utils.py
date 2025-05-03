"""
Cryptographic utilities for the onion network.
Handles encryption and decryption operations for secure communication.
"""

import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as symmetric_padding
from cryptography.hazmat.backends import default_backend


def generate_keypair(key_size=2048):
    """
    Generate an RSA key pair with the specified key size.
    
    Args:
        key_size (int): Size of the RSA key in bits.
        
    Returns:
        tuple: (public_key, private_key)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return public_key, private_key


def public_key_to_pem(public_key):
    """
    Convert a public key object to PEM format string.
    
    Args:
        public_key: The public key object.
        
    Returns:
        str: PEM encoded public key.
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')


def pem_to_public_key(pem_string):
    """
    Convert a PEM format string to a public key object.
    
    Args:
        pem_string (str): PEM encoded public key.
        
    Returns:
        object: The public key object.
    """
    return serialization.load_pem_public_key(
        pem_string.encode('utf-8'),
        backend=default_backend()
    )


def asymmetric_encrypt(public_key, data):
    """
    Encrypt data using RSA public key with OAEP padding.
    
    Args:
        public_key: RSA public key.
        data (bytes): Data to encrypt.
        
    Returns:
        bytes: Encrypted data.
    """
    encrypted_data = public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted_data


def asymmetric_decrypt(private_key, encrypted_data):
    """
    Decrypt data using RSA private key with OAEP padding.
    
    Args:
        private_key: RSA private key.
        encrypted_data (bytes): Data to decrypt.
        
    Returns:
        bytes: Decrypted data.
    """
    decrypted_data = private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted_data


def symmetric_encrypt(key, data):
    """
    Encrypt data using AES-CBC with PKCS7 padding.
    
    Args:
        key (bytes): AES key.
        data (bytes): Data to encrypt.
        
    Returns:
        tuple: (initialization_vector, encrypted_data)
    """
    padder = symmetric_padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    initialization_vector = os.urandom(16)
    cipher = Cipher(
        algorithms.AES(key), 
        modes.CBC(initialization_vector),
        backend=default_backend()
    )
    
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    return initialization_vector, encrypted_data


def symmetric_decrypt(key, initialization_vector, encrypted_data):
    """
    Decrypt data using AES-CBC with PKCS7 padding.
    
    Args:
        key (bytes): AES key.
        initialization_vector (bytes): Initialization vector.
        encrypted_data (bytes): Data to decrypt.
        
    Returns:
        bytes: Decrypted data.
    """
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(initialization_vector),
        backend=default_backend()
    )
    
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()
    
    unpadder = symmetric_padding.PKCS7(128).unpadder()
    decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()
    
    return decrypted_data


def generate_symmetric_key(size=32):
    """
    Generate a random symmetric key.
    
    Args:
        size (int): Size of the key in bytes.
        
    Returns:
        bytes: Random key.
    """
    return os.urandom(size)


if __name__ == "__main__":
    # Test the cryptographic functions
    print("Testing cryptographic functions...")
    
    # Test RSA key generation and encryption/decryption
    public_key, private_key = generate_keypair(1024)
    test_data = b"Test message for RSA encryption"
    
    encrypted = asymmetric_encrypt(public_key, test_data)
    decrypted = asymmetric_decrypt(private_key, encrypted)
    
    assert decrypted == test_data
    print("RSA encryption/decryption: Success")
    
    # Test AES encryption/decryption
    aes_key = generate_symmetric_key()
    test_data = b"Test message for AES encryption"
    
    iv, encrypted = symmetric_encrypt(aes_key, test_data)
    decrypted = symmetric_decrypt(aes_key, iv, encrypted)
    
    assert decrypted == test_data
    print("AES encryption/decryption: Success")
