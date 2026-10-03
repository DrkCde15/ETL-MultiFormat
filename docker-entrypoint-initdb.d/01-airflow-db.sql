-- Executado pelo entrypoint do Postgres apenas na primeira subida (volume vazio).
-- O POSTGRES_DB do compose já cria o multi_format_etl (gold); falta o banco de
-- metadados do Airflow.
CREATE DATABASE airflow;
