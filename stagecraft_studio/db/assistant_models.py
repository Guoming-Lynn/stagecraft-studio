"""M6 storage. Credentials and raw prompts are deliberately absent."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from stagecraft_studio.db.base import Base


class ProviderProfile(Base):
    __tablename__ = "provider_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_json: Mapped[str] = mapped_column(Text)
    capabilities_json: Mapped[str] = mapped_column(Text)
    credential_id: Mapped[str] = mapped_column(String(64))


class LLMCall(Base):
    __tablename__ = "llm_call"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    stage_run_id: Mapped[int | None] = mapped_column(ForeignKey("stage_run.id"))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    sources_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Proposal(Base):
    __tablename__ = "proposal"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("llm_call.id"))
    stage_run_id: Mapped[int | None] = mapped_column(ForeignKey("stage_run.id"))
    body_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
