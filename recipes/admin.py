from django.contrib import admin
from .models import SavedRecipe, MealPlan

@admin.register(SavedRecipe)
class SavedRecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'cuisine', 'budget', 'created_at', 'share_id')
    list_filter = ('cuisine', 'created_at')
    search_fields = ('name', 'user__username', 'ingredients_used')
    ordering = ('-created_at',)
    readonly_fields = ('share_id', 'created_at')

@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'day', 'meal_type', 'recipe_name', 'created_at')
    list_filter = ('day', 'meal_type')
    search_fields = ('user__username', 'recipe_name')
    ordering = ('day',)
