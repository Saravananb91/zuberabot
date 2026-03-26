"""PostgreSQL database connection and session management."""

import os
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from zuberabot.database.models import Base
from loguru import logger


class DatabaseManager:
    """Manage PostgreSQL database connections."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection string.
                Format: postgresql://user:password@host:port/database
                If not provided, reads from DATABASE_URL env var.
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:Sara12345$@localhost:5433/zubera_bot"
        )
        
        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=10,  # Max 10 connections in pool
            max_overflow=20,  # Allow 20 additional connections
            pool_timeout=30,  # Connection timeout
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL logging
        )
        
        # Configure connection event listeners
        self._setup_event_listeners()
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine
        )
        
        logger.info(f"Database manager initialized for: {self._safe_url()}")
    
    def _safe_url(self) -> str:
        """Get database URL with password masked."""
        if "@" in self.database_url:
            parts = self.database_url.split("@")
            if ":" in parts[0]:
                user_pass = parts[0].split("//")[1].split(":")
                return f"postgresql://{user_pass[0]}:****@{parts[1]}"
        return self.database_url
    
    def _setup_event_listeners(self):
        """Setup connection event listeners for logging and monitoring."""
        
        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            logger.debug("New database connection established")
        
        @event.listens_for(self.engine, "close")
        def receive_close(dbapi_conn, connection_record):
            logger.debug("Database connection closed")
    
    def create_tables(self):
        """Create all database tables if they don't exist."""
        from sqlalchemy import text
        try:
            # Initialize pgvector extension first
            with self.engine.begin() as conn:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception as ex:
                    logger.warning(f"Could not load pgvector extension: {ex}. Proceeding without it.")
                
            # Import models dynamically to ensure they register in Base.metadata
            import zuberabot.database.vector_store
            
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables. USE WITH CAUTION!"""
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("All database tables dropped")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session context manager.
        
        Yields:
            Database session.
            
        Example:
            with db_manager.get_session() as session:
                user = session.query(User).filter_by(user_id="whatsapp:123").first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """
        Get database session directly (for async contexts).
        
        Note: Remember to close the session when done!
        
        Returns:
            Database session.
        """
        return self.SessionLocal()
    
    def close(self):
        """Close all database connections."""
        self.engine.dispose()
        logger.info("Database connections closed")
    
    def health_check(self) -> bool:
        """
        Check database connectivity.
        
        Returns:
            True if database is accessible, False otherwise.
        """
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            logger.info("Database health check: OK")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    # Session Management Methods
    
    def get_or_create_session(self, session_key: str, user_id: str):
        """
        Get existing session or create new one.
        
        Args:
            session_key: Session identifier (channel:chat_id)
            user_id: User identifier
            
        Returns:
            Session object
        """
        from zuberabot.database.models import ChatSession as SessionModel
        from zuberabot.database.models import User
        
        with self.get_session() as session:
            # Try to get existing session
            db_session = session.query(SessionModel).filter_by(session_key=session_key).first()
            
            if db_session:
                # Update last accessed
                db_session.last_accessed = db_session.updated_at
                session.commit()
                return db_session
            
            # Ensure user exists before creating session (foreign key constraint)
            existing_user = session.query(User).filter_by(user_id=user_id).first()
            if not existing_user:
                # Extract phone number from user_id (e.g. "whatsapp:918072421984@s.whatsapp.net")
                phone = user_id.split(":")[-1].split("@")[0] if ":" in user_id else user_id
                new_user = User(user_id=user_id, phone_number=phone, name=phone)
                session.add(new_user)
                session.commit()
                logger.info(f"Auto-created user: {user_id}")
            
            # Create new session
            db_session = SessionModel(
                user_id=user_id,
                session_key=session_key,
                messages=[],
                session_metadata={}
            )
            session.add(db_session)
            session.commit()
            session.refresh(db_session)
            logger.info(f"Created new session: {session_key} for user {user_id}")
            return db_session
    
    def add_session_message(self, session_key: str, role: str, content: str, **kwargs):
        """
        Add message to session.
        
        Args:
            session_key: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            **kwargs: Additional message metadata
        """
        from zuberabot.database.models import ChatSession as SessionModel
        
        with self.get_session() as session:
            db_session = session.query(SessionModel).filter_by(session_key=session_key).first()
            if db_session:
                db_session.add_message(role, content, **kwargs)
                session.commit()
    
    def get_session_history(self, session_key: str, max_messages: int = 50):
        """
        Get session message history.
        
        Args:
            session_key: Session identifier
            max_messages: Maximum messages to return
            
        Returns:
            List of messages in LLM format
        """
        from zuberabot.database.models import ChatSession as SessionModel
        
        with self.get_session() as session:
            db_session = session.query(SessionModel).filter_by(session_key=session_key).first()
            if db_session:
                return db_session.get_history(max_messages)
            return []
    
    def cleanup_inactive_sessions(self, days: int = 7) -> int:
        """
        Archive or delete inactive sessions older than specified days.
        
        Args:
            days: Number of days of inactivity
            
        Returns:
            Number of sessions cleaned up
        """
        from datetime import datetime, timedelta
        from zuberabot.database.models import ChatSession as SessionModel
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with self.get_session() as session:
            inactive_sessions = session.query(SessionModel).filter(
                SessionModel.last_accessed < cutoff_date,
                SessionModel.is_active == True
            ).all()
            
            count = 0
            for db_session in inactive_sessions:
                db_session.is_active = False
                count += 1
            
            session.commit()
            logger.info(f"Cleaned up {count} inactive sessions")
            return count
            
    def delete_session(self, session_key: str) -> bool:
        """
        Delete a session from the database.
        
        Args:
            session_key: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        from zuberabot.database.models import ChatSession as SessionModel
        
        with self.get_session() as session:
            db_session = session.query(SessionModel).filter_by(session_key=session_key).first()
            if db_session:
                session.delete(db_session)
                session.commit()
                logger.info(f"Deleted session: {session_key}")
                return True
            return False
            
    def list_sessions(self, limit: int = 50) -> list[dict]:
        """
        List recent sessions.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session info dicts
        """
        from zuberabot.database.models import ChatSession as SessionModel
        
        with self.get_session() as session:
            sessions = session.query(SessionModel).order_by(SessionModel.updated_at.desc()).limit(limit).all()
            return [
                {
                    "key": s.session_key,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "is_active": s.is_active
                }
                for s in sessions
            ]
    
    # Workspace Management Methods
    
    def get_or_create_workspace(self, user_id: str, base_path: str = None):
        """
        Get or create user workspace.
        
        Args:
            user_id: User identifier
            base_path: Base directory for workspaces (defaults to ~/.zuberabot/workspaces)
            
        Returns:
            UserWorkspace object
        """
        from pathlib import Path
        from zuberabot.database.models import UserWorkspace
        
        if base_path is None:
            base_path = str(Path.home() / ".nanobot" / "workspaces")
        
        with self.get_session() as session:
            workspace = session.query(UserWorkspace).filter_by(user_id=user_id).first()
            
            if workspace:
                return workspace
            
            # Create unique workspace path
            # Use safe filename from user_id
            safe_id = user_id.replace(":", "_").replace("/", "_")
            workspace_path = str(Path(base_path) / safe_id)
            
            # Create directory
            Path(workspace_path).mkdir(parents=True, exist_ok=True)
            
            # Create workspace record
            workspace = UserWorkspace(
                user_id=user_id,
                workspace_path=workspace_path,
                storage_used_mb=0,
                max_storage_mb=1000
            )
            session.add(workspace)
            session.commit()
            session.refresh(workspace)
            logger.info(f"Created workspace for user {user_id} at {workspace_path}")
            return workspace
    
    def get_workspace_path(self, user_id: str) -> Optional[str]:
        """
        Get workspace path for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Workspace path or None
        """
        from zuberabot.database.models import UserWorkspace
        
        with self.get_session() as session:
            workspace = session.query(UserWorkspace).filter_by(user_id=user_id).first()
            return workspace.workspace_path if workspace else None
    

    # Ticket Operations

    def create_ticket(
        self,
        user_id: int | str,
        channel: str,
        chat_id: str,
        subject: str,
        description: str = "",
        **kwargs
    ):
        """Create a new ticket."""
        from zuberabot.database.models import Ticket

        # Ensure user_id is string for our Postgres schema
        user_id_str = str(user_id)
        
        # Check if user exists, if not create basic record
        # This handles migration cases where user might not be in users table yet
        with self.get_session() as session:
            from zuberabot.database.models import User
            if not session.query(User).filter_by(user_id=user_id_str).first():
                 # Minimal user creation
                 user = User(
                     user_id=user_id_str,
                     phone_number=user_id_str.split(':')[-1] if ':' in user_id_str else user_id_str
                 )
                 session.add(user)
                 session.commit()

        with self.get_session() as session:
            ticket = Ticket(
                user_id=user_id_str,
                channel=channel,
                chat_id=chat_id,
                subject=subject,
                description=description,
                priority=kwargs.get('priority', 'medium'),
                extra_data=kwargs.get('metadata', {})
            )
            session.add(ticket)
            session.commit()
            session.refresh(ticket)
            logger.info(f"Created ticket #{ticket.id} for user {user_id}")
            return ticket
    
    def get_ticket(self, ticket_id: int):
        """Get ticket by ID."""
        from zuberabot.database.models import Ticket
        
        with self.get_session() as session:
            return session.query(Ticket).filter_by(id=ticket_id).first()
    
    def update_ticket_status(self, ticket_id: int, status: str) -> bool:
        """Update ticket status."""
        from datetime import datetime
        from zuberabot.database.models import Ticket
        
        with self.get_session() as session:
            ticket = session.query(Ticket).filter_by(id=ticket_id).first()
            if ticket:
                ticket.status = status
                ticket.updated_at = datetime.utcnow()
                if status in ['resolved', 'closed']:
                    ticket.resolved_at = datetime.utcnow()
                session.commit()
                return True
            return False
    
    def get_user_tickets(self, user_id: int | str, status: Optional[str] = None):
        """Get all tickets for a user, optionally filtered by status."""
        from zuberabot.database.models import Ticket
        
        user_id_str = str(user_id)
        
        with self.get_session() as session:
            query = session.query(Ticket).filter_by(user_id=user_id_str)
            if status:
                query = query.filter_by(status=status)
            return query.order_by(Ticket.created_at.desc()).all()
    

    # Expense Operations

    def add_expense(
        self,
        user_id: int | str,
        amount: float,
        category: str,
        description: str = "",
        date: Optional[str] = None
    ):
        """Add a new expense."""
        from datetime import datetime
        from zuberabot.database.models import Expense
        
        user_id_str = str(user_id)
        
        # Ensure user exists (similar to ticket creation logic)
        # Check if user exists, if not create basic record
        with self.get_session() as session:
            from zuberabot.database.models import User
            if not session.query(User).filter_by(user_id=user_id_str).first():
                 # Minimal user creation
                 user = User(
                     user_id=user_id_str,
                     phone_number=user_id_str.split(':')[-1] if ':' in user_id_str else user_id_str
                 )
                 session.add(user)
                 session.commit()
        
        with self.get_session() as session:
            expense_date = datetime.fromisoformat(date) if date else datetime.utcnow()
            
            expense = Expense(
                user_id=user_id_str,
                amount=amount,
                category=category,
                description=description,
                date=expense_date
            )
            session.add(expense)
            session.commit()
            session.refresh(expense)
            logger.info(f"Added expense {amount} for user {user_id}")
            return expense

    def get_expenses(
        self,
        user_id: int | str,
        month: Optional[str] = None,
        category: Optional[str] = None
    ):
        """Get expenses filtered by month (YYYY-MM) or category."""
        from sqlalchemy import extract
        from zuberabot.database.models import Expense
        
        user_id_str = str(user_id)
        
        with self.get_session() as session:
            query = session.query(Expense).filter_by(user_id=user_id_str)
            
            if month:
                try:
                    year, month_num = map(int, month.split('-'))
                    query = query.filter(
                        extract('year', Expense.date) == year,
                        extract('month', Expense.date) == month_num
                    )
                except ValueError:
                    logger.error(f"Invalid month format: {month}")
            
            if category:
                query = query.filter_by(category=category)
                
            return query.order_by(Expense.date.desc()).all()

    # User Management Methods
    
    def get_or_create_user(self, phone_number: str, channel: str = "whatsapp", **kwargs):
        """
        Get existing user or create new one.
        
        Args:
            phone_number: User phone number
            channel: Communication channel
            **kwargs: Additional user attributes
            
        Returns:
            Tuple of (User, created_flag)
        """
        from zuberabot.database.models import User
        
        user_id = f"{channel}:{phone_number}"
        
        with self.get_session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            
            if user:
                return user, False
            
            # Create new user
            user = User(
                user_id=user_id,
                phone_number=phone_number,
                **kwargs
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info(f"Created new user: {user_id}")
            return user, True


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get global database manager instance.
    
    Returns:
        Database manager singleton.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.create_tables()
    return _db_manager


def init_database(database_url: Optional[str] = None, create_tables: bool = True):
    """
    Initialize global database manager.
    
    Args:
        database_url: PostgreSQL connection string.
        create_tables: Whether to create tables on initialization.
    """
    global _db_manager
    _db_manager = DatabaseManager(database_url)
    if create_tables:
        _db_manager.create_tables()
    return _db_manager

