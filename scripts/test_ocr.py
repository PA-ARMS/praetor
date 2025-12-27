"""Test OCR functionality"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.ocr_service import ocr_service

print("=" * 60)
print("OCR Service Test")
print("=" * 60)
print()

# Check if OCR is available
print("Checking OCR availability...")
if ocr_service.is_available():
    print("[OK] OCR is available!")
    print()
    
    # Try to get version
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract version: {version}")
    except Exception as e:
        print(f"Could not get version: {e}")
    
    print()
    print("OCR is ready to use!")
    print()
    print("To test with a scanned PDF:")
    print("  1. Upload a scanned PDF through the web interface")
    print("  2. The system will automatically detect it and use OCR")
    print()
else:
    print("[ERROR] OCR is NOT available")
    print()
    print("Installation instructions:")
    print(ocr_service.get_installation_instructions())
    print()

