"""Repeatable fictional records for development and evaluation."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Any


DISCLAIMER = (
    "Educational prototype using fictional data. It does not diagnose, provide "
    "medical advice, verify practitioners, or make real appointments."
)

SPECIALTIES = {
    "general_practice": ("General Practitioner", ["general assessment", "preventive care"]),
    "emergency_medicine": ("Emergency Physician", ["urgent assessment", "emergency care"]),
    "cardiology": ("Cardiologist", ["heart health", "cardiac assessment"]),
    "respiratory_medicine": ("Respiratory Physician", ["breathing", "lung health"]),
    "dermatology": ("Dermatologist", ["skin rash", "eczema", "acne"]),
    "neurology": ("Neurologist", ["headache", "migraine", "neurological symptoms"]),
    "orthopaedics": ("Orthopaedic Specialist", ["joint pain", "knee pain", "mobility"]),
    "physiotherapy": ("Physiotherapist", ["rehabilitation", "mobility", "joint pain"]),
    "paediatrics": ("Paediatrician", ["child health", "fever", "development"]),
    "endocrinology": ("Endocrinologist", ["diabetes", "thyroid", "hormonal health"]),
    "psychology": ("Psychologist", ["anxiety", "stress", "sleep difficulties"]),
    "psychiatry": ("Psychiatrist", ["mental health", "medication review"]),
    "gastroenterology": ("Gastroenterologist", ["digestive health", "abdominal symptoms"]),
    "ophthalmology": ("Ophthalmologist", ["eye health", "vision assessment"]),
    "ent": ("ENT Specialist", ["ear health", "nose and throat"]),
    "womens_health": ("Women's Health Specialist", ["reproductive health", "preventive care"]),
    "urology": ("Urologist", ["urinary health", "kidney assessment"]),
    "oncology": ("Oncologist", ["cancer care", "treatment coordination"]),
    "dentistry": ("Dentist", ["oral health", "dental assessment"]),
    "podiatry": ("Podiatrist", ["foot health", "gait assessment"]),
}

LANGUAGES = ["Arabic", "Hindi", "Mandarin", "Urdu", "Vietnamese"]

SUBURBS = [
    ("Sydney Demo", -33.8688, 151.2093),
    ("Parramatta Demo", -33.8150, 151.0011),
    ("Chatswood Demo", -33.7969, 151.1833),
    ("Bondi Demo", -33.8915, 151.2767),
    ("Liverpool Demo", -33.9200, 150.9238),
    ("Ryde Demo", -33.8151, 151.1062),
    ("Penrith Demo", -33.7507, 150.6877),
    ("Hurstville Demo", -33.9676, 151.1010),
    ("Manly Demo", -33.7960, 151.2850),
    ("Burwood Demo", -33.8774, 151.1030),
]


def generate_hospitals(count: int = 50, seed: int = 42) -> list[dict[str, Any]]:
    """Create a geographically varied, entirely fictional provider network."""
    rng = random.Random(seed)
    specialty_names = list(SPECIALTIES)
    hospitals = []
    for index in range(1, count + 1):
        suburb, base_latitude, base_longitude = SUBURBS[(index - 1) % len(SUBURBS)]
        fields = [specialty_names[(index - 1 + offset * 3) % len(specialty_names)] for offset in range(4)]
        if "general_practice" not in fields:
            fields[0] = "general_practice"
        hospitals.append({
            "id": f"HOSP-{index:03d}",
            "name": f"Demo {suburb.removesuffix(' Demo')} Health Network {index:02d}",
            "address": f"{80 + index} Synthetic Avenue, {suburb} NSW",
            "latitude": round(base_latitude + rng.uniform(-0.018, 0.018), 6),
            "longitude": round(base_longitude + rng.uniform(-0.018, 0.018), 6),
            "accessibility": ["wheelchair_access", rng.choice(["accessible_parking", "interpreter_service"])],
            "email": f"intake{index:02d}@hospital.ptzero.example",
            "phone": f"+61 2 9000 {index:04d}",
            "emergency_phone": "000 (demonstration label only)",
            "medical_fields": sorted(set(fields)),
            "synthetic": True,
        })
    return hospitals


HOSPITALS = generate_hospitals()

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
    """Generate 50 hospitals, 50 doctors, 20 patients, and future slots."""
    rng = random.Random(seed)
    start_date = start_date or date.today()
    hospitals = generate_hospitals(50, seed)
    doctors: list[dict[str, Any]] = []
    slots: list[dict[str, Any]] = []
    patients: list[dict[str, Any]] = []
    specialties = list(SPECIALTIES.items())

    for index in range(1, 51):
        specialty, (title, expertise) = specialties[(index - 1) % len(specialties)]
        hospital = hospitals[index - 1]
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
            "email": f"doctor{index:03d}@clinicians.ptzero.example",
            "phone": f"+61 2 9100 {index:04d}",
            "on_call": specialty in {"emergency_medicine", "general_practice"} and index % 2 == 0,
            "video_room_url": f"/video-room.html?room=ONCALL-{index:03d}",
            "synthetic": True,
        }
        doctors.append(doctor)

        for day_offset in range(1, 15):
            slot_day = start_date + timedelta(days=day_offset)
            if slot_day.weekday() >= 5:
                continue
            for hour in (9, 11, 14, 16):
                start = datetime.combine(slot_day, time(hour), tzinfo=timezone.utc)
                slots.append({
                    "id": f"SLOT-{index:03d}-{slot_day:%Y%m%d}-{hour:02d}",
                    "doctor_id": doctor["id"],
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=30)).isoformat(),
                    "status": "free" if (index + day_offset + hour) % 4 else "busy",
                    "mode": "telehealth" if hour == 16 else "in_person",
                })

    generated_cases = SyntheticPatientGenerator(seed + 10).generate(20)
    for index, case in enumerate(generated_cases, start=1):
        suburb, latitude, longitude = SUBURBS[(index - 1) % len(SUBURBS)]
        patients.append({
            "id": f"PAT-{index:03d}",
            "display_name": f"Synthetic Patient {index:02d}",
            "email": f"patient{index:03d}@people.ptzero.example",
            "age": case["age"],
            "suburb": suburb,
            "latitude": latitude,
            "longitude": longitude,
            "conditions": [case["expected_specialty"].replace("_", " ") + " demonstration"],
            "medications": [] if index % 3 else ["Synthetic medication record"],
            "allergies": [] if index % 4 else ["Synthetic allergy record"],
            "synthetic": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return {"hospitals": hospitals, "doctors": doctors, "slots": slots, "patients": patients}
