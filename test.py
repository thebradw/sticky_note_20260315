# test_setup.py
print("Testing sticky-note project setup...")
print("=" * 40)

try:
    import anthropic
    print("✅ anthropic - Ready for Claude API")
except ImportError as e:
    print("❌ anthropic failed:", e)

try:
    from PIL import Image
    print("✅ PIL/Pillow - Ready for image processing")
except ImportError as e:
    print("❌ PIL failed:", e)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    print("✅ reportlab - Ready for PDF generation")
except ImportError as e:
    print("❌ reportlab failed:", e)

try:
    import requests
    print("✅ requests - Ready for HTTP calls")
except ImportError as e:
    print("❌ requests failed:", e)

try:
    import os
    from dotenv import load_dotenv
    print("✅ python-dotenv - Ready for environment variables")
except ImportError as e:
    print("❌ dotenv failed:", e)

print("=" * 40)
print("🚀 Setup test complete!")

# Test Python version
import sys
print(f"Python version: {sys.version}")
print(f"Python path: {sys.executable}")