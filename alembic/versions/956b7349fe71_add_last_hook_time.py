"""add last_hook_time

Revision ID: 956b7349fe71
Revises: 51eb9fa9b6ec
Create Date: 2020-05-03 01:35:38.054231

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '956b7349fe71'
down_revision = '51eb9fa9b6ec'
branch_labels = None
depends_on = None


def upgrade():
    # with op.batch_alter_table("users") as batch_op:
    #     batch_op.add_column(sa.Column("last_hook_time", sa.DateTime))
    pass


def downgrade():
    # with op.batch_alter_table("users") as batch_op:
    #     batch_op.drop_column("last_hook_time")
    pass
