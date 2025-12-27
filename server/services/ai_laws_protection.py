"""
AI Laws Protection Service - Ensures AI Laws are never modified or tampered with
Implements checksum verification, structure validation, and tampering detection
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple
from server.utils.logger import setup_logger


class AILawsProtection:
    """Protection service for AI Laws - ensures immutability"""
    
    # Expected checksum of the AI Laws file (calculated from original)
    # This should be set to the hash of the verified, correct AI Laws file
    EXPECTED_CHECKSUM = None  # Will be calculated on first load
    
    # Required structure - all articles must be present
    REQUIRED_ARTICLES = [
        "article_i", "article_ii", "article_iii", "article_iv", "article_v",
        "article_vi", "article_vii", "article_viii", "article_ix", "article_x"
    ]
    
    # Required top-level keys
    REQUIRED_KEYS = ["preamble", "articles", "enforcement"]
    
    def __init__(self):
        self.logger = setup_logger("ai_laws_protection")
        self.ai_laws_path = Path(__file__).parent.parent.parent / "config" / "ai_laws.json"
        self.checksum_file = Path(__file__).parent.parent.parent / "config" / ".ai_laws_checksum"
        self._initialize_checksum()
    
    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _initialize_checksum(self):
        """Initialize or verify the expected checksum"""
        if self.checksum_file.exists():
            try:
                with open(self.checksum_file, 'r') as f:
                    stored_checksum = f.read().strip()
                    if stored_checksum:
                        AILawsProtection.EXPECTED_CHECKSUM = stored_checksum
                        self.logger.debug(f"Loaded stored AI Laws checksum: {stored_checksum[:16]}...")
            except Exception as e:
                self.logger.warning(f"Could not read checksum file: {e}")
        
        # If no checksum stored, calculate from current file and store it
        # This happens on first run - establishes the baseline
        if not AILawsProtection.EXPECTED_CHECKSUM and self.ai_laws_path.exists():
            try:
                with open(self.ai_laws_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    checksum = self._calculate_checksum(content)
                    # Store checksum for future verification
                    with open(self.checksum_file, 'w') as f:
                        f.write(checksum)
                    AILawsProtection.EXPECTED_CHECKSUM = checksum
                    self.logger.info(f"[OK] Initialized AI Laws checksum (baseline established): {checksum[:16]}...")
                    self.logger.info("  AI Laws are now protected - any modification will be detected")
            except Exception as e:
                self.logger.error(f"Could not initialize checksum: {e}")
    
    def verify_ai_laws(self) -> Tuple[bool, Optional[str]]:
        """
        Verify AI Laws file integrity and structure
        
        Returns:
            (is_valid, error_message)
        """
        if not self.ai_laws_path.exists():
            return False, "AI Laws file does not exist"
        
        try:
            # Read file content
            with open(self.ai_laws_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verify checksum
            if AILawsProtection.EXPECTED_CHECKSUM:
                current_checksum = self._calculate_checksum(content)
                if current_checksum != AILawsProtection.EXPECTED_CHECKSUM:
                    error_msg = (
                        f"CRITICAL: AI Laws file has been MODIFIED! "
                        f"Expected checksum: {AILawsProtection.EXPECTED_CHECKSUM[:16]}..., "
                        f"Actual: {current_checksum[:16]}... "
                        f"The AI Laws are IMMUTABLE and cannot be changed."
                    )
                    self.logger.critical(error_msg)
                    return False, error_msg
            
            # Parse and validate structure
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                return False, f"AI Laws file is not valid JSON: {e}"
            
            # Verify required top-level keys
            for key in self.REQUIRED_KEYS:
                if key not in data:
                    return False, f"AI Laws missing required key: {key}"
            
            # Verify all articles are present
            articles = data.get("articles", {})
            missing_articles = []
            for article in self.REQUIRED_ARTICLES:
                if article not in articles:
                    missing_articles.append(article)
            
            if missing_articles:
                return False, f"AI Laws missing required articles: {', '.join(missing_articles)}"
            
            # Verify enforcement section
            enforcement = data.get("enforcement", {})
            if not enforcement:
                return False, "AI Laws missing enforcement section"
            
            if enforcement.get("deviation_from_code") != "critical_error":
                return False, "AI Laws enforcement section has been modified"
            
            # All checks passed
            return True, None
            
        except Exception as e:
            return False, f"Error verifying AI Laws: {e}"
    
    def load_ai_laws(self) -> Optional[Dict]:
        """
        Load AI Laws with verification
        
        Returns:
            AI Laws dict if valid, None if tampered with
        """
        is_valid, error = self.verify_ai_laws()
        
        if not is_valid:
            self.logger.critical(f"AI LAWS VERIFICATION FAILED: {error}")
            self.logger.critical("SYSTEM CANNOT OPERATE WITHOUT VALID AI LAWS")
            # Return None to indicate failure - system should not proceed
            return None
        
        try:
            with open(self.ai_laws_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.critical(f"Could not load AI Laws: {e}")
            return None
    
    def get_checksum(self) -> Optional[str]:
        """Get current checksum of AI Laws file"""
        if not self.ai_laws_path.exists():
            return None
        try:
            with open(self.ai_laws_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self._calculate_checksum(content)
        except Exception:
            return None


# Singleton instance
ai_laws_protection = AILawsProtection()

