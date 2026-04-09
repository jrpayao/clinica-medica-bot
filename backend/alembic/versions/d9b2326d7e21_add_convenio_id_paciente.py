"""add_convenio_id_paciente

Revision ID: d9b2326d7e21
Revises: 3fdd458c2137
Create Date: 2026-04-04 11:16:29.740630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9b2326d7e21'
down_revision: Union[str, None] = '3fdd458c2137'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tipo_atendimento_enum = sa.Enum('CONVENIO', 'PARTICULAR', name='tipo_atendimento')
    tipo_atendimento_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('pacientes', sa.Column('tipo_atendimento', sa.Enum('CONVENIO', 'PARTICULAR', name='tipo_atendimento'), nullable=True))
    op.add_column('pacientes', sa.Column('convenio_id', sa.Integer(), nullable=True))
    op.create_index('ix_pacientes_convenio_id', 'pacientes', ['convenio_id'], unique=False)
    op.create_foreign_key('fk_pacientes_convenio_id', 'pacientes', 'convenios', ['convenio_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_pacientes_convenio_id', 'pacientes', type_='foreignkey')
    op.drop_index('ix_pacientes_convenio_id', table_name='pacientes')
    op.drop_column('pacientes', 'convenio_id')
    op.drop_column('pacientes', 'tipo_atendimento')
    op.execute('DROP TYPE IF EXISTS tipo_atendimento')
