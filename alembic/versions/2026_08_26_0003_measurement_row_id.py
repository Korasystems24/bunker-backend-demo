"""Числовой row-id измерений: контракт мока отдаёт монотонный integer id.

PK гипертаблицы составной (bunker_id, ts, event_id), а фронт ждёт числовой
`id` в каждом измерении (см. generateMeasurement мока).

Нюанс Timescale: на гипертаблице с включённой компрессией (columnstore)
нельзя добавить колонку с неконстантным DEFAULT (`nextval`, IDENTITY) —
поэтому колонка добавляется без дефолта, а значение присваивает
BEFORE INSERT триггер из отдельной последовательности. Это работает и для
обычных INSERT, и для COPY (сидинг), и переживает включение компрессии.

Уникальность гарантирует сама последовательность: уник-индекс на
гипертаблице всё равно обязан включать колонку времени.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Каждый элемент — РОВНО ОДИН оператор SQL: asyncpg не выполняет
# несколько операторов за один вызов.
_UP_STATEMENTS: tuple[str, ...] = (
    "CREATE SEQUENCE IF NOT EXISTS measurements_id_seq",
    "ALTER TABLE measurements ADD COLUMN id BIGINT",
    # Тело функции — один оператор (CREATE FUNCTION).
    """
    CREATE FUNCTION measurements_assign_id() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        NEW.id := nextval('measurements_id_seq');
        RETURN NEW;
    END;
    $$
    """,
    """
    CREATE TRIGGER trg_measurements_assign_id
    BEFORE INSERT ON measurements
    FOR EACH ROW WHEN (NEW.id IS NULL)
    EXECUTE FUNCTION measurements_assign_id()
    """,
)

_DOWN_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS trg_measurements_assign_id ON measurements",
    "DROP FUNCTION IF EXISTS measurements_assign_id()",
    "ALTER TABLE measurements DROP COLUMN id",
    "DROP SEQUENCE IF EXISTS measurements_id_seq",
)


def upgrade() -> None:
    for statement in _UP_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWN_STATEMENTS:
        op.execute(statement)
