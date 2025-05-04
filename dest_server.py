import socket
import threading
import base64
import re
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import os
import json

DEST_PORT = 9100

def encrypt_aes_128_cbc(plaintext, key):
    # Generate a random 128-bit IV.
    iv = os.urandom(16)
    # Create a new AES-CBC cipher object.
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    # Pad the plaintext to a multiple of the block length.
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext) + padder.finalize()
    # Encrypt the plaintext.
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return iv + ct

def handle_client(conn, addr):
    try:
        data = conn.recv(65536)
        if not data:
            print(f"[DestServer] No data received from {addr}")
            return
        print(f"[DestServer] Received from {addr}: {data!r}, len={len(data)}, type={type(data)}")
        try:
            # Try both raw bytes and utf-8 decode for maximum compatibility
            try:
                payload_str = data.decode('utf-8')
                print(f"[DestServer] Decoded payload_str: {payload_str!r}")
            except Exception as e:
                print(f"[DestServer] ERROR: Could not decode as utf-8: {e}")
                payload_str = None
            # If utf-8 decode failed, try base64-decode then utf-8
            if payload_str is None or not payload_str.strip().startswith('{'):
                try:
                    payload_bytes = base64.b64decode(data)
                    payload_str = payload_bytes.decode('utf-8')
                    print(f"[DestServer] Base64-decoded then utf-8 payload_str: {payload_str!r}")
                except Exception as e:
                    print(f"[DestServer] ERROR: Could not base64-decode or utf-8 decode: {e}")
                    payload_str = None
            if payload_str is not None:
                try:
                    payload_json = json.loads(payload_str)
                    print(f"[DestServer] Parsed JSON: {payload_json}")
                    # Build a response JSON
                    response = {"result": "OK", "echo": payload_json}
                    response_bytes = json.dumps(response).encode('utf-8')
                    print(f"[DestServer] Response bytes (UTF-8 JSON): {response_bytes!r}")
                    to_send = response_bytes
                    print(f"[DestServer] Sending UTF-8 JSON response: {to_send!r}")
                except Exception as e:
                    print(f"[DestServer] ERROR: Could not parse JSON: {e}")
                    error_message = f"ERROR: {str(e)}".encode('utf-8')
                    # Wrap all errors in a JSON object for consistency
                    error_json = json.dumps({"result": "ERROR", "error": str(e)}).encode('utf-8')
                    to_send = error_json
            else:
                error_message = "ERROR: Could not decode payload as JSON."
                error_json = json.dumps({"result": "ERROR", "error": error_message}).encode('utf-8')
                to_send = error_json
        except Exception as e:
            print(f"[DestServer] ERROR: Invalid input: {e}\nPayload: {data}")
            error_message = f"ERROR: {str(e)}".encode('utf-8')
            error_json = json.dumps({"result": "ERROR", "error": str(e)}).encode('utf-8')
            to_send = error_json
        print(f"[DestServer] Sending back: {to_send!r}, len={len(to_send)}, type={type(to_send)}")
        conn.sendall(to_send)
    except Exception as e:
        print(f"[DestServer] Error with {addr}: {e}")
        error_message = f"ERROR: {str(e)}".encode('utf-8')
        error_json = json.dumps({"result": "ERROR", "error": str(e)}).encode('utf-8')
        conn.sendall(error_json)
    finally:
        conn.close()

def start_dest_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", DEST_PORT))  # Accept connections from any interface
        s.listen()
        print(f"[DestServer] Listening on port {DEST_PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_dest_server()
