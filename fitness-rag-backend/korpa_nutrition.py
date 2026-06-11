import json
import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use a stable Gemini model
model = genai.GenerativeModel(
    "gemini-2.0-flash",
    generation_config={
        "response_mime_type": "application/json"
    }
)

# Load scraped dataset
with open("foods_dataset.json", "r", encoding="utf-8") as f:
    foods = json.load(f)

for food in foods:

    # Ensure fields exist
    food.setdefault("ingredients", [])
    food.setdefault("allergens", [])

    # Only enrich dishes without nutrition
    if food["calories"] is None:

        dish = food["dish"]
        restaurant = food["restaurant"]

        # Skip garbage entries
        if len(dish) < 3 or "menu" in dish.lower():
            continue

        print(f"Processing: {dish} ({restaurant})")

        prompt = f"""
Estimate nutrition and ingredients for this restaurant dish.

Dish: {dish}

Return ONLY valid JSON in this format:

{{
 "calories": number,
 "protein": number,
 "ingredients": ["ingredient1","ingredient2"],
 "allergens": ["gluten","milk","nuts","eggs","soy","fish","shellfish"]
}}
"""

        try:

            response = model.generate_content(prompt)

            text = response.text.strip()

            # Extract JSON safely
            match = re.search(r"\{.*\}", text, re.DOTALL)

            if match:
                json_text = match.group(0)
                data = json.loads(json_text)
            else:
                raise ValueError("No JSON found in model response")

            food["calories"] = data.get("calories")
            food["protein"] = data.get("protein")
            food["ingredients"] = data.get("ingredients", [])
            food["allergens"] = data.get("allergens", [])

        except Exception as e:
            print("Error:", e)

# Save enriched dataset
with open("foods_dataset_enriched.json", "w", encoding="utf-8") as f:
    json.dump(foods, f, indent=4, ensure_ascii=False)

print("Finished enrichment")