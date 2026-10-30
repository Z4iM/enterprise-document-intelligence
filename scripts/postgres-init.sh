#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres --set=app_password="$(cat /run/secrets/app_password)" <<'SQL'
CREATE ROLE edi LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE edi OWNER edi ENCODING 'UTF8';
SQL
