"""merge_heads_accounts_y_emails

Revision ID: merge_heads_accounts_y_emails
Revises: 85bae8defcf9, actualizar_emails_2_usos_a_completed
Create Date: 2026-01-21

"""

from alembic import op  # noqa: F401


# revision identifiers, used by Alembic.
revision = "merge_heads_accounts_y_emails"
down_revision = ("85bae8defcf9", "actualizar_emails_2_usos_a_completed")
branch_labels = None
depends_on = None


def upgrade():
    # Merge migration: no-op.
    pass


def downgrade():
    # Downgrading a merge is a no-op.
    pass


