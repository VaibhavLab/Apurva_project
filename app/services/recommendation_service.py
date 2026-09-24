from app.data.recommendations import RECOMMENDATIONS


class RecommendationService:
    MAX_RESOURCES = 3

    def recommend(self, topic: str, sentiment: str) -> list[dict]:
        category = {"loneliness": "sadness", "anger": "relaxation"}.get(topic, topic)
        if category == "general" and sentiment == "positive":
            category = "positive"
        elif category == "general" and sentiment == "negative":
            category = "sadness"
        return [dict(item) for item in RECOMMENDATIONS.get(category, RECOMMENDATIONS["general"])][:self.MAX_RESOURCES]
