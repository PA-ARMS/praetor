"""
Conversation Subject Service - Detects and organizes conversation topics
"""
import re
from typing import Optional, List, Dict
from server.utils.logger import setup_logger

logger = setup_logger("conversation_subject")


class ConversationSubjectService:
    """Service to detect and organize conversation subjects"""
    
    def __init__(self):
        # Common legal topic patterns
        self.legal_topics = {
            "statute": ["statute", "code section", "law", "legislation", "act"],
            "case_law": ["case", "precedent", "ruling", "decision", "opinion", "holding"],
            "motion": ["motion", "filing", "pleading", "petition"],
            "contract": ["contract", "agreement", "terms", "clause", "provision"],
            "tort": ["negligence", "defamation", "personal injury", "tort"],
            "criminal": ["criminal", "felony", "misdemeanor", "charge", "indictment"],
            "family_law": ["divorce", "custody", "child support", "alimony", "visitation"],
            "employment": ["employment", "discrimination", "harassment", "wrongful termination"],
            "real_estate": ["property", "real estate", "landlord", "tenant", "lease"],
            "business": ["corporation", "llc", "partnership", "business entity"],
            "estate": ["will", "estate", "probate", "trust", "inheritance"],
            "immigration": ["immigration", "visa", "citizenship", "deportation"],
            "bankruptcy": ["bankruptcy", "chapter 7", "chapter 11", "chapter 13"],
            "intellectual_property": ["patent", "trademark", "copyright", "ip"],
        }
        
        # Question patterns that indicate subject
        self.question_patterns = [
            r"what (is|are|was|were) (the|a|an)? (.+?)(\?|$)",
            r"how (do|does|did|can|should) (.+?)(\?|$)",
            r"tell me (about|more about) (.+?)(\?|$)",
            r"explain (.+?)(\?|$)",
            r"find (me|the|a|an) (.+?)(\?|$)",
            r"look up (.+?)(\?|$)",
        ]
    
    def detect_subject(self, message: str, conversation_history: Optional[List[Dict]] = None) -> Optional[str]:
        """
        Detect the subject/topic of a conversation from the message and history
        
        Args:
            message: The current user message
            conversation_history: Optional list of previous messages in the conversation
            
        Returns:
            A short subject string (e.g., "Domestic Assault Statute") or None
        """
        if not message or len(message.strip()) < 10:
            return None
        
        message_lower = message.lower()
        
        # If this is continuing a conversation, check history first
        if conversation_history:
            # Look for subject in previous messages
            for msg in reversed(conversation_history):
                if msg.get("subject"):
                    # Check if current message relates to same subject
                    if self._is_related(message, msg.get("subject", "")):
                        return msg.get("subject")
        
        # Extract key terms from message
        subject = self._extract_subject_from_message(message)
        
        return subject
    
    def _extract_subject_from_message(self, message: str) -> Optional[str]:
        """Extract subject from a single message"""
        message_lower = message.lower()
        
        # Check for specific legal topics
        detected_topics = []
        for topic, keywords in self.legal_topics.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_topics.append(topic)
        
        # Extract specific terms (statute names, case names, etc.)
        # Look for capitalized phrases (likely proper nouns)
        capitalized_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', message)
        
        # Remove common words
        common_words = {"The", "This", "That", "What", "How", "When", "Where", "Why", "Can", "Should", "Will", "Would"}
        meaningful_phrases = [p for p in capitalized_phrases if p not in common_words and len(p) > 3]
        
        # Try to extract from question patterns
        question_subject = None
        for pattern in self.question_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                # Get the captured group (the subject)
                groups = match.groups()
                if groups:
                    # Take the last non-empty group
                    for group in reversed(groups):
                        if group and len(group.strip()) > 3:
                            question_subject = group.strip()
                            break
                if question_subject:
                    break
        
        # Build subject string
        subject_parts = []
        
        # Add topic category if detected
        if detected_topics:
            # Use the most specific topic
            topic_name = detected_topics[0].replace("_", " ").title()
            subject_parts.append(topic_name)
        
        # Add specific terms
        if meaningful_phrases:
            # Take first 1-2 meaningful phrases
            specific_terms = " ".join(meaningful_phrases[:2])
            if specific_terms:
                subject_parts.append(specific_terms)
        
        # Add question subject if found
        if question_subject and question_subject not in " ".join(subject_parts).lower():
            subject_parts.append(question_subject.title())
        
        # If we have parts, combine them
        if subject_parts:
            subject = " - ".join(subject_parts[:2])  # Limit to 2 parts
            # Clean up and truncate
            subject = re.sub(r'\s+', ' ', subject).strip()
            if len(subject) > 150:
                subject = subject[:147] + "..."
            return subject
        
        # Fallback: use first 50 chars of message
        if len(message) > 50:
            return message[:47] + "..."
        return message
    
    def _is_related(self, message: str, subject: str) -> bool:
        """Check if a message is related to a given subject"""
        message_lower = message.lower()
        subject_lower = subject.lower()
        
        # Extract key words from subject
        subject_words = set(re.findall(r'\b\w{4,}\b', subject_lower))
        message_words = set(re.findall(r'\b\w{4,}\b', message_lower))
        
        # Check for overlap
        overlap = subject_words.intersection(message_words)
        if len(overlap) >= 2:  # At least 2 words in common
            return True
        
        # Check if message contains subject keywords
        if any(word in message_lower for word in subject_words if len(word) > 4):
            return True
        
        return False
    
    def get_conversations_by_subject(self, user_id: int, db) -> Dict[str, List[Dict]]:
        """
        Get all conversations organized by subject
        
        Returns:
            Dictionary mapping subject -> list of conversation summaries
        """
        try:
            from server.models import ChatMessage
            
            # Get all unique conversations with subjects
            conversations = db.query(
                ChatMessage.conversation_id,
                ChatMessage.subject,
                ChatMessage.timestamp
            ).filter(
                ChatMessage.user_id == user_id,
                ChatMessage.subject.isnot(None)
            ).distinct().order_by(ChatMessage.timestamp.desc()).all()
            
            # Group by subject
            by_subject = {}
            for conv_id, subject, timestamp in conversations:
                if subject not in by_subject:
                    by_subject[subject] = []
                by_subject[subject].append({
                    "conversation_id": conv_id,
                    "subject": subject,
                    "last_activity": timestamp.isoformat() if timestamp else None
                })
            
            return by_subject
        except Exception as e:
            logger.error(f"Error getting conversations by subject: {e}")
            return {}


# Singleton instance
conversation_subject_service = ConversationSubjectService()

