"""Validation helpers for BehavMetrix forms and ingestion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import pandas as pd

SQL_SCHEMES = {"postgresql", "postgresql+psycopg2", "mysql", "sqlite", "mssql+pyodbc"}


def validate_sql_credentials(data: Mapping[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}

    host = str(data.get("host", "")).strip()
    if not host:
        errors["host"] = "Host is required"

    port = data.get("port")
    try:
        if port is None or str(port).strip() == "":
            raise ValueError
        port_int = int(port)
        if not 0 < port_int < 65536:
            raise ValueError
    except ValueError:
        errors["port"] = "Port must be a number between 1 and 65535"

    username = str(data.get("username", "")).strip()
    if not username:
        errors["username"] = "Username is required"

    if not str(data.get("database", "")).strip():
        errors["database"] = "Database name is required"

    if not str(data.get("table", "")).strip():
        errors["table"] = "Table name is required"

    if password := data.get("password"):
        if len(str(password)) < 3:
            errors["password"] = "Password must be at least 3 characters"

    scheme = str(data.get("driver", "")).strip() or "postgresql"
    if scheme not in SQL_SCHEMES:
        errors["driver"] = "Unsupported database driver"

    return errors


def build_sqlalchemy_uri(data: Mapping[str, Any]) -> str:
    driver = str(data.get("driver", "postgresql"))
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    host = str(data.get("host", "localhost"))
    port = str(data.get("port", "5432"))
    database = str(data.get("database", ""))

    if password:
        credentials = f"{username}:{password}"
    else:
        credentials = username
    return f"{driver}://{credentials}@{host}:{port}/{database}"


def validate_sqlalchemy_uri(uri: str) -> str | None:
    parsed = urlparse(uri)
    if not parsed.scheme or parsed.scheme not in SQL_SCHEMES:
        return "Unsupported or missing SQLAlchemy driver"
    if not parsed.hostname:
        return "Hostname is required"
    if not parsed.path or parsed.path == "/":
        return "Database name is required"
    return None


def validate_dataframe(df: pd.DataFrame, required_columns: set[str]) -> list[str]:
    errors: list[str] = []
    missing = required_columns - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {', '.join(sorted(missing))}")

    for column in required_columns:
        if column not in df.columns:
            continue
        if df[column].isnull().all():
            errors.append(f"Column '{column}' must have at least one value")
    return errors


def validate_custom_fields(schema: list[dict[str, Any]], payload: Mapping[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field in schema:
        name = field.get("field_name")
        label = field.get("label", name)
        if not name:
            continue
        required = bool(field.get("required"))
        value = payload.get(name)
        if required and (value is None or str(value).strip() == ""):
            errors[name] = f"{label} is required"
            continue
        datatype = field.get("data_type", "string")
        if value is None or str(value).strip() == "":
            continue
        try:
            if datatype == "number":
                float(value)
            elif datatype == "integer":
                int(value)
        except ValueError:
            errors[name] = f"{label} must be a valid {datatype}"
    return errors
