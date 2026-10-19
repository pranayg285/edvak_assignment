
import json
from pathlib import Path
from typing import Optional, Any

# Assumes the JSON files are in the same folder as this file.
DATA_DIR = Path(__file__).resolve().parent / "data"


def load_json(filename: str) -> Any:
    """Load a JSON file from the project data directory."""
    path = DATA_DIR / filename

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_patients() -> list[dict]:
    """Load all patient records."""
    return load_json("patients.json")


def normalize_contact(value: Optional[str]) -> str:
    """Normalize an email address or phone number for comparison."""
    if not value:
        return ""

    value = value.strip().lower()

    # Ignore common phone-number formatting differences.
    if "@" not in value:
        return "".join(char for char in value if char.isdigit())

    return value


def find_patient(
    patient_id: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict]:
    """
    Find a patient by ID or registered contact information.

    Names alone are deliberately not accepted as lookup criteria.
    Returns None if no unique patient can be identified.
    """
    patients = load_patients()

    if patient_id:
        matches = [
            patient for patient in patients
            if patient.get("id") == patient_id
        ]
    elif phone or email:
        matches = []

        for patient in patients:
            phone_matches = (
                bool(phone)
                and normalize_contact(phone)
                == normalize_contact(patient.get("phone"))
            )

            email_matches = (
                bool(email)
                and normalize_contact(email)
                == normalize_contact(patient.get("email"))
            )

            if phone_matches or email_matches:
                matches.append(patient)
    else:
        return None

    # Never arbitrarily select one record if multiple records match.
    if len(matches) != 1:
        return None

    return matches[0]


def verify_patient(
    patient: dict,
    sender_name: Optional[str] = None,
    sender_phone: Optional[str] = None,
    sender_email: Optional[str] = None,
    stated_dob: Optional[str] = None,
) -> bool:
    """
    Verify a patient according to the clinic's privacy policy.

    A registered phone/email can verify the patient.
    Otherwise, both name and DOB must match.
    """
    registered_phone = normalize_contact(patient.get("phone"))
    registered_email = normalize_contact(patient.get("email"))

    supplied_phone = normalize_contact(sender_phone)
    supplied_email = normalize_contact(sender_email)

    contact_matches = (
        bool(supplied_phone)
        and supplied_phone == registered_phone
    ) or (
        bool(supplied_email)
        and supplied_email == registered_email
    )

    if contact_matches:
        return True

    name_matches = (
        bool(sender_name)
        and sender_name.strip().casefold()
        == patient.get("name", "").strip().casefold()
    )

    dob_matches = (
        bool(stated_dob)
        and stated_dob == patient.get("dob")
    )

    return name_matches and dob_matches


def find_authorized_caregiver(
    patient: dict,
    sender_name: Optional[str] = None,
    sender_phone: Optional[str] = None,
) -> bool:
    """
    Check whether the sender matches the caregiver on file.

    Caregiver identity is checked against the recorded name and
    phone number. A name-only match is not sufficient.
    """
    caregiver = patient.get("authorised_caregiver")

    if not caregiver:
        return False

    if not sender_name or not sender_phone:
        return False

    name_matches = (
        sender_name.strip().casefold()
        == caregiver.get("name", "").strip().casefold()
    )

    phone_matches = (
        normalize_contact(sender_phone)
        == normalize_contact(caregiver.get("phone"))
    )

    return name_matches and phone_matches


if __name__ == "__main__":
    patient = find_patient(phone="555-0102")

    if patient:
        print("Patient found:", patient["id"])
        print("Verified:", verify_patient(
            patient,
            sender_phone="555-0102"
        ))
    else:
        print("No unique patient found.")
