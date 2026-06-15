import os
import shutil

src = r"static/logo.png"
dst = r"android/app/src/main/res/drawable/app_logo.png"

# Ensure destination directory exists
os.makedirs(os.path.dirname(dst), exist_ok=True)

try:
    shutil.copyfile(src, dst)
    print("✅ Success! App logo has been copied to your Android project.")
except Exception as e:
    print(f"❌ Error copying logo: {e}")
