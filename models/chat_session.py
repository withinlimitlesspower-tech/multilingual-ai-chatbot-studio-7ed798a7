"""
Database models for chat sessions and message history.
Uses SQLAlchemy ORM with Flask-SQLAlchemy extension.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
import uuid

db = SQLAlchemy()


class ChatSession(db.Model):
    """
    Represents a chat session with metadata and relationships to messages.
    """
    __tablename__ = 'chat_sessions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False, default="New Chat")
    user_id = db.Column(db.String(100), nullable=True, index=True)  # For multi-user support
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = db.Column(JSONB, nullable=False, default=dict)  # Store session-specific metadata
    
    # Relationships
    messages = db.relationship('ChatMessage', backref='session', lazy='dynamic', 
                               cascade='all, delete-orphan', order_by='ChatMessage.created_at')
    
    def __init__(self, title: str = "New Chat", user_id: Optional[str] = None, 
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize a new chat session.
        
        Args:
            title: Session title
            user_id: Optional user identifier
            metadata: Optional session metadata
        """
        self.title = title
        self.user_id = user_id
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to dictionary representation.
        
        Returns:
            Dictionary with session data
        """
        return {
            'id': self.id,
            'title': self.title,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata,
            'message_count': self.messages.count()
        }
    
    def update_title_from_messages(self) -> None:
        """
        Update session title based on first user message content.
        Auto-generates title if not manually set.
        """
        if self.title == "New Chat" and self.messages.count() > 0:
            first_user_message = self.messages.filter_by(role='user').first()
            if first_user_message:
                # Extract first 50 chars for title
                content = first_user_message.content
                if len(content) > 50:
                    self.title = content[:47] + "..."
                else:
                    self.title = content
                db.session.commit()
    
    @classmethod
    def get_user_sessions(cls, user_id: str, limit: int = 50, offset: int = 0) -> List['ChatSession']:
        """
        Get chat sessions for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            offset: Pagination offset
            
        Returns:
            List of chat sessions
        """
        return cls.query.filter_by(user_id=user_id)\
                       .order_by(cls.updated_at.desc())\
                       .limit(limit)\
                       .offset(offset)\
                       .all()
    
    @classmethod
    def cleanup_old_sessions(cls, days_old: int = 30) -> int:
        """
        Delete sessions older than specified days.
        
        Args:
            days_old: Delete sessions older than this many days
            
        Returns:
            Number of sessions deleted
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        old_sessions = cls.query.filter(cls.created_at < cutoff_date).all()
        
        count = len(old_sessions)
        for session in old_sessions:
            db.session.delete(session)
        
        if count > 0:
            db.session.commit()
        
        return count


class ChatMessage(db.Model):
    """
    Represents a single message within a chat session.
    """
    __tablename__ = 'chat_messages'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), 
                          nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    metadata = db.Column(JSONB, nullable=False, default=dict)  # Store message metadata
    
    # Media references
    audio_url = db.Column(db.String(500), nullable=True)  # URL to generated audio
    image_url = db.Column(db.String(500), nullable=True)  # URL to generated/fetched image
    video_url = db.Column(db.String(500), nullable=True)  # URL to generated/fetched video
    
    # API response metadata
    model_used = db.Column(db.String(100), nullable=True)  # Which AI model was used
    tokens_used = db.Column(db.Integer, nullable=True)  # Token count for this message
    processing_time = db.Column(db.Float, nullable=True)  # Processing time in seconds
    
    # Indexes
    __table_args__ = (
        db.Index('idx_session_created', 'session_id', 'created_at'),
        db.Index('idx_role_session', 'role', 'session_id'),
    )
    
    def __init__(self, session_id: str, role: str, content: str, 
                 metadata: Optional[Dict[str, Any]] = None, audio_url: Optional[str] = None,
                 image_url: Optional[str] = None, video_url: Optional[str] = None,
                 model_used: Optional[str] = None, tokens_used: Optional[int] = None,
                 processing_time: Optional[float] = None) -> None:
        """
        Initialize a new chat message.
        
        Args:
            session_id: Parent session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional message metadata
            audio_url: URL to audio file
            image_url: URL to image file
            video_url: URL to video file
            model_used: AI model used for generation
            tokens_used: Token count
            processing_time: Processing time in seconds
        """
        self.session_id = session_id
        self.role = role
        self.content = content
        self.metadata = metadata or {}
        self.audio_url = audio_url
        self.image_url = image_url
        self.video_url = video_url
        self.model_used = model_used
        self.tokens_used = tokens_used
        self.processing_time = processing_time
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary representation.
        
        Returns:
            Dictionary with message data
        """
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'metadata': self.metadata,
            'audio_url': self.audio_url,
            'image_url': self.image_url,
            'video_url': self.video_url,
            'model_used': self.model_used,
            'tokens_used': self.tokens_used,
            'processing_time': self.processing_time
        }
    
    @classmethod
    def get_session_messages(cls, session_id: str, limit: int = 100, 
                            offset: int = 0) -> List['ChatMessage']:
        """
        Get messages for a specific session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            offset: Pagination offset
            
        Returns:
            List of chat messages
        """
        return cls.query.filter_by(session_id=session_id)\
                       .order_by(cls.created_at.asc())\
                       .limit(limit)\
                       .offset(offset)\
                       .all()
    
    @classmethod
    def get_recent_messages(cls, session_id: str, count: int = 10) -> List['ChatMessage']:
        """
        Get most recent messages for a session.
        
        Args:
            session_id: Session identifier
            count: Number of recent messages to return
            
        Returns:
            List of recent chat messages
        """
        return cls.query.filter_by(session_id=session_id)\
                       .order_by(cls.created_at.desc())\
                       .limit(count)\
                       .all()
    
    @classmethod
    def cleanup_orphaned_messages(cls) -> int:
        """
        Delete messages that reference non-existent sessions.
        
        Returns:
            Number of messages deleted
        """
        from sqlalchemy import text
        
        # Using raw SQL for efficiency with large datasets
        sql = text("""
            DELETE FROM chat_messages 
            WHERE session_id NOT IN (SELECT id FROM chat_sessions)
        """)
        
        result = db.session.execute(sql)
        db.session.commit()
        
        return result.rowcount


class UserPreference(db.Model):
    """
    Stores user preferences for the chatbot.
    """
    __tablename__ = 'user_preferences'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    language_preference = db.Column(db.String(10), nullable=False, default='en')
    voice_preference = db.Column(db.String(50), nullable=True)  # 11Labs voice ID
    theme = db.Column(db.String(20), nullable=False, default='light')
    auto_play_audio = db.Column(db.Boolean, nullable=False, default=True)
    show_timestamps = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    preferences = db.Column(JSONB, nullable=False, default=dict)  # Additional preferences
    
    def __init__(self, user_id: str, language_preference: str = 'en', 
                 voice_preference: Optional[str] = None, theme: str = 'light',
                 auto_play_audio: bool = True, show_timestamps: bool = True,
                 preferences: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize user preferences.
        
        Args:
            user_id: User identifier
            language_preference: Preferred language code
            voice_preference: Preferred voice ID
            theme: UI theme preference
            auto_play_audio: Auto-play audio messages
            show_timestamps: Show message timestamps
            preferences: Additional preferences
        """
        self.user_id = user_id
        self