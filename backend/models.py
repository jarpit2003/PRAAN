import os
import uuid
from datetime import date, datetime
from sqlalchemy import (
    create_engine, Column, String, Numeric, Boolean, Date,
    DateTime, Text, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/praan_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Patient(Base):
    __tablename__ = "patients"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name             = Column(String(100), nullable=False)
    blood_type       = Column(String(3), nullable=False)
    city             = Column(String(50), nullable=False)
    hemoglobin_level = Column(Numeric(4, 1))
    last_transfusion = Column(Date)
    thalassemia_type = Column(String(30))
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)

    requests = relationship("TransfusionRequest", back_populates="patient", cascade="all, delete")


class Donor(Base):
    __tablename__ = "donors"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name               = Column(String(100), nullable=False)
    phone              = Column(String(15), nullable=False, unique=True)
    blood_type         = Column(String(3), nullable=False)
    city               = Column(String(50), nullable=False)
    response_score     = Column(Numeric(3, 1), default=5.0)
    last_donation      = Column(Date)
    preferred_language = Column(String(2), default="en")
    is_active          = Column(Boolean, default=True)
    topsis_score       = Column(Numeric(6, 4), default=0.5)
    created_at         = Column(DateTime(timezone=True), default=datetime.utcnow)

    matches = relationship("DonorMatch", back_populates="donor", cascade="all, delete")


class TransfusionRequest(Base):
    __tablename__ = "transfusion_requests"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id     = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    predicted_date = Column(Date, nullable=False)
    urgency        = Column(String(10), nullable=False)
    status         = Column(String(10), nullable=False, default="pending")
    notes          = Column(Text)
    raised_by      = Column(String(20), default="coordinator")
    created_at     = Column(DateTime(timezone=True), default=datetime.utcnow)

    patient = relationship("Patient", back_populates="requests")
    matches = relationship("DonorMatch", back_populates="request", cascade="all, delete")


class DonorMatch(Base):
    __tablename__ = "donor_matches"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id   = Column(UUID(as_uuid=True), ForeignKey("transfusion_requests.id", ondelete="CASCADE"), nullable=False)
    donor_id     = Column(UUID(as_uuid=True), ForeignKey("donors.id", ondelete="CASCADE"), nullable=False)
    match_score  = Column(Numeric(5, 2), nullable=False)
    confirmed    = Column(Boolean, default=False)
    confirmed_at = Column(DateTime(timezone=True))
    notified_at  = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), default=datetime.utcnow)

    request = relationship("TransfusionRequest", back_populates="matches")
    donor   = relationship("Donor", back_populates="matches")
