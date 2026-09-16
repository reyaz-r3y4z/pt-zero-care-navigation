"""Repeatable fictional records for development and evaluation."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Any


DISCLAIMER = (
    "Educational prototype using fictional data. It does not diagnose, provide "
    "medical advice, verify practitioners, or make real appointments."
)

HOSPITALS = [
    {
        "id": "HOSP-001", "name": "Demo Harbour Health Centre",
        "address": "100 Example Street, Sydney Demo NSW",
        "latitude": -33.8688, "longitude": 151.2093,
        "accessibility": ["wheelchair_access", "accessible_parking"],
    },
    {
        "id": "HOSP-002", "name": "Demo Western Community Hospital",
        "address": "200 Sample Road, Parramatta Demo NSW",
        "latitude": -33.8150, "longitude": 151.0011,
        "accessibility": ["wheelchair_access", "interpreter_service"],
    },
    {
        "id": "HOSP-003", "name": "Demo North Specialist Centre",
        "address": "300 Prototype Avenue, Chatswood Demo NSW",
        "latitude": -33.7969, "longitude": 151.1833,
        "accessibility": ["wheelchair_access"],
    },
]

SPECIALTIES = {
    "general_practice": ("General Practitioner", ["general assessment", "preventive care"]),
    "dermatology": ("Dermatologist", ["skin rash", "eczema", "acne"]),
    "neurology": ("Neurologist", ["headache", "migraine", "neurological symptoms"]),
    "orthopaedics": ("Orthopaedic Specialist", ["joint pain", "knee pain", "mobility"]),
    "physiotherapy": ("Physiotherapist", ["rehabilitation", "mobility", "joint pain"]),
    "paediatrics": ("Paediatrician", ["child health", "fever", "development"]),
    "endocrinology": ("Endocrinologist", ["diabetes", "thyroid", "hormonal health"]),
    "psychology": ("Psychologist", ["anxiety", "stress", "sleep difficulties"]),
}

LANGUAGES = ["Arabic", "Hindi", "Mandarin", "Urdu", "Vietnamese"]

PATIENT_SCENARIOS = [
    {
        "id": "CASE-SKIN", "label": "Persistent skin irritation",
        "age": 34, "symptoms": ["itchy skin rash", "dry skin", "red patches"],
        "duration_days": 9, "severity": 5, "expected_specialty": "dermatology",
    },
    {
        "id": "CASE-HEADACHE", "label": "Recurring headaches",
        "age": 41, "symptoms": ["recurring headache", "light sensitivity", "nausea"],
        "duration_days": 12, "severity": 7, "expected_specialty": "neurology",
    },
    {
        "id": "CASE-KNEE", "label": "Ongoing knee pain",
        "age": 58, "symptoms": ["knee pain", "stiffness", "pain while walking"],
        "duration_days": 30, "severity": 6, "expected_specialty": "orthopaedics",
    },
    {
        "id": "CASE-ANXIETY", "label": "Anxiety support",
        "age": 27, "symptoms": ["persistent worry", "poor sleep", "stress"],
        "duration_days": 35, "severity": 5, "expected_specialty": "psychology",
    },
    {
        "id": "CASE-URGENT", "label": "Emergency routing demonstration",
        "age": 65, "symptoms": ["chest pressure", "shortness of breath", "sweating"],
        "duration_days": 0, "severity": 9, "expected_specialty": "emergency_medicine",
    },
]

PATIENT_TEMPLATES = [
    {
        "label": "Skin concern", "age_range": (16, 82), "duration_range": (2, 35),
        "severity_choices": [3, 4, 5, 6, 7],
        "required": ["skin rash"],
        "optional": ["itchy skin", "dry skin", "red patches", "mild swelling"],
        "expected_specialty": "dermatology",
    },
    {
        "label": "Recurring headache", "age_range": (18, 78), "duration_range": (1, 25),
        "severity_choices": [4, 5, 6, 7, 8],
        "required": ["recurring headache"],
        "optional": ["light sensitivity", "nausea", "dizziness", "difficulty concentrating"],
        "expected_specialty": "neurology",
    },
    {
        "label": "Mobility concern", "age_range": (20, 88), "duration_range": (4, 100),
        "severity_choices": [3, 4, 5, 6, 7],
        "required": ["knee pain"],
        "optional": ["stiffness", "pain while walking", "reduced mobility"],
        "expected_specialty": "orthopaedics",
    },
    {
        "label": "Wellbeing support", "age_range": (18, 75), "duration_range": (7, 120),
        "severity_choices": [3, 4, 5, 6, 7],
        "required": ["persistent worry"],
        "optional": ["poor sleep", "stress", "difficulty concentrating"],
        "expected_specialty": "psychology",
    },
    {
        "label": "Emergency-routing demonstration", "age_range": (30, 88),
        "duration_range": (0, 1), "severity_choices": [8, 9, 10],
        "required": ["chest pressure", "shortness of breath"],
        "optional": ["sweating", "nausea"],
        "expected_specialty": "emergency_medicine",
    },
]


class SyntheticPatientGenerator:
    """Creates varied but correlated cases; it is a generator, not a care agent."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def generate(self, count: int = 5) -> list[dict[str, Any]]:
        if not 1 <= count <= 10_000:
            raise ValueError("count must be between 1 and 10,000")
        cases = []
        for index in range(count):
            template = PATIENT_TEMPLATES[index % len(PATIENT_TEMPLATES)]
            optional_count = self.rng.randint(1, min(3, len(template["optional"])))
            symptoms = [*template["required"], *self.rng.sample(template["optional"], optional_count)]
            self.rng.shuffle(symptoms)
            cases.append({
                "id": f"SYN-{index + 1:03d}",
                "label": f"{template['label']} #{index + 1}",
                "age": self.rng.randint(*template["age_range"]),
                "symptoms": symptoms,
                "duration_days": self.rng.randint(*template["duration_range"]),
                "severity": self.rng.choice(template["severity_choices"]),
                "expected_specialty": template["expected_specialty"],
                "synthetic": True,
            })
        return cases


def generate_records(seed: int = 42, start_date: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Generate a coherent provider network and future appointment slots."""
    rng = random.Random(seed)
    start_date = start_date or date.today()
    doctors: list[dict[str, Any]] = []
    slots: list[dict[str, Any]] = []

    for index, (specialty, (title, expertise)) in enumerate(SPECIALTIES.items(), start=1):
        hospital = HOSPITALS[(index - 1) % len(HOSPITALS)]
        doctor = {
            "id": f"DOC-{index:03d}",
            "name": f"Dr Demo {index:03d}",
            "professional_title": title,
            "specialty": specialty,
            "expertise": expertise,
            "languages": ["English", rng.choice(LANGUAGES)],
            "years_experience": rng.randint(4, 25),
            "accepting_new_patients": index % 6 != 0,
            "hospital_id": hospital["id"],
            "synthetic": True,
        }
        doctors.append(doctor)

        for day_offset in range(1, 8):
            slot_day = start_date + timedelta(days=day_offset)
            if slot_day.weekday() >= 5:
                continue
            for hour in (9, 11, 14, 16):
                start = datetime.combine(slot_day, time(hour), tzinfo=timezone.utc)
                slots.append({
                    "id": f"SLOT-{index:03d}-{day_offset:02d}-{hour:02d}",
                    "doctor_id": doctor["id"],
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=30)).isoformat(),
                    "status": "free" if (index + day_offset + hour) % 4 else "busy",
                    "mode": "telehealth" if hour == 16 else "in_person",
                })
    return {"hospitals": HOSPITALS, "doctors": doctors, "slots": slots}
