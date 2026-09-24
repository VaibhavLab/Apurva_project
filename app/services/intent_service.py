import re


class IntentService:
    """Small, transparent topic classifier; replaceable with Rasa NLU."""
    TOPICS = {
        "sleep": r"\b(sleep\w*|insomnia|awake|nightmares?)\b",
        "study": r"\b(exams?|assignments?|study\w*|studying|college|homework|grades?|revision|semester)\b",
        "anxiety": r"\b(anxious|anxiety|panic\w*|worr\w*|nervous|afraid)\b",
        "loneliness": r"\b(alone|lonely|loneliness|isolated|disconnected)\b",
        "anger": r"\b(angry|anger|furious|irritated|frustrat\w*)\b",
        "sadness": r"\b(sad\w*|unhappy|cry\w*|grief|grieving|depressed|heartbroken|hopeless)\b",
        "stress": r"\b(stress\w*|overwhelm\w*|pressure|burnt out|burnout|deadline\w*)\b",
        "motivation": r"\b(motivat\w*|procrastinat\w*|goals?|purpose|productive|stuck)\b",
        "mindfulness": r"\b(mindful\w*|present|meditat\w*)\b",
        "relaxation": r"\b(relax\w*|unwind|calm|rest|breath\w*)\b",
    }
    TITLES = {"study": "Study & Exam Reflection", "sleep": "Finding Better Rest", "anxiety": "Working Through Worry",
              "loneliness": "Feeling Connected", "anger": "Making Space to Pause", "sadness": "A Difficult Day",
              "stress": "Taking the Pressure Off", "motivation": "One Small Step", "mindfulness": "A Mindful Moment",
              "relaxation": "Time to Unwind"}

    def detect_topic(self, text: str) -> str:
        normalized = text.lower()
        return next((topic for topic, pattern in self.TOPICS.items() if re.search(pattern, normalized)), "general")

    def detect_intent(self, text: str) -> str:
        normalized = text.strip().lower().rstrip(".!?")
        if re.fullmatch(r"(hi|hello|hey|good (morning|evening|afternoon))( there)?", normalized):
            return "greet"
        if re.fullmatch(r"(thanks|thank you|thanks a lot|thank you so much)", normalized):
            return "thanks"
        if normalized in ("bye", "goodbye", "see you", "good night"):
            return "goodbye"
        return self.detect_topic(text)

    def title(self, text: str, sentiment: str, risk: str) -> str:
        if risk == "high":
            return "Reaching Out for Support"
        return self.TITLES.get(self.detect_topic(text), "A Good Moment" if sentiment == "positive" else "A Moment to Reflect")
