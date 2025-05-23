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
import signal

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
        self.shutdown_registered = False
        signal.signal(signal.SIGINT, self.deregister_and_exit)
        signal.signal(signal.SIGTERM, self.deregister_and_exit)

    def deregister_and_exit(self, signum, frame):
        if self.shutdown_registered:
            return
        self.shutdown_registered = True
        self.log(f"[Relay] Deregistering from CDS and shutting down...")
        info = {
            'ip': self.ip,
            'port': self.listen_port,
            'deregister': True
        }
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((CDS_IP, CDS_PORT))
                s.sendall(json.dumps(info).encode())
                s.recv(1024)
        except Exception as e:
            self.log(f"[Relay] ERROR during deregistration: {e}")
        os._exit(0)

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
            s.bind(("0.0.0.0", self.listen_port))  # Accept connections from any interface
            s.listen()
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_message, args=(conn, addr), daemon=True).start()

    def handle_message(self, conn, addr):
        thread_id = threading.get_ident()
        try:
            data = conn.recv(65536)
            self.log(f"[Relay] [DEBUG] Raw data received: {data!r}")
            if not data:
                self.log(f"[Relay] [DEBUG] No data received, closing connection.")
                conn.close()
                return
            try:
                # Defensive: if data is not valid UTF-8 or not JSON, treat as last hop
                try:
                    payload_str = data.decode('utf-8')
                    payload_json = json.loads(payload_str)
                except Exception:
                    # Not JSON, treat as last hop
                    self.log(f"[Relay] [DEBUG] Data is not JSON, treating as last hop.")
                    self.forward_to_dest(data, None, addr, conn)
                    return
                # If here, data is JSON, process as normal
                session_key_enc = payload_json.get('session_key')
                payload_b64 = payload_json.get('payload')
                if not session_key_enc or not payload_b64:
                    self.log(f"[Relay] [DEBUG] Missing session_key or payload, treating as last hop.")
                    self.forward_to_dest(data, None, addr, conn)
                    return
                session_key = rsa_decrypt(self.private_key, base64.b64decode(session_key_enc))
                payload_bytes = base64.b64decode(payload_b64)
                decrypted = aes_decrypt(session_key, payload_bytes)
                self.log(f"[Relay] [DEBUG] AES-decrypted payload: type={type(decrypted)}, len={len(decrypted)}, preview={decrypted[:60]!r}")
                # Try to parse as JSON for next hop
                try:
                    next_layer = json.loads(decrypted.decode('utf-8'))
                    # Forward to next relay
                    next_ip = next_layer.get('next_ip')
                    next_port = next_layer.get('next_port')
                    next_session_key_enc = next_layer.get('session_key')
                    next_payload_b64 = next_layer.get('payload')
                    if not next_ip or not next_port or not next_session_key_enc or not next_payload_b64:
                        raise Exception("Missing fields for next hop")
                    # Prepare next layer
                    next_payload = json.dumps({
                        'session_key': next_session_key_enc,
                        'payload': next_payload_b64
                    }).encode('utf-8')
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((next_ip, int(next_port)))
                        s.sendall(next_payload)
                        response = s.recv(65536)
                    self.log(f"[Relay] [DEBUG] Received response from next relay: type={type(response)}, len={len(response)}, preview={response[:60]!r}")
                    # Wrap response in AES for this layer
                    enc_response = aes_encrypt(session_key, response)
                    response_payload = base64.b64encode(enc_response)
                    conn.sendall(response_payload)
                    self.log(f"[Relay] [DEBUG] Sent wrapped response to previous hop.")
                except Exception as e:
                    self.log(f"[Relay] [DEBUG] Could not parse decrypted payload as JSON, treating as last hop. Error: {e}")
                    self.forward_to_dest(decrypted, session_key, addr, conn)
            except Exception as e:
                self.log(f"[Relay] ERROR in message processing: {e}")
                try:
                    dummy = base64.b64encode(b'ERROR')
                    conn.sendall(dummy)
                except Exception as e2:
                    self.log(f"[Relay] ERROR sending error response: {e2}")
            finally:
                self.log(f"[Relay] [handle_message END] addr={addr}, thread={thread_id}")
                conn.close()
        except Exception as e:
            self.log(f"[Relay] ERROR in handle_message: {e}")

    def forward_to_dest(self, payload, session_key, addr, conn):
        try:
            self.log(f"[Relay] [Last Hop] Forwarding payload to dest 127.0.0.1:9100, len={len(payload)}, type={type(payload)}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("127.0.0.1", 9100))
                self.log(f"[Relay] [Last Hop] Sending to dest: type={type(payload)}, len={len(payload)}, preview={payload[:60]!r}")
                s.sendall(payload)
                response = s.recv(65536)
            self.log(f"[Relay] [Last Hop] Received response from dest: type={type(response)}, len={len(response)}, preview={response[:60]!r}")
            # Always send a valid response to the client, even if session_key is None (error fallback)
            try:
                decoded_resp = response.decode('utf-8')
                response_json = json.dumps({'result': 'OK', 'echo': decoded_resp})
            except Exception:
                import base64 as _base64
                response_json = json.dumps({'result': 'OK', 'echo': _base64.b64encode(response).decode('utf-8'), 'encoding': 'base64'})
            response_bytes = response_json.encode('utf-8')
            self.log(f"[Relay] [Last Hop] Response to client (UTF-8 JSON): {response_bytes[:120]!r}")
            if session_key:
                enc_response = aes_encrypt(session_key, response_bytes)
                self.log(f"[Relay] [Last Hop] AES-encrypted response (hex): {enc_response.hex()[:120]}")
                response_payload = base64.b64encode(enc_response)
                self.log(f"[Relay] [Last Hop] Base64-encoded AES-encrypted response: type={type(response_payload)}, len={len(response_payload)}, preview={response_payload[:60]!r}")
                conn.sendall(response_payload)
                self.log(f"[Relay] [Last Hop] Sent response to {addr}: {response_payload[:60]!r}... (len={len(response_payload)})")
            else:
                # Fallback: send plaintext JSON (not encrypted)
                conn.sendall(response_bytes)
                self.log(f"[Relay] [Last Hop] Sent plaintext response to {addr}: {response_bytes[:60]!r}... (len={len(response_bytes)})")
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
