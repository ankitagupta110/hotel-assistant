from datetime import datetime

from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    guest_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    check_in: Mapped[str] = mapped_column(String(32), nullable=False)
    check_out: Mapped[str] = mapped_column(String(32), nullable=False)
    room_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
