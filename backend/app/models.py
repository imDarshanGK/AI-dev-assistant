from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    histories = relationship(
        "QueryHistory", back_populates="user", cascade="all, delete-orphan"
    )
    favorites = relationship(
        "FavoriteResult", back_populates="user", cascade="all, delete-orphan"
    )


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    user = relationship("User", back_populates="histories")


class FavoriteResult(Base):
    __tablename__ = "favorite_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    user = relationship("User", back_populates="favorites")


class DigestSubscription(Base):
    __tablename__ = "digest_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SharedSnippet(Base):
    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    deliveries = relationship(
        "WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    deliveries = relationship(
        "WebhookDelivery", back_populates="event", cascade="all, delete-orphan"
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("webhook_events.id"), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False)

    webhook = relationship("Webhook", back_populates="deliveries")
    event = relationship("WebhookEvent", back_populates="deliveries")

