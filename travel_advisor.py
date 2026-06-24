"""
Personal Travel Advisor Agent
Reads past travel bookings from travel_choices.json, extracts travel preferences
using Claude, then generates a personalized trip plan for a new destination.
"""

import json
import os
import anthropic

CHOICES_FILE = os.path.join(os.path.dirname(__file__), "travel_choices.json")
MODEL = "claude-opus-4-8"


def load_past_bookings() -> dict:
    with open(CHOICES_FILE, "r") as f:
        return json.load(f)


def extract_preferences(client: anthropic.Anthropic, bookings: dict) -> str:
    bookings_text = json.dumps(bookings, indent=2)
    print("Analyzing your past travel bookings...\n")

    with client.messages.stream(
        model=MODEL,
        max_tokens=1500,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": (
                    "You are a travel analyst. Analyze the following past travel bookings "
                    "and extract a concise traveler profile: preferred travel pace, accommodation style, "
                    "budget range, activity types, dining preferences, transport habits, and overall travel vibe.\n\n"
                    f"Past bookings:\n{bookings_text}\n\n"
                    "Return a structured traveler profile summary."
                ),
            }
        ],
    ) as stream:
        preferences = stream.get_final_message().content[-1].text

    return preferences


def generate_trip_plan(client: anthropic.Anthropic, preferences: str, destination: str) -> str:
    print(f"Creating your personalized trip plan for {destination}...\n")

    with client.messages.stream(
        model=MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"You are an expert personal travel advisor. Based on the traveler profile below, "
                    f"create a detailed day-by-day trip plan for {destination} that matches their style.\n\n"
                    f"Traveler Profile:\n{preferences}\n\n"
                    f"Generate a trip plan that includes:\n"
                    f"1. Recommended trip duration\n"
                    f"2. Best time to visit\n"
                    f"3. Accommodation recommendation (matching their style)\n"
                    f"4. Day-by-day itinerary (activities, dining, transport)\n"
                    f"5. Estimated daily budget in USD\n"
                    f"6. 3 personalized tips based on their travel traits\n\n"
                    f"Make it feel genuinely tailored to this traveler, not generic."
                ),
            }
        ],
    ) as stream:
        plan = stream.get_final_message().content[-1].text

    return plan


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY environment variable not set.")

    client = anthropic.Anthropic(api_key=api_key)

    destination = input("Where would you like to travel next? ").strip()
    if not destination:
        print("No destination provided. Exiting.")
        return

    bookings = load_past_bookings()
    print(f"\nFound {len(bookings['past_bookings'])} past trips in your travel history.\n")

    preferences = extract_preferences(client, bookings)
    print("── Your Traveler Profile ──────────────────────────────────")
    print(preferences)
    print()

    trip_plan = generate_trip_plan(client, preferences, destination)
    print(f"── Your Personalized Trip Plan: {destination} ──────────────")
    print(trip_plan)
    print()


if __name__ == "__main__":
    main()
