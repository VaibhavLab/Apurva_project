from app.services.intent_service import IntentService


class ChatbotService:
    """Local response selection. Rasa is optional and is not called by this engine."""
    SAFETY_RESPONSE = (
        "I'm concerned about what you've shared, and I'm glad you reached out. "
        "If you may be in immediate danger, please contact local emergency services or a crisis-support service now. "
        "If possible, reach out to someone you trust and stay with another person. "
        "This chatbot cannot provide emergency assistance."
    )
    OPENINGS = {
        "negative": ["That sounds difficult to carry. Thank you for sharing it.", "It sounds like this has been weighing on you.",
                     "There is room here to talk about what's been difficult."],
        "positive": ["It's good to hear there's something positive in your day.", "That sounds like a moment worth appreciating.",
                     "Thank you for sharing that bright spot."],
        "neutral": ["I'm here to listen.", "Thank you for sharing what's on your mind.", "We can take this at your pace."],
    }
    RESPONSES = {
        "stress": ["A short pause and one manageable next step may help. What's taking up the most space in your mind?",
                   "You don't have to work through everything at once. Is there one thing you could set aside for a moment?"],
        "study": ["Academic demands can take a lot of energy. Would breaking one task into a small next step feel useful?",
                  "A short break can give you room to reset. Which part of your studies would you like to talk about?"],
        "sleep": ["What have your evenings been like lately? A gentle wind-down routine may be worth exploring.",
                  "Rest can be difficult when your mind is busy. Is there something keeping you awake? If sleep problems persist, a healthcare professional can help."],
        "anxiety": ["If it feels comfortable, take a moment to notice your surroundings. What is worrying you most right now?",
                    "We can focus on one concern at a time. Would you like to talk about what brought this feeling on?"],
        "loneliness": ["Feeling disconnected can be hard. Is there someone you would feel comfortable reaching out to, even briefly?",
                       "You deserve connection. What kind of company or support would feel helpful today?"],
        "sadness": ["You don't need to force yourself to feel differently. Would you like to share what has been happening?",
                    "A small act of care might be enough for now. What usually helps you feel a little supported?"],
        "anger": ["Giving yourself a little space before responding can help. What happened from your perspective?",
                  "Would a short pause feel useful before we explore what's been frustrating you?"],
        "motivation": ["A very small first step still counts. What's one thing you'd like to move toward?",
                       "What would a manageable version of your goal look like today?"],
        "mindfulness": ["If you like, notice one sound and one thing you can see. How does this moment feel?",
                        "There is no need to get a practice perfect. Would a short guided pause interest you?"],
        "relaxation": ["You can give yourself permission to slow down. What helps you unwind?",
                       "A quiet moment can be a place to start. Would you like to explore a short relaxation resource?"],
        "general": ["Would you like to tell me a little more about your day?", "What feels most useful to talk about right now?",
                    "Would you prefer to reflect on a moment, or explore a small next step?"],
    }

    def respond(self, text: str, sentiment: dict, topic: str, risk_level: str, turn: int = 0) -> str:
        if risk_level == "high":
            return self.SAFETY_RESPONSE
        intent = IntentService().detect_intent(text)
        simple = {"greet": ["Hello. I'm MindCare, a wellness-support chatbot. How are you feeling today?",
                            "Hi there. You can share what's on your mind, at your own pace."],
                  "thanks": ["You're welcome. We can keep talking whenever you're ready.", "Thank you for taking a moment for yourself. What would feel helpful next?"],
                  "goodbye": ["Take care of yourself. You can return to this conversation whenever you like.", "Thank you for sharing this time. Take things at your own pace."]}
        if intent in simple:
            return simple[intent][turn % len(simple[intent])]
        openings = self.OPENINGS[sentiment["label"]]
        responses = self.RESPONSES.get(topic, self.RESPONSES["general"])
        if sentiment["label"] == "positive" and topic == "general":
            responses = ["What made that moment meaningful for you?", "Is there something from today you'd like to make more time for?"]
        return openings[turn % len(openings)] + " " + responses[turn % len(responses)]
