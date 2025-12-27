# AI Laws Protection System

## IMMUTABLE BASE CODE

The AI Laws (`ai_laws.json`) are the **FUNDAMENTAL BASE CODE** of this system - equivalent to the laws of physics. They are **IMMUTABLE** and **CANNOT BE MODIFIED** by anyone.

## Protection Mechanisms

### 1. Checksum Verification
- Every time the system starts, it verifies the AI Laws file against a stored checksum
- If the checksum doesn't match, the system **WILL NOT START**
- Checksum is stored in `config/.ai_laws_checksum`

### 2. Structure Validation
- System verifies that all 10 required articles are present
- System verifies that required keys (preamble, articles, enforcement) exist
- System verifies that enforcement section is correct

### 3. Startup Verification
- AI Laws are verified **before** the server starts
- If verification fails, the server **refuses to start**
- Critical error is logged with full details

### 4. Runtime Protection
- AI Laws are loaded through `ai_laws_protection` service
- Every load verifies integrity
- If tampering is detected, system logs critical error and refuses to operate

## What Happens If Someone Tries to Modify AI Laws

1. **Checksum Mismatch Detected**: System detects the file has been changed
2. **Critical Error Logged**: Full details logged to system logs
3. **Server Refuses to Start**: System will not start with modified AI Laws
4. **Error Message**: Clear message that AI Laws are immutable and cannot be modified

## File Locations

- **AI Laws File**: `config/ai_laws.json` (IMMUTABLE)
- **Checksum File**: `config/.ai_laws_checksum` (auto-generated)
- **Protection Service**: `server/services/ai_laws_protection.py`

## Required Structure

The AI Laws file MUST contain:
- `preamble`: System description
- `articles`: All 10 articles (article_i through article_x)
- `enforcement`: Enforcement rules (deviation_from_code: "critical_error")

## Restoration

If AI Laws are accidentally modified:
1. Restore from version control (git)
2. Or restore from backup
3. System will automatically verify and resume operation

## Security Note

This protection prevents:
- Accidental modification
- Unauthorized changes
- Tampering attempts
- Corruption

The system treats AI Laws as **read-only base code** that defines the fundamental operating principles.

