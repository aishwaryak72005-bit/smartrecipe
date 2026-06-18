import os
import requests
import json
from django.conf import settings
from groq import Groq

# Common conversions: amount string to grams
CONVERSIONS = {
    # Eggs
    "1 egg": 50, "2 eggs": 100, "3 eggs": 150, "4 eggs": 200,
    # Spoons
    "1 tsp": 5, "1 tbsp": 15, "2 tbsp": 30, "3 tbsp": 45, "1/2 tsp": 2.5, "1/2 tbsp": 7.5,
    # Cups
    "1 cup rice": 185, "1 cup flour": 120,
    "1 cup milk": 240, "1 cup water": 240,
    "1 cup dal": 200, "1 cup vegetables": 150,
    "1/2 cup": 100, "1/4 cup": 50,
    # Common Indian
    "1 onion": 150, "1 tomato": 100,
    "1 potato": 150, "1 cup paneer": 200,
    "1 piece chicken": 150,
}

USDA_NUTRIENT_IDS = {
    'calories': 1008,
    'protein': 1003,
    'fat': 1004,
    'carbs': 1005,
    'fiber': 1079,
    'sugar': 2000,
    'sodium': 1093,
    'cholesterol': 1253,
    'saturated_fat': 1258
}

groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

_NUTRITION_CACHE_100G = {}

def get_nutrition_for_ingredient(ingredient_name, quantity_grams):
    """
    Fetches nutrition info from USDA FoodData Central.
    Returns dict with keys: calories, protein, fat, carbs, fiber, sugar, sodium, cholesterol, saturated_fat.
    Values are scaled to quantity_grams.
    """
    api_key = getattr(settings, 'USDA_API_KEY', '')
    
    # Default zero structure
    result = {k: 0.0 for k in USDA_NUTRIENT_IDS.keys()}
    result['ingredient'] = ingredient_name
    result['quantity_g'] = quantity_grams
    
    if not api_key:
        return _fallback_groq_nutrition(ingredient_name, quantity_grams, result)

    cache_key = ingredient_name.lower().strip()
    
    # Use cache if available
    if cache_key in _NUTRITION_CACHE_100G:
        food_nutrients = _NUTRITION_CACHE_100G[cache_key]
        for key, n_id in USDA_NUTRIENT_IDS.items():
            per_100g = food_nutrients.get(n_id, 0.0)
            result[key] = round((float(per_100g) / 100.0) * float(quantity_grams), 1)
        return result

    try:
        url = "https://api.nal.usda.gov/fdc/v1/foods/search"
        params = {
            'query': ingredient_name,
            'api_key': api_key,
            'pageSize': 1
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('foods'):
            return _fallback_groq_nutrition(ingredient_name, quantity_grams, result)
            
        food = data['foods'][0]
        food_nutrients = {n['nutrientId']: n['value'] for n in food.get('foodNutrients', [])}
        _NUTRITION_CACHE_100G[cache_key] = food_nutrients
        
        for key, n_id in USDA_NUTRIENT_IDS.items():
            per_100g = food_nutrients.get(n_id, 0.0)
            result[key] = round((float(per_100g) / 100.0) * float(quantity_grams), 1)
            
        return result
        
    except Exception as e:
        print(f"USDA API error for {ingredient_name}: {e}")
        return _fallback_groq_nutrition(ingredient_name, quantity_grams, result)

def _fallback_groq_nutrition(ingredient_name, quantity_grams, default_result):
    """Fallback to Groq if USDA fails or no key."""
    try:
        prompt = (
            f"Give exact nutrition per 100g for '{ingredient_name}' in JSON format with keys: "
            "calories, protein, fat, carbs, fiber, sugar, sodium, cholesterol, saturated_fat. "
            "Only return valid JSON, nothing else."
        )
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        # Find json block
        if "{" in content:
            content = content[content.find("{"):content.rfind("}")+1]
        
        parsed = json.loads(content)
        
        # Save to cache
        cache_key = ingredient_name.lower().strip()
        fake_food_nutrients = {}
        for key, n_id in USDA_NUTRIENT_IDS.items():
            fake_food_nutrients[n_id] = float(parsed.get(key, 0.0))
        _NUTRITION_CACHE_100G[cache_key] = fake_food_nutrients
        
        for key in USDA_NUTRIENT_IDS.keys():
            per_100g = parsed.get(key, 0.0)
            default_result[key] = round((float(per_100g) / 100.0) * float(quantity_grams), 1)
        return default_result
    except Exception as e:
        print(f"Groq API error for {ingredient_name}: {e}")
        
    return default_result

import re
def parse_quantity_to_grams(amount_str):
    """
    Parses a string like '2 eggs' or '400g chicken' into integer grams.
    Uses CONVERSIONS dict first, then regex.
    """
    amount_str = str(amount_str).lower().strip()
    
    # 1. Exact match in conversions
    for key, grams in CONVERSIONS.items():
        if key in amount_str:
            return grams
            
    # 2. Extract explicit grams or kg
    g_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g|gram|grams)', amount_str)
    if g_match:
        return int(float(g_match.group(1)))
        
    kg_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)', amount_str)
    if kg_match:
        return int(float(kg_match.group(1)) * 1000)
        
    ml_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ml|milliliter)', amount_str)
    if ml_match:
        return int(float(ml_match.group(1))) # 1ml ~ 1g for liquids
        
    l_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|liter|litre)', amount_str)
    if l_match:
        return int(float(l_match.group(1)) * 1000)
        
    # Default fallback: assume 100g if we absolutely can't tell
    return 100
