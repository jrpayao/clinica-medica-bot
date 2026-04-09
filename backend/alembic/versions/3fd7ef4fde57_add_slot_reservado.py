"""add_slot_reservado

Revision ID: 3fd7ef4fde57
Revises: d9b2326d7e21
Create Date: 2026-04-04 11:36:38.893424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fd7ef4fde57'
down_revision: Union[str, None] = 'd9b2326d7e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adicionar coluna reservado_em ao slot
    op.add_column('slots', sa.Column('reservado_em', sa.DateTime(timezone=True), nullable=True))
    # Adicionar valor RESERVADO ao enum slot_status
    op.execute("ALTER TYPE slot_status ADD VALUE IF NOT EXISTS 'RESERVADO'")


def downgrade() -> None:
    op.drop_column('slots', 'reservado_em')
    # Nota: remover valor de enum PostgreSQL requer recriação do tipo — não suportado neste downgrade
