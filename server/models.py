"""
Database models for users, roles, and chat history
"""
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Enum as SQLEnum, Float, JSON, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, backref
from datetime import datetime
import enum
from server.config import settings

Base = declarative_base()
logger = logging.getLogger(__name__)


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    PARALEGAL = "paralegal"
    ATTORNEY = "attorney"
    ATTORNEY_PARTNER = "attorney_partner"


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.PARALEGAL)
    supervising_attorney_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # For paralegals
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)  # Require password change on first login
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    supervising_attorney = relationship("User", remote_side=[id], backref="paralegals")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(username={self.username}, role={self.role})>"


class ChatMessage(Base):
    """Chat message model"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String(100), nullable=False, index=True)
    subject = Column(String(200), nullable=True, index=True)  # Conversation topic/subject
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    sources = Column(Text, nullable=True)  # JSON string of sources (truncated for display)
    full_sources = Column(Text, nullable=True)  # JSON string of complete source data with full text
    warnings = Column(Text, nullable=True)  # JSON string of warnings
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="chat_messages")
    
    def __repr__(self):
        return f"<ChatMessage(user_id={self.user_id}, conversation_id={self.conversation_id}, subject={self.subject})>"


class AuditLog(Base):
    """Audit logging for security and compliance"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # e.g., login_success, chat_query
    path = Column(String(255), nullable=True)
    method = Column(String(10), nullable=True)
    status = Column(Integer, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)  # small JSON snippet or context
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")


class PredictionValidation(Base):
    """Tracks prediction validation against actual outcomes"""
    __tablename__ = "prediction_validations"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(100), nullable=False, index=True)  # CourtListener case ID or internal ID
    case_name = Column(String(255), nullable=True)
    case_facts = Column(Text, nullable=False)  # Facts used for prediction
    case_type = Column(String(50), nullable=True, index=True)
    jurisdiction = Column(String(50), nullable=True, index=True)
    
    # Prediction data
    predicted_outcome = Column(String(100), nullable=False)
    predicted_confidence = Column(Float, nullable=False)
    predicted_probabilities = Column(Text, nullable=True)  # JSON string
    similar_scenarios_count = Column(Integer, nullable=False, default=0)
    
    # Actual outcome
    actual_outcome = Column(String(100), nullable=False)
    actual_outcome_source = Column(String(100), nullable=True)  # e.g., "CourtListener", "manual"
    actual_reasoning_excerpt = Column(Text, nullable=True)
    actual_reasoning_citation = Column(String(255), nullable=True)
    
    # Validation results
    is_correct = Column(Boolean, nullable=False, index=True)
    error_type = Column(String(50), nullable=True, index=True)
    confidence_issue = Column(String(50), nullable=True)
    predicted_reasoning = Column(Text, nullable=True)
    
    # Metadata
    validated_at = Column(DateTime, default=datetime.utcnow, index=True)
    case_metadata = Column(Text, nullable=True)  # JSON string of additional case data
    
    def __repr__(self):
        return f"<PredictionValidation(case_id={self.case_id}, is_correct={self.is_correct})>"


class ErrorAnalysis(Base):
    """Stores detailed error analysis for learning"""
    __tablename__ = "error_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(Integer, ForeignKey("prediction_validations.id"), nullable=False, index=True)
    
    # Error classification
    error_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=True)  # major, minor
    
    # Analysis data (stored as JSON)
    outcome_mismatch = Column(Text, nullable=True)  # JSON
    misleading_scenarios = Column(Text, nullable=True)  # JSON
    missing_factors = Column(Text, nullable=True)  # JSON
    confidence_analysis = Column(Text, nullable=True)  # JSON
    
    # Learning insights
    insights = Column(Text, nullable=True)  # JSON
    recommendations = Column(Text, nullable=True)  # JSON array
    
    # Metadata
    analyzed_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    validation = relationship("PredictionValidation", backref="error_analysis")
    
    def __repr__(self):
        return f"<ErrorAnalysis(validation_id={self.validation_id}, error_type={self.error_type})>"


