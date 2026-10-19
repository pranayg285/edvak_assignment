
import re


# Explicit patterns for the synthetic assignment.
# This is a baseline and must not be treated as exhaustive.
EMERGENCY_PATTERNS = [
    r"\bcrushing chest pain\b",
    r"\bchest pain\b.{0,100}\b(left arm|arm pain|sweat|dizz)",
    r"\b(chest pain|shortness of breath)\b",
    r"\b(hit|struck|injured)\b.{0,40}\b(head)\b.{0,80}\b(confused|confusion)\b",
    r"\b(fell|fall)\b.{0,60}\b(head)\b.{0,80}\b(confused|confusion)\b",
    r"\b(confused|confusion)\b.{0,60}\b(head injury|hit (her|his|my) head)\b",
    r"\b(dark stools|black stools|vomiting blood)\b",
    r"\b(bleeding heavily|uncontrolled bleeding|severe bleeding)\b",
    r"\b(severe asthma|can't breathe|cannot breathe|struggling to breathe)\b",
    r"\b(severe hypoglycemia|severe hypoglycaemia)\b",
    r"\b(unconscious|not breathing|unresponsive)\b",
]

URGENT_PATTERNS = [
    r"\bfeeling really low\b",
    r"\bdon't see the point of anything\b",
    r"\bdo not see the point of anything\b",
    r"\bout of (my )?(pills|medication|medicine)\b",
    r"\bASAP\b",
    r"\bfever\b.{0,60}\b(two days|2 days|three days|3 days)\b",
]


def matches_any(text: str, patterns: list[str]) -> list[str]:
    """Return all matching patterns."""
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def classify_urgency(message_text: str) -> dict:
    """
    Classify message urgency.

    Emergency signals take priority over urgent signals.
    This is a transparent baseline, not a clinically validated classifier.
    """
    text = message_text or ""

    emergency_matches = matches_any(text, EMERGENCY_PATTERNS)

    if emergency_matches:
        return {
            "urgency": "emergency",
            "requires_immediate_escalation": True,
            "automated_clinical_advice_allowed": False,
            "matched_patterns": emergency_matches,
        }

    urgent_matches = matches_any(text, URGENT_PATTERNS)

    if urgent_matches:
        return {
            "urgency": "urgent",
            "requires_immediate_escalation": False,
            "automated_clinical_advice_allowed": False,
            "matched_patterns": urgent_matches,
        }

    return {
        "urgency": "routine",
        "requires_immediate_escalation": False,
        "automated_clinical_advice_allowed": False,
        "matched_patterns": [],
    }


def build_emergency_result(message_id: str) -> dict:
    """
    Build a safe emergency handling decision.

    The caller must successfully route the message and record the
    tool call before claiming that the clinic has been alerted.
    """
    return {
        "id": message_id,
        "urgency": "emergency",
        "actions": ["escalate_emergency"],
        "routed_to": ["clinician_urgent"],
        "automated_clinical_advice": False,
        "reply_draft": (
            "This may be a medical emergency. Please call 911 "
            "or go to the nearest emergency department. "
            "The clinic has been alerted."
        ),
    }


if __name__ == "__main__":
    examples = [
        "I have crushing chest pain going into my left arm.",
        "I feel really low and don't see the point of anything.",
        "Please refill my medication.",
        "I'm dying to get a physical before my trip lol.",
    ]

    for example in examples:
        print("\nMessage:", example)
        print(classify_urgency(example))
