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

    def test_seeded_operations_directory(self) -> None:
        self.assertEqual(self.register().status_code, 201)
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["hospitals"], 50)
        self.assertEqual(dashboard["doctors"], 50)
        self.assertEqual(dashboard["patients"], 20)
        self.assertGreaterEqual(dashboard["medical_fields"], 15)
        self.assertEqual(len(self.client.get("/api/providers").json()), 50)
        self.assertEqual(len(self.client.get("/api/hospitals").json()), 50)
        self.assertEqual(len(self.client.get("/api/patients").json()), 20)

    def test_nearby_fields_booking_and_activity_log(self) -> None:
        self.assertEqual(self.register().status_code, 201)
        nearby = self.client.get("/api/medical-fields/nearby?patient_id=PAT-001")
        self.assertEqual(nearby.status_code, 200)
        self.assertEqual(len(nearby.json()), 10)
        self.assertTrue(nearby.json()[0]["medical_fields"])

        patient = {**PATIENT, "patient_id": "PAT-001"}
        navigation = self.client.post(
            "/api/navigate", json=patient, headers={"X-CSRF-Token": self.csrf()}
        )
        self.assertEqual(navigation.status_code, 200)
        recommendation = navigation.json()["recommendations"][0]
        booked = self.client.post("/api/appointments", headers={"X-CSRF-Token": self.csrf()}, json={
            "patient_id": "PAT-001", "slot_id": recommendation["slot_id"],
            "reason": "Synthetic test booking",
        })
        self.assertEqual(booked.status_code, 201)
        self.assertEqual(booked.json()["status"], "confirmed")
        self.assertEqual(booked.json()["integration_status"], "synthetic_hospital_confirmed")
        self.assertEqual(len(self.client.get("/api/appointments").json()), 1)
        event_types = {item["event_type"] for item in self.client.get("/api/activity").json()}
        self.assertIn("navigation_completed", event_types)
        self.assertIn("appointment_booked", event_types)

    def test_on_call_rooms_are_explicitly_synthetic(self) -> None:
        self.assertEqual(self.register().status_code, 201)
        doctors = self.client.get("/api/on-call").json()
        self.assertTrue(doctors)
        self.assertTrue(all(item["synthetic"] for item in doctors))
        self.assertTrue(all(item["video_room_url"].startswith("/video-room.html") for item in doctors))
        page = self.client.get("/video-room.html")
        self.assertIn("NO CLINICIAN IS CONNECTED", page.text)


if __name__ == "__main__":
    unittest.main()
