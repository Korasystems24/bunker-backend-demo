-- Выполняется при ПЕРВОЙ инициализации тома БД (docker-entrypoint-initdb.d).
CREATE EXTENSION IF NOT EXISTS timescaledb;