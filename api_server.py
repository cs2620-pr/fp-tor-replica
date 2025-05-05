# Flask API to connect React frontend with the Tor relay backend
# Exposes /api/send to allow two clients to chat through the relay network
# Returns relay hops, layers, and step-by-step details for visualization

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import json
import os
import base64
import re
from datetime import datetime
import threading
import sqlite3
from flask_socketio import SocketIO, emit
import socket
from signal import SIGTERM
import psutil

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Simulate or connect to your real relay logic here
# For now, we'll mock the relay process for visualization

def onion_layers(message):
    # Simulate 3 layers of encryption (base64 for demo)
    k1 = base64.b64encode((message + ' [K1]').encode()).decode()
    k2 = base64.b64encode((k1 + ' [K2]').encode()).decode()
    k3 = base64.b64encode((k2 + ' [K3]').encode()).decode()
    return [k3, k2, k1]

def relay_steps(sender, recipient, message):
    layers = onion_layers(message)
    hops = [sender, 'Relay 1', 'Relay 2', 'Relay 3', recipient]
    layer_labels = [
        f"Layer 3 (Relay 1): {layers[0]}",
        f"Layer 2 (Relay 2): {layers[1]}",
        f"Layer 1 (Relay 3): {layers[2]}",
        f"Destination: {message}",
        ""
    ]
    steps = [
        "Client wraps the message in 3 layers of encryption (K3, K2, K1).",
        "Relay 1 removes the outermost layer (K3).",
        "Relay 2 removes the next layer (K2).",
        "Relay 3 removes the last layer (K1).",
        "Message delivered to recipient."
    ]
    return {
        'hops': hops,
        'layers': layer_labels,
        'steps': steps
    }

