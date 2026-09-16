from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from app.main import create_app


PATIENT = {
    "age": 34,
    "symptoms": ["itchy skin rash", "dry skin"],
    "duration_days": 8,
    "severity": 5,
    "location": {"latitude": -33.8688, "longitude": 151.2093, "suburb": "Sydney Demo"},
    "preferences": {
        "languages": ["English"], "consultation_mode": "either",
        "maximum_travel_km": 40, "accessibility": [],
    },
}


class APITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        app = create_app(Path(self.temporary.name) / "api.db")
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary.cleanup()

    def register(self):
        return self.client.post("/api/auth/register", json={
            "email": "learner@example.com",
            "display_name": "MVP Learner",
            "password": "A-strong-demo-password-2026",
        })

    def csrf(self) -> str:
        return self.client.cookies.get("pt_zero_csrf")

    def test_health_and_home_are_public(self) -> None:
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["auth"], "enabled")

    def test_protected_route_requires_authentication(self) -> None:
        self.assertEqual(self.client.get("/api/providers").status_code, 401)
        self.assertEqual(self.client.post("/api/navigate", json=PATIENT).status_code, 401)

    def test_registration_session_and_logout(self) -> None:
        registered = self.register()
        self.assertEqual(registered.status_code, 201)
        self.assertTrue(self.client.cookies.get("pt_zero_session"))
        self.assertTrue(self.csrf())
        self.assertEqual(self.client.get("/api/auth/me").json()["email"], "learner@example.com")

        no_csrf = self.client.post("/api/navigate", json=PATIENT)
        self.assertEqual(no_csrf.status_code, 403)
        result = self.client.post(
            "/api/navigate", json=PATIENT, headers={"X-CSRF-Token": self.csrf()}
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["recommended_specialties"][0], "dermatology")

        logout = self.client.post("/api/auth/logout", headers={"X-CSRF-Token": self.csrf()})
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_duplicate_registration_and_login(self) -> None:
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 409)
        self.client.cookies.clear()
        wrong = self.client.post("/api/auth/login", json={
            "email": "learner@example.com", "password": "wrong-password"
        })
        self.assertEqual(wrong.status_code, 401)
        correct = self.client.post("/api/auth/login", json={
            "email": "LEARNER@example.com", "password": "A-strong-demo-password-2026"
        })
        self.assertEqual(correct.status_code, 200)


if __name__ == "__main__":
    unittest.main()
