import os
import sys

# Add parent directory to path to import backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ai.privacy import scrub_pii


def test_scrubber():
    test_cases = [
        {
            "name": "Email Scrubbing",
            "input": "My email is john.doe@example.com and you can reach me there.",
            "contains": "[EMAIL_REDACTED]",
            "excludes": "john.doe@example.com",
        },
        {
            "name": "Phone Scrubbing (Tunisian)",
            "input": "Call me at +216 22 333 444 or 22333444.",
            "contains": "[PHONE_REDACTED]",
            "excludes": "22333444",
        },
        {
            "name": "Address Scrubbing (French Style)",
            "input": "I live at Rue de la Liberte, Tunis 1002.",
            "contains": "[ADDRESS_REDACTED]",
            "excludes": "Rue de la Liberte",
        },
        {
            "name": "Name Scrubbing (Heuristic)",
            "input": "Name: Rayen Mazigh\nRole: Developer",
            "contains": "[NAME_REDACTED]",
            "excludes": "Rayen Mazigh",
        },
    ]

    print("--- PII Scrubber Verification ---")
    all_passed = True
    for tc in test_cases:
        output = scrub_pii(tc["input"])
        passed = (tc["contains"] in output) and (tc["excludes"] not in output)
        status = "PASSED" if passed else "FAILED"
        print(f"[{status}] {tc['name']}")
        if not passed:
            print(f"  Input: {tc['input']}")
            print(f"  Output: {output}")
            all_passed = False

    if all_passed:
        print("\n✅ All PII scrubbing tests passed!")
    else:
        print("\n❌ Some PII scrubbing tests failed.")


if __name__ == "__main__":
    test_scrubber()
