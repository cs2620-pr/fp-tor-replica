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

class TorExtraIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        # Clean DB before each test
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users;")
            c.execute("DELETE FROM messages;")
            conn.commit()

    def test_message_delivery_with_relay_failure(self):
        # Register users
        requests.post(f"{API_URL}/api/register", json={"username": "alice", "password": "pw"})
        requests.post(f"{API_URL}/api/register", json={"username": "bob", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "alice", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "bob", "password": "pw"})
        # Simulate relay failure by requesting excessive relay count
        payload = {"sender": "alice", "recipient": "bob", "message": "test failover", "relay_count": 100}
        resp = requests.post(f"{API_URL}/api/send", json=payload)
        self.assertIn(resp.status_code, [200, 400, 500])
        data = resp.json()
        # Should fail gracefully with error or fallback
        self.assertIn("success", data)
        if not data["success"]:
            self.assertIn("error", data)
        else:
            self.assertIn("relay_path", data)

    def test_monitor_shows_live_relay_and_client_counts(self):
        # Register and login users
        requests.post(f"{API_URL}/api/register", json={"username": "erin", "password": "pw"})
        requests.post(f"{API_URL}/api/register", json={"username": "frank", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "erin", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "frank", "password": "pw"})
        # Check monitor
        resp = requests.get(f"{API_URL}/api/monitor")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("relays", data)
        self.assertIn("clients", data)
        self.assertGreaterEqual(len(data["clients"]), 2)
        self.assertIsInstance(data["relays"], list)

    def test_frontend_backend_message_flow(self):
        # Simulate what the frontend would do: register, login, send message, fetch messages
        u1, u2 = "frontendA", "frontendB"
        requests.post(f"{API_URL}/api/register", json={"username": u1, "password": "pw"})
        requests.post(f"{API_URL}/api/register", json={"username": u2, "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": u1, "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": u2, "password": "pw"})
        payload = {"sender": u1, "recipient": u2, "message": "hello from FE", "relay_count": 2}
        resp = requests.post(f"{API_URL}/api/send", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        # Now fetch messages for u2 (simulate frontend polling)
        resp2 = requests.get(f"{API_URL}/api/monitor")
        self.assertEqual(resp2.status_code, 200)
        messages = resp2.json().get("messages", [])
        found = any(m.get("from") == u1 and m.get("to") == u2 for m in messages)
        self.assertTrue(found)

    def test_message_encryption_layers(self):
        # Register and login
        requests.post(f"{API_URL}/api/register", json={"username": "encuser1", "password": "pw"})
        requests.post(f"{API_URL}/api/register", json={"username": "encuser2", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "encuser1", "password": "pw"})
        requests.post(f"{API_URL}/api/login", json={"username": "encuser2", "password": "pw"})
        # Send message with 3 relays
        payload = {"sender": "encuser1", "recipient": "encuser2", "message": "layer test", "relay_count": 3}
        resp = requests.post(f"{API_URL}/api/send", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        # Check that relay_path has 3 hops (3 encryption layers)
        self.assertEqual(len(data["relay_path"]), 3)

if __name__ == "__main__":
    unittest.main()
