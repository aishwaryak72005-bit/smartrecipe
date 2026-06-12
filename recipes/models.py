from django.db import models
from django.contrib.auth.models import User

import uuid

class SavedRecipe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    share_id = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    ingredients_used = models.TextField()
    budget = models.CharField(max_length=50)
    cuisine = models.CharField(max_length=100, blank=True)
    ai_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class MealPlan(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'), ('Friday', 'Friday'), ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]
    MEAL_CHOICES = [
        ('Breakfast', 'Breakfast'), ('Lunch', 'Lunch'),
        ('Snack', 'Snack'), ('Dinner', 'Dinner'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    meal_type = models.CharField(max_length=10, choices=MEAL_CHOICES)
    recipe_name = models.CharField(max_length=200)
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day', 'meal_type']
        unique_together = ('user', 'day', 'meal_type')

    def __str__(self):
        return f"{self.user.username} - {self.day} {self.meal_type}: {self.recipe_name}"