import requests

API_KEY = "0J9ASLD2Lk7evnRUh8SZel6nes69xGSf5ehyh6fe"


def get_nutrition(food_name):

    url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    params = {
        "query": food_name,
        "api_key": API_KEY,
        "pageSize": 1
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "foods" not in data or len(data["foods"]) == 0:
        return None

    food = data["foods"][0]

    calories = None
    protein = None

    for nutrient in food.get("foodNutrients", []):

        if nutrient["nutrientName"] == "Energy":
            calories = nutrient["value"]

        if nutrient["nutrientName"] == "Protein":
            protein = nutrient["value"]

    return {
        "calories": calories,
        "protein": protein
    }