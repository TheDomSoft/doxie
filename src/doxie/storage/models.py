"""SQLAlchemy models for Doxie storage.

Defines core entities: Document, Section, and Metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class Document(Base):
    """Represents an ingested document."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    path: Mapped[str] = mapped_column(String(2048))
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Optional persisted full text for convenience (can be omitted if large)
    text: Mapped[Optional[str]] = mapped_column(Text, default=None)

    sections: Mapped[list[Section]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    metadata_items: Mapped[list[Metadata]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Section(Base):
    """A logical section (e.g., heading) within a document."""

    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))

    title: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    level: Mapped[int] = mapped_column(Integer, default=1)

    start_offset: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    end_offset: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    document: Mapped[Document] = relationship(back_populates="sections")


class Metadata(Base):
    """Key-value metadata associated with a document."""

    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))

    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[Optional[str]] = mapped_column(Text, default=None)

    document: Mapped[Document] = relationship(back_populates="metadata_items")
