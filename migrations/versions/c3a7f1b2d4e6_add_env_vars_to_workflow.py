"""Add env_vars to Workflow

Revision ID: c3a7f1b2d4e6
Revises: b696b2e909f1
Create Date: 2026-04-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a7f1b2d4e6'
down_revision = 'b696b2e909f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('env_vars', sa.Text(), nullable=True, server_default='{}'))


def downgrade():
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.drop_column('env_vars')
