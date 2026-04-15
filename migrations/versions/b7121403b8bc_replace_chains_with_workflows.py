"""replace chains with workflows

Revision ID: b7121403b8bc
Revises: f2f45507bd84
Create Date: 2026-04-15 16:55:37.917427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7121403b8bc'
down_revision = 'f2f45507bd84'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create new tables
    op.create_table('workflows',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_enabled', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('workflow_edges',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workflow_id', sa.String(), nullable=False),
    sa.Column('source_job_id', sa.String(), nullable=False),
    sa.Column('target_job_id', sa.String(), nullable=False),
    sa.Column('trigger_condition', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['source_job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['target_job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('workflow_node_positions',
    sa.Column('workflow_id', sa.String(), nullable=False),
    sa.Column('job_id', sa.String(), nullable=False),
    sa.Column('x', sa.Float(), nullable=False),
    sa.Column('y', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
    sa.PrimaryKeyConstraint('workflow_id', 'job_id')
    )

    # 2. Re-point FK on executions BEFORE dropping old tables
    with op.batch_alter_table('executions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_exec_chain', type_='foreignkey')
        batch_op.create_foreign_key('fk_exec_edge', 'workflow_edges', ['triggered_by_chain_id'], ['id'])

    # 3. Drop old tables (no longer referenced)
    op.drop_table('job_chains')
    op.drop_table('chain_node_positions')


def downgrade():
    # 1. Re-create old tables
    op.create_table('job_chains',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('source_job_id', sa.VARCHAR(), nullable=False),
    sa.Column('target_job_id', sa.VARCHAR(), nullable=False),
    sa.Column('trigger_condition', sa.VARCHAR(), nullable=False),
    sa.ForeignKeyConstraint(['source_job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['target_job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_job_id', 'target_job_id')
    )
    op.create_table('chain_node_positions',
    sa.Column('job_id', sa.VARCHAR(), nullable=False),
    sa.Column('x', sa.FLOAT(), nullable=False),
    sa.Column('y', sa.FLOAT(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('job_id')
    )

    # 2. Re-point FK back
    with op.batch_alter_table('executions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_exec_edge', type_='foreignkey')
        batch_op.create_foreign_key('fk_exec_chain', 'job_chains', ['triggered_by_chain_id'], ['id'])

    # 3. Drop new tables
    op.drop_table('workflow_node_positions')
    op.drop_table('workflow_edges')
    op.drop_table('workflows')
