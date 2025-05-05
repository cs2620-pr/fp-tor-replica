import unittest
import subprocess
import time
import os
import json
import sqlite3
import sys

API_URL = "http://127.0.0.1:5050"
DB_PATH = "chat.db"

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../relays'))
from crypto_utils import *
sys.path.pop(0)

class TorIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Clean up users/messages in DB
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users;")
            c.execute("DELETE FROM messages;")
            conn.commit()

    def test_send_message_through_multiple_relays(self):
        # Register users
        r1 = requests.post(f"{API_URL}/api/register", json={"username": "alice", "password": "pw"})
        r2 = requests.post(f"{API_URL}/api/register", json={"username": "bob", "password": "pw"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # Login
        l1 = requests.post(f"{API_URL}/api/login", json={"username": "alice", "password": "pw"})
        l2 = requests.post(f"{API_URL}/api/login", json={"username": "bob", "password": "pw"})
        self.assertEqual(l1.status_code, 200)
        self.assertEqual(l2.status_code, 200)
        # Send message with 3 relays
        payload = {"sender": "alice", "recipient": "bob", "message": "hi via tor!", "relay_count": 3}
        resp = requests.post(f"{API_URL}/api/send", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("relay_path", data)
        self.assertEqual(len(data["relay_path"]), 3)

    def test_send_message_with_invalid_relay_count(self):
        # Register users
        requests.post(f"{API_URL}/api/register", json={"username": "carol", "password": "pw"})
        requests.post(f"{API_URL}/api/register", json={"username": "dave", "password": "pw"})
        # Send message with invalid relay_count
        payload = {"sender": "carol", "recipient": "dave", "message": "bad relay count", "relay_count": "notanumber"}
        resp = requests.post(f"{API_URL}/api/send", json=payload)
        # Should not crash, should still return a valid response
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("relay_path", data)
        # Should default to 3 relays
        self.assertEqual(len(data["relay_path"]), 3)

    def test_monitor_reflects_message_path(self):
        # Register and send
        requests.post(f"{API_URL}/api/register", json={"username": "erin", "password": "pw"})
        requests.post(f"{API_URL}/api/register", json={"username": "frank", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "erin", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "frank", "password": "pw"})
        payload = {"sender": "erin", "recipient": "frank", "message": "hop trace", "relay_count": 2}
        requests.post(f"{API_URL}/api/send", json=payload)
        # Check monitor
        resp = requests.get(f"{API_URL}/api/monitor")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        found = any(m.get("from") == "erin" and m.get("to") == "frank" and isinstance(m.get("path"), list) for m in data.get("messages", []))
        self.assertTrue(found)

    def test_cds_and_destination_status(self):
        resp = requests.get(f"{API_URL}/api/monitor")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cds_running", data)
        self.assertIn("destination_server_running", data)
        self.assertIsInstance(data["cds_running"], bool)
        self.assertIsInstance(data["destination_server_running"], bool)

if __name__ == "__main__":
    unittest.main()
