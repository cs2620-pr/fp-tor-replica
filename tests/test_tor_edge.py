import unittest
import requests
import sqlite3
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../relays'))
from crypto_utils import *
sys.path.pop(0)

API_URL = "http://127.0.0.1:5050"
DB_PATH = "chat.db"

class TorEdgeCaseTestCase(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users;")
            c.execute("DELETE FROM messages;")
            conn.commit()

    def get_available_relays(self):
        try:
            resp = requests.get(f"{API_URL}/api/monitor")
            data = resp.json()
            return len(data.get("relays", []))
        except Exception:
            return 0

    def test_message_to_nonexistent_user(self):
        # Register sender only
        requests.post(f"{API_URL}/api/register", json={"username": "sender", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "sender", "password": "pw"})
        # Attempt to send to nonexistent recipient
        payload = {"sender": "sender", "recipient": "ghost", "message": "hi ghost", "relay_count": 2}
        resp = requests.post(f"{API_URL}/api/send", json=payload)
        # Should fail gracefully
        self.assertIn(resp.status_code, [200, 400, 500])
        data = resp.json()
        self.assertIn("success", data)
        if not data["success"]:
            self.assertIn("error", data)

    def test_multiple_concurrent_messages(self):
        # Register users
        for uname in ["alice", "bob", "carol"]:
            requests.post(f"{API_URL}/api/register", json={"username": uname, "password": "pw"})
            requests.post(f"{API_URL}/api/login", json={"username": uname, "password": "pw"})
        # Send multiple messages in quick succession
        results = []
        for i in range(5):
            payload = {"sender": "alice", "recipient": "bob", "message": f"msg {i}", "relay_count": 2}
            resp = requests.post(f"{API_URL}/api/send", json=payload)
            results.append(resp.status_code)
        # All should return success (200)
        self.assertTrue(all(code == 200 for code in results))

    # The following tests have been removed as requested:
    # - test_monitor_message_path_integrity
    # - test_relay_path_length_variation

if __name__ == "__main__":
    unittest.main()
