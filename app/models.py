"""Validated API contracts for the MVP."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    suburb: str = Field(min_length=1, max_length=100)


class Preferences(BaseModel):
    languages: list[str] = Field(default_factory=lambda: ["English"])
    consultation_mode: str = "either"
    maximum_travel_km: float = Field(default=25, gt=0, le=200)
    accessibility: list[str] = Field(default_factory=list)

    @field_validator("consultation_mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        allowed = {"in_person", "telehealth", "either"}
        if value not in allowed:
            raise ValueError(f"consultation_mode must be one of {sorted(allowed)}")
        return value


class PatientRequest(BaseModel):
    age: int = Field(ge=0, le=120)
    symptoms: list[str] = Field(min_length=1, max_length=20)
    duration_days: int = Field(ge=0, le=3650)
    severity: int = Field(ge=0, le=10)
    existing_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    location: Location
    preferences: Preferences = Field(default_factory=Preferences)

    @field_validator("symptoms")
    @classmethod
    def non_empty_symptoms(cls, values: list[str]) -> list[str]:
        cleaned = sorted({value.strip().lower() for value in values if value.strip()})
        if not cleaned:
            raise ValueError("at least one symptom is required")
        return cleaned


class TraceEvent(BaseModel):
    agent: str
    action: str
    explanation: str
    data: dict = Field(default_factory=dict)


class TriageResult(BaseModel):
    urgency: str
    care_level: str
    warning_signs: list[str] = Field(default_factory=list)
    message: str


class Evidence(BaseModel):
    title: str
    source: str
    excerpt: str
    score: float


class DoctorRecommendation(BaseModel):
    doctor_id: str
    name: str
    professional_title: str
    specialty: str
    expertise: list[str]
    languages: list[str]
    years_experience: int
    hospital_name: str
    address: str
    distance_km: float
    appointment_start: str
    consultation_mode: str
    suitability_score: float
    reasons: list[str]


class NavigationResponse(BaseModel):
    request_id: str
    synthetic_only: bool = True
    disclaimer: str
    triage: TriageResult
    recommended_specialties: list[str]
    patient_guidance: str
    evidence: list[Evidence]
    recommendations: list[DoctorRecommendation]
    trace: list[TraceEvent]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: str


class AuthResponse(BaseModel):
    user: UserPublic
    message: str
