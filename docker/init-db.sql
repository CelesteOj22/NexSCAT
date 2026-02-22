-- docker/init-db.sql
-- Crea la base de datos de SonarQube separada de NexSCAT
SELECT 'CREATE DATABASE sonarqube_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sonarqube_db')\gexec
