import pytest

from app.services.sentiment_service import SentimentService
from app.services.intent_service import IntentService
from app.services.recommendation_service import RecommendationService


@pytest.mark.parametrize("text,label", [("I feel amazing today", "positive"), ("I feel terrible today", "negative"),
                                        ("I went to college today", "neutral")])
def test_sentiment(text, label):
    result = SentimentService().analyze(text)
    assert result["label"] == label
    assert -1 <= result["score"] <= 1


@pytest.mark.parametrize("text,topic", [("I am stressed about exams", "study"), ("I can't sleep", "sleep"),
    ("I'm anxious", "anxiety"), ("I feel lonely", "loneliness"), ("I'm angry", "anger"),
    ("I have been sad", "sadness"), ("I'm overwhelmed", "stress"), ("I need motivation", "motivation"),
    ("I want to relax", "relaxation"), ("mindfulness", "mindfulness"), ("Hello", "general")])
def test_topics(text, topic):
    assert IntentService().detect_topic(text) == topic


@pytest.mark.parametrize("topic", list(IntentService.TOPICS) + ["general"])
def test_resources_are_bounded_and_safe(topic):
    results = RecommendationService().recommend(topic, "negative")
    assert 1 <= len(results) <= 3
    assert all(item["url"].startswith("https://www.youtube.com/results?search_query=") for item in results)
    assert all(set(item) == {"title", "description", "category", "url"} for item in results)


def test_positive_general_resources():
    results = RecommendationService().recommend("general", "positive")
    assert results[0]["title"] == "Gratitude Practice"
