"""create_initial_tables

Revision ID: 98fe57788dda
Revises:
Create Date: 2026-08-14

Creates the four core tables required by the Basir AI MVP:
  - cafe
  - meja         (JSONB roi, unique (cafe_id, nomor_meja))
  - status_meja  (PK == FK to meja, check constraints on status & terisi)
  - snapshot     (unique (cafe_id, area_kamera))
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "98fe57788dda"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # cafe
    # ------------------------------------------------------------------
    op.create_table(
        "cafe",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nama", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="Asia/Jakarta",
        ),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_cafe_slug"),
    )

    # ------------------------------------------------------------------
    # meja
    # ------------------------------------------------------------------
    op.create_table(
        "meja",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("cafe_id", sa.BigInteger(), nullable=False),
        sa.Column("nomor_meja", sa.Integer(), nullable=False),
        sa.Column("kapasitas", sa.SmallInteger(), nullable=False),
        sa.Column("roi", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["cafe_id"],
            ["cafe.id"],
            name="fk_meja_cafe_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cafe_id", "nomor_meja", name="uq_meja_cafe_nomor"),
        sa.CheckConstraint("kapasitas > 0", name="ck_meja_kapasitas_positive"),
    )
    op.create_index("ix_meja_cafe_id", "meja", ["cafe_id"])

    # ------------------------------------------------------------------
    # status_meja
    # ------------------------------------------------------------------
    op.create_table(
        "status_meja",
        sa.Column("meja_id", sa.BigInteger(), nullable=False),
        sa.Column("terisi", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["meja_id"],
            ["meja.id"],
            name="fk_status_meja_meja_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("meja_id"),
        sa.CheckConstraint(
            "status IN ('available', 'partial', 'occupied')",
            name="ck_status_meja_status_valid",
        ),
        sa.CheckConstraint(
            "terisi >= 0",
            name="ck_status_meja_terisi_non_negative",
        ),
    )

    # ------------------------------------------------------------------
    # snapshot
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("cafe_id", sa.BigInteger(), nullable=False),
        sa.Column("area_kamera", sa.String(120), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["cafe_id"],
            ["cafe.id"],
            name="fk_snapshot_cafe_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cafe_id", "area_kamera", name="uq_snapshot_cafe_area"),
    )
    op.create_index("ix_snapshot_cafe_id", "snapshot", ["cafe_id"])


def downgrade() -> None:
    op.drop_table("snapshot")
    op.drop_table("status_meja")
    op.drop_table("meja")
    op.drop_table("cafe")
