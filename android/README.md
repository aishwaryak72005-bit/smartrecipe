# BudgetBites Android WebView Wrapper

This is a complete Android Studio project folder containing a WebView wrapper for your BudgetBites Django web app.

## How to Run This Project

1. Open **Android Studio**.
2. Click **File -> Open...** and select this `android` folder (`c:\Users\Admin\OneDrive\Desktop\smartrecipe\android`).
3. Wait for Android Studio to sync the project and download Gradle.
4. Start your local Django development server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
5. In Android Studio, launch an Android Emulator (or connect your physical phone with USB Debugging enabled).
6. Click the green **Run** button to install and launch the application!

## Going to Production

When you publish your web app to Heroku, PythonAnywhere, or AWS, simply change the URL loaded in `MainActivity.kt` (located at `app/src/main/java/com/budgetbites/app/MainActivity.kt`):

```kotlin
// Change this line:
myWebView.loadUrl("http://10.0.2.2:8000/")

// To your live URL:
myWebView.loadUrl("https://your-domain.com/")
```
