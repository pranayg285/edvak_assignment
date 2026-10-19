
import json
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent / "data"

# The assignment uses a simulated date, not the computer's real date.
TODAY = date(2026, 11, 9)


def load_json(filename: str):
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_patient_medications(patient_id: str) -> list[dict]:
    """Return all medication records belonging to a patient."""
    medications = load_json("medications.json")

    return [
        medication
        for medication in medications
        if medication.get("patient_id") == patient_id
    ]


def get_patient_appointments(
    patient_id: str,
    include_cancelled: bool = False,
) -> list[dict]:
    """Return a patient's appointments, excluding cancelled ones by default."""
    appointments = load_json("appointments.json")

    results = [
        appointment
        for appointment in appointments
        if appointment.get("patient_id") == patient_id
    ]

    if not include_cancelled:
        results = [
            appointment
            for appointment in results
            if appointment.get("status") != "cancelled"
        ]

    return results


def get_provider_appointments(
    provider_id: str,
    appointment_date: str,
) -> list[dict]:
    """Return appointments for one provider on one date."""
    appointments = load_json("appointments.json")

    return [
        appointment
        for appointment in appointments
        if appointment.get("provider") == provider_id
        and appointment.get("date") == appointment_date
        and appointment.get("status") != "cancelled"
    ]


def get_clinic_config() -> dict:
    """Return clinic hours, provider details and policies."""
    return load_json("clinic.json")


def get_patient(patient_id: str) -> Optional[dict]:
    """Retrieve a patient by ID."""
    patients = load_json("patients.json")

    matches = [
        patient
        for patient in patients
        if patient.get("id") == patient_id
    ]

    return matches[0] if len(matches) == 1 else None


def _subtract_one_year(day: date) -> date:
    """Calculate a one-calendar-year cutoff, handling leap days."""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def check_refill_eligibility(
    patient_id: str,
    medication_name: Optional[str] = None,
) -> dict:
    """
    Check clinic refill policy. This does not approve or send a prescription.
    """
    patient = get_patient(patient_id)

    if not patient:
        return {
            "eligible": False,
            "reason": "patient_not_found",
            "action": "request_verification",
        }

    medications = get_patient_medications(patient_id)

    if medication_name:
        requested = medication_name.strip().casefold()
        medications = [
            medication for medication in medications
            if medication.get("medication", "").strip().casefold()
            == requested
        ]

    if not medications:
        return {
            "eligible": False,
            "reason": "medication_not_found",
            "action": "route_to_provider",
        }

    # Avoid making an arbitrary decision if more than one medication matches.
    if len(medications) > 1:
        return {
            "eligible": False,
            "reason": "medication_ambiguous",
            "action": "request_clarification",
        }

    medication = medications[0]

    if medication.get("controlled_schedule"):
        return {
            "eligible": False,
            "reason": "controlled_substance",
            "action": "route_to_provider",
            "medication": medication["medication"],
        }

    last_visit_raw = patient.get("last_visit")

    if not last_visit_raw:
        return {
            "eligible": False,
            "reason": "last_visit_unknown",
            "action": "route_to_provider",
        }

    last_visit = date.fromisoformat(last_visit_raw)
    cutoff = _subtract_one_year(TODAY)

    if last_visit < cutoff or last_visit > TODAY:
        return {
            "eligible": False,
            "reason": "visit_outside_12_month_window",
            "action": "refill_needs_visit",
            "follow_up_action": "offer_appointment",
        }

    if medication.get("refills_remaining", 0) <= 0:
        return {
            "eligible": False,
            "reason": "no_refills_remaining",
            "action": "route_to_provider",
        }

    last_filled = date.fromisoformat(medication["last_filled"])
    days_supply = medication["days_supply"]

    supply_end = last_filled + timedelta(days=days_supply)
    earliest_request = supply_end - timedelta(days=7)

    if TODAY < earliest_request:
        return {
            "eligible": False,
            "reason": "too_early",
            "action": "refill_too_early",
            "supply_end_date": supply_end.isoformat(),
            "earliest_request_date": earliest_request.isoformat(),
        }

    return {
        "eligible": True,
        "reason": "eligible_for_provider_approval",
        "action": "prepare_refill_for_approval",
        "medication": medication["medication"],
        "prescriber": medication["prescriber"],
        "refills_remaining": medication["refills_remaining"],
        "supply_end_date": supply_end.isoformat(),
    }


if __name__ == "__main__":
    print("Robert's medications:")
    print(get_patient_medications("P002"))

    print("\nRobert's appointments:")
    print(get_patient_appointments("P002"))

    print("\nRobert's lisinopril refill check:")
    print(check_refill_eligibility("P002", "Lisinopril 10 mg"))
