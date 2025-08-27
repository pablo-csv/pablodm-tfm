# © 2025 Pablo Díaz-Masa. Licenciado bajo CC BY-NC-ND 4.0.
# Ver LICENSE o https://creativecommons.org/licenses/by-nc-nd/4.0/

import pandas as pd, fsspec, json, os

BUCKET = os.getenv("STATIC_BUCKET", "OWN-BUCKET-NAME")

def read_text_from_gcs(path: str) -> str:
    with fsspec.open(f"gs://{BUCKET}/{path}", "r", encoding="utf-8") as f:
        return f.read()

def read_csv_from_gcs(path: str) -> pd.DataFrame:
    return pd.read_csv(f"gs://{BUCKET}/{path}")
