"""add_estabelecimento_id_token_usage

Revision ID: aef53d41f21e
Revises: 18e03ff4a210
Create Date: 2026-04-08 17:34:05.355941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aef53d41f21e'
down_revision: Union[str, None] = '18e03ff4a210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('token_usage', sa.Column('estabelecimento_id', sa.Integer(), nullable=True))
    op.create_index('ix_token_usage_estabelecimento_id', 'token_usage', ['estabelecimento_id'], unique=False)
    op.create_foreign_key(
        'fk_token_usage_estabelecimento',
        'token_usage', 'estabelecimentos',
        ['estabelecimento_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_token_usage_estabelecimento', 'token_usage', type_='foreignkey')
    op.drop_index('ix_token_usage_estabelecimento_id', table_name='token_usage')
    op.drop_column('token_usage', 'estabelecimento_id')
