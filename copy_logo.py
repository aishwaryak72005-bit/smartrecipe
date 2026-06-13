import shutil
import os

src = r"C:\Users\Admin\.gemini\antigravity\brain\4b0ee8da-1cfb-410a-ac03-5cc9c334f494\media__1781342559122.jpg"
dst = r"c:\Users\Admin\OneDrive\Desktop\smartrecipe\static\logo.png"

try:
    shutil.copyfile(src, dst)
    print("✅ Success! The new logo has been copied to your static folder.")
    print("👉 Next step: Do a HARD REFRESH (Ctrl + Shift + R) on your browser to see it!")
except Exception as e:
    print(f"Error copying file: {e}")
