import sys
import os
import socket
import threading
import base64
import json
import time
from crypto_utils import generate_rsa_keypair, serialize_public_key, rsa_decrypt, aes_decrypt, aes_encrypt, public_key_fingerprint
import re
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# --- Logging Setup ---
def log(msg):
    print(msg, flush=True)
    try:
        with open(f"relay{os.environ.get('RELAY_ID', 'X')}.log", 'a') as f:
            f.write(msg + '\n')
            f.flush()
    except Exception as e:
        print(f"[Relay] Logging error: {e}", flush=True)

log("[Relay] ---- Relay process started ----")

CDS_IP = '127.0.0.1'
CDS_PORT = 9000

class RelayNode:
    def __init__(self, relay_id, listen_port):
        self.relay_id = relay_id
        self.listen_port = listen_port
        # Set up logging function first
        self.log = lambda msg: log(f"[Relay {self.relay_id}] {msg}")
        self.ip = self.get_own_ip()
        self.load_or_generate_keys()
        self.public_key_pem = serialize_public_key(self.public_key).decode()
        self.log(f"[Relay] Public key fingerprint: {public_key_fingerprint(self.public_key)}")
        self.log(f"[Relay] [KEY] Public key fingerprint: {public_key_fingerprint(self.public_key)}")

    def get_own_ip(self):
        # Get the local IP address (not 127.0.0.1)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def load_or_generate_keys(self):
        keyfile = f"relay{self.relay_id}_key.pem"
        if os.path.exists(keyfile):
            with open(keyfile, "rb") as f:
                privkey = serialization.load_pem_private_key(
                    f.read(), password=None)
            self.private_key = privkey
            self.public_key = privkey.public_key()
            self.log(f"[Relay] Loaded persistent RSA keypair from {keyfile}")
        else:
            privkey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            with open(keyfile, "wb") as f:
                f.write(privkey.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            self.private_key = privkey
            self.public_key = privkey.public_key()
            self.log(f"[Relay] Generated and saved new RSA keypair to {keyfile}")

    def register_with_cds(self):
        self.log(f"Registering with CDS at {CDS_IP}:{CDS_PORT}")
        info = {
            'ip': self.ip,
            'port': self.listen_port,
            'public_key': self.public_key_pem
        }
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((CDS_IP, CDS_PORT))
            s.sendall(json.dumps(info).encode())
            resp = s.recv(1024)
            if resp == b'OK':
                self.log(f"[Relay] Registered with CDS: {info}")
            else:
                self.log(f"[Relay] Registration failed: {resp}")

    def start(self):
        self.log(f"Relay {self.relay_id} starting on {self.ip}:{self.listen_port} (RELAY PORT {self.listen_port})")
        self.register_with_cds()
        threading.Thread(target=self.listen, daemon=True).start()
        self.log(f"[Relay] Listening for incoming messages on port {self.listen_port} (RELAY PORT {self.listen_port})")
        while True:
            pass

    def listen(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to all interfaces for compatibility
            s.bind(("0.0.0.0", self.listen_port))
            s.listen()
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_message, args=(conn, addr), daemon=True).start()

    def handle_message(self, conn, addr):
        import threading
        import traceback
        sent_response = False
        thread_id = threading.get_ident()
        self.log(f"[Relay] [handle_message ENTERED] addr={addr}, thread={thread_id}, relay_port={getattr(self, 'listen_port', 'unknown')}")
        try:
            data = conn.recv(65536)
            self.log(f"[Relay] [DEBUG] Raw data received: {data!r}")
            if not data:
                self.log(f"[Relay] No data received from {addr}")
                raise ValueError("No data received")
            try:
                # Always decode as JSON at the outermost layer
                if isinstance(data, bytes):
                    try:
                        msg = json.loads(data.decode('utf-8'))
                    except Exception as e:
                        self.log(f"[Relay] ERROR: Could not decode JSON: {e}\nData: {data!r}")
                        raise
                else:
                    msg = json.loads(data)
                self.log(f"[Relay] [DEBUG] Data after JSON parse: type={type(msg)}, keys={list(msg.keys())}")
                # Decrypt session key
                self.log(f"[Relay] Received session_key (base64): {msg['session_key']}")
                session_key_enc = base64.b64decode(msg['session_key'])
                self.log(f"[Relay] Decoded session_key_enc (hex): {session_key_enc.hex()}")
                self.log(f"[Relay] Decrypting session key with fingerprint: {public_key_fingerprint(self.public_key)}")
                session_key = rsa_decrypt(self.private_key, session_key_enc)
                self.log(f"[Relay] Decrypted session_key (hex): {session_key.hex()}")
                # Always base64-decode the payload before AES decryption
                self.log(f"[Relay] [DEBUG] About to AES-decrypt payload (passing base64 string directly)")
                payload_bytes = base64.b64decode(msg['payload'])
                self.log(f"[Relay] [DEBUG] Payload base64-decoded: type={type(payload_bytes)}, len={len(payload_bytes)}, preview={payload_bytes[:60]!r}")
                decrypted = aes_decrypt(session_key, payload_bytes)
                self.log(f"[Relay] [DEBUG] AES-decrypted payload: type={type(decrypted)}, len={len(decrypted)}, preview={decrypted[:60]!r}")
                self.log(f"[Relay] [DEBUG] AES-decrypted payload (hex): {decrypted.hex()[:120]}")
                # Try to decode as JSON to determine if this is the last hop
                try:
                    # Only decode as JSON if possible
                    next_msg = json.loads(decrypted.decode('utf-8'))
                    self.log(f"[Relay] [DEBUG] Next hop JSON keys: {list(next_msg.keys())}")
                    # Forward to next relay
                    next_ip = next_msg['next_ip']
                    next_port = next_msg['next_port']
                    self.log(f"[Relay] [DEBUG] Forwarding to next relay {next_ip}:{next_port}")
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((next_ip, next_port))
                        s.sendall(decrypted)
                        response = s.recv(65536)
                    self.log(f"[Relay] [DEBUG] Received response from next relay: type={type(response)}, len={len(response)}, preview={response[:60]!r}")
                    # Return path logging
                    try:
                        response_bytes = base64.b64decode(response)
                        self.log(f"[Relay] [RETURN] Base64-decoded response: type={type(response_bytes)}, len={len(response_bytes)}, preview={response_bytes[:60]!r}")
                    except Exception as e:
                        self.log(f"[Relay] [RETURN] ERROR: Could not base64-decode response from next relay: {e}")
                        raise
                    # Attempt to AES-decrypt for logging (simulate what next hop will do)
                    try:
                        decrypted_response = aes_decrypt(session_key, response_bytes)
                        self.log(f"[Relay] [RETURN] AES-decrypted response: type={type(decrypted_response)}, len={len(decrypted_response)}, preview={decrypted_response[:60]!r}")
                        try:
                            utf8_decoded = decrypted_response.decode('utf-8')
                            self.log(f"[Relay] [RETURN] AES-decrypted response as UTF-8: {utf8_decoded}")
                        except Exception as e:
                            self.log(f"[Relay] [RETURN] AES-decrypted response not UTF-8: {e}")
                    except Exception as e:
                        self.log(f"[Relay] [RETURN] ERROR: Could not AES-decrypt response_bytes: {e}")
                    # Encrypt response with this session key and send back up
                    enc_response = aes_encrypt(session_key, response_bytes)
                    self.log(f"[Relay] [RETURN] AES-encrypted response (hex): {enc_response.hex()[:120]}")
                    response_payload = base64.b64encode(enc_response)
                    self.log(f"[Relay] [RETURN] Base64-encoded AES-encrypted response: type={type(response_payload)}, len={len(response_payload)}, preview={response_payload[:60]!r}")
                    conn.sendall(response_payload)
                    sent_response = True
                except Exception as e:
                    self.log(f"[Relay] [DEBUG] Payload is not JSON, assuming last hop. Error: {e}")
                    # Last hop: forward to destination server
                    self.forward_to_dest(decrypted, session_key, addr, conn)
                    sent_response = True
            except Exception as e:
                self.log(f"[Relay] ERROR in message processing: {e}\n{traceback.format_exc()}")
                try:
                    dummy = base64.b64encode(b'ERROR')
                    conn.sendall(dummy)
                    sent_response = True
                except Exception as e2:
                    self.log(f"[Relay] ERROR sending error response: {e2}\n{traceback.format_exc()}")
            finally:
                self.log(f"[Relay] [handle_message END] addr={addr}, thread={thread_id}")
                conn.close()
        except Exception as e:
            self.log(f"[Relay] ERROR in handle_message: {e}\n{traceback.format_exc()}")

    def forward_to_dest(self, payload, session_key, addr, conn):
        try:
            dest_ip = self.dest_ip if hasattr(self, 'dest_ip') else '127.0.0.1'
            dest_port = self.dest_port if hasattr(self, 'dest_port') else 9100
            self.log(f"[Relay] [Last Hop] Forwarding payload to dest {dest_ip}:{dest_port}, len={len(payload)}, type={type(payload)}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((dest_ip, dest_port))
                if isinstance(payload, bytes):
                    payload_bytes = payload
                elif isinstance(payload, str):
                    payload_bytes = payload.encode('utf-8')
                else:
                    payload_bytes = str(payload).encode('utf-8')
                self.log(f"[Relay] [Last Hop] Sending to dest: type={type(payload_bytes)}, len={len(payload_bytes)}, preview={repr(payload_bytes)[:80]}")
                s.sendall(payload_bytes)
                response = s.recv(65536)
            self.log(f"[Relay] [Last Hop] Received response from dest: type={type(response)}, len={len(response)}, preview={response[:60]!r}")
            # Diagnostic logging: try to decode as UTF-8 and log result
            try:
                decoded_response = response.decode('utf-8')
                self.log(f"[Relay] [Last Hop] Response from dest decoded as UTF-8: {decoded_response[:120]!r}")
            except Exception as e:
                self.log(f"[Relay] [Last Hop] Response from dest NOT UTF-8 decodable: {e}")
            # Log raw bytes in hex
            self.log(f"[Relay] [Last Hop] Response from dest (hex): {response.hex()[:120]}")
            # Ensure response is bytes (should be from dest server)
            if isinstance(response, str):
                response = response.encode('utf-8')
            # Encrypt and base64-encode only once
            self.log(f"[Relay] [Last Hop] About to AES-encrypt response: type={type(response)}, len={len(response)}, preview={response[:60]!r}")
            enc_response = aes_encrypt(session_key, response)
            self.log(f"[Relay] [Last Hop] AES-encrypted response (hex): {enc_response.hex()[:120]}")
            response_payload = base64.b64encode(enc_response)
            self.log(f"[Relay] [Last Hop] Base64-encoded AES-encrypted response: type={type(response_payload)}, len={len(response_payload)}, preview={response_payload[:60]!r}")
            conn.sendall(response_payload)
            self.log(f"[Relay] [Last Hop] Sent response to {addr}: {response_payload[:60]!r}... (len={len(response_payload)})")
        except Exception as e:
            self.log(f"[Relay] [Last Hop] ERROR forwarding to dest: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        log("Usage: python relay.py <relay_id> <listen_port>")
        sys.exit(1)
    relay_id = sys.argv[1]
    listen_port = int(sys.argv[2])
    relay = RelayNode(relay_id, listen_port)
    relay.start()
