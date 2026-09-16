"""Reproducible routing, safety, ranking, and latency benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agents import Coordinator
from app.models import PatientRequest
from app.rag import KnowledgeBase
from app.repository import Repository
from app.synthetic import SyntheticPatientGenerator


ROOT = Path(__file__).parents[1]


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile_value))
    return ordered[index]


def run(total: int, seed: int) -> dict:
    cases = SyntheticPatientGenerator(seed).generate(total)
    latencies = []
    correct_routes = 0
    emergencies = 0
    emergency_stops = 0
    ranked_non_emergencies = 0

    with tempfile.TemporaryDirectory() as folder:
        repository = Repository(Path(folder) / "benchmark.db")
        coordinator = Coordinator(repository, KnowledgeBase(ROOT / "app" / "data" / "knowledge.json"))
        for case in cases:
            request = PatientRequest.model_validate({
                "age": case["age"], "symptoms": case["symptoms"],
                "duration_days": case["duration_days"], "severity": case["severity"],
                "location": {"latitude": -33.8688, "longitude": 151.2093, "suburb": "Sydney Demo"},
                "preferences": {"languages": ["English"], "consultation_mode": "either", "maximum_travel_km": 50},
            })
            started = time.perf_counter()
            result = coordinator.navigate(request)
            latencies.append((time.perf_counter() - started) * 1000)
            expected = case["expected_specialty"]
            correct_routes += expected in result.recommended_specialties
            if expected == "emergency_medicine":
                emergencies += 1
                emergency_stops += result.triage.care_level == "emergency" and not result.recommendations
            else:
                ranked_non_emergencies += bool(result.recommendations)
        repository.close()

    non_emergency_total = total - emergencies
    return {
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "cases": total, "seed": seed},
        "quality": {
            "routing_accuracy": round(correct_routes / total, 4),
            "emergency_stop_recall": round(emergency_stops / emergencies, 4) if emergencies else 1.0,
            "provider_result_rate": round(ranked_non_emergencies / non_emergency_total, 4) if non_emergency_total else 1.0,
        },
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 3),
            "p50": round(percentile(latencies, .50), 3),
            "p95": round(percentile(latencies, .95), 3),
            "max": round(max(latencies), 3),
        },
        "thresholds": {"routing_accuracy": .95, "emergency_stop_recall": 1.0, "p95_ms": 100.0},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=250)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.cases, args.seed)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    quality, latency, thresholds = report["quality"], report["latency_ms"], report["thresholds"]
    if (quality["routing_accuracy"] < thresholds["routing_accuracy"]
            or quality["emergency_stop_recall"] < thresholds["emergency_stop_recall"]
            or latency["p95"] > thresholds["p95_ms"]):
        raise SystemExit("Benchmark thresholds failed")


if __name__ == "__main__":
    main()
