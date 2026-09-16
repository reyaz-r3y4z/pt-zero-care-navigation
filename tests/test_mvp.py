from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.agents import Coordinator
from app.models import PatientRequest
from app.rag import KnowledgeBase
from app.repository import Repository
from app.synthetic import SyntheticPatientGenerator


ROOT = Path(__file__).parents[1]


def request(symptoms: list[str], severity: int = 5) -> PatientRequest:
    return PatientRequest.model_validate({
        "age": 34, "symptoms": symptoms, "duration_days": 8, "severity": severity,
        "location": {"latitude": -33.8688, "longitude": 151.2093, "suburb": "Sydney Demo"},
        "preferences": {"languages": ["English"], "consultation_mode": "either", "maximum_travel_km": 40},
    })


class MVPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.repository = Repository(Path(self.temporary.name) / "test.db")
        knowledge = KnowledgeBase(ROOT / "app" / "data" / "knowledge.json")
        self.coordinator = Coordinator(self.repository, knowledge)

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def test_skin_case_routes_and_ranks(self) -> None:
        result = self.coordinator.navigate(request(["itchy skin rash", "dry skin"]))
        self.assertEqual(result.recommended_specialties[0], "dermatology")
        self.assertTrue(result.evidence)
        self.assertTrue(result.recommendations)
        self.assertEqual(result.recommendations[0].specialty, "dermatology")
        scores = [item.suitability_score for item in result.recommendations]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_emergency_stops_provider_search(self) -> None:
        result = self.coordinator.navigate(request(["chest pressure", "shortness of breath"], 9))
        self.assertEqual(result.triage.care_level, "emergency")
        self.assertEqual(result.recommendations, [])
        self.assertEqual([event.agent for event in result.trace], ["intake_agent", "safety_agent", "knowledge_agent"])

    def test_unknown_symptom_falls_back_to_general_practice(self) -> None:
        result = self.coordinator.navigate(request(["unmatched demonstration symptom"]))
        self.assertEqual(result.recommended_specialties, ["general_practice"])

    def test_synthetic_generator_is_varied_and_repeatable(self) -> None:
        first = SyntheticPatientGenerator(seed=9).generate(10)
        second = SyntheticPatientGenerator(seed=9).generate(10)
        self.assertEqual(first, second)
        self.assertGreater(len({tuple(case["symptoms"]) for case in first}), 5)
        self.assertTrue(all(case["synthetic"] for case in first))


if __name__ == "__main__":
    unittest.main()
