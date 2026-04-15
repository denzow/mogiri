"""allow multiple job instances in workflow

Revision ID: d998a9c4c65b
Revises: b7121403b8bc
Create Date: 2026-04-15 16:55:37.917427

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'd998a9c4c65b'
down_revision = 'b7121403b8bc'
branch_labels = None
depends_on = None


def upgrade():
    # jobs.schedule_value: allow NULL for schedule_type="none"
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('schedule_value',
               existing_type=sa.VARCHAR(),
               nullable=True)

    # workflow_node_positions: add id (PK) and node_key columns
    # SQLite cannot add NOT NULL without default, so we recreate the table
    op.create_table('_new_workflow_node_positions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('job_id', sa.String(), nullable=False),
        sa.Column('node_key', sa.String(), nullable=False, server_default=''),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.PrimaryKeyConstraint('id')
    )
    # Migrate existing data (generate id and node_key from job_id)
    op.execute(text(
        "INSERT INTO _new_workflow_node_positions (id, workflow_id, job_id, node_key, x, y) "
        "SELECT lower(hex(randomblob(16))), workflow_id, job_id, job_id || ':' || '0', x, y "
        "FROM workflow_node_positions"
    ))
    op.drop_table('workflow_node_positions')
    op.rename_table('_new_workflow_node_positions', 'workflow_node_positions')

    # workflows: add start node and entry job columns
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('entry_job_ids', sa.Text(), server_default='[]'))
        batch_op.add_column(sa.Column('start_node_x', sa.Float(), server_default='50'))
        batch_op.add_column(sa.Column('start_node_y', sa.Float(), server_default='250'))


def downgrade():
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.drop_column('start_node_y')
        batch_op.drop_column('start_node_x')
        batch_op.drop_column('entry_job_ids')

    # Recreate old table format
    op.create_table('_old_workflow_node_positions',
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('job_id', sa.String(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.PrimaryKeyConstraint('workflow_id', 'job_id')
    )
    op.execute(
        "INSERT OR IGNORE INTO _old_workflow_node_positions (workflow_id, job_id, x, y) "
        "SELECT workflow_id, job_id, x, y FROM workflow_node_positions"
    )
    op.drop_table('workflow_node_positions')
    op.rename_table('_old_workflow_node_positions', 'workflow_node_positions')

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('schedule_value',
               existing_type=sa.VARCHAR(),
               nullable=False)
