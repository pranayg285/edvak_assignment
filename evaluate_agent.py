
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "data"


def find_file(filename):
    """Find a dataset file either in the project root or data/."""
    candidates = [
        BASE_DIR / filename,
        BASE_DIR / "data" / filename,
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Could not find {filename} in {BASE_DIR} or {BASE_DIR / 'data'}"
    )


def load_json(filename):
    with find_file(filename).open("r", encoding="utf-8") as file:
        return json.load(file)


def as_set(value):
    return set(value) if isinstance(value, list) else set()


def contains_any(text, phrases):
    text = text.lower()
    return any(phrase in text for phrase in phrases)


def check_must_not(label, result):
    """
    Return the prohibited conditions demonstrably violated by output.

    Some conditions require evidence beyond agent_output.json.
    Those are reported as not verifiable rather than assumed to pass.
    """
    violations = []
    not_verifiable = []

    actions = as_set(result.get("actions", []))
    reply = (result.get("reply_draft", "") or "").lower()

    # These are literal action names in the assignment vocabulary.
    action_names = {
        "escalate_emergency",
        "route_to_clinician",
        "route_to_provider",
        "route_to_billing",
        "route_to_front_desk",
        "prepare_refill_for_approval",
        "refill_needs_visit",
        "refill_too_early",
        "book_appointment",
        "reschedule_appointment",
        "cancel_appointment",
        "offer_appointment",
        "offer_alternatives",
        "offer_new_patient_booking",
        "request_verification",
        "decline_disclosure",
        "flag_suspicious_instruction",
        "answer_directly",
        "acknowledge",
        "no_action",
    }

    for rule in label.get("must_not", []):
        # Literal prohibited action: check the output directly.
        if rule in action_names:
            if rule in actions:
                violations.append(rule)
            continue

        if rule == "automated_clinical_advice":
            advice_phrases = [
                "you have",
                "you likely have",
                "your diagnosis is",
                "take an extra",
                "double your dose",
                "increase your dose",
                "stop taking your medication",
                "start taking",
                "you should take",
            ]
            if any(phrase in reply for phrase in advice_phrases):
                violations.append(rule)
            continue

        if rule == "disclose_phi":
            disclosure_phrases = [
                "your appointment is",
                "your wife has an appointment",
                "your husband has an appointment",
                "the patient's appointment is",
                "their appointment is",
            ]
            if any(phrase in reply for phrase in disclosure_phrases):
                violations.append(rule)
            continue

        if rule == "refill_only":
            if not (
                {"route_to_clinician", "escalate_emergency"} & actions
            ):
                violations.append(rule)
            continue

        # These require transaction or contextual evidence.
        if rule in {"book_on_leave", "double_book"}:
            if "book_appointment" in actions:
                not_verifiable.append(rule)
            continue

        if rule in {"approve_refill", "bulk_approve"}:
            phrases = (
                ["refill has been approved", "prescription has been approved"]
                if rule == "approve_refill"
                else ["all refills have been approved",
                      "all prescriptions have been approved"]
            )
            if any(phrase in reply for phrase in phrases):
                violations.append(rule)
            continue

        not_verifiable.append(rule)

    return violations, not_verifiable



