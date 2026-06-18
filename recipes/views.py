from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from groq import Groq
from .models import SavedRecipe, MealPlan, DailyRequestLog, UserProfile, MacroLog, RecipeHistory

def is_user_premium(user):
    if user.is_superuser:
        return True
    try:
        if hasattr(user, 'profile') and user.profile.is_premium:
            return True
    except Exception:
        pass
    return False
import os
import requests
import urllib.parse as _urlparse
import urllib.request
import json
import re
from dotenv import load_dotenv

from .nutrition_service import get_nutrition_for_ingredient, parse_quantity_to_grams

load_dotenv()

client = Groq(api_key=os.getenv('GROQ_API_KEY'))

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def call_gemini_api(prompt, system_instruction="", max_tokens=1200, temperature=0.7):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }
    
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    except Exception as e:
        print(f"Gemini API Error: {e}")
        # Fallback to Groq
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction or "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=15
        )
        return response.choices[0].message.content



def get_youtube_videos(search_query):
    try:
        api_key = os.getenv('YOUTUBE_API_KEY')
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": search_query + " Indian recipe cooking",
            "key": api_key,
            "maxResults": 6,
            "type": "video",
            "videoEmbeddable": "true",
            "relevanceLanguage": "en",
        }
        response = requests.get(url, params=params)
        data = response.json()
        videos = []
        for item in data.get("items", []):
            videos.append({
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                "video_id": item["id"]["videoId"],
                "channel": item["snippet"]["channelTitle"],
            })
        return videos[:3]
    except Exception as e:
        return []

import re

def scrape_bing_image(query):
    """Scrapes Bing Images for a highly accurate recipe photo."""
    try:
        # Force food/dish context strongly
        safe_query = _urlparse.quote(f'"{query}" indian food recipe plated dish -animal -bird -farm')
        url = f"https://www.bing.com/images/search?q={safe_query}&form=HDRSC2&qft=+filterui:photo-photo"
        
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            html = response.read().decode('utf-8')
            matches = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
            
            # Skip first 2 only, but validate more strictly
            for match in matches[2:12]:  # check up to 12 results
                if (match.startswith('http') and 
                    any(ext in match.lower() for ext in ['jpg', 'png', 'jpeg']) and
                    # Skip common wrong domains
                    not any(bad in match for bad in ['wikimedia', 'wikipedia', 'alamy', 'shutterstock'])):
                    return match
    except Exception as e:
        print(f"Bing Scrape Error: {e}")
    return None

