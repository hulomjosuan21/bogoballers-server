import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from datetime import datetime
import os
import re
from difflib import get_close_matches

# Path to Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Project paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
image_path = os.path.join(BASE_DIR, "image2.png")

# Allowed addresses
ALLOWED_ADDRESSES = {
    "Brgy. Dakit, Bogo City, Cebu",
    "Cebu City",
    "Mandaue City"
}

def preprocess_image(image_path):
    """Preprocess the image to improve OCR accuracy."""
    img = Image.open(image_path)
    
    # Convert to grayscale
    img = img.convert("L")
    
    # Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)
    
    # Apply sharpening filter
    img = img.filter(ImageFilter.SHARPEN)
    
    # Threshold (black/white)
    img = img.point(lambda p: p > 150 and 255)  
    
    # Resize to make text bigger
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    
    return img

def clean_text(text):
    """Fix common OCR mistakes."""
    text = text.replace("l", "1")  # letter l -> number 1 in dates
    text = text.replace("Bray.", "Brgy.")
    return text

def extract_info(image_path):
    """Extract birthdate and address from image using OCR."""
    img = preprocess_image(image_path)
    text = pytesseract.image_to_string(img)
    text = clean_text(text)
    
    print("OCR Output:\n", text)  # Debugging
    
    birthdate = None
    address = None

    # Numeric date format
    date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text)
    if date_match:
        try:
            birthdate = datetime.strptime(date_match.group(1), "%m/%d/%Y").date()
        except ValueError:
            try:
                birthdate = datetime.strptime(date_match.group(1), "%m-%d-%Y").date()
            except ValueError:
                pass

    # Month name date format
    if not birthdate:
        date_match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
        if date_match:
            try:
                birthdate = datetime.strptime(date_match.group(1), "%B %d, %Y").date()
            except ValueError:
                pass

    for line in text.splitlines():
        if "address" in line.lower():
            raw_address = line.split(":", 1)[-1].strip()
            match = get_close_matches(raw_address, ALLOWED_ADDRESSES, n=1, cutoff=0.6)
            address = match[0] if match else raw_address
            break

    return birthdate, address

def validate(birthdate, address):
    """Check if person is allowed based on age and address."""
    if not birthdate or not address:
        return False, "Missing birthdate or address"

    today = datetime.today().date()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

    if age > 18:
        return False, f"Not allowed: Age is {age} (>18)"

    if address not in ALLOWED_ADDRESSES:
        return False, f"Not allowed: Address '{address}' not in allowed list"

    return True, "Valid"

if __name__ == "__main__":
    dob, addr = extract_info(image_path)
    is_valid, msg = validate(dob, addr)
    print(msg)