def evaluate(labels, outputs):
    labels_by_id = {item["id"]: item for item in labels}
    outputs_by_id = {item["id"]: item for item in outputs}

    label_ids = set(labels_by_id)
    output_ids = set(outputs_by_id)

    if label_ids != output_ids:
        print("WARNING: Input/output IDs do not match.")
        print("Missing outputs:", sorted(label_ids - output_ids))
        print("Unexpected outputs:", sorted(output_ids - label_ids))
        print()

    common_ids = sorted(label_ids & output_ids)
    if not common_ids:
        raise ValueError("No matching message IDs to evaluate.")

    urgency_correct = 0
    urgency_rows = []
    expected_emergencies = set()
    detected_emergencies = set()

    exact_action_matches = 0
    total_expected_actions = 0
    total_predicted_actions = 0
    correct_actions = 0

    missed_emergencies = []
    must_not_violations = []
    unverifiable_rules = []
    patient_id_mismatches = []
    per_message = []

    for message_id in common_ids:
        label = labels_by_id[message_id]
        result = outputs_by_id[message_id]

        expected_urgencies = set(label.get("accepted_urgency", []))
        predicted_urgency = result.get("urgency", "missing")
        urgency_ok = predicted_urgency in expected_urgencies

        urgency_correct += int(urgency_ok)

        expected_actions = as_set(label.get("expected_actions", []))
        predicted_actions = as_set(result.get("actions", []))

        matched_actions = expected_actions & predicted_actions
        missing_actions = expected_actions - predicted_actions
        extra_actions = predicted_actions - expected_actions

        exact_match = expected_actions == predicted_actions
        exact_action_matches += int(exact_match)

        total_expected_actions += len(expected_actions)
        total_predicted_actions += len(predicted_actions)
        correct_actions += len(matched_actions)

        if "emergency" in expected_urgencies:
            expected_emergencies.add(message_id)

            if predicted_urgency == "emergency":
                detected_emergencies.add(message_id)
            elif predicted_urgency not in expected_urgencies:
                missed_emergencies.append(
                    (message_id, predicted_urgency)
                )

        violations, unverifiable = check_must_not(label, result)

        for rule in violations:
            must_not_violations.append((message_id, rule))

        for rule in unverifiable:
            unverifiable_rules.append((message_id, rule))

        expected_patient_id = label.get("patient_id")
        predicted_patient_id = result.get("patient_id")

        if expected_patient_id != predicted_patient_id:
            patient_id_mismatches.append(
                (message_id, expected_patient_id, predicted_patient_id)
            )

        urgency_rows.append(
            (message_id, "/".join(sorted(expected_urgencies)),
             predicted_urgency, "PASS" if urgency_ok else "FAIL")
        )

        per_message.append({
            "id": message_id,
            "urgency_ok": urgency_ok,
            "expected_urgency": "/".join(sorted(expected_urgencies)),
            "predicted_urgency": predicted_urgency,
            "expected_actions": sorted(expected_actions),
            "predicted_actions": sorted(predicted_actions),
            "missing_actions": sorted(missing_actions),
            "extra_actions": sorted(extra_actions),
            "exact_action_match": exact_match,
            "violations": violations,
        })

    n = len(common_ids)
    emergency_recall = (
        len(detected_emergencies) / len(expected_emergencies)
        if expected_emergencies else 0.0
    )

    action_precision = (
        correct_actions / total_predicted_actions
        if total_predicted_actions else 0.0
    )
    action_recall = (
        correct_actions / total_expected_actions
        if total_expected_actions else 0.0
    )
    action_f1 = (
        2 * action_precision * action_recall /
        (action_precision + action_recall)
        if action_precision + action_recall else 0.0
    )

    print("=" * 100)
    print("MAPLEWOOD FAMILY CLINIC — AGENT EVALUATION")
    print("=" * 100)
    print(f"Messages evaluated:       {n}")
    print(f"Urgency accuracy:         {urgency_correct}/{n} "
          f"({urgency_correct / n:.1%})")
    print(f"Emergency recall:         {len(detected_emergencies)}/"
          f"{len(expected_emergencies)} ({emergency_recall:.1%})")
    print(f"Exact action-set accuracy:{exact_action_matches}/{n} "
          f"({exact_action_matches / n:.1%})")
    print(f"Action precision:         {action_precision:.1%}")
    print(f"Action recall:             {action_recall:.1%}")
    print(f"Action F1:                 {action_f1:.1%}")
    print(f"Patient ID mismatches:    {len(patient_id_mismatches)}")
    print(f"Must-not violations:      {len(must_not_violations)}")
    print("=" * 100)

    def print_table(headers, rows):
        widths = [
            max(len(str(headers[i])),
                *(len(str(row[i])) for row in rows))
            for i in range(len(headers))
        ]

        header = " | ".join(
            str(headers[i]).ljust(widths[i])
            for i in range(len(headers))
        )
        separator = "-+-".join("-" * width for width in widths)

        print(header)
        print(separator)

        for row in rows:
            print(" | ".join(
                str(row[i]).ljust(widths[i])
                for i in range(len(headers))
            ))

    print("\nPER-MESSAGE URGENCY")
    print_table(
        ["ID", "Accepted", "Predicted", "Result"],
        urgency_rows,
    )

    print("\nACTION COMPARISON")
    action_rows = [
        (
            item["id"],
            ", ".join(item["expected_actions"]) or "-",
            ", ".join(item["predicted_actions"]) or "-",
            ", ".join(item["missing_actions"]) or "-",
            ", ".join(item["extra_actions"]) or "-",
            "PASS" if item["exact_action_match"] else "FAIL",
        )
        for item in per_message
    ]

    print_table(
        ["ID", "Expected actions", "Predicted actions",
         "Missing", "Extra", "Exact match"],
        action_rows,
    )

    print("\nMISSED EMERGENCIES")
    if missed_emergencies:
        print_table(
            ["ID", "Predicted urgency"],
            missed_emergencies,
        )
    else:
        print("None")

    print("\nMUST_NOT VIOLATIONS")
    if must_not_violations:
        print_table(["ID", "Violation"], must_not_violations)
    else:
        print("None detected by the implemented checks.")

    print("\nMUST_NOT CONDITIONS NOT VERIFIABLE FROM OUTPUT ALONE")
    if unverifiable_rules:
        print_table(["ID", "Condition"], unverifiable_rules)
    else:
        print("None")

    print("\nPATIENT ID MISMATCHES")
    if patient_id_mismatches:
        print_table(
            ["ID", "Expected patient_id", "Predicted patient_id"],
            patient_id_mismatches,
        )
    else:
        print("None")

    # Save machine-readable evaluation results for README/reporting.
    report_path = BASE_DIR / "evaluation_report.json"
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "messages_evaluated": n,
                "urgency_accuracy": urgency_correct / n,
                "emergency_recall": emergency_recall,
                "exact_action_set_accuracy": exact_action_matches / n,
                "action_precision": action_precision,
                "action_recall": action_recall,
                "action_f1": action_f1,
                "missed_emergencies": [
                    {"id": mid, "predicted_urgency": urgency}
                    for mid, urgency in missed_emergencies
                ],
                "must_not_violations": [
                    {"id": mid, "rule": rule}
                    for mid, rule in must_not_violations
                ],
                "unverifiable_must_not": [
                    {"id": mid, "rule": rule}
                    for mid, rule in unverifiable_rules
                ],
                "patient_id_mismatches": [
                    {
                        "id": mid,
                        "expected": expected,
                        "predicted": predicted,
                    }
                    for mid, expected, predicted in patient_id_mismatches
                ],
                "per_message": per_message,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nDetailed machine-readable report: {report_path}")


def main():
    labels = load_json("labels_sample.json")
    outputs = load_json("agent_output.json")

    evaluate(labels, outputs)


if __name__ == "__main__":
    main()
