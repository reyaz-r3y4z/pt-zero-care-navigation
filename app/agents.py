"""Multi-agent workflow with safety gating and explainable decisions."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models import (
    DoctorRecommendation, NavigationResponse, PatientRequest, TraceEvent, TriageResult,
)
from app.rag import KnowledgeBase
from app.repository import Repository
from app.synthetic import DISCLAIMER


RED_FLAGS = {
    "chest pressure": "chest pressure",
    "chest pain": "chest pain",
    "shortness of breath": "breathing difficulty",
    "difficulty breathing": "breathing difficulty",
    "face drooping": "possible stroke sign",
    "slurred speech": "possible stroke sign",
    "severe bleeding": "severe bleeding",
    "unconscious": "loss of consciousness",
}

SPECIALTY_KEYWORDS = {
    "dermatology": ["skin", "rash", "itchy", "eczema", "acne", "mole"],
    "neurology": ["headache", "migraine", "numbness", "tremor", "light sensitivity"],
    "orthopaedics": ["knee", "joint", "bone", "shoulder", "back pain"],
    "physiotherapy": ["mobility", "stiffness", "rehabilitation", "walking"],
    "paediatrics": ["child", "infant", "baby", "development"],
    "endocrinology": ["diabetes", "thirst", "thyroid", "hormone", "urination"],
    "psychology": ["anxiety", "worry", "stress", "panic", "poor sleep"],
}


class IntakeAgent:
    def run(self, patient: PatientRequest) -> tuple[PatientRequest, TraceEvent]:
        return patient, TraceEvent(
            agent="intake_agent", action="accepted",
            explanation="Validated and normalized the structured patient report.",
            data={"symptom_count": len(patient.symptoms), "age": patient.age},
        )


class SafetyAgent:
    def run(self, patient: PatientRequest) -> tuple[TriageResult, TraceEvent]:
        text = " ".join(patient.symptoms)
        warnings = sorted({label for phrase, label in RED_FLAGS.items() if phrase in text})
        is_emergency = bool(warnings)
        triage = TriageResult(
            urgency="emergency" if is_emergency else ("soon" if patient.severity >= 7 else "routine"),
            care_level="emergency" if is_emergency else "outpatient",
            warning_signs=warnings,
            message=(
                "Configured emergency warning signs were detected. Do not wait for an online "
                "recommendation; seek immediate local emergency assistance."
                if is_emergency else
                "No configured emergency warning sign was detected. This is not medical clearance."
            ),
        )
        return triage, TraceEvent(
            agent="safety_agent", action="stop" if is_emergency else "continue",
            explanation="Applied deterministic warning-sign rules before any ranking.",
            data={"warning_signs": warnings},
        )


class SpecialtyAgent:
    def run(self, patient: PatientRequest) -> tuple[list[str], TraceEvent]:
        text = " ".join(patient.symptoms)
        scores = {
            specialty: sum(keyword in text for keyword in keywords)
            for specialty, keywords in SPECIALTY_KEYWORDS.items()
        }
        matches = [name for name, score in sorted(scores.items(), key=lambda x: x[1], reverse=True) if score]
        if patient.age < 16 and "paediatrics" not in matches:
            matches.insert(0, "paediatrics")
        specialties = list(dict.fromkeys([*matches, "general_practice"]))[:3]
        return specialties, TraceEvent(
            agent="specialty_agent", action="route",
            explanation="Mapped reported words to care categories; this is not a diagnosis.",
            data={"specialties": specialties, "scores": {k: v for k, v in scores.items() if v}},
        )


class KnowledgeAgent:
    def __init__(self, knowledge: KnowledgeBase) -> None:
        self.knowledge = knowledge

    def run(self, patient: PatientRequest, specialties: list[str]):
        evidence = self.knowledge.search(" ".join([*patient.symptoms, *specialties]))
        guidance = evidence[0].excerpt if evidence else (
            "The prototype could not find grounded guidance; seek advice from a qualified professional."
        )
        return guidance, evidence, TraceEvent(
            agent="knowledge_agent", action="retrieve",
            explanation="Retrieved relevant passages from the local demonstration knowledge base.",
            data={"evidence_count": len(evidence)},
        )


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    first, second = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = math.sin(delta_lat / 2) ** 2 + math.cos(first) * math.cos(second) * math.sin(delta_lon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


@dataclass
class Candidate:
    provider: dict[str, Any]
    distance: float
    slot: dict[str, Any] | None = None


class ProviderAgent:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def run(self, patient: PatientRequest, specialties: list[str]):
        candidates = []
        for provider in self.repository.providers():
            if provider["specialty"] not in specialties or not provider["accepting_new_patients"]:
                continue
            distance = distance_km(
                patient.location.latitude, patient.location.longitude,
                provider["latitude"], provider["longitude"],
            )
            if patient.preferences.consultation_mode != "telehealth" and distance > patient.preferences.maximum_travel_km:
                continue
            candidates.append(Candidate(provider, distance))
        return candidates, TraceEvent(
            agent="provider_agent", action="search",
            explanation="Filtered fictional providers by specialty, intake status, and travel range.",
            data={"candidate_count": len(candidates)},
        )


class AvailabilityAgent:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def run(self, patient: PatientRequest, candidates: list[Candidate]):
        modes = ({"in_person", "telehealth"} if patient.preferences.consultation_mode == "either"
                 else {patient.preferences.consultation_mode})
        available = []
        for candidate in candidates:
            slots = self.repository.free_slots(candidate.provider["id"], modes)
            if slots:
                candidate.slot = slots[0]
                available.append(candidate)
        return available, TraceEvent(
            agent="availability_agent", action="find_slots",
            explanation="Selected each provider's earliest compatible fictional appointment.",
            data={"available_count": len(available)},
        )


class RankingAgent:
    def run(self, patient: PatientRequest, specialties: list[str], candidates: list[Candidate]):
        if not candidates:
            return [], TraceEvent(
                agent="ranking_agent", action="no_results",
                explanation="No provider satisfied all current filters.", data={},
            )
        earliest = min(datetime.fromisoformat(item.slot["start"]) for item in candidates if item.slot)
        preferred_languages = {item.lower() for item in patient.preferences.languages}
        results = []
        for candidate in candidates:
            provider, slot = candidate.provider, candidate.slot
            if slot is None:
                continue
            specialty_score = 1.0 if provider["specialty"] == specialties[0] else 0.75
            wait_hours = (datetime.fromisoformat(slot["start"]) - earliest).total_seconds() / 3600
            availability_score = max(0.0, 1 - wait_hours / 168)
            distance_score = max(0.0, 1 - candidate.distance / patient.preferences.maximum_travel_km)
            language_match = bool(preferred_languages & {x.lower() for x in provider["languages"]})
            accessibility_match = all(
                need in provider["accessibility"] for need in patient.preferences.accessibility
            )
            score = 100 * (
                0.40 * specialty_score + 0.25 * availability_score + 0.15 * distance_score
                + 0.10 * float(language_match) + 0.10 * float(accessibility_match)
            )
            reasons = [
                f"Matches {provider['specialty'].replace('_', ' ')} care",
                f"Earliest compatible fictional slot: {slot['start']}",
                f"Approximately {candidate.distance:.1f} km from the entered location",
            ]
            if language_match:
                reasons.append("Matches a preferred language")
            if accessibility_match and patient.preferences.accessibility:
                reasons.append("Matches requested accessibility features")
            results.append(DoctorRecommendation(
                doctor_id=provider["id"], slot_id=slot["id"], name=provider["name"],
                professional_title=provider["professional_title"], specialty=provider["specialty"],
                expertise=provider["expertise"], languages=provider["languages"],
                years_experience=provider["years_experience"], hospital_name=provider["hospital_name"],
                doctor_email=provider["email"], hospital_email=provider["hospital_email"],
                hospital_phone=provider["hospital_phone"],
                address=provider["address"], distance_km=round(candidate.distance, 1),
                appointment_start=slot["start"], consultation_mode=slot["mode"],
                suitability_score=round(score, 1), reasons=reasons,
            ))
        results.sort(key=lambda item: (-item.suitability_score, item.appointment_start))
        return results[:5], TraceEvent(
            agent="ranking_agent", action="rank",
            explanation="Applied an explainable weighted score: specialty 40%, availability 25%, distance 15%, language 10%, accessibility 10%.",
            data={"result_count": min(5, len(results))},
        )


class Coordinator:
    def __init__(self, repository: Repository, knowledge: KnowledgeBase) -> None:
        self.intake = IntakeAgent()
        self.safety = SafetyAgent()
        self.specialty = SpecialtyAgent()
        self.knowledge = KnowledgeAgent(knowledge)
        self.provider = ProviderAgent(repository)
        self.availability = AvailabilityAgent(repository)
        self.ranking = RankingAgent()

    def navigate(self, request: PatientRequest) -> NavigationResponse:
        trace = []
        patient, event = self.intake.run(request); trace.append(event)
        triage, event = self.safety.run(patient); trace.append(event)
        if triage.care_level == "emergency":
            guidance, evidence, event = self.knowledge.run(patient, ["emergency"]); trace.append(event)
            return NavigationResponse(
                request_id=str(uuid.uuid4()), disclaimer=DISCLAIMER, triage=triage,
                recommended_specialties=["emergency_medicine"], patient_guidance=guidance,
                evidence=evidence, recommendations=[], trace=trace,
            )
        specialties, event = self.specialty.run(patient); trace.append(event)
        guidance, evidence, event = self.knowledge.run(patient, specialties); trace.append(event)
        candidates, event = self.provider.run(patient, specialties); trace.append(event)
        candidates, event = self.availability.run(patient, candidates); trace.append(event)
        recommendations, event = self.ranking.run(patient, specialties, candidates); trace.append(event)
        return NavigationResponse(
            request_id=str(uuid.uuid4()), disclaimer=DISCLAIMER, triage=triage,
            recommended_specialties=specialties, patient_guidance=guidance,
            evidence=evidence, recommendations=recommendations, trace=trace,
        )