def search_pexels(query):
    """Searches Pexels API for a high-quality stock photo of the food."""
    try:
        url = f"https://api.pexels.com/v1/search?query={_urlparse.quote(query + ' food')}&per_page=1"
        req = urllib.request.Request(
            url, 
            headers={'Authorization': 'kCoZacsyijtocE2EJeO2F0MjXQ3Ed5O1LrIW606rzzZ2BUd8AEwJjFK4'}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data and data.get('photos'):
                print(f"Pexels hit for query: '{query}'")
                return data['photos'][0]['src']['large']
    except Exception as e:
        print(f"Pexels Error: {e}")
    return None


def search_themealdb(query):
    """Try TheMealDB with multiple query strategies."""
    # Strategy 1: full name
    # Strategy 2: first main ingredient only  
    # Strategy 3: simplified name
    queries_to_try = [
        query,
        query.split(' and ')[0],           # "Chicken and Egg Curry" → "Chicken"
        query.replace(' and ', ' '),        # "Chicken Egg Curry"
        ' '.join(query.split()[:2]),        # First 2 words only
    ]
    
    for q in queries_to_try:
        try:
            meal_url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={_urlparse.quote(q)}"
            req = urllib.request.Request(meal_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                if data and data.get('meals'):
                    print(f"TheMealDB hit for query: '{q}'")
                    return data['meals'][0]['strMealThumb']
        except Exception:
            continue
    return None


def get_wiki_image(query):
    """
    Image fetching has been disabled per user request.
    """
    return ""



# Per-recipe visual identity (emoji + gradient fallback when no photo found)
DISH_EMOJIS = ['🍛', '🥘', '🍜', '🥗', '🍚', '🥙', '🍲', '🫕', '🥞', '🍱', '🥣', '🧆']
DISH_GRADIENTS = [
    'linear-gradient(145deg,#7c3aed 0%,#a855f7 50%,#ec4899 100%)',
    'linear-gradient(145deg,#f59e0b 0%,#ef4444 100%)',
    'linear-gradient(145deg,#10b981 0%,#0ea5e9 100%)',
    'linear-gradient(145deg,#6366f1 0%,#ec4899 100%)',
    'linear-gradient(145deg,#d97706 0%,#f59e0b 50%,#fbbf24 100%)',
    'linear-gradient(145deg,#0f2027 0%,#203a43 50%,#2c5364 100%)',
    'linear-gradient(145deg,#134e5e 0%,#71b280 100%)',
    'linear-gradient(145deg,#c94b4b 0%,#4b134f 100%)',
]

# ── Realistic Indian Grocery Price Database (2024 market rates) ──────────────
INDIAN_GROCERY_PRICES = {
    # Oils & Fats
    'oil': 180, 'cooking oil': 180, 'sunflower oil': 180, 'mustard oil': 150,
    'groundnut oil': 200, 'coconut oil': 220, 'ghee': 550, 'butter': 55,
    'refined oil': 180, 'vegetable oil': 175,
    # Vegetables
    'onion': 40, 'tomato': 30, 'potato': 25, 'garlic': 60, 'ginger': 80,
    'green chilli': 30, 'capsicum': 50, 'carrot': 40, 'peas': 60,
    'spinach': 30, 'palak': 30, 'cauliflower': 40, 'broccoli': 60,
    'cabbage': 25, 'brinjal': 30, 'eggplant': 30, 'okra': 40, 'bhindi': 40,
    'lady finger': 40, 'bitter gourd': 35, 'bottle gourd': 20, 'lemon': 5,
    'lime': 5, 'curry leaves': 15, 'coriander leaves': 15, 'mint': 20,
    'drumstick': 50, 'raw banana': 25, 'corn': 20, 'mushroom': 80,
    'beans': 50, 'french beans': 50, 'cluster beans': 40,
    # Pulses & Lentils
    'dal': 120, 'toor dal': 130, 'moong dal': 120, 'chana dal': 110,
    'urad dal': 130, 'masoor dal': 100, 'rajma': 130, 'kidney beans': 130,
    'black gram': 130, 'green gram': 110, 'moong': 110, 'lentils': 120,
    'chickpeas': 120, 'chana': 80, 'black chana': 80, 'white chana': 100,
    'kabuli chana': 120,
    # Rice & Grains
    'rice': 60, 'basmati rice': 100, 'brown rice': 90, 'wheat': 35,
    'wheat flour': 45, 'atta': 45, 'maida': 40, 'semolina': 50, 'suji': 50,
    'rava': 50, 'poha': 60, 'oats': 120, 'barley': 70, 'ragi': 90,
    'jowar': 60, 'bajra': 50, 'cornflour': 60, 'besan': 80, 'gram flour': 80,
    # Dairy
    'milk': 25, 'curd': 30, 'yogurt': 30, 'paneer': 90, 'cheese': 200,
    'cream': 50, 'khoya': 180, 'mawa': 180, 'condensed milk': 110,
    'buttermilk': 20, 'chaas': 20,
    # Meat, Fish & Eggs
    'egg': 8, 'eggs': 8, 'chicken': 200, 'mutton': 700, 'fish': 250,
    'prawn': 350, 'shrimp': 350, 'tuna': 120,
    # Spices (small packs/sachets)
    'turmeric': 20, 'haldi': 20, 'cumin': 30, 'jeera': 30,
    'coriander powder': 25, 'dhania': 20, 'red chilli powder': 30,
    'chilli powder': 30, 'garam masala': 35, 'pepper': 30,
    'black pepper': 30, 'cardamom': 70, 'elaichi': 70, 'cloves': 50,
    'lavang': 50, 'cinnamon': 30, 'dalchini': 30, 'bay leaf': 20,
    'tej patta': 20, 'mustard seeds': 25, 'rai': 25, 'fennel seeds': 30,
    'saunf': 30, 'fenugreek seeds': 25, 'methi seeds': 25, 'ajwain': 25,
    'carom seeds': 25, 'asafoetida': 30, 'hing': 30, 'star anise': 40,
    'saffron': 250, 'kesar': 250, 'nutmeg': 40, 'jaiphal': 40,
    'mace': 50, 'paprika': 30, 'kashmiri chilli': 40, 'chaat masala': 30,
    'sambar powder': 40, 'rasam powder': 35, 'biryani masala': 50,
    'curry powder': 40, 'kitchen king masala': 40, 'pav bhaji masala': 35,
    # Dry Fruits & Nuts
    'cashew': 700, 'cashews': 700, 'almond': 900, 'almonds': 900,
    'raisin': 200, 'raisins': 200, 'peanut': 100, 'peanuts': 100,
    'walnut': 800, 'pistachios': 1200, 'dates': 200,
    # Sugar & Sweeteners
    'sugar': 45, 'jaggery': 60, 'gur': 60, 'honey': 250,
    'brown sugar': 80, 'powdered sugar': 50,
    # Sauces & Condiments
    'tomato sauce': 80, 'soy sauce': 70, 'vinegar': 40,
    'tamarind': 50, 'imli': 50, 'kokum': 60,
    # Staples
    'salt': 20, 'bread': 50, 'pav': 35, 'roti': 10,
    'water': 0, 'ice': 10,
}

def get_ingredient_price(ingredient_name):
    """Look up realistic market price for an ingredient."""
    name = ingredient_name.lower().strip()
    # Direct match
    if name in INDIAN_GROCERY_PRICES:
        return INDIAN_GROCERY_PRICES[name]
    # Partial match — find if any known key is contained in the ingredient name
    for key, price in INDIAN_GROCERY_PRICES.items():
        if key in name or name in key:
            return price
    return None  # Unknown ingredient, keep AI's estimate



def get_nutrition_info(recipe_name, ingredients_list, serving_size):
    """Get nutritional info for a recipe using Groq AI."""
    try:
        prompt = f"""
Give the approximate nutritional information for one serving of "{recipe_name}".
Ingredients used: {ingredients_list}
Serving size: {serving_size} people (calculate per 1 serving)

Reply ONLY in this exact format, nothing else:
Calories: [number] kcal
Protein: [number] g
Carbohydrates: [number] g
Fat: [number] g
Fiber: [number] g
Sodium: [number] mg
Health Score: [number between 1-10]
Health Note: [one short sentence about this dish health-wise]
"""
        system_instruction = "You are a nutritionist. Reply only in the exact format given."
        
        text = call_gemini_api(prompt, system_instruction, max_tokens=200, temperature=0.3)
        if not text:
            return None
        info = {}
        for line in text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, _, val = line.partition(':')
                info[key.strip()] = val.strip()
        return {
            'calories': info.get('Calories', 'N/A'),
            'protein': info.get('Protein', 'N/A'),
            'carbs': info.get('Carbohydrates', 'N/A'),
            'fat': info.get('Fat', 'N/A'),
            'fiber': info.get('Fiber', 'N/A'),
            'sodium': info.get('Sodium', 'N/A'),
            'health_score': info.get('Health Score', '7'),
            'health_note': info.get('Health Note', ''),
        }
    except Exception:
        return None


import re
def parse_recipes(ai_response):
    recipes = []
    # Robustly split by "RECIPE 1:", "RECIPE 1.", "**RECIPE 1**", etc.
    parts = re.split(r'\*?\*?RECIPE\s*\d+[:.]?\*?\*?\s*', ai_response, flags=re.IGNORECASE)
    colors = [
        'linear-gradient(135deg,#7c3aed,#a855f7)',
        'linear-gradient(135deg,#ec4899,#f472b6)',
        'linear-gradient(135deg,#6366f1,#818cf8)',
    ]
    emojis = ['🍛', '🥘', '🍜']

    for i, part in enumerate(parts[1:]):
        try:
            lines = part.strip().split('\n')
            recipe = {
                'number': i + 1,
                'color': colors[i % len(colors)],
                'emoji': emojis[i % len(emojis)],
                'name': '',
                'description': '',
                'cost': '',
                'restaurant_price': '',
                'budget_score': '',
                'difficulty': 'Medium',
                'servings': '2',
                'why_this_recipe': '',
                'time': '',
                'ingredients': [],
                'instructions': [],
                'missing': [],
                'dietary_preference': [],
                'tips': 'No tips available.',
                'variations': 'No variations available.',
            }
            section = ''
            for line in lines:
                line = line.replace('**', '').replace('*', '').strip()
                if not line:
                    continue
                if 'Name:' in line:
                    recipe['name'] = line.split('Name:')[1].strip()
                elif 'Description:' in line:
                    recipe['description'] = line.split('Description:')[1].strip()
                elif 'Estimated Cost:' in line:
                    recipe['cost'] = line.split('Estimated Cost:')[1].strip()
                elif 'Restaurant Price:' in line:
                    recipe['restaurant_price'] = line.split('Restaurant Price:')[1].strip()
                elif 'Budget Score:' in line:
                    recipe['budget_score'] = line.split('Budget Score:')[1].strip()
                elif 'Difficulty Level:' in line:
                    recipe['difficulty'] = line.split('Difficulty Level:')[1].strip()
                elif 'Servings:' in line:
                    recipe['servings'] = line.split('Servings:')[1].strip()
                elif 'Why this recipe:' in line:
                    recipe['why_this_recipe'] = line.split('Why this recipe:')[1].strip()
                elif 'Cooking Time:' in line:
                    recipe['time'] = line.split('Cooking Time:')[1].strip()
                elif 'Ingredients Needed' in line:
                    section = 'ingredients'
                elif 'Instructions' in line:
                    section = 'instructions'
                elif 'Missing Ingredients' in line:
                    section = 'missing'
                elif line.startswith('-') and section == 'ingredients':
                    ingredient = line[1:].strip()
                    has_it = '✅' in ingredient or 'have it' in ingredient.lower()
                    
                    if '|' in ingredient:
                        ing_parts = [p.strip() for p in ingredient.split('|')]
                        ing_name = ing_parts[0].replace('✅', '').replace('❌', '').strip()
                        measurement = ing_parts[1] if len(ing_parts) > 1 else ""
                        recipe['ingredients'].append({
                            'text': ing_name,
                            'measurement': measurement,
                            'have': has_it,
                        })
                    else:
                        # Fallback for old recipes
                        recipe['ingredients'].append({
                            'text': ingredient.replace('✅', '').replace('❌', '').strip(),
                            'measurement': '',
                            'have': has_it,
                        })
                elif line and line[0].isdigit() and section == 'instructions':
                    recipe['instructions'].append(line)
                elif line.startswith('-') and section == 'missing':
                    raw = line[1:].strip()
                    # Strip AI-guessed price from the ingredient name e.g. "Oil - ₹10"
                    name_part = raw.split('-')[0].split('₹')[0].strip()
                    if name_part.lower() != 'none':
                        try:
                            real_price = get_ingredient_price(name_part)
                            if real_price is not None:
                                display = f"{name_part} - ₹{real_price}"
                            else:
                                display = raw
                        except Exception:
                            display = raw
                        recipe['missing'].append(display)
                elif 'Nutritional Info' in line:
                    try:
                        # Split by the first colon to get the data part
                        data_part = line.split(':', 1)[1]
                        nutri_parts = data_part.split('|')
                        
                        def extract_num(text):
                            nums = re.findall(r'\d+', text)
                            return nums[0] if nums else '0'

                        recipe['nutrition'] = {
                            'calories': extract_num(nutri_parts[0]) if len(nutri_parts) > 0 else '0',
                            'protein': extract_num(nutri_parts[1]) if len(nutri_parts) > 1 else '0',
                            'carbs': extract_num(nutri_parts[2]) if len(nutri_parts) > 2 else '0',
                            'fat': extract_num(nutri_parts[3]) if len(nutri_parts) > 3 else '0',
                        }
                    except:
                        recipe['nutrition'] = None
                elif 'Dietary Preference:' in line:
                    raw_pref = line.split('Dietary Preference:')[1].strip()
                    recipe['dietary_preference'] = [p.strip() for p in raw_pref.split(',') if p.strip()]
                elif 'Tips:' in line:
                    recipe['tips'] = line.split('Tips:')[1].strip()
                elif 'Variations:' in line:
                    recipe['variations'] = line.split('Variations:')[1].strip()
                elif 'AI Taste Score:' in line:
                    recipe['rating'] = line.split('AI Taste Score:')[1].strip()

            if recipe['name']:
                try:
                    recipe['image_url'] = get_wiki_image(recipe['name'])
                except:
                    recipe['image_url'] = ''

                # Clean up cost
                cost_str = recipe.get('cost', '')
                cost_clean = re.sub(r'[^\d]', '', cost_str)
                if cost_clean:
                    recipe['cost'] = cost_clean
                else:
                    recipe['cost'] = cost_str.replace('₹', '').replace('Rs.', '').replace('Rs', '').replace('INR', '').strip()

                # Clean up restaurant price
                rest_str = recipe.get('restaurant_price', '')
                rest_clean = re.sub(r'[^\d]', '', rest_str)
                if rest_clean:
                    recipe['restaurant_price'] = rest_clean
                else:
                    recipe['restaurant_price'] = rest_str.replace('₹', '').replace('Rs.', '').replace('Rs', '').replace('INR', '').strip()

                # Calculate a fallback restaurant price in Python if not present
                try:
                    cost_val = int(recipe['cost'])
                except ValueError:
                    digits = re.findall(r'\d+', recipe['cost'])
                    cost_val = int(digits[0]) if digits else 0

                if (not recipe['restaurant_price'] or recipe['restaurant_price'] == '') and cost_val > 0:
                    recipe['restaurant_price'] = str(cost_val + 50)

                recipes.append(recipe)
        except Exception as e:
            print(f"Error parsing recipe {i}: {e}")
            continue

    # Even if recipes is empty, return what we have (could be empty list)
    return recipes


@login_required(login_url='/login/')
def home_view(request):
    return render(request, 'recipes/home.html')


@login_required(login_url='/login/')
def suggest_view(request):
    quick_ingredients = {
        '🧅 Vegetables': [
            'Onion', 'Tomato', 'Potato', 'Garlic', 'Ginger',
            'Green Chilli', 'Capsicum', 'Carrot', 'Peas', 'Spinach',
            'Cauliflower', 'Cabbage', 'Brinjal', 'Okra / Bhindi',
            'Bitter Gourd', 'Bottle Gourd', 'Mushroom', 'Corn',
            'Coriander Leaves', 'Curry Leaves', 'Mint', 'Drumstick',
            'Zucchini', 'Broccoli', 'Bell Pepper', 'Sweet Potato',
            'Pumpkin', 'Radish', 'Beetroot', 'Spring Onion',
        ],
        '🫘 Dal & Lentils': [
            'Toor Dal', 'Moong Dal', 'Chana Dal', 'Urad Dal',
            'Masoor Dal', 'Rajma', 'Chickpeas', 'Whole Moong',
            'Black Chana', 'Green Moong', 'Lentils', 'Kidney Beans',
        ],
        '🌾 Grains & Flour': [
            'Rice', 'Basmati Rice', 'Wheat / Atta', 'Maida',
            'Semolina / Suji', 'Poha', 'Oats', 'Besan',
            'Ragi', 'Cornflour', 'Bread', 'Pav',
            'Quinoa', 'Millet', 'Brown Rice', 'Rice Flour',
        ],
        '🍝 Pasta & Noodles': [
            'Spaghetti', 'Macaroni', 'Penne', 'Instant Noodles',
            'Rice Noodles', 'Hakka Noodles', 'Pasta', 'Vermicelli',
        ],
        '🍞 Bakery': [
            'White Bread', 'Brown Bread', 'Burger Buns',
            'Pizza Base', 'Tortilla / Wrap', 'Croissant',
        ],
        '🥛 Dairy': [
            'Milk', 'Curd / Yogurt', 'Paneer', 'Butter',
            'Ghee', 'Cream', 'Cheese', 'Buttermilk',
            'Khoya / Mawa', 'Condensed Milk', 'Mozzarella',
        ],
        '🍗 Protein': [
            'Egg', 'Chicken', 'Mutton', 'Fish',
            'Prawn', 'Soya Chunks', 'Tofu',
            'Peanuts', 'Cashews', 'Almonds',
            'Bacon', 'Beef', 'Pork', 'Sausage',
        ],
        '🌶️ Spices': [
            'Salt', 'Turmeric', 'Red Chilli Powder', 'Cumin / Jeera',
            'Coriander Powder', 'Garam Masala', 'Mustard Seeds',
            'Black Pepper', 'Cardamom', 'Cloves', 'Cinnamon',
            'Bay Leaf', 'Hing / Asafoetida', 'Fennel Seeds',
            'Chaat Masala', 'Sambar Powder', 'Biryani Masala',
            'Oregano', 'Chilli Flakes', 'Mixed Herbs', 'Paprika',
        ],
        '🥫 Sauces': [
            'Tomato Ketchup', 'Mayonnaise', 'Soy Sauce',
            'Chilli Sauce', 'Schezwan Sauce', 'Pizza Sauce',
            'Mustard Sauce', 'Pasta Sauce', 'Peanut Butter',
        ],
        '🫙 Pantry Staples': [
            'Cooking Oil', 'Sunflower Oil', 'Mustard Oil', 'Coconut Oil',
            'Sugar', 'Jaggery / Gur', 'Honey', 'Tamarind',
            'Tomato Sauce', 'Soy Sauce', 'Vinegar',
            'Olive Oil', 'Sesame Oil',
        ],
        '🧂 Basic Pantry': [
            'Salt', 'Cooking Oil', 'Turmeric', 'Red Chilli Powder',
            'Cumin / Jeera', 'Mustard Seeds', 'Coriander Powder',
            'Garam Masala', 'Hing / Asafoetida', 'Black Pepper',
            'Bay Leaf', 'Water', 'Ghee', 'Butter',
        ],
    }
    quick_budgets = [50, 100, 150, 200, 500]


    if request.method == 'POST':
        ingredients = request.POST.get('ingredients', '')
        budget = request.POST.get('budget', '')
        serving_size = request.POST.get('serving_size', '2')
        cuisine = request.POST.get('cuisine', 'any')

        cuisine_map = {
            'any': 'Any Indian cuisine',
            'south_indian': 'South Indian',
            'north_indian': 'North Indian',
            'street_food': 'Indian Street Food',
            'healthy': 'Healthy Indian',
            'quick': 'Quick Indian (under 20 minutes)',
        }
        cuisine_text = cuisine_map.get(cuisine, 'Any Indian cuisine')

        meal_type   = request.POST.get('meal_type', 'any')
        spice_level = request.POST.get('spice_level', 'any')
        diet_pref   = request.POST.get('diet_pref', 'any')

        # Build extra context strings
        meal_text  = '' if meal_type  == 'any' else f'Meal type: {meal_type.replace("_"," ").title()}.'
        spice_text = '' if spice_level == 'any' else f'Spice level: {spice_level.replace("_"," ").title()}.'
        diet_text  = '' if diet_pref  == 'any' else f'Diet preference: {diet_pref.replace("_"," ").title()}.'

        # Strict dietary rules per cuisine/festival
        DIETARY_RULES = {
            # Festivals
            'navratri':  '🚨 STRICT: Navratri Vrat. NO meat/fish/eggs/onion/garlic/wheat/regular rice. Only sabudana, kuttu, singhare ka atta, samak rice, sendha namak, potatoes, peanuts, dairy, fruits, vrat vegetables.',
            'diwali':    '🚨 STRICT: Diwali. NO meat/chicken/fish/eggs. 100% pure vegetarian only. Festive sweets, namkeen, and veg curries.',
            'holi':      '🚨 STRICT: Holi. NO meat/fish/eggs. Vegetarian only — gujiya, thandai, dahi bhalle, dal baati.',
            'ganesh':    '🚨 STRICT: Ganesh Chaturthi. Pure vegetarian. Focus on modak, puran poli, panchamrit, and Maharashtrian prasad dishes.',
            'pongal':    '🚨 STRICT: Pongal/Sankranti. Vegetarian. Focus on pongal, sakkarai pongal, sesame sweets, ellu bella, til ladoo.',
            'onam':      '🚨 STRICT: Onam Sadya. Strictly vegetarian Kerala feast. Include avial, olan, sambar, payasam, thoran, pachadi, pappadam.',
            'raksha':    '🚨 STRICT: Raksha Bandhan. Focus on sweets and festive snacks: kheer, halwa, barfi, ladoo, gulab jamun.',
            'baisakhi':  'Baisakhi harvest festival. Punjabi food preferred — sarson da saag, makki di roti, lassi, pinni, churma.',
            'christmas': 'Christmas special. Include plum cake, biryani, roast dishes, wine cake, fruit pudding, coconut sweets.',
            'eid':       'Eid Mubarak! Traditional Eid non-veg dishes welcome: biryani, korma, nihari, haleem, sheer khurma, seviyan.',
            # Regions
            'gujarati':  '🚨 STRICT: Gujarati cuisine. NO meat/fish/eggs. Prefer no onion/garlic. Dhokla, thepla, kadhi, dal dhokli.',
            'jain':      '🚨 STRICT: Jain diet. NO meat/fish/eggs/onion/garlic/potatoes/root vegetables. Only above-ground vegetables.',
            'vegan':     '🚨 STRICT: Vegan diet. NO meat/fish/eggs/dairy/honey. Only plant-based ingredients.',
            'diabetic':  '🚨 STRICT: Diabetic-friendly. Low sugar, low refined carbs, no deep frying, no maida. Prefer whole grains, dal, vegetables.',
            'south_indian': 'South Indian. Prefer vegetarian. Use coconut, curry leaves, mustard seeds, tamarind, sambar, rasam.',
            'kerala':    'Kerala cuisine. Coconut-based gravies, fish curry (meen curry), appam, puttu, sadya dishes.',
            'chettinad': 'Chettinad Tamil Nadu. Known for bold spices — kalpasi, marathi mokku, star anise. Can include non-veg.',
            'andhra':    'Andhra cuisine. Very spicy! Gongura, pesarattu, pulusu, biryani. Can include non-veg.',
            'karnataka': 'Karnataka cuisine. Bisi bele bath, ragi mudde, vangi bath, masala dosa.',
            'north_indian': 'North Indian style. Dal makhani, paneer, rajma, naan, roti. Veg or non-veg.',
            'punjabi':   'Punjabi cuisine. Sarson da saag, butter chicken, lassi, makki roti, chole bhature.',
            'rajasthani':'Rajasthani cuisine. Dal baati churma, gatte ki sabzi, ker sangri, bajra roti, laal maas.',
            'kashmiri':  'Kashmiri cuisine. Rogan josh, dum aloo, haak, modur pulao, shufta.',
            'bihari':    'Bihari cuisine. Litti chokha, sattu paratha, dal peetha, khaja.',
            'bengali':   'Bengali cuisine. Fish dishes are traditional and encouraged. Hilsa, doi maach, mishti doi, sandesh, rasgulla.',
            'odia':      'Odia cuisine. Dalma, pakhala bhat, chhena poda, santula.',
            'maharashtrian': 'Maharashtrian cuisine. Misal pav, vada pav, puran poli, aamti, bhakri.',
            'goan':      'Goan cuisine. Fish curry rice, vindaloo, sorpotel, bebinca, feni-based dishes.',
            'hyderabadi':'Hyderabadi cuisine. Dum biryani, haleem, mirchi ka salan, double ka meetha.',
            'mughlai':   'Mughlai cuisine. Biryani, korma, nihari, shahi tukda, kebabs.',
            'healthy':   '🚨 STRICT: Healthy only. No deep frying, no excess oil, no refined sugar. Grilling, steaming, or light sautéing preferred.',
            'quick':     '🚨 STRICT: Under 20 minutes cooking time only. No slow-cooking.',
            'street_food': 'Indian street food. Chaat, pav bhaji, golgappa, bhel puri, kachori, samosa, dabeli.',
        }
        diet_rule = DIETARY_RULES.get(cuisine, '')

        # Diet preference override (stricter than cuisine sometimes)
        DIET_OVERRIDES = {
            'vegetarian': '🚨 ALSO STRICT: User wants VEGETARIAN only. NO meat/chicken/fish/eggs.',
            'vegan':      '🚨 ALSO STRICT: User wants VEGAN only. NO meat/fish/eggs/dairy/honey.',
            'non_veg':    'User prefers non-vegetarian recipes. Include meat/chicken/fish options.',
            'eggetarian': 'User is eggetarian. Eggs are allowed but NO meat or fish.',
            'jain':       '🚨 ALSO STRICT: Jain diet. NO meat/fish/eggs/onion/garlic/root vegetables.',
            'diabetic':   '🚨 ALSO STRICT: Diabetic-friendly. Low sugar, low carb, no maida, no deep frying.',
            'high_protein': 'Focus on high-protein ingredients: dal, paneer, chicken, eggs, soy, sprouts.',
        }
        diet_override = DIET_OVERRIDES.get(diet_pref, '')

        assume_pantry = request.POST.get('assume_pantry', 'no')
        pantry_rule = ""
        if assume_pantry == 'yes':
            pantry_rule = "3. PANTRY STAPLES: Assume the user already has basic items like salt, cooking oil, water, turmeric, and basic Indian spices. Do not account for their cost."

        prompt = f"""
You are a helpful Indian recipe assistant.

USER'S INVENTORY & CONSTRAINTS:
Available Ingredients: {ingredients}
Max Budget: ₹{budget}
Serving Size: {serving_size} people

{meal_text}
{spice_text}
{diet_rule}
{diet_override}
{diet_text}

CRITICAL RULES:
1. STRICT BUDGET: Every single dish suggested MUST have an estimated cost less than or equal to ₹{budget}. DO NOT suggest dishes that exceed the budget.
2. AVAILABLE INGREDIENTS: The dishes should primarily use the 'Available Ingredients'.
{pantry_rule}
4. PRICING: Be practical and realistic with Indian grocery prices.

Suggest exactly 5 dish names that can be made.
Reply ONLY with this exact format — nothing else:

1. [Dish name] - [one line description] - ₹[estimated cost]
2. [Dish name] - [one line description] - ₹[estimated cost]
3. [Dish name] - [one line description] - ₹[estimated cost]
4. [Dish name] - [one line description] - ₹[estimated cost]
5. [Dish name] - [one line description] - ₹[estimated cost]
"""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful Indian recipe assistant. Reply only in the exact format requested."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7,
            )
            ai_text = response.choices[0].message.content

            dishes = []
            emojis = ['🍛', '🥘', '🍜', '🫓', '🥗']
            colors = [
                'linear-gradient(135deg,#7c3aed,#a855f7)',
                'linear-gradient(135deg,#ec4899,#f472b6)',
                'linear-gradient(135deg,#6366f1,#818cf8)',
                'linear-gradient(135deg,#f59e0b,#fbbf24)',
                'linear-gradient(135deg,#10b981,#34d399)',
            ]

            for i, line in enumerate(ai_text.strip().split('\n')):
                line = line.strip()
                if not line or not line[0].isdigit():
                    continue
                line = line[2:].strip() if len(line) > 1 and line[1] == '.' else line[3:].strip()
                parts = line.split(' - ')
                if len(parts) >= 2:
                    dishes.append({
                        'name': parts[0].strip(),
                        'description': parts[1].strip() if len(parts) > 1 else '',
                        'cost': parts[2].strip() if len(parts) > 2 else '',
                        'emoji': emojis[i] if i < len(emojis) else '🍽️',
                        'color': colors[i] if i < len(colors) else colors[0],
                    })

            return render(request, 'recipes/suggest.html', {
                'dishes': dishes,
                'ingredients': ingredients,
                'budget': budget,
                'serving_size': serving_size,
                'cuisine': cuisine,
                'quick_ingredients': quick_ingredients,
                'quick_budgets': quick_budgets,
            })

        except Exception as e:
            error_message = f"AI Error: {str(e)}"
            return render(request, 'recipes/suggest.html', {
                'quick_ingredients': quick_ingredients,
                'quick_budgets': quick_budgets,
                'error_message': error_message,
            })

    return render(request, 'recipes/suggest.html', {
        'quick_ingredients': quick_ingredients,
        'quick_budgets': quick_budgets,
    })


@login_required(login_url='/login/')
def calculate_recipe_nutrition(ingredients_list, servings):
    total = {
        'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0,
        'fiber': 0.0, 'sugar': 0.0, 'sodium': 0.0, 'cholesterol': 0.0, 'saturated_fat': 0.0
    }
    
    ingredient_details = []
    
    for ing in ingredients_list:
        # ing is dict with 'text' and 'measurement'
        name = ing.get('text', '')
        measure = ing.get('measurement', '')
        full_str = f"{measure} {name}".strip()
        grams = parse_quantity_to_grams(full_str)
        
        nutri = get_nutrition_for_ingredient(name, grams)
        
        ingredient_details.append({
            'name': name,
            'quantity': full_str,
            'grams': grams,
            'nutrition': nutri
        })
        
        for k in total.keys():
            total[k] += nutri.get(k, 0.0)
            
    # Per serving
    per_serving = {k: round(v / max(1, servings), 1) for k, v in total.items()}
    
    # Calculate health score
    score = 100
    if per_serving['sodium'] > 600: score -= 10
    if per_serving['saturated_fat'] > 5: score -= 10
    if per_serving['sugar'] > 10: score -= 5
    if per_serving['protein'] > 20: score += 10
    if per_serving['fiber'] > 3: score += 5
    score = max(0, min(100, score)) # clamp 0-100
    
    # Smart Health Tags
    tags = []
    if per_serving['protein'] > 20: tags.append("✅ High Protein")
    if per_serving['carbs'] < 20: tags.append("✅ Low Carb")
    if per_serving['sodium'] < 400: tags.append("✅ Low Sodium")
    if per_serving['cholesterol'] > 300: tags.append("⚠️ High Cholesterol")
    if per_serving['protein'] > 25: tags.append("💪 Muscle Building")
    if per_serving['calories'] < 400: tags.append("🏃 Weight Loss Friendly")
    
    # Suitability
    suitability = {"is": [], "is_not": []}
    if "✅ Low Carb" in tags: suitability["is"].append("Keto / Low-Carb Diets")
    if "💪 Muscle Building" in tags: suitability["is"].append("Athletes / Bodybuilders")
    if per_serving['sodium'] > 600: suitability["is_not"].append("People with High Blood Pressure")
    if per_serving['sugar'] > 10: suitability["is_not"].append("Diabetics")
    
    if not suitability["is"]: suitability["is"].append("General Healthy Eating")
    
    return {
        'total': total,
        'per_serving': per_serving,
        'ingredients': ingredient_details,
        'health_score': score,
        'health_tags': tags,
        'suitability': suitability
    }


def generate_view(request):
    quick_ingredients = {
        '🧅 Vegetables': [
            'Onion', 'Tomato', 'Potato', 'Garlic', 'Ginger',
            'Green Chilli', 'Capsicum', 'Carrot', 'Peas', 'Spinach',
            'Cauliflower', 'Cabbage', 'Brinjal', 'Okra / Bhindi',
            'Bitter Gourd', 'Bottle Gourd', 'Mushroom', 'Corn',
            'Coriander Leaves', 'Curry Leaves', 'Mint', 'Drumstick',
            'Zucchini', 'Broccoli', 'Bell Pepper', 'Sweet Potato',
            'Pumpkin', 'Radish', 'Beetroot', 'Spring Onion',
        ],
        '🫘 Dal & Lentils': [
            'Toor Dal', 'Moong Dal', 'Chana Dal', 'Urad Dal',
            'Masoor Dal', 'Rajma', 'Chickpeas', 'Whole Moong',
            'Black Chana', 'Green Moong', 'Lentils', 'Kidney Beans',
        ],
        '🌾 Grains & Flour': [
            'Rice', 'Basmati Rice', 'Wheat / Atta', 'Maida',
            'Semolina / Suji', 'Poha', 'Oats', 'Besan',
            'Ragi', 'Cornflour', 'Bread', 'Pav',
            'Quinoa', 'Millet', 'Brown Rice', 'Rice Flour',
        ],
        '🍝 Pasta & Noodles': [
            'Spaghetti', 'Macaroni', 'Penne', 'Instant Noodles',
            'Rice Noodles', 'Hakka Noodles', 'Pasta', 'Vermicelli',
        ],
        '🍞 Bakery': [
            'White Bread', 'Brown Bread', 'Burger Buns',
            'Pizza Base', 'Tortilla / Wrap', 'Croissant',
        ],
        '🥛 Dairy': [
            'Milk', 'Curd / Yogurt', 'Paneer', 'Butter',
            'Ghee', 'Cream', 'Cheese', 'Buttermilk',
            'Khoya / Mawa', 'Condensed Milk', 'Mozzarella',
        ],
        '🍗 Protein': [
            'Egg', 'Chicken', 'Mutton', 'Fish',
            'Prawn', 'Soya Chunks', 'Tofu',
            'Peanuts', 'Cashews', 'Almonds',
            'Bacon', 'Beef', 'Pork', 'Sausage',
        ],
        '🌶️ Spices': [
            'Salt', 'Turmeric', 'Red Chilli Powder', 'Cumin / Jeera',
            'Coriander Powder', 'Garam Masala', 'Mustard Seeds',
            'Black Pepper', 'Cardamom', 'Cloves', 'Cinnamon',
            'Bay Leaf', 'Hing / Asafoetida', 'Fennel Seeds',
            'Chaat Masala', 'Sambar Powder', 'Biryani Masala',
            'Oregano', 'Chilli Flakes', 'Mixed Herbs', 'Paprika',
        ],
        '🥫 Sauces': [
            'Tomato Ketchup', 'Mayonnaise', 'Soy Sauce',
            'Chilli Sauce', 'Schezwan Sauce', 'Pizza Sauce',
            'Mustard Sauce', 'Pasta Sauce', 'Peanut Butter',
        ],
        '🫙 Pantry Staples': [
            'Cooking Oil', 'Sunflower Oil', 'Mustard Oil', 'Coconut Oil',
            'Sugar', 'Jaggery / Gur', 'Honey', 'Tamarind',
            'Tomato Sauce', 'Soy Sauce', 'Vinegar',
            'Olive Oil', 'Sesame Oil',
        ],
        '🧂 Basic Pantry': [
            'Salt', 'Cooking Oil', 'Turmeric', 'Red Chilli Powder',
            'Cumin / Jeera', 'Mustard Seeds', 'Coriander Powder',
            'Garam Masala', 'Hing / Asafoetida', 'Black Pepper',
            'Bay Leaf', 'Water', 'Ghee', 'Butter',
        ],
    }
    quick_budgets = [50, 100, 150, 200, 500]


    if request.method == 'POST':
        from django.utils import timezone
        today = timezone.localdate()
        log = DailyRequestLog.objects.filter(user=request.user).order_by('-date').first()
        if not log:
            log = DailyRequestLog.objects.create(user=request.user)
            log.date = today
            log.save()
        elif log.date != today:
            # It's a new day! Reset the quota.
            log.date = today
            log.request_count = 0
            log.save()
        ingredients = request.POST.get('ingredients', '')
        budget = request.POST.get('budget', '')
        serving_size = request.POST.get('serving_size', '2')
        cuisine = request.POST.get('cuisine', 'any')
        leftover_mode = request.POST.get('leftover_mode', False)
        selected_dish = request.POST.get('selected_dish', '')
        
        if log.request_count >= 5 and not is_user_premium(request.user):
            return render(request, 'recipes/generate.html', {
                'quick_ingredients': quick_ingredients,
                'quick_budgets': quick_budgets,
                'error_message': "You have reached your daily limit of 5 recipe generations. Check back tomorrow! ⏰",
                'quota_exceeded': True,
                'quota_count': log.request_count,
                'quota_limit': 5,
                'ingredients': ingredients,
                'budget': budget,
                'serving_size': serving_size,
                'cuisine': cuisine,
            })
            
        # Increment request count
        log.request_count += 1
        log.save()
        
        user_xp_str = request.POST.get('user_xp', '0')
        try:
            user_xp = int(user_xp_str)
        except:
            user_xp = 0
            
        recipe_count = 3 + (user_xp // 100)

        # Map cuisine values to modes
        festivals = ['diwali', 'holi', 'eid', 'navratri']
        regions = ['south_indian', 'north_indian', 'bengali', 'gujarati', 'maharashtrian']
        
        festival_text = f"Festival Special: {cuisine.capitalize()}" if cuisine in festivals else ""
        region_text = f"Regional Style: {cuisine.capitalize()}" if cuisine in regions else ""
        cuisine_text = "Indian Street Food" if cuisine == 'street_food' else "Any Indian cuisine"
        
        mode_context = f"{region_text} {festival_text} {cuisine_text}".strip()

        meal_type   = request.POST.get('meal_type', 'any')
        spice_level = request.POST.get('spice_level', 'any')
        diet_pref   = request.POST.get('diet_pref', 'any')
        meal_text_g  = '' if meal_type  == 'any' else f'Meal type: {meal_type.replace("_"," ").title()}.'
        spice_text_g = '' if spice_level == 'any' else f'Spice level required: {spice_level.replace("_"," ").title()}.'

        # Strict dietary rules for generate view
        DIETARY_RULES_GEN = {
            'navratri':  '🚨 STRICT: Navratri Vrat. NO meat/fish/eggs/onion/garlic/wheat/regular rice. Sabudana, kuttu, singhare ka atta, samak rice, sendha namak, potatoes, peanuts, dairy only.',
            'diwali':    '🚨 STRICT: Diwali. NO meat/chicken/fish/eggs. 100% pure vegetarian. Festive sweets, namkeen, veg curries.',
            'holi':      '🚨 STRICT: Holi. NO meat/fish/eggs. Vegetarian only. Gujiya, thandai, dal baati.',
            'ganesh':    '🚨 STRICT: Ganesh Chaturthi. Pure vegetarian. Modak, puran poli, panchamrit, prasad dishes.',
            'pongal':    '🚨 STRICT: Pongal/Sankranti. Vegetarian. Pongal, sakkarai pongal, sesame sweets, til ladoo.',
            'onam':      '🚨 STRICT: Onam Sadya. Strictly vegetarian Kerala feast. Avial, olan, sambar, payasam, thoran, pachadi.',
            'raksha':    '🚨 STRICT: Raksha Bandhan. Focus on sweets: kheer, halwa, barfi, ladoo, gulab jamun.',
            'baisakhi':  'Baisakhi. Punjabi food. Sarson da saag, makki roti, lassi, pinni, churma.',
            'christmas': 'Christmas. Plum cake, biryani, roast chicken, fruit pudding, coconut sweets.',
            'eid':       'Eid. Traditional non-veg: biryani, korma, nihari, haleem, sheer khurma, seviyan. Lamb and chicken encouraged.',
            'gujarati':  '🚨 STRICT: Gujarati. NO meat/fish/eggs. Prefer no onion/garlic. Dhokla, thepla, kadhi, undhiyu.',
            'jain':      '🚨 STRICT: Jain. NO meat/fish/eggs/onion/garlic/potatoes/root vegetables.',
            'vegan':     '🚨 STRICT: Vegan. NO meat/fish/eggs/dairy/honey. Plant-based only.',
            'diabetic':  '🚨 STRICT: Diabetic-friendly. Low sugar, low refined carbs, no deep frying, no maida.',
            'south_indian': 'South Indian. Prefer vegetarian. Coconut, curry leaves, mustard seeds, tamarind.',
            'kerala':    'Kerala. Coconut-based, fish curry (meen curry), appam, puttu, sadya dishes.',
            'chettinad': 'Chettinad. Bold spices. Can be non-veg.',
            'andhra':    'Andhra. Very spicy! Gongura, pulusu. Non-veg OK.',
            'karnataka': 'Karnataka. Bisi bele bath, ragi mudde, masala dosa.',
            'north_indian': 'North Indian. Dal makhani, paneer, rajma, naan. Veg or non-veg.',
            'punjabi':   'Punjabi. Butter chicken, chole, sarson da saag, lassi.',
            'rajasthani':'Rajasthani. Dal baati churma, gatte, ker sangri, laal maas.',
            'kashmiri':  'Kashmiri. Rogan josh, dum aloo, haak, modur pulao.',
            'bihari':    'Bihari. Litti chokha, sattu paratha, dal peetha.',
            'bengali':   'Bengali. Fish dishes highly encouraged. Hilsa, doi maach, mishti doi, rasgulla.',
            'odia':      'Odia. Dalma, pakhala bhat, chhena poda.',
            'maharashtrian': 'Maharashtrian. Misal pav, vada pav, puran poli, aamti.',
            'goan':      'Goan. Fish curry rice, vindaloo, sorpotel, bebinca.',
            'hyderabadi':'Hyderabadi. Dum biryani, haleem, mirchi ka salan.',
            'mughlai':   'Mughlai. Biryani, korma, nihari, shahi tukda, kebabs.',
            'healthy':   '🚨 STRICT: Healthy only. No deep frying, no excess oil, no refined sugar.',
            'quick':     '🚨 STRICT: All recipes under 20 minutes. No slow-cooking.',
            'street_food': 'Indian street food. Chaat, pav bhaji, golgappa, bhel, kachori, samosa.',
        }
        diet_rule_gen = DIETARY_RULES_GEN.get(cuisine, '')

        DIET_OVERRIDES_GEN = {
            'vegetarian': '🚨 ALSO: User wants VEGETARIAN only. NO meat/chicken/fish/eggs.',
            'vegan':      '🚨 ALSO: Vegan only. NO meat/fish/eggs/dairy/honey.',
            'non_veg':    'User prefers non-vegetarian. Include meat/chicken/fish options.',
            'eggetarian': 'Eggetarian. Eggs allowed but NO meat or fish.',
            'jain':       '🚨 ALSO: Jain. NO meat/fish/eggs/onion/garlic/root vegetables.',
            'diabetic':   '🚨 ALSO: Diabetic-friendly. Low sugar, low carb, no maida.',
            'high_protein': 'High-protein focus: dal, paneer, chicken, eggs, soy, sprouts.',
        }
        diet_override_gen = DIET_OVERRIDES_GEN.get(diet_pref, '')

        if leftover_mode:
            mode_text = f"These are LEFTOVER ingredients. Suggest creative recipes to use them up. {mode_context}"
        elif selected_dish:
            mode_text = f"The user selected '{selected_dish}'. Generate recipes focused on this dish. {mode_context}"
        else:
            mode_text = f"Suggest fresh recipes using these ingredients. {mode_context}"
        prompt_recipes = ""
        for i in range(1, recipe_count + 1):
            prompt_recipes += f"""
RECIPE {i}:
Name: [Recipe name]
Description: [One line description]
AI Taste Score: [Score]/10
Nutritional Info (Per 1 Serving): [Calories] kcal | [Protein]g P | [Carbs]g C | [Fat]g F
Estimated Cost: ₹[cost]
Restaurant Price: ₹[cost]
Budget Score: [Score between 1-10]
Difficulty Level: [Easy/Medium/Hard]
Servings: [number]
Why this recipe: [One short sentence explaining why this fits their ingredients and budget]
Cooking Time: [time in minutes]
Dietary Preference: [e.g., Vegetarian, Gluten-Free]
Ingredients Needed:
- [ingredient 1] | [exact measurement] | have it ✅
- [ingredient 2] | [exact measurement] | need to buy ❌ (approx ₹[price])
Instructions:
1. [Step 1]
2. [Step 2]
3. [Step 3]
Tips: [One expert tip]
Variations: [One variation idea]
Missing Ingredients to Buy:
- [ingredient] - ₹[price]
"""
        
        assume_pantry = request.POST.get('assume_pantry', 'no')
        pantry_rule_gen = ""
        if assume_pantry == 'yes':
            pantry_rule_gen = "3. PANTRY STAPLES: Assume the user already has basic items like salt, cooking oil, water, turmeric, and basic Indian spices. DO NOT list these as missing ingredients to buy."

        prompt = f"""
You are a helpful Indian recipe assistant.

USER'S INVENTORY & CONSTRAINTS:
Available Ingredients: {ingredients}
Max Budget: ₹{budget}
Serving Size: {serving_size} people

{mode_text}
{meal_text_g}
{spice_text_g}

{diet_rule_gen}
{diet_override_gen}

CRITICAL RULES:
1. STRICT BUDGET: The total Estimated Cost of the recipe MUST be less than or equal to ₹{budget}. Do NOT suggest recipes that exceed this budget.
2. AVAILABLE INGREDIENTS: Carefully check the user's 'Available Ingredients'. Do NOT list these as 'need to buy'. They already have them!
{pantry_rule_gen}
4. MISSING INGREDIENTS: Only list ingredients the user DOES NOT have in the 'Missing Ingredients' section. If they have everything needed, write 'None'.
5. PRICING: Be realistic with Indian grocery prices.
6. EXACT MACROS (PER SERVING): You are acting as a Certified Clinical Nutritionist. You MUST calculate the EXACT Calories, Protein, Carbs, and Fats PER 1 SERVING of the dish. Do not calculate for the entire batch if the serving size is >1. Be highly accurate using standard USDA database values.

Provide EXACTLY {recipe_count} recipe options.
You must return the response strictly in the following format:
{prompt_recipes}
"""

        try:
            system_instruction = "You are a helpful Indian recipe assistant. Always follow the exact format provided."
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1200,
                temperature=0.7,
            )
            ai_response = response.choices[0].message.content
            
            recipes = parse_recipes(ai_response)
            
            # --- USDA API Nutrition Calculation ---
            for recipe in recipes:
                if recipe.get('ingredients'):
                    real_nutri = calculate_recipe_nutrition(recipe['ingredients'], serving_size)
                    recipe['real_nutrition'] = real_nutri
                    
                    # Update old nutrition dictionary to map to new per-serving values
                    # so the frontend macro logger still works without changes
                    if not recipe.get('nutrition'):
                        recipe['nutrition'] = {}
                    recipe['nutrition']['calories'] = real_nutri['per_serving']['calories']
                    recipe['nutrition']['protein'] = real_nutri['per_serving']['protein']
                    recipe['nutrition']['carbs'] = real_nutri['per_serving']['carbs']
                    recipe['nutrition']['fat'] = real_nutri['per_serving']['fat']
            
            youtube_videos = get_youtube_videos(
                selected_dish if selected_dish else ingredients
            )

            # Add dish image to each recipe (already done in parse_recipes, but ensure fallback)
            for i, recipe in enumerate(recipes):
                recipe['dish_emoji'] = DISH_EMOJIS[i % len(DISH_EMOJIS)]
                recipe['dish_gradient'] = DISH_GRADIENTS[i % len(DISH_GRADIENTS)]
                # Image fetching is fully disabled, so we intentionally leave image_url empty
                pass

            # --- AUTO-SAVE TO HISTORY ---
            premium = is_user_premium(request.user)
            for r in recipes:
                if r.get('name'):
                    nutrition = r.get('nutrition') or {}
                    RecipeHistory.objects.create(
                        user=request.user,
                        name=r['name'],
                        description=r.get('description', ''),
                        ingredients_used=ingredients,
                        budget=budget,
                        cuisine=cuisine,
                        calories=nutrition.get('calories', ''),
                        protein=nutrition.get('protein', ''),
                        carbs=nutrition.get('carbs', ''),
                        fat=nutrition.get('fat', ''),
                        cost=r.get('cost', ''),
                        ai_response='',
                    )
            # Free users: keep only last 10 entries
            if not premium:
                all_ids = list(
                    RecipeHistory.objects.filter(user=request.user)
                    .order_by('-generated_at')
                    .values_list('id', flat=True)
                )
                if len(all_ids) > 10:
                    RecipeHistory.objects.filter(id__in=all_ids[10:]).delete()

            return render(request, 'recipes/generate.html', {
                'quick_ingredients': quick_ingredients,
                'quick_budgets': quick_budgets,
                'recipes': recipes,
                'ai_response': ai_response,
                'ingredients': ingredients,
                'budget': budget,
                'serving_size': serving_size,
                'cuisine': cuisine,
                'youtube_videos': youtube_videos,
                'selected_dish': selected_dish,
                'quota_count': 0 if is_user_premium(request.user) else log.request_count,
                'quota_limit': "\u221e" if is_user_premium(request.user) else 5,
            })

        except Exception as e:
            error_message = f"AI Error: {str(e)}"
            quota_count = 0 if is_user_premium(request.user) else log.request_count
            quota_limit = "∞" if is_user_premium(request.user) else 5
            return render(request, 'recipes/generate.html', {
                'quick_ingredients': quick_ingredients,
                'quick_budgets': quick_budgets,
                'error_message': error_message,
                'quota_count': quota_count,
                'quota_limit': quota_limit,
            })

    from datetime import date
    from django.utils import timezone
    today = timezone.localdate()
    log = DailyRequestLog.objects.filter(user=request.user).order_by('-date').first()
    if not log:
        log = DailyRequestLog.objects.create(user=request.user)
        log.date = today
        log.save()
    elif log.date != today:
        log.date = today
        log.request_count = 0
        log.save()
    
    quota_count = 0 if is_user_premium(request.user) else log.request_count
    quota_limit = "∞" if is_user_premium(request.user) else 5
    
    return render(request, 'recipes/generate.html', {
        'quick_ingredients': quick_ingredients,
        'quick_budgets': quick_budgets,
        'quota_count': quota_count,
        'quota_limit': quota_limit,
    })


@login_required(login_url='/login/')
def save_recipe_view(request):
    if request.method == 'POST':
        name = request.POST.get('recipe_name', '')
        description = request.POST.get('recipe_description', '')
        ingredients_used = request.POST.get('ingredients', '')
        budget = request.POST.get('budget', '')
        cuisine = request.POST.get('cuisine', '')
        ai_response = request.POST.get('ai_response', '')

        recipe = SavedRecipe.objects.filter(
            user=request.user,
            name=name
        ).first()

        if not recipe:
            recipe = SavedRecipe.objects.create(
                user=request.user,
                name=name,
                description=description,
                ingredients_used=ingredients_used,
                budget=budget,
                cuisine=cuisine,
                ai_response=ai_response,
            )
            return JsonResponse({'status': 'saved', 'message': f'{name} saved!', 'share_id': str(recipe.share_id)})
        else:
            return JsonResponse({'status': 'exists', 'message': 'Already saved!', 'share_id': str(recipe.share_id)})

    return JsonResponse({'status': 'error'})

def shared_recipe_view(request, share_id):
    from django.shortcuts import get_object_or_404
    recipe_obj = get_object_or_404(SavedRecipe, share_id=share_id)
    # Parse the recipe from the stored ai_response (which is the full Llama response)
    # Actually, if we just want to display the specific recipe, we need to extract it
    # We can just use the parse_recipes utility!
    recipes = parse_recipes(recipe_obj.ai_response)
    
    # We want to find the specific recipe that was saved, because ai_response has 3 recipes!
    # Or wait, the whole ai_response might be 3 recipes. Let's find the one matching the name
    specific_recipe = None
    for r in recipes:
        if r['name'].lower().strip() == recipe_obj.name.lower().strip():
            specific_recipe = r
            break
            
    if not specific_recipe and recipes:
        specific_recipe = recipes[0] # Fallback
        
    return render(request, 'recipes/shared_recipe.html', {
        'recipe_obj': recipe_obj,
        'recipe': specific_recipe,
    })


@login_required(login_url='/login/')
def saved_recipes_view(request):
    saved_recipes = SavedRecipe.objects.filter(user=request.user).order_by('-created_at')
    for sr in saved_recipes:
        recipes = parse_recipes(sr.ai_response)
        specific = None
        for r in recipes:
            if r['name'].lower().strip() == sr.name.lower().strip():
                specific = r
                break
        if not specific and recipes:
            specific = recipes[0]
            
        if specific:
            specific['missing'] = [ing['text'] for ing in specific.get('ingredients', []) if not ing.get('have')]
            
        sr.parsed_recipe = specific

    return render(request, 'recipes/saved_recipes.html', {
        'saved_recipes': saved_recipes,
    })


@login_required(login_url='/login/')
def delete_recipe_view(request, recipe_id):
    try:
        recipe = SavedRecipe.objects.get(id=recipe_id, user=request.user)
        recipe.delete()
    except SavedRecipe.DoesNotExist:
        pass
    return redirect('saved_recipes')


# ─── Meal Planner ────────────────────────────────────────────────────────────

DAYS_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MEAL_ORDER = ['Breakfast', 'Lunch', 'Snack', 'Dinner']


@login_required(login_url='/login/')
def meal_planner_view(request):
    """Weekly meal planner page."""
    plans = MealPlan.objects.filter(user=request.user)
    # Build a grid: { day: { meal_type: MealPlan } }
    grid = {day: {meal: None for meal in MEAL_ORDER} for day in DAYS_ORDER}
    for plan in plans:
        if plan.day in grid and plan.meal_type in grid[plan.day]:
            grid[plan.day][plan.meal_type] = plan

    saved_recipes = SavedRecipe.objects.filter(user=request.user).values_list('name', flat=True)

    return render(request, 'recipes/meal_planner.html', {
        'grid': grid,
        'days': DAYS_ORDER,
        'meals': MEAL_ORDER,
        'saved_recipe_names': list(saved_recipes),
    })


@login_required(login_url='/login/')
@require_POST
def save_meal_view(request):
    """Save or update a meal slot."""
    day = request.POST.get('day', '')
    meal_type = request.POST.get('meal_type', '')
    recipe_name = request.POST.get('recipe_name', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not day or not meal_type or not recipe_name:
        return JsonResponse({'status': 'error', 'message': 'Missing fields'})

    obj, created = MealPlan.objects.update_or_create(
        user=request.user,
        day=day,
        meal_type=meal_type,
        defaults={'recipe_name': recipe_name, 'notes': notes},
    )
    return JsonResponse({
        'status': 'saved',
        'recipe_name': obj.recipe_name,
        'notes': obj.notes,
        'id': obj.id,
    })


@login_required(login_url='/login/')
@require_POST
def delete_meal_view(request):
    """Remove a meal slot."""
    meal_id = request.POST.get('meal_id', '')
    try:
        meal = MealPlan.objects.get(id=meal_id, user=request.user)
        meal.delete()
        return JsonResponse({'status': 'deleted'})
    except MealPlan.DoesNotExist:
        return JsonResponse({'status': 'error'})


# ─── Cooking Tips (AI) ────────────────────────────────────────────────────────

@login_required(login_url='/login/')
def cooking_tips_view(request):
    """Return AI-generated quick tips for a recipe name (AJAX)."""
    recipe_name = request.GET.get('recipe', '')
    if not recipe_name:
        return JsonResponse({'tips': []})
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert Indian chef. Give practical, short tips."},
                {"role": "user", "content": (
                    f"Give exactly 4 quick pro cooking tips for making '{recipe_name}' perfectly. "
                    "Each tip must be one short sentence. Reply ONLY as a numbered list:\n"
                    "1. tip\n2. tip\n3. tip\n4. tip"
                )},
            ],
            max_tokens=250,
            temperature=0.6,
        )
        text = response.choices[0].message.content.strip()
        tips = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(('- ', '* ')):
                tips.append(line[2:].strip())
            elif line and line[0].isdigit() and '.' in line:
                tips.append(line.split('.', 1)[1].strip())
            elif len(line) > 10 and not line.endswith(':'):
                tips.append(line)
        # Filter empty
        tips = [t for t in tips if t][:4]
        return JsonResponse({'tips': tips})
    except Exception as e:
        print("Cooking tips error:", e)
        return JsonResponse({'tips': []})

