from typing import Optional
import re

class AgreementDetector:
    """
    Detects which pension agreement the user is referring to based on input text.
    """

    def __init__(self):
        self.known_agreements = ["PA16", "SKR2023", "ITP1", "ITP2", "KAP-KL"]

    def detect(self, message: str) -> Optional[str]:
        """
        Scan user message and return the matched agreement if found.
        """
        message_lower = message.lower()
        for agreement in self.known_agreements:
            if agreement.lower() in message_lower:
                return agreement

        # Try fallback with fuzzy matching (e.g. 'pa 16' with space)
        if "pa 16" in message_lower:
            return "PA16"

        return None


# Example usage (can be removed in production):
if __name__ == "__main__":
    detector = AgreementDetector()
    test_input = "Vad gäller efterlevnadsskydd i PA16 avdelning 2?"
    print("🔍 Agreement detected:", detector.detect(test_input))
