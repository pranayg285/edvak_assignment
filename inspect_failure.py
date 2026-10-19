
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "data"

def load_file(name):
    for path in [BASE_DIR / name, BASE_DIR / "data" / name]:
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
    raise FileNotFoundError(name)

labels = {
    item["id"]: item for item in load_file("labels_sample.json")
}
outputs = {
    item["id"]: item for item in load_file("agent_output.json")
}

for message_id in ["M004", "M011", "M014", "M021", "M027", "M036"]:
    expected = labels[message_id]
    actual = outputs[message_id]

    print(f"\n{'=' * 65}")
    print(message_id)
    print("Expected patient:", expected.get("patient_id"))
    print("Actual patient:  ", actual.get("patient_id"))
    print("Expected urgency:", expected.get("accepted_urgency"))
    print("Actual urgency:  ", actual.get("urgency"))
    print("Expected actions:", expected.get("expected_actions"))
    print("Actual actions:  ", actual.get("actions"))
    print("Routed to:       ", actual.get("routed_to"))
    print("Tool calls:      ", actual.get("tool_calls"))
    print("Reply draft:     ", actual.get("reply_draft"))
