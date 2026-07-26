"""add knowledge evolution fields (origin parent_id evolution_note)

Revision ID: c5040cf68986
Revises: 26c1a3a4aef1
Create Date: 2026-06-24 16:19:00.945450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c5040cf68986'
down_revision: Union[str, Sequence[str], None] = '26c1a3a4aef1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('strategy_knowledge', sa.Column('origin', sa.String(), nullable=True))
    op.add_column('strategy_knowledge', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.add_column('strategy_knowledge', sa.Column('evolution_note', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('strategy_knowledge', 'evolution_note')
    op.drop_column('strategy_knowledge', 'parent_id')
    op.drop_column('strategy_knowledge', 'origin')
