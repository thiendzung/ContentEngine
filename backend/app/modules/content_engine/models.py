class CalibrationExample(TimestampMixin, Base):
    __tablename__ = "calibration_examples"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(32))
    intent: Mapped[str | None] = mapped_column(String(64))
    example_type: Mapped[str] = mapped_column(String(32), nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    approved_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint("polarity in ('positive','negative')", name="ck_calibration_polarity"),
        CheckConstraint(
            "status in ('candidate','approved','retired')", name="ck_calibration_status"
        ),
    )


def register_models() -> None:
    """Import hook used by migration metadata discovery."""
    from app.modules.content_engine.journal import models as _journal_models  # noqa: F401
    from app.modules.customer_intelligence import (
        models as _customer_intelligence_models,  # noqa: F401
    )
    from app.modules.harness import models as _harness_models  # noqa: F401
    from app.modules.knowledge import models as _knowledge_models  # noqa: F401
    from app.modules.learning import models as _learning_models  # noqa: F401
    from app.modules.measurement import models as _measurement_models  # noqa: F401
    from app.modules.publishing import models as _publishing_models  # noqa: F401