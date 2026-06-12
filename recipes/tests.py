from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from recipes.models import SavedRecipe, MealPlan

class RecipeAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123'
        )
        self.home_url = reverse('home')
        self.generate_url = reverse('generate')
        self.suggest_url = reverse('suggest')
        self.saved_recipes_url = reverse('saved_recipes')
        self.meal_planner_url = reverse('meal_planner')

    def test_home_page_requires_login(self):
        response = self.client.get(self.home_url)
        # Should redirect to login
        self.assertRedirects(response, f"{reverse('login')}?next={self.home_url}")

    def test_home_page_authenticated(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'recipes/home.html')

    def test_saved_recipe_model(self):
        recipe = SavedRecipe.objects.create(
            user=self.user,
            name="Test Recipe",
            ingredients_used="Tomato, Onion",
            ai_response='{"ingredients": [], "instructions": []}'
        )
        self.assertEqual(SavedRecipe.objects.count(), 1)
        self.assertEqual(recipe.name, "Test Recipe")
        self.assertTrue(recipe.share_id)

    def test_meal_plan_model(self):
        meal = MealPlan.objects.create(
            user=self.user,
            day="Monday",
            meal_type="Dinner",
            recipe_name="Pasta"
        )
        self.assertEqual(MealPlan.objects.count(), 1)
        self.assertEqual(meal.recipe_name, "Pasta")
        self.assertEqual(str(meal), f"{self.user.username} - Monday Dinner: Pasta")

    def test_generate_page_loads(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(self.generate_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'recipes/generate.html')
