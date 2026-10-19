
from mcp.server.fastmcp import FastMCP

from patient_lookup import (
    find_patient,
    verify_patient,
    find_authorized_caregiver,
)

from clinic_data import (
    get_patient,
    get_patient_medications,
    get_patient_appointments,
    check_refill_eligibility,
)

from urgency_rules import (
    classify_urgency,
    build_emergency_result,
)

from appointment_manager import AppointmentManager


mcp = FastMCP("Maplewood Clinic Tools")

# State persists while this server process remains running.
appointment_manager = AppointmentManager()
message_queue = []


ALLOWED_QUEUES = {
    "clinician_urgent",
    "clinician_routine",
    "provider_refills",
    "front_desk",
    "billing",
}


@mcp.tool()
def find_patient_tool(
    patient_id: str = "",
    phone: str = "",
    email: str = "",
) -> dict:
    """Find a patient by ID or registered contact information."""
    patient = find_patient(
        patient_id=patient_id or None,
        phone=phone or None,
        email=email or None,
    )

    if not patient:
        return {
            "found": False,
            "patient": None,
        }

    # Return only the fields needed by the caller.
    return {
        "found": True,
        "patient": {
            "id": patient.get("id"),
            "name": patient.get("name"),
            "phone": patient.get("phone"),
            "email": patient.get("email"),
        },
    }


@mcp.tool()
def verify_patient_tool(
    patient_id: str,
    sender_name: str = "",
    sender_phone: str = "",
    sender_email: str = "",
    stated_dob: str = "",
) -> dict:
    """Verify a sender against a known patient record."""
    patient = get_patient(patient_id)

    if not patient:
        return {
            "verified": False,
            "reason": "patient_not_found",
        }

    verified = verify_patient(
        patient,
        sender_name=sender_name or None,
        sender_phone=sender_phone or None,
        sender_email=sender_email or None,
        stated_dob=stated_dob or None,
    )

    return {"verified": verified}


@mcp.tool()
def check_authorized_caregiver(
    patient_id: str,
    sender_name: str,
    sender_phone: str,
) -> dict:
    """Check whether a sender matches the recorded caregiver."""
    patient = get_patient(patient_id)

    if not patient:
        return {
            "authorized": False,
            "reason": "patient_not_found",
        }

    authorized = find_authorized_caregiver(
        patient,
        sender_name=sender_name,
        sender_phone=sender_phone,
    )

    return {"authorized": authorized}


@mcp.tool()
def get_medications(patient_id: str) -> list[dict]:
    """Retrieve medication records for a patient."""
    return get_patient_medications(patient_id)


@mcp.tool()
def check_refill(
    patient_id: str,
    medication_name: str,
) -> dict:
    """Evaluate refill eligibility using clinic policy."""
    return check_refill_eligibility(
        patient_id,
        medication_name,
    )


@mcp.tool()
def get_appointments(patient_id: str) -> list[dict]:
    """Retrieve non-cancelled appointments for a patient."""
    return get_patient_appointments(patient_id)


@mcp.tool()
def find_free_slots(
    provider_id: str,
    visit_type: str,
    start_date: str,
    end_date: str,
    preferred_period: str = "",
) -> list[dict]:
    """Find free slots for a provider and visit type."""
    return appointment_manager.find_free_slots(
        provider_id=provider_id,
        visit_type=visit_type,
        start_date=start_date,
        end_date=end_date,
        preferred_period=preferred_period or None,
    )


@mcp.tool()
def book_appointment(
    patient_id: str,
    provider_id: str,
    visit_type: str,
    appointment_date: str,
    start: str,
) -> dict:
    """Book an available appointment slot."""
    return appointment_manager.book_appointment(
        patient_id=patient_id,
        provider_id=provider_id,
        visit_type=visit_type,
        appointment_date=appointment_date,
        start=start,
    )


@mcp.tool()
def cancel_appointment(
    appointment_id: str,
    patient_id: str,
) -> dict:
    """Cancel an appointment belonging to the verified patient."""
    return appointment_manager.cancel_appointment(
        appointment_id,
        patient_id,
    )


@mcp.tool()
def reschedule_appointment(
    appointment_id: str,
    patient_id: str,
    new_date: str,
    new_start: str,
) -> dict:
    """Move an existing appointment to a free slot."""
    return appointment_manager.reschedule_appointment(
        appointment_id=appointment_id,
        patient_id=patient_id,
        new_date=new_date,
        new_start=new_start,
    )


@mcp.tool()
def assess_urgency(message_text: str) -> dict:
    """Screen a message for emergency and urgent indicators."""
    return classify_urgency(message_text)


@mcp.tool()
def route_message(
    message_id: str,
    queue: str,
    reason: str,
) -> dict:
    """Route a message to an approved human queue."""
    if queue not in ALLOWED_QUEUES:
        return {
            "success": False,
            "reason": "invalid_queue",
        }

    record = {
        "message_id": message_id,
        "queue": queue,
        "reason": reason,
    }

    message_queue.append(record)

    return {
        "success": True,
        "routing": record,
    }


@mcp.tool()
def draft_reply(
    patient_name: str,
    message_text: str,
    action_summary: str,
    language: str = "English",
) -> dict:
    """
    Produce a basic administrative reply draft.

    This is a template, not an LLM-generated clinical response.
    """
    name = patient_name.strip() or "there"

    if language.casefold() == "spanish":
        reply = (
            f"Hola {name}, hemos recibido su mensaje. "
            f"{action_summary} Si necesita ayuda adicional, "
            "comuníquese con la clínica."
        )
    else:
        reply = (
            f"Hi {name}, we've received your message. "
            f"{action_summary} Please contact the clinic if "
            "you need additional assistance."
        )

    return {
        "reply_draft": reply,
        "source_message": message_text,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
