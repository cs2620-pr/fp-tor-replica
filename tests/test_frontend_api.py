import unittest
import requests
import sqlite3

API_URL = "http://127.0.0.1:5050"
DB_PATH = "chat.db"

class FrontendBackendIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users;")
            c.execute("DELETE FROM messages;")
            conn.commit()

    def test_full_user_flow(self):
        # Register user as frontend
        resp = requests.post(f"{API_URL}/api/register", json={"username": "feuser", "password": "pw"})
        self.assertEqual(resp.status_code, 200)
        # Login user
        resp2 = requests.post(f"{API_URL}/api/login", json={"username": "feuser", "password": "pw"})
        self.assertEqual(resp2.status_code, 200)
        # Send message to self (simulate echo)
        payload = {"sender": "feuser", "recipient": "feuser", "message": "echo test", "relay_count": 1}
        resp3 = requests.post(f"{API_URL}/api/send", json=payload)
        self.assertEqual(resp3.status_code, 200)
        data = resp3.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(len(data["relay_path"]), 1)
        # Check monitor for message
        resp4 = requests.get(f"{API_URL}/api/monitor")
        self.assertEqual(resp4.status_code, 200)
        messages = resp4.json().get("messages", [])
        found = any(m.get("from") == "feuser" and m.get("to") == "feuser" for m in messages)
        self.assertTrue(found)

    def test_monitor_lists_all_clients_and_relays(self):
        # Register and login multiple users
        for uname in ["u1", "u2", "u3"]:
            requests.post(f"{API_URL}/api/register", json={"username": uname, "password": "pw"})
            requests.post(f"{API_URL}/api/login", json={"username": uname, "password": "pw"})
        resp = requests.get(f"{API_URL}/api/monitor")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data.get("clients", [])), 3)
        self.assertIn("relays", data)
        self.assertIsInstance(data["relays"], list)

if __name__ == "__main__":
    unittest.main()
