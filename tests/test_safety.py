import pytest

from app.services.safety_service import SafetyService
from app.services.chatbot_service import ChatbotService


@pytest.mark.parametrize("text", ["I failed my exam.", "I feel terrible today", "I don't want to hurt myself.",
    "I am not going to kill myself.", "We studied suicide prevention at college", "I feel anxious and lonely"])
def test_ordinary_or_negated_language(text):
    assert SafetyService().analyze(text) == {"risk_level": "normal"}


@pytest.mark.parametrize("text", ["I want to kill myself", "I'm going to hurt myself tonight", "I plan to end my life",
    "I am about to commit suicide", "I don't want to live", "I can’t keep myself safe", "I am suicidal",
    "I took an overdose", "I will take my own life", "I intend to harm myself"])
def test_high_risk_language(text):
    assert SafetyService().analyze(text) == {"risk_level": "high"}


def test_high_risk_overrides_positive_sentiment():
    result = ChatbotService().respond("I am happy but I will kill myself", {"label": "positive"}, "general", "high")
    assert "local emergency services" in result
    assert "cannot provide emergency assistance" in result
