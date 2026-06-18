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


class DailyRequestLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    request_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-date']
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user.username} - {self.date}: {self.request_count} requests"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_premium = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} Profile (Premium: {self.is_premium})"

class MacroLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    recipe_name = models.CharField(max_length=200)
    calories = models.IntegerField(default=0)
    protein_g = models.IntegerField(default=0)
    carbs_g = models.IntegerField(default=0)
    fats_g = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.recipe_name} ({self.calories} kcal)"

class RecipeHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipe_history')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    ingredients_used = models.TextField(blank=True)  # JSON string
    budget = models.CharField(max_length=50, blank=True)
    cuisine = models.CharField(max_length=100, blank=True)
    calories = models.CharField(max_length=50, blank=True)
    protein = models.CharField(max_length=50, blank=True)
    carbs = models.CharField(max_length=50, blank=True)
    fat = models.CharField(max_length=50, blank=True)
    cost = models.CharField(max_length=50, blank=True)
    ai_response = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.generated_at.strftime('%d %b %Y')})"

# Auto-create UserProfile
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)
    instance.profile.save()