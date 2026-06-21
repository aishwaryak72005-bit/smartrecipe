from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('generate/', views.generate_view, name='generate'),
    path('suggest/', views.suggest_view, name='suggest'),
    path('save-recipe/', views.save_recipe_view, name='save_recipe'),
    path('saved-recipes/', views.saved_recipes_view, name='saved_recipes'),
    path('delete-recipe/<int:recipe_id>/', views.delete_recipe_view, name='delete_recipe'),
    # Meal Planner
    path('meal-planner/', views.meal_planner_view, name='meal_planner'),
    path('meal-planner/save/', views.save_meal_view, name='save_meal'),
    path('meal-planner/delete/', views.delete_meal_view, name='delete_meal'),
    # AI Cooking Tips
    path('cooking-tips/', views.cooking_tips_view, name='cooking_tips'),
    path('share/<uuid:share_id>/', views.shared_recipe_view, name='shared_recipe'),
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),
    path('api/bonus-recipe/', views.bonus_recipe_api, name='bonus_recipe_api'),
    # AI Fridge Scanner
    path('api/scan-fridge/', views.scan_fridge_api, name='scan_fridge_api'),
    # Craving Mode (Premium)
    path('cravings/', views.craving_view, name='cravings'),
    path('api/cravings/checklist/', views.api_cravings_checklist, name='api_cravings_checklist'),
    path('api/cravings/instructions/', views.api_cravings_instructions, name='api_cravings_instructions'),
    path('upgrade/', views.upgrade_premium_view, name='upgrade_premium'),
    
    # Razorpay Payment endpoints
    path('create-order/', views.create_order_view, name='create_order'),
    path('payment-success/', views.payment_success_page_view, name='payment_success_page'),
    path('api/payment-success/', views.payment_success_view, name='payment_success'),
    path('payment-failed/', views.payment_failed_view, name='payment_failed'),
    
    # Premium: Macros
    path('macros/', views.macros_view, name='macros'),
    path('api/macros/log/', views.log_macro_api, name='log_macro_api'),
    
    # Premium: Grocery List
    path('api/meal-planner/grocery-list/', views.api_generate_grocery_list, name='api_generate_grocery_list'),

    # Recipe History
    path('history/', views.recipe_history_view, name='recipe_history'),
    path('history/delete/<int:history_id>/', views.delete_history_view, name='delete_history'),
]