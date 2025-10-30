# database/models.py
"""
Simplified and Alembic-compatible SQLAlchemy models for HTS and Tariff Programs.
"""

from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, Table
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from .base import Base

# Many-to-many association table between HTS codes and tariff programs
hts_tariff_association = Table(
    "hts_tariff_association",
    Base.metadata,
    Column("hts_id", Integer, ForeignKey("hts_codes.id", ondelete="CASCADE"), primary_key=True),
    Column("tariff_program_id", Integer, ForeignKey("tariff_programs.id", ondelete="CASCADE"), primary_key=True),
    Column("rate_percentage", String(50), nullable=True)
)


class HTSCode(Base):
    """Model for Harmonized Tariff Schedule (HTS) codes."""
    __tablename__ = "hts_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hts_number = Column(String(20), nullable=False, index=True)
    hts_digits = Column(String(10), nullable=False, unique=True, index=True)
    indent = Column(String(10), nullable=True)

    description = Column(Text, nullable=True)
    general_rate_of_duty = Column(String(200), nullable=True)
    special_rate_of_duty = Column(Text, nullable=True)
    column_2_rate_of_duty = Column(String(200), nullable=True)
    unit_of_quantity = Column(String(100), nullable=True)

    # Optional for text search
    text = Column(Text, nullable=True)
    prefix4 = Column(String(4), index=True)
    prefix6 = Column(String(6), index=True)

    # Relationship with tariff programs
    tariff_programs = relationship(
        "TariffProgram",
        secondary=hts_tariff_association,
        back_populates="hts_codes"
    )

    @hybrid_property
    def full_description(self):
        """Returns a concatenated full description."""
        return self.description or ""

    def __repr__(self):
        return f"<HTSCode(hts='{self.hts_number}', desc='{(self.description or '')[:40]}')>"


class TariffProgram(Base):
    """Model for tariff or preferential trade programs."""
    __tablename__ = "tariff_programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    program_code = Column(String(10), nullable=False, unique=True, index=True)
    program_name = Column(String(200), nullable=True)
    group_name = Column(String(100), nullable=True)
    countries = Column(Text, nullable=True)  # semicolon-separated
    description = Column(Text, nullable=True)

    hts_codes = relationship(
        "HTSCode",
        secondary=hts_tariff_association,
        back_populates="tariff_programs"
    )

    @hybrid_property
    def country_list(self):
        return [c.strip() for c in (self.countries or "").split(";") if c.strip()]

    def __repr__(self):
        return f"<TariffProgram(code='{self.program_code}', name='{self.program_name}')>"


class CountryCode(Base):
    """Optional model for standardized country info."""
    __tablename__ = "country_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    iso_code = Column(String(2), nullable=False, unique=True, index=True)
    country_name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<CountryCode(iso='{self.iso_code}', name='{self.country_name}')>"
