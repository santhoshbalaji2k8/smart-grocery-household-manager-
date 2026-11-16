import os
import tempfile
import unittest
from fastapi.testclient import TestClient

class OwnerAuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ['DATABASE_PATH'] = os.path.join(cls.tmp.name, 'web-test.db')
        os.environ['AUTH_SECRET'] = 'test-only-secret-value-that-is-long-enough'
        os.environ['OWNER_SETUP_KEY'] = 'test-owner-setup-key-value'
        from web_backend.main import app
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.tmp.cleanup()

    def test_public_health_and_setup_status(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        self.assertIn('setup_required', self.client.get('/api/auth/status').json())

    def test_api_requires_bearer_token(self):
        self.assertEqual(self.client.get('/api/products').status_code, 401)

    def test_first_owner_can_register_and_login(self):
        r = self.client.post('/api/auth/register', json={
            'email': 'owner@example.com', 'password': 'VeryStrongPassword123', 'setup_key': 'test-owner-setup-key-value'
        })
        self.assertEqual(r.status_code, 200, r.text)
        token = r.json()['access_token']
        self.assertEqual(self.client.get('/api/products', headers={
            'Authorization': 'Bearer ' + token
        }).status_code, 200)
        export = self.client.get('/api/export/products/csv', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(export.status_code, 200)
        self.assertIn('text/csv', export.headers.get('content-type', ''))
        self.assertEqual(self.client.post('/api/auth/login', json={
            'email': 'owner@example.com', 'password': 'VeryStrongPassword123', 'setup_key': 'test-owner-setup-key-value'
        }).status_code, 200)

    def test_public_second_registration_is_disabled(self):
        r = self.client.post('/api/auth/register', json={
            'email': 'second@example.com', 'password': 'AnotherStrongPassword123', 'setup_key': 'test-owner-setup-key-value'
        })
        self.assertEqual(r.status_code, 403)

    def test_invalid_credentials_are_rejected(self):
        r = self.client.post('/api/auth/login', json={
            'email': 'owner@example.com', 'password': 'wrong-password-123'
        })
        self.assertEqual(r.status_code, 401)

if __name__ == '__main__':
    unittest.main()
