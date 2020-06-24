"""added sent_at to reminders

Revision ID: 1d0d96b152df
Revises: 956b7349fe71
Create Date: 2020-06-24 04:40:42.961985

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d0d96b152df'
down_revision = '956b7349fe71'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("reminders") as batch_op:
        batch_op.add_column(sa.Column("sent_at", sa.DateTime))


def downgrade():
    with op.batch_alter_table("reminders") as batch_op:
        batch_op.drop_column("sent_at")
