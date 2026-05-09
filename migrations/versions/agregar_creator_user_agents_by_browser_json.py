"""agregar creator_user_agents_by_browser_json a bot_global_config

Revision ID: agregar_creator_user_agents_by_browser_json
Revises: agregar_creator_user_agents_json
Create Date: 2026-05-05 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "agregar_creator_user_agents_by_browser_json"
down_revision = "agregar_creator_user_agents_json"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("bot_global_config")]
    if "creator_user_agents_by_browser_json" not in cols:
        op.add_column(
            "bot_global_config",
            sa.Column("creator_user_agents_by_browser_json", sa.Text(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("bot_global_config")]
    if "creator_user_agents_by_browser_json" in cols:
        op.drop_column("bot_global_config", "creator_user_agents_by_browser_json")