class ReasoningTrace(Base):
    """Stores generated reasoning for auditing and reuse"""
    __tablename__ = "reasoning_traces"
    
    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(Integer, ForeignKey("prediction_validations.id"), nullable=False, index=True)
    
    thesis = Column(Text, nullable=True)
    supporting_factors = Column(Text, nullable=True)  # JSON array
    citation_hints = Column(Text, nullable=True)  # JSON array or text
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    validation = relationship(
        "PredictionValidation",
        backref=backref("reasoning_trace", uselist=False, cascade="all, delete-orphan")
    )
    
    def __repr__(self):
        return f"<ReasoningTrace(validation_id={self.validation_id})>"


class ReasoningValidation(Base):
    """Stores reasoning comparison scores"""
    __tablename__ = "reasoning_validations"
    
    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(Integer, ForeignKey("prediction_validations.id"), nullable=False, unique=True)
    
    reasoning_score = Column(Float, nullable=True)
    fidelity_score = Column(Float, nullable=True)
    completeness_score = Column(Float, nullable=True)
    citation_alignment_score = Column(Float, nullable=True)
    
    missing_elements = Column(Text, nullable=True)  # JSON array
    extra_elements = Column(Text, nullable=True)  # JSON array
    curiosity_prompts = Column(Text, nullable=True)  # JSON array of follow-up questions
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    validation = relationship(
        "PredictionValidation",
        backref=backref("reasoning_validation", uselist=False, cascade="all, delete-orphan")
    )
    
    def __repr__(self):
        return f"<ReasoningValidation(validation_id={self.validation_id}, score={self.reasoning_score})>"


class LearningPattern(Base):
    """Stores learned patterns from error analysis"""
    __tablename__ = "learning_patterns"
    
    id = Column(Integer, primary_key=True, index=True)
    pattern_type = Column(String(50), nullable=False, index=True)  # e.g., "overconfidence", "procedural_miss"
    pattern_description = Column(Text, nullable=False)
    
    # Pattern data
    conditions = Column(Text, nullable=True)  # JSON - conditions that trigger this pattern
    recommendations = Column(Text, nullable=True)  # JSON array
    affected_case_types = Column(String(255), nullable=True)  # comma-separated
    
    # Statistics
    occurrence_count = Column(Integer, default=1)
    accuracy_impact = Column(Float, nullable=True)  # How much this pattern affects accuracy
    
    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)
    
    def __repr__(self):
        return f"<LearningPattern(pattern_type={self.pattern_type}, count={self.occurrence_count})>"


class UserCorrection(Base):
    """Stores user corrections and feedback on AI responses"""
    __tablename__ = "user_corrections"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Correction data
    original_response = Column(Text, nullable=False)  # The AI's original response
    corrected_response = Column(Text, nullable=True)  # User's correction (if provided)
    correction_type = Column(String(50), nullable=False, index=True)  # "factual_error", "citation_error", "missing_info", "incorrect_interpretation", "other"
    correction_details = Column(Text, nullable=True)  # Detailed explanation of the correction
    is_attorney_correction = Column(Boolean, default=False, index=True)  # True if corrected by attorney/attorney_partner
    
    # Verification status
    verification_status = Column(String(20), nullable=False, default="pending", index=True)  # "pending", "verified", "rejected", "needs_review"
    verified_by_rag = Column(Boolean, default=False)  # Whether RAG system verified this correction
    rag_verification_details = Column(Text, nullable=True)  # JSON - RAG verification results
    verified_by_attorney = Column(Boolean, default=False)  # Whether an attorney verified this
    verifying_attorney_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Learning integration
    incorporated_into_rag = Column(Boolean, default=False, index=True)  # Whether correction added to RAG corpus
    incorporated_into_patterns = Column(Boolean, default=False)  # Whether used to update learning patterns
    learning_impact = Column(Float, nullable=True)  # Measured impact on future accuracy
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    verified_at = Column(DateTime, nullable=True)
    incorporated_at = Column(DateTime, nullable=True)
    
    # Relationships
    chat_message = relationship("ChatMessage", backref="corrections")
    user = relationship("User", foreign_keys=[user_id])
    verifying_attorney = relationship("User", foreign_keys=[verifying_attorney_id])
    
    def __repr__(self):
        return f"<UserCorrection(id={self.id}, type={self.correction_type}, status={self.verification_status})>"