def call_tor_client_backend(sender, recipient, message, relay_count=3):
    import re
    # Ensure relay_count is an int
    try:
        relay_count = int(relay_count)
    except Exception:
        relay_count = 3
    msg_json = json.dumps({"from": sender, "to": recipient, "text": message})
    dest_ip = "127.0.0.1"
    dest_port = 9100
    try:
        proc = subprocess.Popen([
            "python3", "client.py", dest_ip, str(dest_port), msg_json, "--path_length", str(relay_count)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.path.dirname(__file__))
        out, err = proc.communicate(timeout=10)
        logs = out.decode(errors="ignore") + err.decode(errors="ignore")
        print("[API DEBUG] --- FULL CLIENT LOGS START ---")
        print(logs)
        print("[API DEBUG] --- FULL CLIENT LOGS END ---")
        relay_pattern = re.compile(r"Relay ([\d\.]+):(\d+) public key fingerprint")
        full_hops = []
        for match in relay_pattern.finditer(logs):
            ip, port = match.groups()
            full_hops.append(f"{ip}:{port}")
        print(f"[API DEBUG] Parsed relay path: {full_hops}")
        if not full_hops:
            print("[API WARNING] No relays parsed from logs, using fallback placeholder relays.")
            try:
                from cds import get_all_relays
                relays = get_all_relays()
                full_hops = [f"{r['ip']}:{r['port']}" for r in relays][:relay_count]
            except Exception as e:
                print(f"[API ERROR] Could not get relays from CDS: {e}")
                full_hops = ["Relay 1", "Relay 2", "Relay 3"][:relay_count]
        layers = []
        steps = []
        for line in logs.splitlines():
            if "Layer" in line and "relay" in line:
                layers.append(line.strip())
            if "decrypted" in line or "decoded" in line:
                steps.append(line.strip())
        if not layers:
            layers = ["Layer 3", "Layer 2", "Layer 1", "Destination", ""]
        if not steps:
            steps = ["Message sent through relays."]
        return {
            'hops': full_hops,
            'layers': layers,
            'steps': steps,
            'logs': logs
        }
    except Exception as e:
        print(f"[API ERROR] Exception in call_tor_client_backend: {e}")
        return {
            'hops': [f"Relay {i+1}" for i in range(relay_count)],
            'layers': ["Layer 3", "Layer 2", "Layer 1", "Destination", ""],
            'steps': [f"Error: {str(e)}"],
            'logs': str(e)
        }

DB_PATH = os.path.join(os.path.dirname(__file__), 'chat.db')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            avatar TEXT,
            online INTEGER,
            last_seen TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            recipient TEXT,
            text TEXT,
            timestamp TEXT,
            delivered INTEGER DEFAULT 0,
            read INTEGER DEFAULT 0,
            relay_path TEXT
        )''')
        conn.commit()
init_db()

# --- DB helper functions ---
def get_user(username):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT username, password, avatar, online, last_seen FROM users WHERE username=?', (username,))
        row = c.fetchone()
        if row:
            return dict(zip(['username', 'password', 'avatar', 'online', 'last_seen'], row))
        return None

def set_user_online(username, online):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET online=?, last_seen=datetime("now") WHERE username=?', (int(online), username))
        conn.commit()

def add_user(username, password, avatar=None):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password, avatar, online, last_seen) VALUES (?, ?, ?, 1, datetime("now"))', (username, password, avatar or ''))
        conn.commit()

def get_all_users():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT username, avatar, online FROM users')
        return [{'username': u, 'avatar': a, 'online': bool(o)} for u, a, o in c.fetchall()]

def add_message(sender, recipient, text, relay_path=None):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO messages (sender, recipient, text, timestamp, relay_path) VALUES (?, ?, ?, datetime("now"), ?)', (sender, recipient, text, json.dumps(relay_path) if relay_path else None))
        conn.commit()

def get_conversations(username):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT sender, recipient, text, timestamp, delivered, read FROM messages WHERE sender=? OR recipient=? ORDER BY timestamp', (username, username))
        return [dict(zip(['from', 'to', 'text', 'timestamp', 'delivered', 'read'], row)) for row in c.fetchall()]

def mark_messages_delivered(sender, recipient):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('UPDATE messages SET delivered=1 WHERE sender=? AND recipient=?', (sender, recipient))
        conn.commit()

def mark_messages_read(sender, recipient):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('UPDATE messages SET read=1 WHERE sender=? AND recipient=?', (sender, recipient))
        conn.commit()

# --- Relay and Server Management Endpoints ---
def find_relay_process_by_port(port):
    """Find PID of relay.py process with the given port as argument."""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmd = proc.info['cmdline']
            if cmd and 'relay.py' in cmd and str(port) in cmd:
                return proc.pid
        except Exception:
            continue
    return None

def find_destination_server_process():
    """Find PID of dest_server.py process."""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmd = proc.info['cmdline']
            if cmd and 'dest_server.py' in cmd:
                return proc.pid
        except Exception:
            continue
    return None

def find_cds_process():
    """Find PID of cds.py process."""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmd = proc.info['cmdline']
            if cmd and 'cds.py' in cmd:
                return proc.pid
        except Exception:
            continue
    return None

@app.route('/api/relay/start', methods=['POST'])
def start_relay():
    data = request.json
    relay_id = data.get('relay_id')  # e.g. port or unique identifier
    port = data.get('port')
    if not port:
        return jsonify({'success': False, 'error': 'Missing relay port'}), 400
    # Check if relay already running
    if find_relay_process_by_port(port):
        return jsonify({'success': False, 'error': f'Relay already running on port {port}'}), 400
    try:
        proc = subprocess.Popen([
            'python3', 'relay.py', str(relay_id), str(port)
        ], cwd=os.path.dirname(__file__))
        return jsonify({'success': True, 'pid': proc.pid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/relay/stop', methods=['POST'])
def stop_relay():
    data = request.json
    port = data.get('port')
    pid = find_relay_process_by_port(port)
    if not pid:
        return jsonify({'success': False, 'error': 'Relay not running or unknown port'}), 404
    try:
        os.kill(pid, SIGTERM)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/destination/start', methods=['POST'])
def start_destination():
    if find_destination_server_process():
        return jsonify({'success': False, 'error': 'Destination server already running'}), 400
    try:
        proc = subprocess.Popen([
            'python3', 'dest_server.py'
        ], cwd=os.path.dirname(__file__))
        return jsonify({'success': True, 'pid': proc.pid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/destination/stop', methods=['POST'])
def stop_destination():
    pid = find_destination_server_process()
    if not pid:
        return jsonify({'success': False, 'error': 'Destination server not running'}), 404
    try:
        os.kill(pid, SIGTERM)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cds/start', methods=['POST'])
def start_cds():
    if find_cds_process():
        return jsonify({'success': False, 'error': 'CDS already running'}), 400
    try:
        proc = subprocess.Popen([
            'python3', 'cds.py'
        ], cwd=os.path.dirname(__file__))
        return jsonify({'success': True, 'pid': proc.pid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cds/stop', methods=['POST'])
def stop_cds():
    pid = find_cds_process()
    if not pid:
        return jsonify({'success': False, 'error': 'CDS not running'}), 404
    try:
        os.kill(pid, SIGTERM)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Optional: API server stop (will terminate itself)
@app.route('/api/api_server/stop', methods=['POST'])
def stop_api_server():
    os._exit(0)
    return jsonify({'success': True})

# --- Replace in-memory endpoints with DB-backed versions ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    avatar = data.get('avatar')
    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing username or password'}), 400
    if get_user(username):
        return jsonify({'success': False, 'error': 'Username already exists'}), 409
    add_user(username, password, avatar)
    return jsonify({'success': True, 'user': {'username': username, 'avatar': avatar}})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = get_user(username)
    if not user or user['password'] != password:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    set_user_online(username, True)
    return jsonify({'success': True, 'user': {'username': username, 'avatar': user['avatar']}})

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json
    username = data.get('username')
    set_user_online(username, False)
    return jsonify({'success': True})

@app.route('/api/users', methods=['GET'])
def get_users():
    users = get_all_users()
    return jsonify(users)

@app.route('/api/messages', methods=['GET', 'POST'])
def chat_messages():
    if request.method == 'GET':
        username = request.args.get('username')
        if not username:
            return jsonify({'error': 'Missing username', 'conversations': [], 'unread': {}})
        convs = get_conversations(username)
        unread = {}
        for m in convs:
            if m['to'] == username and not m['read']:
                unread[m['from']] = unread.get(m['from'], 0) + 1
        return jsonify({'conversations': convs, 'unread': unread})
    else:
        data = request.json
        from_user = data.get('from')
        to_user = data.get('to')
        text = data.get('text')
        if not from_user or not to_user or not text:
            return jsonify({'success': False, 'error': 'Missing fields'})
        add_message(from_user, to_user, text)
        mark_messages_delivered(from_user, to_user)
        socketio.emit('new_message', {
            'from': from_user,
            'to': to_user,
            'text': text
        })
        return jsonify({'success': True})

@app.route('/api/messages/read', methods=['POST'])
def mark_read():
    data = request.json
    from_user = data.get('from')
    to_user = data.get('to')
    mark_messages_read(from_user, to_user)
    socketio.emit('read_message', {'from': from_user, 'to': to_user})
    return jsonify({'success': True})

# --- SocketIO events for user status (optional for monitor) ---
@socketio.on('user_online')
def user_online(data):
    username = data.get('username')
    set_user_online(username, True)
    emit('user_status', {'username': username, 'online': True})

@socketio.on('user_offline')
def user_offline(data):
    username = data.get('username')
    set_user_online(username, False)
    emit('user_status', {'username': username, 'online': False})

# --- Monitor endpoint (still simulated relays, will update next) ---
@app.route('/api/monitor', methods=['GET'])
def monitor():
    import random
    relays = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            s.connect(("127.0.0.1", 9001))
            s.sendall(b'LIST_RELAYS')
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b''.join(chunks)
            relays = json.loads(data.decode()) if data else []
    except Exception as e:
        relays = []
    # Only keep relays that have a running process
    filtered_relays = []
    for relay in relays:
        port = relay.get('port')
        if port and find_relay_process_by_port(port):
            relay['id'] = relay.get('id') or relay.get('port') or f"{relay.get('ip')}:{relay.get('port')}"
            relay['status'] = 'online'
            filtered_relays.append(relay)
    # Destination server status
    destination_running = bool(find_destination_server_process())
    cds_running = bool(find_cds_process())
    relayCount_arg = request.args.get('relayCount', None)
    if relayCount_arg is not None:
        try:
            relayCount = int(relayCount_arg)
            shown_relays = filtered_relays[:relayCount]
        except Exception:
            shown_relays = filtered_relays
    else:
        shown_relays = filtered_relays
    users = get_all_users()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT sender, recipient, text, timestamp, relay_path FROM messages ORDER BY timestamp DESC LIMIT 5')
        last_msgs = c.fetchall()
    paths = []
    for m in last_msgs:
        relay_path = None
        try:
            relay_path = json.loads(m[4]) if m[4] else None
        except Exception:
            relay_path = None
        # Only use relay_path if it is a valid, non-empty list of relay ip:port strings
        if relay_path and isinstance(relay_path, list) and any(isinstance(x, str) and ':' in x for x in relay_path):
            path = relay_path
        else:
            # fallback: show nothing, or optionally the relays from shown_relays
            path = []
        paths.append({'from': m[0], 'to': m[1], 'path': path, 'time': m[3]})
    return jsonify({
        'relays': shown_relays,
        'clients': users,
        'messages': paths,
        'destination_server_running': destination_running,
        'cds_running': cds_running
    })

@app.route('/api/send', methods=['POST'])
def send():
    data = request.json
    # Accept both old and new payloads for compatibility
    sender = data.get('sender') or data.get('from')
    recipient = data.get('recipient') or data.get('to')
    message = data.get('message') or data.get('text')
    relay_count = data.get('relay_count', 3)
    if not sender or not recipient or not message:
        return jsonify({'success': False, 'error': 'Missing sender, recipient, or message'})
    try:
        relay_data = call_tor_client_backend(sender, recipient, message, relay_count)
        relay_path = relay_data.get('hops') if relay_data else None
        # Always return the relay path as a list of ip:port strings in the API response
        add_message(sender, recipient, message, relay_path)
        mark_messages_delivered(sender, recipient)
        socketio.emit('new_message', {
            'from': sender,
            'to': recipient,
            'text': message,
            'relay_path': relay_path
        })
        return jsonify({'success': True, 'relay_path': relay_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5050)
