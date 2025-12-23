"""Database models and utilities for chat history persistence."""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class Chat(Base):
    """Chat session model."""
    __tablename__ = "chats"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    plans = relationship("Plan", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    """Chat message model."""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    attachments = Column(JSON, nullable=True)  # [{type: "image", data: "base64..."}, ...]
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chat = relationship("Chat", back_populates="messages")


class Plan(Base):
    """Execution plan model."""
    __tablename__ = "plans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, approved, executed, cancelled
    plan_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chat = relationship("Chat", back_populates="plans")


class Database:
    """Database operations handler."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def create_chat(self, title: Optional[str] = None) -> Chat:
        """Create a new chat session."""
        with self.Session() as session:
            chat = Chat(title=title)
            session.add(chat)
            session.commit()
            session.refresh(chat)
            return {"id": chat.id, "title": chat.title, "created_at": chat.created_at.isoformat()}
    
    def get_chats(self, limit: int = 50) -> List[dict]:
        """Get all chats ordered by most recent."""
        with self.Session() as session:
            chats = session.query(Chat).order_by(Chat.updated_at.desc()).limit(limit).all()
            return [
                {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat(), 
                 "updated_at": c.updated_at.isoformat()}
                for c in chats
            ]
    
    def get_chat(self, chat_id: str) -> Optional[dict]:
        """Get a specific chat by ID."""
        with self.Session() as session:
            chat = session.query(Chat).filter(Chat.id == chat_id).first()
            if chat:
                return {"id": chat.id, "title": chat.title, "created_at": chat.created_at.isoformat()}
            return None
    
    def add_message(self, chat_id: str, role: str, content: str, attachments: List[dict] = None) -> dict:
        """Add a message to a chat."""
        with self.Session() as session:
            message = Message(
                chat_id=chat_id,
                role=role,
                content=content,
                attachments=attachments
            )
            session.add(message)
            
            # Update chat's updated_at
            chat = session.query(Chat).filter(Chat.id == chat_id).first()
            if chat:
                chat.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(message)
            return {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "attachments": message.attachments,
                "created_at": message.created_at.isoformat()
            }
    
    def get_messages(self, chat_id: str, limit: int = 100) -> List[dict]:
        """Get all messages for a chat."""
        with self.Session() as session:
            messages = session.query(Message)\
                .filter(Message.chat_id == chat_id)\
                .order_by(Message.created_at.asc())\
                .limit(limit)\
                .all()
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "attachments": m.attachments,
                    "created_at": m.created_at.isoformat()
                }
                for m in messages
            ]
    
    def save_plan(self, chat_id: str, plan_data: dict) -> dict:
        """Save an execution plan."""
        with self.Session() as session:
            plan = Plan(chat_id=chat_id, plan_data=plan_data)
            session.add(plan)
            session.commit()
            session.refresh(plan)
            return {
                "id": plan.id,
                "status": plan.status,
                "plan_data": plan.plan_data,
                "created_at": plan.created_at.isoformat()
            }
    
    def update_plan_status(self, plan_id: str, status: str) -> bool:
        """Update the status of a plan."""
        with self.Session() as session:
            plan = session.query(Plan).filter(Plan.id == plan_id).first()
            if plan:
                plan.status = status
                session.commit()
                return True
            return False
    
    def get_pending_plan(self, chat_id: str) -> Optional[dict]:
        """Get the pending plan for a chat."""
        with self.Session() as session:
            plan = session.query(Plan)\
                .filter(Plan.chat_id == chat_id, Plan.status == "pending")\
                .order_by(Plan.created_at.desc())\
                .first()
            if plan:
                return {
                    "id": plan.id,
                    "status": plan.status,
                    "plan_data": plan.plan_data,
                    "created_at": plan.created_at.isoformat()
                }
            return None
    
    def update_chat_title(self, chat_id: str, title: str) -> bool:
        """Update the title of a chat."""
        with self.Session() as session:
            chat = session.query(Chat).filter(Chat.id == chat_id).first()
            if chat:
                chat.title = title
                session.commit()
                return True
            return False
    
    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages."""
        with self.Session() as session:
            chat = session.query(Chat).filter(Chat.id == chat_id).first()
            if chat:
                session.delete(chat)
                session.commit()
                return True
            return False
