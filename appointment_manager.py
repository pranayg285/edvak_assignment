
import json
import uuid
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

TODAY = date(2026, 11, 9)


def load_json(filename):
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


class AppointmentManager:
    def __init__(self):
        clinic = load_json("clinic.json")

        self.clinic = clinic
        self.appointments = load_json("appointments.json")

        self.providers = {
            provider["id"]: provider
            for provider in clinic["providers"]
        }

        self.visit_types = clinic["visit_types"]
        self.holidays = set(clinic["holidays"])
        self.open_days = set(clinic["hours"]["days"])

        self.open_time = time.fromisoformat(clinic["hours"]["open"])
        self.close_time = time.fromisoformat(clinic["hours"]["close"])

        lunch_start, lunch_end = clinic["hours"]["lunch"]
        self.lunch_start = time.fromisoformat(lunch_start)
        self.lunch_end = time.fromisoformat(lunch_end)

    def _parse_datetime(self, day, clock):
        return datetime.combine(
            date.fromisoformat(day),
            time.fromisoformat(clock),
        )

    def _provider_available(self, provider_id, day):
        if provider_id not in self.providers:
            return False

        provider = self.providers[provider_id]

        if day < TODAY:
            return False

        if day.isoformat() in self.holidays:
            return False

        if day.strftime("%a") not in self.open_days:
            return False

        for leave_start, leave_end in provider.get("leave", []):
            if leave_start <= day.isoformat() <= leave_end:
                return False

        return True

    def _has_conflict(
        self,
        provider_id,
        start,
        end,
        exclude_appointment_id=None,
    ):
        for appointment in self.appointments:
            if appointment.get("status") == "cancelled":
                continue

            if appointment.get("provider") != provider_id:
                continue

            if appointment.get("id") == exclude_appointment_id:
                continue

            existing_start = self._parse_datetime(
                appointment["date"], appointment["start"]
            )
            existing_end = self._parse_datetime(
                appointment["date"], appointment["end"]
            )

            # Half-open intervals: an appointment may start exactly
            # when the previous appointment ends.
            if start < existing_end and existing_start < end:
                return True

        return False

    def find_free_slots(
        self,
        provider_id,
        visit_type,
        start_date,
        end_date,
        preferred_period=None,
    ):
        """
        Return available slots for a provider and visit type.

        Dates use YYYY-MM-DD. preferred_period may be "morning"
        or "afternoon".
        """
        if provider_id not in self.providers:
            return []

        if visit_type not in self.visit_types:
            return []

        first_day = date.fromisoformat(start_date)
        last_day = date.fromisoformat(end_date)

        if last_day < first_day:
            return []

        duration = self.visit_types[visit_type]
        results = []
        current_day = first_day

        while current_day <= last_day:
            if self._provider_available(provider_id, current_day):
                current = datetime.combine(
                    current_day, self.open_time
                )
                closing = datetime.combine(
                    current_day, self.close_time
                )
                lunch_start = datetime.combine(
                    current_day, self.lunch_start
                )
                lunch_end = datetime.combine(
                    current_day, self.lunch_end
                )

                while current + timedelta(minutes=duration) <= closing:
                    end = current + timedelta(minutes=duration)

                    allowed_start = current.minute in (0, 20, 40)
                    avoids_lunch = (
                        end <= lunch_start or current >= lunch_end
                    )

                    period_matches = (
                        preferred_period is None
                        or (
                            preferred_period == "morning"
                            and current.time() < self.lunch_start
                        )
                        or (
                            preferred_period == "afternoon"
                            and current.time() >= self.lunch_end
                        )
                    )

                    if (
                        allowed_start
                        and avoids_lunch
                        and period_matches
                        and not self._has_conflict(
                            provider_id, current, end
                        )
                    ):
                        results.append({
                            "provider": provider_id,
                            "date": current_day.isoformat(),
                            "start": current.strftime("%H:%M"),
                            "end": end.strftime("%H:%M"),
                            "visit_type": visit_type,
                        })

                    current += timedelta(minutes=20)

            current_day += timedelta(days=1)

        return results

    def book_appointment(
        self,
        patient_id,
        provider_id,
        visit_type,
        appointment_date,
        start,
    ):
        """Book only a currently available, valid slot."""
        slots = self.find_free_slots(
            provider_id,
            visit_type,
            appointment_date,
            appointment_date,
        )

        chosen = next(
            (
                slot for slot in slots
                if slot["start"] == start
            ),
            None,
        )

        if chosen is None:
            return {
                "success": False,
                "reason": "slot_unavailable_or_invalid",
            }

        appointment = {
            "id": f"NEW-{uuid.uuid4().hex[:8].upper()}",
            "patient_id": patient_id,
            **chosen,
            "status": "booked",
        }

        self.appointments.append(appointment)

        return {
            "success": True,
            "appointment": deepcopy(appointment),
        }

    def cancel_appointment(self, appointment_id, patient_id):
        """Cancel an appointment only for its owning patient."""
        for appointment in self.appointments:
            if appointment.get("id") != appointment_id:
                continue

            if appointment.get("patient_id") != patient_id:
                return {
                    "success": False,
                    "reason": "patient_mismatch",
                }

            if appointment.get("status") == "cancelled":
                return {
                    "success": False,
                    "reason": "already_cancelled",
                }

            appointment["status"] = "cancelled"

            return {
                "success": True,
                "appointment": deepcopy(appointment),
            }

        return {
            "success": False,
            "reason": "appointment_not_found",
        }

    def reschedule_appointment(
        self,
        appointment_id,
        patient_id,
        new_date,
        new_start,
    ):
        """
        Find the existing booking and attempt to move it.
        Preserve the original booking if the new slot is invalid.
        """
        appointment = next(
            (
                item for item in self.appointments
                if item.get("id") == appointment_id
            ),
            None,
        )

        if not appointment:
            return {
                "success": False,
                "reason": "appointment_not_found",
            }

        if appointment.get("patient_id") != patient_id:
            return {
                "success": False,
                "reason": "patient_mismatch",
            }

        if appointment.get("status") == "cancelled":
            return {
                "success": False,
                "reason": "already_cancelled",
            }

        slots = self.find_free_slots(
            appointment["provider"],
            appointment["visit_type"],
            new_date,
            new_date,
        )

        chosen = next(
            (
                slot for slot in slots
                if slot["start"] == new_start
            ),
            None,
        )

        if chosen is None:
            return {
                "success": False,
                "reason": "slot_unavailable_or_invalid",
            }

        # Revalidate while excluding the original booking.
        new_begin = self._parse_datetime(
            chosen["date"], chosen["start"]
        )
        new_end = self._parse_datetime(
            chosen["date"], chosen["end"]
        )

        if self._has_conflict(
            appointment["provider"],
            new_begin,
            new_end,
            exclude_appointment_id=appointment_id,
        ):
            return {
                "success": False,
                "reason": "slot_conflict",
            }

        appointment.update(chosen)

        return {
            "success": True,
            "appointment": deepcopy(appointment),
        }


if __name__ == "__main__":
    manager = AppointmentManager()

    slots = manager.find_free_slots(
        provider_id="KIM",
        visit_type="annual_physical",
        start_date="2026-11-09",
        end_date="2026-11-13",
        preferred_period="afternoon",
    )

    print("Available slots:", len(slots))
    for slot in slots[:5]:
        print(slot)
