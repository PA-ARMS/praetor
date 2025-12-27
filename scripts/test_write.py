from pathlib import Path
import sys

# Test file writing
test_file = Path("C:/LAWFIRMAI/data/test_output.txt")
test_file.parent.mkdir(parents=True, exist_ok=True)

try:
    test_file.write_text("Test successful at " + str(__import__('datetime').datetime.now()))
    print("File written successfully")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)



