class UserKnowledge(Base):
    """Stores user-provided legal knowledge, expertise, and annotations"""
    __tablename__ = "user_knowledge"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Knowledge content
    title = Column(String(255), nullable=False)  # Brief title/description
    content = Column(Text, nullable=False)  # The actual knowledge content
    knowledge_type = Column(String(50), nullable=False, index=True)  # "statute_interpretation", "case_note", "procedure", "precedent", "practice_tip", "other"
    
    # Legal context
    topic = Column(String(255), nullable=True, index=True)  # e.g., "Domestic Assault", "Contract Formation"
    jurisdiction = Column(String(50), nullable=True, index=True)  # "Virginia", "Federal", etc.
    related_statutes = Column(Text, nullable=True)  # JSON array of related statute citations
    related_cases = Column(Text, nullable=True)  # JSON array of related case citations
    
    # Source/attribution
    source_type = Column(String(50), nullable=False, default="user_provided")  # "user_provided", "attorney_expertise", "firm_practice"
    is_attorney_knowledge = Column(Boolean, default=False, index=True)  # True if from attorney/attorney_partner
    verified_by_attorney = Column(Boolean, default=False)  # Whether verified by another attorney
    verifying_attorney_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Learning integration
    incorporated_into_rag = Column(Boolean, default=False, index=True)  # Whether added to RAG corpus
    usage_count = Column(Integer, default=0)  # How many times this knowledge was used
    helpful_count = Column(Integer, default=0)  # How many times marked as helpful
    
    # Metadata
    tags = Column(Text, nullable=True)  # JSON array of tags for categorization
    notes = Column(Text, nullable=True)  # Additional notes
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)  # Can be deactivated
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    verifying_attorney = relationship("User", foreign_keys=[verifying_attorney_id])
    
    def __repr__(self):
        return f"<UserKnowledge(id={self.id}, type={self.knowledge_type}, topic={self.topic})>"


class ResponseReview(Base):
    """Stores senior partner reviews of AI responses for continuous learning"""
    __tablename__ = "response_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Senior partner who reviewed
    
    # Review data
    review_status = Column(String(20), nullable=False, default="pending", index=True)  # "pending", "approved", "needs_correction", "flagged"
    accuracy_rating = Column(Integer, nullable=True)  # 1-5 scale for accuracy
    completeness_rating = Column(Integer, nullable=True)  # 1-5 scale for completeness
    clarity_rating = Column(Integer, nullable=True)  # 1-5 scale for clarity
    
    # Review feedback
    feedback_notes = Column(Text, nullable=True)  # Detailed feedback from reviewer
    correction_suggestions = Column(Text, nullable=True)  # Specific corrections or improvements
    strengths = Column(Text, nullable=True)  # What the AI did well
    weaknesses = Column(Text, nullable=True)  # Areas for improvement
    
    # Learning integration flags
    should_incorporate = Column(Boolean, default=False, index=True)  # Whether this review should be used for learning
    incorporated_into_learning = Column(Boolean, default=False, index=True)  # Whether feedback has been incorporated
    learning_priority = Column(String(20), nullable=True, default="normal")  # "high", "normal", "low"
    
    # Metadata
    reviewed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chat_message = relationship("ChatMessage", backref="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    
    def __repr__(self):
        return f"<ResponseReview(id={self.id}, chat_message_id={self.chat_message_id}, status={self.review_status})>"


# Database setup
connect_args = {}
db_url = settings.DATABASE_URL

if "sqlite" in db_url:
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    
    def ensure_column(table_name: str, column_name: str, ddl: str):
        try:
            existing_columns = {col["name"] for col in inspect(engine).get_columns(table_name)}
            if column_name not in existing_columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
                logger.info("Added missing column %s.%s", table_name, column_name)
        except Exception as exc:
            logger.warning("Could not ensure column %s.%s: %s", table_name, column_name, exc)
    
    ensure_column("prediction_validations", "actual_reasoning_excerpt", "TEXT")
    ensure_column("prediction_validations", "actual_reasoning_citation", "VARCHAR(255)")
    ensure_column("prediction_validations", "predicted_reasoning", "TEXT")
    ensure_column("chat_messages", "subject", "VARCHAR(200)")
    ensure_column("chat_messages", "full_sources", "TEXT")  # Complete source data for expansion


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