# ─── Chatbot API ────────────────────────────────────────────────────────

import json

@login_required(login_url='/login/')
@require_POST
def chatbot_api(request):
    """Handle chat messages to the AI assistant."""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        context = data.get('context', '')
        
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
            
        system_prompt = (
            "You are Chef AI, a friendly and expert cooking assistant for BudgetBites. "
            "Help the user with recipe substitutions, cooking techniques, and Indian cuisine. "
            "Keep answers concise and very helpful. "
            f"Current Context: {context}"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        ai_reply = response.choices[0].message.content
        return JsonResponse({'reply': ai_reply})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)

@login_required(login_url='/login/')
@require_POST
def bonus_recipe_api(request):
    try:
        data = json.loads(request.body)
        base_recipe = data.get('base_recipe', 'Main Dish')
        
        prompt = f"""
Generate exactly ONE bonus dessert or sweet dish recipe that pairs well with '{base_recipe}'.
You must return the response strictly in the following format:

RECIPE 1:
Name: [Recipe name]
Description: [One line description]
AI Taste Score: [Score]/10
Nutritional Info: [Calories] kcal | [Protein]g P | [Carbs]g C | [Fat]g F
Estimated Cost: ₹[cost]
Cooking Time: [time in minutes]
Ingredients Needed:
- [ingredient 1] - have it ✅
Instructions:
1. [Step 1]
2. [Step 2]
3. [Step 3]
Missing Ingredients to Buy:
None
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert chef. Follow the exact format."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
            temperature=0.7,
        )
        ai_response = response.choices[0].message.content
        recipes = parse_recipes(ai_response)
        
        if recipes:
            recipe = recipes[0]
            recipe['dish_emoji'] = '🍰'
            recipe['dish_gradient'] = 'linear-gradient(135deg, #fcd34d, #fb923c)'
            recipe['number'] = 'BONUS'
            return JsonResponse({'status': 'success', 'recipe': recipe})
        return JsonResponse({'status': 'error', 'message': 'Failed to parse bonus recipe.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# ─── AI Fridge Scanner ────────────────────────────────────────────────────────

@login_required(login_url='/login/')
@require_POST
def scan_fridge_api(request):
    """
    Accept a base64-encoded image from the frontend, send it to Gemini 1.5 Flash vision model,
    with Groq vision as fallback, and return a list of detected ingredients.
    """
    try:
        data = json.loads(request.body)
        image_data = data.get('image', '')  # base64 string, e.g. "data:image/jpeg;base64,..."

        if not image_data:
            return JsonResponse({'status': 'error', 'message': 'No image provided'}, status=400)

        # Parse base64 parts
        if ',' in image_data:
            header, _, base64_str = image_data.partition(',')
            mime_type = "image/jpeg"
            if 'image/png' in header:
                mime_type = "image/png"
            elif 'image/webp' in header:
                mime_type = "image/webp"
        else:
            base64_str = image_data
            mime_type = "image/jpeg"

        prompt_text = (
            "Look carefully at this image. Identify ALL visible food ingredients, "
            "vegetables, fruits, dairy, meat, spices, condiments, and pantry items. "
            "Reply ONLY with a comma-separated list of ingredient names. "
            "Use simple common names (e.g. 'onion, tomato, milk, eggs, carrot'). "
            "Do NOT include quantities, descriptions, or any extra text. "
            "If you cannot identify any food items, reply with exactly: NONE"
        )

        # Try Gemini 1.5 Flash Vision first
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64_str
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 200
            }
        }

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                result_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
        except Exception as gemini_err:
            print(f"Gemini Vision API Error: {gemini_err}. Falling back to Groq Vision.")
            # Groq vision API fallback call using llama-3.2-11b-vision-preview
            response = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt_text
                            }
                        ],
                    }
                ],
                max_tokens=200,
                temperature=0.1,
            )
            result_text = response.choices[0].message.content.strip()

        if result_text.upper() == 'NONE' or not result_text:
            return JsonResponse({
                'status': 'success',
                'ingredients': [],
                'message': 'No ingredients detected. Please try with a clearer image.'
            })

        # Parse comma-separated ingredients, clean them up
        raw_ingredients = [i.strip().strip('.').strip() for i in result_text.split(',')]
        ingredients = [i for i in raw_ingredients if i and len(i) > 1]

        return JsonResponse({
            'status': 'success',
            'ingredients': ingredients,
            'count': len(ingredients),
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Vision AI error: {str(e)}'}, status=500)

# ─── Premium Features & Craving Mode ─────────────────────────────────────────

def upgrade_premium_view(request):
    return render(request, 'recipes/upgrade.html')

@login_required(login_url='/login/')
def craving_view(request):
    # The Bouncer: Only allow Admins (Superusers) for now, as payment isn't integrated
    if not request.user.is_superuser:
        return redirect('upgrade_premium')
    return render(request, 'recipes/cravings.html')

@login_required(login_url='/login/')
def api_cravings_checklist(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Premium required'}, status=403)
        
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        craving = data.get('craving', '')
        serving = data.get('serving', '2')
        
        prompt = f"""
        The user wants to cook: {craving}
        Serving size: {serving} people.
        
        Act as a professional chef. What exact ingredients and measurements are required?
        Respond STRICTLY with a JSON list of objects containing 'name' and 'amount'.
        Do NOT include any markdown, backticks, or extra text. Just the raw JSON array.
        Example:
        [
          {{"name": "Garlic", "amount": "4 cloves"}},
          {{"name": "Butter", "amount": "20g"}}
        ]
        """
        
        ai_response = call_gemini_api(prompt, "You are a chef. Output strictly valid JSON without markdown.", temperature=0.2)
        try:
            # Clean possible markdown block
            clean_json = ai_response.replace('```json', '').replace('```', '').strip()
            ingredients = json.loads(clean_json)
            return JsonResponse({'ingredients': ingredients})
        except Exception as e:
            return JsonResponse({'error': 'Failed to parse AI checklist.', 'raw': ai_response}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required(login_url='/login/')
def api_cravings_instructions(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Premium required'}, status=403)
        
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        craving = data.get('craving', '')
        serving = data.get('serving', '2')
        substitutions = data.get('substitutions', [])
        
        sub_text = "\\n".join(substitutions) if substitutions else "No substitutions needed. User has all ingredients."
        
        prompt = f"""
        The user wants to cook: {craving} for {serving} people.
        
        Here are the user's ingredient substitutions/omissions:
        {sub_text}
        
        Act as an interactive, highly-skilled Chef. Write a step-by-step recipe for {craving} that seamlessly incorporates their substitutions or omissions.
        Make it sound encouraging and professional!
        Use Markdown formatting for bolding, bullet points, and numbered lists.
        """
        
        ai_response = call_gemini_api(prompt, "You are an encouraging Chef writing recipes in Markdown.")
        return JsonResponse({'instructions': ai_response})
        
    return JsonResponse({'error': 'Invalid request'}, status=400)


# ─── Fitness Macro Tracker ───────────────────────────────────────────────────

@login_required(login_url='/login/')
def macros_view(request):
    """Premium Dashboard to view daily macros."""
    if not is_user_premium(request.user):
        return redirect('upgrade_premium')
        
    from django.utils import timezone
    today = timezone.localdate()
    
    logs = MacroLog.objects.filter(user=request.user, date=today)
    
    total_cals = sum(log.calories for log in logs)
    total_protein = sum(log.protein_g for log in logs)
    total_carbs = sum(log.carbs_g for log in logs)
    total_fats = sum(log.fats_g for log in logs)
    
    return render(request, 'recipes/macros.html', {
        'logs': logs,
        'total_cals': total_cals,
        'total_protein': total_protein,
        'total_carbs': total_carbs,
        'total_fats': total_fats,
    })

@login_required(login_url='/login/')
@require_POST
def log_macro_api(request):
    if not is_user_premium(request.user):
        return JsonResponse({'error': 'Premium required'}, status=403)
        
    import json
    try:
        data = json.loads(request.body)
        MacroLog.objects.create(
            user=request.user,
            recipe_name=data.get('recipe_name', 'Unknown Recipe'),
            calories=int(data.get('calories', 0)),
            protein_g=int(data.get('protein', 0)),
            carbs_g=int(data.get('carbs', 0)),
            fats_g=int(data.get('fats', 0))
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ─── AI Grocery List Generator ───────────────────────────────────────────────

@login_required(login_url='/login/')
def api_generate_grocery_list(request):
    """Gathers all recipes in the Meal Plan and generates a categorized grocery list."""
    if not is_user_premium(request.user):
        return JsonResponse({'error': 'Premium required'}, status=403)
        
    plans = MealPlan.objects.filter(user=request.user)
    if not plans.exists():
        return JsonResponse({'error': 'Your meal plan is empty!'})
        
    recipe_names = [p.recipe_name for p in plans]
    recipes_text = ", ".join(recipe_names)
    
    prompt = f"""
    The user is planning to cook the following meals this week:
    {recipes_text}
    
    Act as a smart grocery assistant. Combine all the ingredients needed for these meals into a single, organized grocery list.
    Group them by supermarket aisle (e.g., Produce, Dairy, Spices, Meat, Pantry).
    Return the response as a valid JSON object where keys are aisle names and values are arrays of strings (ingredient and rough amount).
    Example:
    {{
      "Produce": ["4 Onions", "2 Tomatoes"],
      "Dairy": ["500ml Milk", "200g Paneer"]
    }}
    Do NOT include markdown backticks. Just raw JSON.
    """
    
    ai_response = call_gemini_api(prompt, "You are a smart grocery list generator. Output strictly valid JSON.", temperature=0.2)
    try:
        import json
        clean_json = ai_response.replace('```json', '').replace('```', '').strip()
        grocery_list = json.loads(clean_json)
        return JsonResponse({'grocery_list': grocery_list})
    except Exception as e:
        return JsonResponse({'error': 'Failed to parse AI grocery list.', 'raw': ai_response}, status=500)


# ─── Recipe History ───────────────────────────────────────────────────────────

@login_required(login_url='/login/')
def recipe_history_view(request):
    """Shows the user's auto-saved recipe history with search & date filter."""
    from django.utils import timezone
    from datetime import timedelta

    premium = is_user_premium(request.user)
    search_q = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date', 'all')

    history_qs = RecipeHistory.objects.filter(user=request.user)

    # Search (premium only)
    if premium and search_q:
        history_qs = history_qs.filter(name__icontains=search_q)

    # Date filter (premium only)
    if premium and date_filter != 'all':
        now = timezone.now()
        if date_filter == 'today':
            history_qs = history_qs.filter(generated_at__date=now.date())
        elif date_filter == 'week':
            history_qs = history_qs.filter(generated_at__gte=now - timedelta(days=7))
        elif date_filter == 'month':
            history_qs = history_qs.filter(generated_at__gte=now - timedelta(days=30))

    history = list(history_qs)
    total_count = RecipeHistory.objects.filter(user=request.user).count()

    return render(request, 'recipes/recipe_history.html', {
        'history': history,
        'premium': premium,
        'search_q': search_q,
        'date_filter': date_filter,
        'total_count': total_count,
    })


@login_required(login_url='/login/')
def delete_history_view(request, history_id):
    """Delete a single history entry."""
    from django.shortcuts import get_object_or_404
    entry = get_object_or_404(RecipeHistory, id=history_id, user=request.user)
    entry.delete()
    return redirect('recipe_history')
