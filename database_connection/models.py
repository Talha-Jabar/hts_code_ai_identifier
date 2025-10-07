# database/models.py
"""
SQLAlchemy ORM models for HTS and Tariff Programs database.
Defines the structure for hts_codes and tariff_programs tables with proper relationships.
"""

from sqlalchemy import Column, Integer, String, Text, Table, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.hybrid import hybrid_property

# Create base class for declarative models
Base = declarative_base()


# Association table for many-to-many relationship between HTS codes and tariff programs
# This table links HTS codes to the tariff programs mentioned in their Special_Rate_of_Duty
hts_tariff_association = Table(
    'hts_tariff_association',
    Base.metadata,
    Column('hts_id', Integer, ForeignKey('hts_codes.id'), primary_key=True),
    Column('tariff_program_id', Integer, ForeignKey('tariff_programs.id'), primary_key=True),
    Column('rate_percentage', String(50), nullable=True)  # Store specific rate if mentioned (e.g., "1.7%")
)


class HTSCode(Base):
    """
    Model for HTS (Harmonized Tariff Schedule) codes.
    Represents processed HTS data with hierarchical specifications and duty rates.
    """
    __tablename__ = 'hts_codes'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # HTS identification columns
    hts_number = Column(String(20), nullable=False, index=True)  # Original HTS number with dots
    hts_digits = Column(String(10), nullable=False, unique=True, index=True)  # Normalized 10-digit code
    indent = Column(String(10), nullable=True)  # Hierarchy level indicator
    
    # Description and specifications
    description = Column(Text, nullable=True)  # Base description
    spec_level_1 = Column(Text, nullable=True)
    spec_level_2 = Column(Text, nullable=True)
    spec_level_3 = Column(Text, nullable=True)
    spec_level_4 = Column(Text, nullable=True)
    spec_level_5 = Column(Text, nullable=True)
    spec_level_6 = Column(Text, nullable=True)
    spec_level_7 = Column(Text, nullable=True)
    spec_level_8 = Column(Text, nullable=True)
    spec_level_9 = Column(Text, nullable=True)
    spec_level_10 = Column(Text, nullable=True)
    
    # Duty and unit information
    unit_of_quantity = Column(String(100), nullable=True)
    general_rate_of_duty = Column(String(200), nullable=True)
    special_rate_of_duty = Column(Text, nullable=True)  # Contains tariff program codes
    column_2_rate_of_duty = Column(String(200), nullable=True)
    
    # Additional fields for search and embeddings
    text = Column(Text, nullable=True)  # Concatenated text for embedding/search
    prefix4 = Column(String(4), nullable=True, index=True)  # First 4 digits for quick filtering
    prefix6 = Column(String(6), nullable=True, index=True)  # First 6 digits for quick filtering
    
    # Relationships
    # Many-to-many relationship with tariff programs
    tariff_programs = relationship(
        "TariffProgram",
        secondary=hts_tariff_association, # type: ignore
        back_populates="hts_codes"
    )
    
    @hybrid_property
    def full_description(self):
        """
        Constructs a full hierarchical description combining base description and all specifications.
        """
        parts = [self.description] if self.description else []
        for i in range(1, 11):
            spec = getattr(self, f'spec_level_{i}', None)
            if spec:
                parts.append(spec)
        return ' > '.join(parts)
    
    def __repr__(self):
        return f"<HTSCode(hts_number='{self.hts_number}', description='{self.description[:50]}...')>"


class TariffProgram(Base):
    """
    Model for tariff programs (trade agreements and preferential programs).
    Contains information about special duty rates for specific countries.
    """
    __tablename__ = 'tariff_programs'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Program identification
    program_code = Column(String(10), nullable=False, unique=True, index=True)  # e.g., "A", "BH", "CL"
    program_name = Column(String(200), nullable=True)  # Full program name/description
    group_name = Column(String(100), nullable=True)  # Program group (e.g., "FTA", "GSP")
    
    # Countries covered by this program (stored as semicolon-separated string)
    countries = Column(Text, nullable=True)  # e.g., "US;CA;MX" for USMCA
    
    # Additional metadata
    description = Column(Text, nullable=True)  # Detailed description of the program
    
    # Relationships
    # Many-to-many relationship with HTS codes
    hts_codes = relationship(
        "HTSCode",
        secondary=hts_tariff_association,
        back_populates="tariff_programs"
    )
    
    @hybrid_property
    def country_list(self):
        """
        Returns a list of country codes covered by this program.
        """
        if self.countries:
            return [c.strip() for c in self.countries.split(';') if c.strip()]
        return []
    
    def __repr__(self):
        return f"<TariffProgram(code='{self.program_code}', name='{self.program_name}')>"


class CountryCode(Base):
    """
    Optional model for storing country information.
    Can be used to normalize country data and add additional metadata.
    """
    __tablename__ = 'country_codes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    iso_code = Column(String(2), nullable=False, unique=True, index=True)  # ISO 3166-1 alpha-2
    country_name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=True)  # e.g., "North America", "Europe"
    
    def __repr__(self):
        return f"<CountryCode(iso='{self.iso_code}', name='{self.country_name}')>"