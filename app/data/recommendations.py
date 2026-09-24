from urllib.parse import urlencode


def resource(title, description, category, query):
    return {"title": title, "description": description, "category": category,
            "url": "https://www.youtube.com/results?" + urlencode({"search_query": query})}


RECOMMENDATIONS = {
    "stress": [resource("5-Minute Breathing Exercise", "A short guided pause to focus on your breathing.", "stress", "NHS breathing exercise stress"),
               resource("Mindfulness for Stress", "Explore a gentle way to step back from a busy day.", "mindfulness", "Oxford mindfulness stress guided practice")],
    "anxiety": [resource("A Grounding Moment", "Follow a guided practice using your surroundings.", "anxiety", "NHS grounding techniques anxiety"),
                resource("Gentle Breathing", "An optional, unhurried breathing practice.", "relaxation", "NHS calming breathing exercise")],
    "sleep": [resource("Wind Down for Sleep", "Explore a quiet, guided bedtime meditation.", "sleep", "UCLA guided sleep meditation"),
              resource("A Healthier Sleep Routine", "Learn about everyday habits that support rest.", "sleep", "NHS sleep routine tips")],
    "sadness": [resource("Practicing Self-Compassion", "Make room for difficult feelings with a kind reflection.", "sadness", "Kristin Neff self compassion guided meditation"),
                resource("A Gentle Mindful Pause", "A brief practice you can take at your own pace.", "mindfulness", "UCLA short mindfulness meditation")],
    "motivation": [resource("Start with One Small Habit", "Explore manageable steps toward a personal goal.", "motivation", "small habits motivation wellbeing"),
                   resource("Positive Reflection", "Make time to notice what matters to you.", "motivation", "gratitude reflection practice Greater Good Science Center")],
    "study": [resource("Study Stress Management", "Ideas for making academic pressure more manageable.", "study", "university student exam stress management"),
              resource("Pomodoro Focus Technique", "Explore focused work sessions with regular breaks.", "study", "university pomodoro study technique"),
              resource("A Short Mindfulness Break", "A small pause between study sessions.", "mindfulness", "UCLA 3 minute breathing meditation")],
    "mindfulness": [resource("A Moment of Mindfulness", "A guided introduction to paying attention to the present.", "mindfulness", "UCLA mindfulness guided meditation beginner")],
    "relaxation": [resource("Relaxing Guided Meditation", "Take an optional pause and unwind at your own pace.", "relaxation", "UCLA guided relaxation meditation")],
    "general": [resource("Everyday Wellbeing", "Explore small, practical ways to care for yourself.", "general", "NHS five steps mental wellbeing")],
    "positive": [resource("Gratitude Practice", "Reflect on a moment you appreciated today.", "mindfulness", "Greater Good Science Center gratitude practice"),
                 resource("Keeping Helpful Habits", "Explore ways to keep making room for what helps.", "motivation", "NHS everyday healthy habits wellbeing")],
}
