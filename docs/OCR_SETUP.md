# OCR Setup Guide

The AKLAWMS system includes OCR (Optical Character Recognition) capabilities to extract text from scanned PDFs and image-based documents.

## Overview

When you upload a scanned PDF (where text is embedded as images rather than actual text), the system will automatically attempt to use OCR to extract the text content.

## Installation

### Windows

1. **Download Tesseract OCR**
   - Visit: https://github.com/UB-Mannheim/tesseract/wiki
   - Download the latest installer (e.g., `tesseract-ocr-w64-setup-5.x.x.exe`)

2. **Install Tesseract**
   - Run the installer
   - **Important**: During installation, check "Add to PATH" or note the installation directory
   - Default location: `C:\Program Files\Tesseract-OCR`

3. **Verify Installation**
   - Open Command Prompt
   - Run: `tesseract --version`
   - You should see version information

4. **If Tesseract is not in PATH**
   - Find the installation directory (usually `C:\Program Files\Tesseract-OCR`)
   - Add it to your system PATH, OR
   - Configure the system by setting the path in code (see Configuration section)

5. **Restart the Application**
   - Close and restart the AKLAWMS server for changes to take effect

### macOS

```bash
# Using Homebrew
brew install tesseract

# Verify installation
tesseract --version
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr

# Verify installation
tesseract --version
```

### Linux (Fedora)

```bash
sudo dnf install tesseract
```

### Linux (Arch)

```bash
sudo pacman -S tesseract
```

## Configuration

If Tesseract is installed but not in your system PATH, you can configure the path manually:

### Option 1: Environment Variable

Set the `TESSDATA_PREFIX` environment variable if needed:

```bash
# Windows (PowerShell)
$env:TESSDATA_PREFIX = "C:\Program Files\Tesseract-OCR\tessdata"

# Linux/macOS
export TESSDATA_PREFIX=/usr/share/tesseract-ocr/tessdata
```

### Option 2: Code Configuration

If needed, you can set the Tesseract path in the code. Edit `server/services/ocr_service.py`:

```python
import pytesseract

# Windows example
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Linux/macOS example
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
```

## Usage

Once Tesseract is installed:

1. **Upload a Scanned PDF**
   - The system will automatically detect if a PDF is scanned (image-based)
   - OCR will be attempted automatically

2. **Processing Time**
   - OCR processing takes longer than regular text extraction
   - Large documents (50+ pages) may take several minutes
   - Progress is logged in the server console

3. **Quality Considerations**
   - OCR accuracy depends on image quality
   - Higher resolution scans produce better results
   - Clean, well-lit documents work best
   - Handwritten text may have lower accuracy

## Troubleshooting

### "OCR not available - Tesseract not installed"

**Solution**: Install Tesseract OCR following the installation steps above.

### "Tesseract found but version check failed"

**Solution**: 
- Verify Tesseract is in your system PATH
- Try running `tesseract --version` in terminal/command prompt
- If it works in terminal but not in the app, restart the application

### "OCR returned no text"

**Possible causes**:
- PDF images are too low resolution
- Images are corrupted
- Text is handwritten (OCR works best with printed text)
- Document is in a language not supported by installed Tesseract language packs

**Solutions**:
- Try improving the PDF quality
- Install additional language packs if needed: `tesseract-ocr-[lang]` (e.g., `tesseract-ocr-spa` for Spanish)
- Use a different OCR tool to pre-process the document

### Slow OCR Processing

**Solutions**:
- OCR is computationally intensive - be patient
- Large documents are processed in batches
- Consider processing documents in smaller chunks
- Ensure adequate system resources (CPU, RAM)

## Language Support

Tesseract supports many languages. To add language support:

### Windows
- Download language data packs from: https://github.com/tesseract-ocr/tessdata
- Place `.traineddata` files in: `C:\Program Files\Tesseract-OCR\tessdata`

### Linux/macOS
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr-[lang]

# Example: Spanish
sudo apt-get install tesseract-ocr-spa
```

## Performance Tips

1. **Image Quality**: Higher DPI scans (300+ DPI) produce better OCR results
2. **Document Preparation**: Clean, straight scans work better than skewed or noisy images
3. **Batch Processing**: Large documents are automatically processed in batches to manage memory
4. **Page Limits**: The system limits OCR to the first 50 pages by default for performance

## Advanced Configuration

The OCR service uses these Tesseract settings by default:
- **OEM Mode 3**: LSTM neural network (best accuracy)
- **PSM Mode 6**: Single uniform block of text (good for legal documents)
- **PSM Mode 3**: Fully automatic page segmentation (fallback if Mode 6 fails)

These can be adjusted in `server/services/ocr_service.py` if needed for specific document types.

## Support

If you encounter issues with OCR:
1. Check that Tesseract is properly installed and in PATH
2. Verify the PDF is actually scanned (not text-based)
3. Check server logs for detailed error messages
4. Try a test document to verify OCR is working

