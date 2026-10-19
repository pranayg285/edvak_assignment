import json
from pathlib import Path
DATA_DIR = Path(__file__).resolve().parent / "data"



def load_json(filename: str):
    path = DATA_DIR / filename

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_all_data():
    return {
        "clinic": load_json("clinic.json"),
        "patients": load_json("patients.json"),
        "medications": load_json("medications.json"),
        "appointments": load_json("appointments.json"),
        "messages": load_json("messages_sample.json"),
        "labels": load_json("labels_sample.json"),
    }


def validate_data(data):
    assert len(data["messages"]) == 40
    assert len(data["labels"]) == 40

    message_ids = [m["id"] for m in data["messages"]]
    label_ids = [label["id"] for label in data["labels"]]

    assert len(set(message_ids)) == len(message_ids)
    assert set(message_ids) == set(label_ids)

    return True


if __name__ == "__main__":
    data = load_all_data()
    validate_data(data)

    print("All JSON files loaded successfully.")
    print("Patients:", len(data["patients"]))
    print("Medications:", len(data["medications"]))
    print("Appointments:", len(data["appointments"]))
    print("Messages:", len(data["messages"]))
    print("Labels:", len(data["labels"]))