import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./behavmetrix.db")
    pdf_output_dir: str = os.getenv("PDF_OUTPUT_DIR", "./exports")


settings = Settings()
