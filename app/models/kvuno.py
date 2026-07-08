from typing import Any, Optional
import datetime

from geoalchemy2.types import Geometry
from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, PrimaryKeyConstraint, REAL, String, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class FileImport(Base):
    __tablename__ = 'file_imports'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='file_imports_pkey'),
        UniqueConstraint('check_sum', name='file_imports_check_sum_key')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_sum: Mapped[str] = mapped_column(String(100), nullable=False)
    file_name: Mapped[str] = mapped_column(String(120), nullable=False)
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    offset: Mapped[Optional[int]] = mapped_column(BigInteger)


class ImportConflict(Base):
    __tablename__ = 'import_conflicts'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='import_conflicts_pkey'),
        Index('idx_conflict_created_at', 'created_at')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(20))
    province: Mapped[Optional[str]] = mapped_column(String(20))
    lon: Mapped[Optional[float]] = mapped_column(REAL)
    lat: Mapped[Optional[float]] = mapped_column(REAL)
    variety: Mapped[Optional[str]] = mapped_column(String(20))
    season_type: Mapped[Optional[str]] = mapped_column(String(20))
    opt_date: Mapped[Optional[str]] = mapped_column(String(8))
    check_sum: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))


class PlantingRecommendation(Base):
    __tablename__ = 'planting_recommendations'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='planting_recommendations_pkey'),
        UniqueConstraint('country', 'province', 'lon', 'lat', 'variety', 'season_type', 'opt_date', name='uq_planting_recommendation'),
        Index('idx_check_sum', 'check_sum'),
        Index('idx_coordinates', 'coordinates', postgresql_using='gist'),
        Index('idx_country', 'country'),
        Index('idx_lat', 'lat'),
        Index('idx_lon', 'lon'),
        Index('idx_opt_date', 'opt_date'),
        Index('idx_planting_option', 'planting_option'),
        Index('idx_planting_recommendations_coordinates', 'coordinates', postgresql_using='gist'),
        Index('idx_province', 'province'),
        Index('idx_season_type', 'season_type'),
        Index('idx_variety', 'variety')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_sum: Mapped[str] = mapped_column(String(100), nullable=False)
    coordinates: Mapped[Any] = mapped_column(Geometry('POINT', 4326, 2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(20))
    province: Mapped[Optional[str]] = mapped_column(String(20))
    lon: Mapped[Optional[float]] = mapped_column(REAL)
    lat: Mapped[Optional[float]] = mapped_column(REAL)
    variety: Mapped[Optional[str]] = mapped_column(String(20))
    season_type: Mapped[Optional[str]] = mapped_column(String(20))
    opt_date: Mapped[Optional[str]] = mapped_column(String(8))
    planting_option: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
