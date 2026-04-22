"""Move env_vars from Workflow to WorkflowNodePosition

Revision ID: d5b8e2f3a1c7
Revises: c3a7f1b2d4e6
Create Date: 2026-04-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5b8e2f3a1c7'
down_revision = 'c3a7f1b2d4e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workflow_node_positions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('env_vars', sa.Text(), nullable=True, server_default='{}'))

    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.drop_column('env_vars')


def downgrade():
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('env_vars', sa.Text(), nullable=True, server_default='{}'))

    with op.batch_alter_table('workflow_node_positions', schema=None) as batch_op:
        batch_op.drop_column('env_vars')
