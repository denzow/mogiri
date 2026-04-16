"""add node_key to edges and executions

Revision ID: a1b2c3d4e5f6
Revises: d998a9c4c65b
Create Date: 2026-04-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'eeb72410b688'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('workflow_edges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_node_key', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('target_node_key', sa.String(), nullable=True))

    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('entry_node_keys', sa.Text(), server_default='[]'))

    with op.batch_alter_table('executions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('node_key', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('executions', schema=None) as batch_op:
        batch_op.drop_column('node_key')

    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.drop_column('entry_node_keys')

    with op.batch_alter_table('workflow_edges', schema=None) as batch_op:
        batch_op.drop_column('target_node_key')
        batch_op.drop_column('source_node_key')
