from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SentimentService:
    """VADER emotional tone, not a diagnosis or a measure of clinical risk."""
    POSITIVE_THRESHOLD = 0.05
    NEGATIVE_THRESHOLD = -0.05

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> dict:
        score = self.analyzer.polarity_scores(text)["compound"]
        label = ("positive" if score >= self.POSITIVE_THRESHOLD else
                 "negative" if score <= self.NEGATIVE_THRESHOLD else "neutral")
        return {"label": label, "score": score}
