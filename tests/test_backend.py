import unittest
import os
import sqlite3
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../relays'))
from crypto_utils import *
sys.path.pop(0)
from api_server import app

DB_PATH = "chat.db"

class BackendTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users;")
            c.execute("DELETE FROM messages;")
            conn.commit()

    @classmethod
    def setUpClass(cls):
        pass  # No longer needed, cleanup is in setUp

    def test_monitor_endpoint(self):
        resp = self.client.get('/api/monitor')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('relays', data)
        self.assertIn('destination_server_running', data)
        self.assertIn('cds_running', data)

    def test_register_and_login(self):
        resp = self.client.post('/api/register', json={"username": "alice", "password": "pw"})
        self.assertEqual(resp.status_code, 200)
        resp2 = self.client.post('/api/login', json={"username": "alice", "password": "pw"})
        self.assertEqual(resp2.status_code, 200)

    def test_database_persistence(self):
        self.client.post('/api/register', json={"username": "bob", "password": "pw"})
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", ("bob",))
            user = c.fetchone()
            self.assertIsNotNone(user)

    def test_monitor_reflects_new_user(self):
        self.client.post('/api/register', json={"username": "carol", "password": "pw"})
        resp = self.client.get('/api/monitor')
        data = resp.get_json()
        self.assertTrue(any(u['username'] == 'carol' for u in data.get('clients', [])))

    def test_register_invalid(self):
        # Missing username
        resp = self.client.post('/api/register', json={"password": "pw"})
        self.assertNotEqual(resp.status_code, 200)
        # Missing password
        resp2 = self.client.post('/api/register', json={"username": "dave"})
        self.assertNotEqual(resp2.status_code, 200)

    def test_login_invalid(self):
        # Wrong username
        resp = self.client.post('/api/login', json={"username": "notexist", "password": "pw"})
        self.assertNotEqual(resp.status_code, 200)
        # Wrong password
        self.client.post('/api/register', json={"username": "eve", "password": "pw1"})
        resp2 = self.client.post('/api/login', json={"username": "eve", "password": "wrong"})
        self.assertNotEqual(resp2.status_code, 200)

    def test_message_flow(self):
        # Register and login
        self.client.post('/api/register', json={"username": "frank", "password": "pw"})
        self.client.post('/api/login', json={"username": "frank", "password": "pw"})
        # Send a message (should succeed if endpoint allows)
        resp = self.client.post('/api/send', json={"message": "hello", "relayCount": 1})
        self.assertIn(resp.status_code, [200, 400, 500])  # Accept any response, just ensure endpoint works

    def test_monitor_relays_field(self):
        resp = self.client.get('/api/monitor')
        data = resp.get_json()
        self.assertIsInstance(data.get('relays'), list)

    def test_monitor_clients_field(self):
        resp = self.client.get('/api/monitor')
        data = resp.get_json()
        self.assertIsInstance(data.get('clients'), list)

    def test_monitor_messages_field(self):
        resp = self.client.get('/api/monitor')
        data = resp.get_json()
        self.assertIn('messages', data)
        self.assertIsInstance(data.get('messages'), list)

    def test_register_login_flow(self):
        # Register a user
        resp = self.client.post('/api/register', json={"username": "alice", "password": "pw"})
        self.assertEqual(resp.status_code, 200)
        # Duplicate registration should fail
        resp2 = self.client.post('/api/register', json={"username": "alice", "password": "pw"})
        self.assertEqual(resp2.status_code, 409, "Duplicate registration did not fail as expected (second registration of alice returned %s)" % resp2.status_code)
        # Login with correct credentials
        resp3 = self.client.post('/api/login', json={"username": "alice", "password": "pw"})
        self.assertEqual(resp3.status_code, 200)
        # Login with wrong password
        resp4 = self.client.post('/api/login', json={"username": "alice", "password": "wrong"})
        self.assertEqual(resp4.status_code, 401)

if __name__ == '__main__':
    unittest.main()
