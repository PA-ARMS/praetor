"""
Outcome Extraction Service - Improved outcome detection from case text
Uses multiple strategies to accurately identify case outcomes
"""
import re
from typing import Optional, Dict, List


class OutcomeExtractionService:
    def __init__(self):
        # Outcome patterns with priority (higher = more reliable)
        self.outcome_patterns = {
            "Defendant Win": [
                (r"motion.*granted", 10),
                (r"grant.*motion", 10),  # "I grant the motion" or "grant [something] motion"
                (r"granted.*motion", 9),  # "motion was granted"
                (r"dismissed.*with.*prejudice", 10),
                (r"summary.*judgment.*for.*defendant", 10),
                (r"judgment.*for.*defendant", 9),
                (r"defendant.*prevails", 8),
                (r"defendant.*wins", 8),
                (r"complaint.*dismissed", 7),
                (r"affirmed.*in.*favor.*of.*defendant", 9),
                (r"reversed.*in.*favor.*of.*defendant", 9),
            ],
            "Plaintiff Win": [
                (r"motion.*denied", 10),
                (r"deny.*motion", 10),  # "I deny the motion" or "deny [something] motion"
                (r"denied.*motion", 9),  # "motion was denied"
                (r"judgment.*for.*plaintiff", 9),
                (r"plaintiff.*prevails", 8),
                (r"plaintiff.*wins", 8),
                (r"affirmed.*in.*favor.*of.*plaintiff", 9),
                (r"reversed.*in.*favor.*of.*plaintiff", 9),
                (r"damages.*awarded", 7),
                (r"plaintiff.*recover", 7),
            ],
            "Dismissed": [
                (r"dismissed.*without.*prejudice", 8),
                (r"voluntarily.*dismissed", 7),
                (r"case.*dismissed", 6),
            ],
            "Settlement": [
                (r"settled", 8),
                (r"settlement.*agreement", 9),
                (r"settlement.*reached", 8),
            ],
            "Reversed": [
                (r"reversed.*and.*remanded", 8),
                (r"reversed", 7),
            ],
            "Remanded": [
                (r"remanded", 7),
                (r"remand.*for.*further", 8),
            ]
        }
    
    def extract_outcome(self, case_text: str, case_data: Optional[Dict] = None) -> str:
        """
        Extract outcome from case text using multiple strategies
        Returns outcome or "Unknown" if cannot determine
        """
        if not case_text or len(case_text.strip()) < 50:
            return "Unknown"
        
        text_lower = case_text.lower()
        
        # Strategy 0: Check case metadata first (most reliable)
        if case_data:
            if case_data.get("outcome"):
                return case_data["outcome"]
            if case_data.get("disposition"):
                normalized = self._normalize_disposition(case_data["disposition"])
                if normalized != "Unknown":
                    return normalized
        
        # Strategy 1: Look for explicit outcome statements in first 5000 chars
        # (outcomes are usually stated early in opinions)
        search_text = text_lower[:5000]
        
        # Find all matches with scores
        matches = []
        for outcome, patterns in self.outcome_patterns.items():
            for pattern, priority in patterns:
                try:
                    matches_found = re.finditer(pattern, search_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    for match in matches_found:
                        matches.append({
                            "outcome": outcome,
                            "priority": priority,
                            "position": match.start(),
                            "text": match.group()
                        })
                except Exception:
                    # Skip invalid patterns
                    continue
        
        if matches:
            # Sort by priority (higher first), then by position (earlier first)
            matches.sort(key=lambda x: (-x["priority"], x["position"]))
            return matches[0]["outcome"]
        
        # Strategy 2: Look for conclusion/holding sections (expanded search)
        conclusion_keywords = [
            "conclusion", "holding", "we hold", "we find", "we conclude",
            "therefore", "accordingly", "for the foregoing", "it is ordered",
            "the court", "this court", "we affirm", "we reverse", "we deny",
            "we grant", "affirmed", "reversed", "denied", "granted"
        ]
        for keyword in conclusion_keywords:
            idx = text_lower.find(keyword)
            if idx != -1:
                # Extract 1000 chars after conclusion keyword
                conclusion_text = text_lower[idx:idx+1000]
                for outcome, patterns in self.outcome_patterns.items():
                    for pattern, priority in patterns:
                        try:
                            if re.search(pattern, conclusion_text, re.IGNORECASE | re.DOTALL):
                                return outcome
                        except Exception:
                            continue
        
        # Strategy 3: Search last 3000 chars (outcomes often at end) for high-priority patterns
        end_text = text_lower[-3000:] if len(text_lower) > 3000 else text_lower
        for outcome, patterns in self.outcome_patterns.items():
            # Only check high-priority patterns (8+) for end-of-text search
            for pattern, priority in patterns:
                if priority >= 8:
                    try:
                        if re.search(pattern, end_text, re.IGNORECASE | re.DOTALL):
                            return outcome
                    except Exception:
                        continue
        
        # Strategy 3b: Search entire text for high-priority patterns (if short enough)
        if len(text_lower) < 10000:
            for outcome, patterns in self.outcome_patterns.items():
                # Only check high-priority patterns (8+) for full text search
                for pattern, priority in patterns:
                    if priority >= 8:
                        try:
                            if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
                                return outcome
                        except Exception:
                            continue
        
        # Strategy 4: Look for common outcome phrases anywhere in text
        common_phrases = {
            "Defendant Win": [
                r"motion.*granted",
                r"grant.*motion",  # "I grant the motion"
                r"granted.*motion",  # "motion was granted"
                r"dismissed.*with.*prejudice",
                r"judgment.*entered.*for.*defendant",
                r"defendant.*motion.*granted",
                r"grant.*defendant",
                r"in.*favor.*of.*defendant",
                r"defendant.*prevails",
                r"defendant.*wins",
                r"for.*defendant",
                r"against.*plaintiff"
            ],
            "Plaintiff Win": [
                r"motion.*denied",
                r"deny.*motion",  # "I deny the motion"
                r"denied.*motion",  # "motion was denied"
                r"judgment.*entered.*for.*plaintiff",
                r"plaintiff.*shall.*recover",
                r"plaintiff.*motion.*granted",
                r"grant.*plaintiff",
                r"in.*favor.*of.*plaintiff",
                r"plaintiff.*prevails",
                r"plaintiff.*wins",
                r"for.*plaintiff",
                r"against.*defendant"
            ],
            "Dismissed": [
                r"dismissed.*without.*prejudice",
                r"voluntarily.*dismissed",
                r"case.*dismissed",
                r"complaint.*dismissed",
                r"action.*dismissed"
            ],
            "Settlement": [
                r"settled",
                r"settlement.*agreement",
                r"settlement.*reached",
                r"stipulated.*settlement"
            ]
        }
        
        for outcome, phrases in common_phrases.items():
            for phrase in phrases:
                if re.search(phrase, text_lower, re.IGNORECASE):
                    return outcome
        
        # Strategy 5: Look for court orders and final judgments
        order_patterns = [
            (r"it is.*ordered.*that.*defendant", "Defendant Win"),
            (r"it is.*ordered.*that.*plaintiff", "Plaintiff Win"),
            (r"the.*court.*orders.*defendant", "Defendant Win"),
            (r"the.*court.*orders.*plaintiff", "Plaintiff Win"),
            (r"we.*affirm.*in.*favor.*of.*defendant", "Defendant Win"),
            (r"we.*affirm.*in.*favor.*of.*plaintiff", "Plaintiff Win"),
        ]
        
        for pattern, outcome in order_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return outcome
        
        # Strategy 6: Look for affirm/reverse patterns (often indicate outcomes)
        if re.search(r"affirmed", text_lower) and not re.search(r"reversed", text_lower):
            # If affirmed and not reversed, likely the lower court's outcome stands
            # Check if it mentions who won
            if re.search(r"defendant", text_lower[:1000]):
                return "Defendant Win"
            elif re.search(r"plaintiff", text_lower[:1000]):
                return "Plaintiff Win"
        
        if re.search(r"reversed.*and.*remanded", text_lower):
            return "Reversed"
        elif re.search(r"reversed", text_lower):
            return "Reversed"
        
        return "Unknown"
    
    def _normalize_disposition(self, disposition: str) -> str:
        """Normalize disposition strings to standard outcomes"""
        disp_lower = disposition.lower()
        
        if any(word in disp_lower for word in ["granted", "dismissed", "defendant"]):
            return "Defendant Win"
        elif any(word in disp_lower for word in ["denied", "plaintiff", "affirmed"]):
            return "Plaintiff Win"
        elif "settlement" in disp_lower:
            return "Settlement"
        elif "reversed" in disp_lower:
            return "Reversed"
        elif "remanded" in disp_lower:
            return "Remanded"
        
        return "Unknown"
    
    def extract_facts_without_outcome(self, case_text: str) -> str:
        """
        Extract facts while removing outcome-related sentences
        More sophisticated than simple keyword replacement
        """
        if not case_text:
            return ""
        
        # More robust sentence splitting that handles abbreviations
        # Split on sentence endings but preserve abbreviations
        sentences = []
        current_sentence = ""
        
        # Split on sentence boundaries more carefully
        parts = re.split(r'([.!?]+)', case_text)
        for i in range(0, len(parts), 2):
            if i < len(parts):
                sentence = parts[i]
                if i + 1 < len(parts):
                    punctuation = parts[i + 1]
                    # Check if this looks like an abbreviation (e.g., "U.S.", "Dr.", "Inc.")
                    if re.search(r'\b[A-Z]\.$', sentence) or re.search(r'\b(?:vs?|etc|Inc|Ltd|Corp)\.$', sentence, re.IGNORECASE):
                        current_sentence += sentence + punctuation
                        continue
                    sentence += punctuation
                else:
                    sentence = parts[i]
                
                if current_sentence:
                    sentence = current_sentence + sentence
                    current_sentence = ""
                
                if sentence.strip():
                    sentences.append(sentence.strip())
        
        if current_sentence:
            sentences.append(current_sentence.strip())
        
        # If sentence splitting failed, use paragraph-based approach
        if len(sentences) < 3:
            # Fall back to paragraph splitting
            paragraphs = case_text.split('\n\n')
            sentences = []
            for para in paragraphs:
                if para.strip():
                    # Split paragraph into sentences more carefully
                    para_sentences = re.split(r'(?<=[.!?])\s+', para)
                    sentences.extend([s.strip() for s in para_sentences if s.strip()])
        
        # Identify and remove outcome sentences
        # More specific patterns to avoid false positives
        outcome_indicators = [
            r"^\s*(?:the\s+)?motion\s+(?:is\s+)?(?:hereby\s+)?granted",
            r"^\s*(?:the\s+)?motion\s+(?:is\s+)?(?:hereby\s+)?denied",
            r"^\s*(?:it\s+is\s+)?(?:hereby\s+)?ordered\s+that",
            r"^\s*(?:the\s+)?(?:court\s+)?(?:hereby\s+)?grants?\s+(?:the\s+)?motion",
            r"^\s*(?:the\s+)?(?:court\s+)?(?:hereby\s+)?denies?\s+(?:the\s+)?motion",
            r"judgment\s+(?:is\s+)?(?:hereby\s+)?entered\s+for",
            r"^\s*(?:the\s+)?complaint\s+(?:is\s+)?(?:hereby\s+)?dismissed",
            r"^\s*(?:we\s+)?(?:hereby\s+)?affirm",
            r"^\s*(?:we\s+)?(?:hereby\s+)?reverse",
            r"^\s*(?:the\s+)?case\s+(?:is\s+)?(?:hereby\s+)?dismissed",
        ]
        
        filtered_sentences = []
        removed_count = 0
        
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            # Skip very short sentences (likely fragments)
            if len(sentence_lower) < 15:
                filtered_sentences.append(sentence)
                continue
            
            # Check if sentence contains outcome indicators
            is_outcome_sentence = False
            for indicator in outcome_indicators:
                if re.search(indicator, sentence_lower, re.IGNORECASE):
                    # But allow if it's in a question or hypothetical
                    if "?" in sentence or "if" in sentence_lower[:30] or "whether" in sentence_lower[:30] or "would" in sentence_lower[:30]:
                        continue
                    is_outcome_sentence = True
                    removed_count += 1
                    break
            
            if not is_outcome_sentence:
                filtered_sentences.append(sentence)
        
        # Rejoin sentences
        result = " ".join(filtered_sentences)
        
        # Fallback: if we removed too much (>40% of sentences), use original with keyword masking
        total_sentences = len(sentences)
        if total_sentences > 0 and (removed_count / total_sentences > 0.4 or len(result.strip()) < len(case_text) * 0.3):
            # Too much removed, use original with masked keywords
            result = case_text
            # Mask outcome keywords but keep the text
            for indicator in outcome_indicators:
                result = re.sub(indicator, "[outcome]", result, flags=re.IGNORECASE)
        
        # Ensure we have enough content
        if len(result.strip()) < 100 and len(case_text) > 200:
            # If result is too short, take first part of original (likely facts section)
            # Take first 80% of text (usually facts come before outcome)
            result = case_text[:int(len(case_text) * 0.8)]
        
        return result[:6000]  # Keep more detail for better matching (increased from 2000)


# Singleton instance
outcome_extraction_service = OutcomeExtractionService()


