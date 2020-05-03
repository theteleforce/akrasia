"""actually make last_command_time

Revision ID: 51eb9fa9b6ec
Revises: 16762e72af61
Create Date: 2020-05-02 17:58:00.974675

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '51eb9fa9b6ec'
down_revision = '16762e72af61'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("last_command_time", sa.DateTime))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_command_time")