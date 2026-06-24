"""
Travel Advisor Web App
Flask backend serving the UI and handling Claude-powered trip planning.
"""

import json
import os
import anthropic
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

app = Flask(__name__)
CHOICES_FILE = os.path.join(os.path.dirname(__file__), "travel_choices.json")
MODEL = "claude-opus-4-8"


def load_past_bookings() -> dict:
    with open(CHOICES_FILE, "r") as f:
        return json.load(f)


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


@app.route("/")
def index():
    bookings = load_past_bookings()
    return render_template("index.html", past_trips=bookings["past_bookings"])


@app.route("/api/plan", methods=["POST"])
def plan_trip():
    data = request.get_json()
    destination = data.get("destination", "").strip()
    preferences = data.get("preferences", {})

    if not destination:
        return jsonify({"error": "Destination is required"}), 400

    bookings = load_past_bookings()
    bookings_text = json.dumps(bookings, indent=2)

    prefs_text = ""
    if preferences:
        prefs_text = (
            "\n\nAdditional preferences provided by the traveler:\n"
            + "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in preferences.items() if v)
        )

    def generate():
        client = get_client()

        # Step 1: extract profile
        yield "data: __PROFILE_START__\n\n"
        profile_parts = []
        with client.messages.stream(
            model=MODEL,
            max_tokens=1000,
            thinking={"type": "adaptive"},
            messages=[{
                "role": "user",
                "content": (
                    "You are a travel analyst. Analyze these past travel bookings and extract "
                    "a concise traveler profile covering: pace, accommodation style, budget range, "
                    "activity types, dining preferences, transport habits, and overall vibe.\n\n"
                    f"Past bookings:\n{bookings_text}{prefs_text}\n\n"
                    "Return a structured traveler profile summary in clear bullet points."
                ),
            }],
        ) as stream:
            for text in stream.text_stream:
                profile_parts.append(text)
                yield f"data: {json.dumps({'type': 'profile', 'chunk': text})}\n\n"

        profile = "".join(profile_parts)
        yield "data: __PROFILE_END__\n\n"

        # Step 2: generate plan
        yield "data: __PLAN_START__\n\n"
        with client.messages.stream(
            model=MODEL,
            max_tokens=3000,
            thinking={"type": "adaptive"},
            messages=[{
                "role": "user",
                "content": (
                    f"You are an expert personal travel advisor. Based on this traveler profile, "
                    f"create a detailed, day-by-day trip plan for **{destination}** that perfectly matches their style.\n\n"
                    f"Traveler Profile:\n{profile}\n\n"
                    f"Structure your response with clear sections:\n"
                    f"## Trip Overview\n"
                    f"## Best Time to Visit\n"
                    f"## Where to Stay\n"
                    f"## Day-by-Day Itinerary\n"
                    f"## Food & Dining Guide\n"
                    f"## Getting Around\n"
                    f"## Budget Breakdown (USD/day)\n"
                    f"## Personalized Tips\n\n"
                    f"Make it genuinely tailored, not generic."
                ),
            }],
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'type': 'plan', 'chunk': text})}\n\n"

        yield "data: __DONE__\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
