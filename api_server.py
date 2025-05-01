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

app = Flask(__name__)
CORS(app)

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

def call_tor_client_backend(sender, recipient, message):
    # Compose message as JSON string (for compatibility with client.py)
    msg_json = json.dumps({"from": sender, "to": recipient, "text": message})
    # These should match your dest_server.py listening config
    dest_ip = "127.0.0.1"
    dest_port = 9100
    # Use subprocess to call client.py and capture output
    try:
        proc = subprocess.Popen([
            "python3", "client.py", dest_ip, str(dest_port), msg_json
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.path.dirname(__file__))
        out, err = proc.communicate(timeout=10)
        # Parse logs for relay hops, layers, steps if possible
        # (You may want to improve this to parse actual output)
        logs = out.decode(errors="ignore") + err.decode(errors="ignore")
        # Try to extract relay order, layers, and final message
        hops = []
        layers = []
        steps = []
        for line in logs.splitlines():
            if "Layer" in line and "relay" in line:
                layers.append(line.strip())
            if "relay order" in line or "relay:" in line:
                hops.append(line.strip())
            if "decrypted" in line or "decoded" in line:
                steps.append(line.strip())
        if not hops:
            hops = [sender, 'Relay 1', 'Relay 2', 'Relay 3', recipient]
        if not layers:
            layers = ["Layer 3", "Layer 2", "Layer 1", "Destination", ""]
        if not steps:
            steps = ["Message sent through relays."]
        return {
            'hops': hops,
            'layers': layers,
            'steps': steps,
            'logs': logs
        }
    except Exception as e:
        return {
            'hops': [sender, 'Relay 1', 'Relay 2', 'Relay 3', recipient],
            'layers': ["Layer 3", "Layer 2", "Layer 1", "Destination", ""],
            'steps': [f"Error: {str(e)}"],
            'logs': str(e)
        }

@app.route('/api/send', methods=['POST'])
def send():
    data = request.json
    try:
        relay_data = call_tor_client_backend(data['from'], data['to'], data['text'])
        # Extract more structured relay info if possible
        relay_info = []
        timing = []
        crypto = []
        debug_inputs = []
        if 'logs' in relay_data and isinstance(relay_data['logs'], str):
            import re
            relay_pattern = re.compile(r'Relay (\d+): IP=([\d.]+), Fingerprint=([a-fA-F0-9]+), Key=([\w+/=]+), Crypto=([\w-]+), Time=([\d.]+)ms, Input=(.+)')
            for match in relay_pattern.finditer(relay_data['logs']):
                relay_info.append({
                    'relay_num': int(match.group(1)),
                    'ip': match.group(2),
                    'fingerprint': match.group(3),
                    'key': match.group(4)
                })
                crypto.append(match.group(5))
                timing.append(float(match.group(6)))
                debug_inputs.append(match.group(7))
        if relay_info:
            relay_data['relay_info'] = relay_info
        if crypto:
            relay_data['crypto'] = crypto
        if timing:
            relay_data['timing'] = timing
        if debug_inputs:
            relay_data['debug_inputs'] = debug_inputs
        return jsonify(relay_data)
    except Exception as e:
        app.logger.error(f"Error in /api/send: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5050, debug=True)
