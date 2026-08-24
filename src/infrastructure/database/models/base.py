from sqlalchemy.orm import DeclarativeBase


# ORM — только справочные таблицы; телеметрия идёт через raw-SQL Gateway.
class Base(DeclarativeBase):
    pass
