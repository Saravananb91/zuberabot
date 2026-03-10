"""Database models for user management and KYC verification."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, JSON, ARRAY, Text, ForeignKey, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User profile model."""
    
    __tablename__ = "users"
    
    user_id = Column(String(100), primary_key=True)  # whatsapp:919876543210
    phone_number = Column(String(20), unique=True, nullable=False)
    name = Column(String(200))
    age = Column(Integer)
    profession = Column(String(100))
    income_range = Column(String(50))  # "5-10L", "10-20L", etc.
    risk_profile = Column(String(20))  # conservative, moderate, aggressive
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    verifications = relationship("Verification", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            "user_id": self.user_id,
            "phone_number": self.phone_number,
            "name": self.name,
            "age": self.age,
            "profession": self.profession,
            "income_range": self.income_range,
            "risk_profile": self.risk_profile,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Verification(Base):
    """KYC verification records."""
    
    __tablename__ = "verifications"
    
    verification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    verification_type = Column(String(50), nullable=False)  # pan, aadhaar, bank, etc.
    identifier = Column(String(100), nullable=False)  # PAN number, Aadhaar number, etc.
    status = Column(String(20), nullable=False)  # verified, failed, pending
    verified_at = Column(DateTime)
    response_data = Column(JSON)  # Full Surepass API response
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="verifications")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert verification to dictionary."""
        return {
            "verification_id": self.verification_id,
            "user_id": self.user_id,
            "verification_type": self.verification_type,
            "identifier": self.identifier,
            "status": self.status,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "response_data": self.response_data,
            "error_message": self.error_message,
        }


class UserPreferences(Base):
    """User investment preferences."""
    
    __tablename__ = "user_preferences"
    
    preference_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), unique=True, nullable=False)
    
    # Investment goals
    investment_goal = Column(String(100))  # retirement, child_education, wealth_creation, etc.
    investment_horizon = Column(Integer)  # years
    monthly_investment_capacity = Column(Integer)  # amount in INR
    preferred_categories = Column(ARRAY(String))  # ['equity', 'debt', 'hybrid']
    
    # Additional preferences
    tax_saving_preference = Column(Boolean, default=False)  # ELSS preference
    preferred_fund_houses = Column(ARRAY(String))  # ['HDFC', 'ICICI', ...]
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="preferences")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary."""
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "investment_goal": self.investment_goal,
            "investment_horizon": self.investment_horizon,
            "monthly_investment_capacity": self.monthly_investment_capacity,
            "preferred_categories": self.preferred_categories,
            "tax_saving_preference": self.tax_saving_preference,
            "preferred_fund_houses": self.preferred_fund_houses,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Conversation(Base):
    """Conversation history for context."""
    
    __tablename__ = "conversations"
    
    conversation_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    response = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user = relationship("User", back_populates="conversations")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary."""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "message": self.message,
            "response": self.response,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Recommendation(Base):
    """Track recommendations given to users."""
    
    __tablename__ = "recommendations"
    
    recommendation_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    scheme_code = Column(String(20), nullable=False)
    fund_name = Column(String(200))
    recommended_amount = Column(Integer)  # Monthly SIP amount
    allocation_percentage = Column(Numeric(5, 2))  # e.g., 40.00 for 40%
    reason = Column(Text)  # Why this fund was recommended
    accepted = Column(Boolean)  # Did user accept the recommendation?
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="recommendations")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "recommendation_id": self.recommendation_id,
            "user_id": self.user_id,
            "scheme_code": self.scheme_code,
            "fund_name": self.fund_name,
            "recommended_amount": self.recommended_amount,
            "allocation_percentage": float(self.allocation_percentage) if self.allocation_percentage else None,
            "reason": self.reason,
            "accepted": self.accepted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChatSession(Base):
    """Database-backed conversation sessions for multi-user support."""
    
    __tablename__ = "sessions"
    
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    session_key = Column(String(200), unique=True, nullable=False, index=True)  # channel:chat_id
    messages = Column(JSON, default=list)  # List of message dicts
    session_metadata = Column(JSON, default=dict)  # Additional session metadata (renamed from metadata)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "session_key": self.session_key,
            "messages": self.messages or [],
            "metadata": self.session_metadata or {},  # Expose as 'metadata' in dict
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "is_active": self.is_active,
        }
    
    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        if self.messages is None:
            self.messages = []
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
    
    def get_history(self, max_messages: int = 15, max_tokens_estimate: int = 800) -> List[Dict[str, Any]]:
        """Get recent message history for LLM context using sliding window."""
        if not self.messages:
            return []
            
        recent = []
        token_count = 0
        
        # Parse backwards to get the most recent messages first
        for msg in reversed(self.messages):
            # Rough approximation: 1 word ~ 1.3 tokens
            estimated_tokens = len(msg["content"].split()) * 1.3
            if token_count + estimated_tokens > max_tokens_estimate or len(recent) >= max_messages:
                # We have hit the limit, stop accumulating
                break
            
            recent.insert(0, {"role": msg["role"], "content": msg["content"]})
            token_count += estimated_tokens
            
        return recent



class UserWorkspace(Base):
    """User-specific workspace configuration for file/memory isolation."""
    
    __tablename__ = "user_workspaces"
    
    workspace_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), unique=True, nullable=False)
    workspace_path = Column(String(500), unique=True, nullable=False)  # Unique path per user
    storage_used_mb = Column(Integer, default=0)  # Storage tracking
    max_storage_mb = Column(Integer, default=1000)  # 1GB default limit
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace to dictionary."""
        return {
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "workspace_path": self.workspace_path,
            "storage_used_mb": self.storage_used_mb,
            "max_storage_mb": self.max_storage_mb,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Ticket(Base):
    """Ticket model for tracking user requests."""
    __tablename__ = 'tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    channel = Column(String(10), nullable=False)
    chat_id = Column(String(50), nullable=False)
    subject = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), default='open', index=True)
    priority = Column(String(10), default='medium')
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    assigned_to = Column(String(50), nullable=True)
    extra_data = Column(JSON, default=dict)  # JSON field in Postgres
    
    # Relationship
    user = relationship("User", backref="tickets")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "assigned_to": self.assigned_to,
            "extra_data": self.extra_data or {},
        }

class Expense(Base):
    """Expense model for tracking user spending."""
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    description = Column(String(200))
    date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="expenses")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": float(self.amount),
            "category": self.category,
            "description": self.description,
            "date": self.date.isoformat(),
            "created_at": self.created_at.isoformat(),
        }
