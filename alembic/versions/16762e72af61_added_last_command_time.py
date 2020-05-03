"""added last command time

Revision ID: 16762e72af61
Revises: 
Create Date: 2020-05-02 17:36:56.623093

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16762e72af61'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("last_command_time", sa.DateTime))

def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_command_time")
