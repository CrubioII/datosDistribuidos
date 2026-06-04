"""
data_loader.py — Pipeline para cargar datos desde Azure Blob Storage o local.

Estrategia:
1. Siempre intenta cargar los CSVs locales (DataSet (1)/DataSet/) -> DataFrames pandas.
   Esto habilita filtrado por tienda, análisis avanzado y todas las visualizaciones.
2. Adicionalmente intenta cargar el JSON precalculado de Azure (resultados Spark).
   Si existe, se usa como atajo para los KPIs sin filtro.

Retorna: (transactions, exploded, categories, precalculated)
"""

import os
import json
import pandas as pd
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from azure.storage.blob import BlobServiceClient
    _HAS_AZURE = True
except Exception:
    _HAS_AZURE = False

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "resultados")
BLOB_PATH = os.getenv("AZURE_BLOB_PATH")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATASET_ROOT = _PROJECT_ROOT / "DataSet (1)" / "DataSet"
_TRANSACTIONS_DIR = _DATASET_ROOT / "Transactions"
_PRODUCTS_DIR = _DATASET_ROOT / "Products"
_NEW_DATA_DIR = _PROJECT_ROOT / "nuevos_datos"
_LOCAL_PRECALC = list(_PROJECT_ROOT.glob("part-*.txt"))


# ════════════════════════════════════════════════════════════
#  1. Precalculado (Azure o local)
# ════════════════════════════════════════════════════════════

def load_from_azure():
    if not _HAS_AZURE or not AZURE_CONNECTION_STRING:
        return None
    try:
        client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container = client.get_container_client(CONTAINER_NAME)
        blob_path = BLOB_PATH
        if not blob_path:
            blobs = list(container.list_blobs(name_starts_with="resultados_base_tmp/part-"))
            if not blobs:
                return None
            latest = max(blobs, key=lambda b: b.last_modified)
            blob_path = latest.name
        raw = container.get_blob_client(blob_path).download_blob().readall().decode("utf-8")
        data = json.loads(raw)
        return json.loads(data) if isinstance(data, str) else data
    except Exception as e:
        print(f"[Azure] No disponible: {e}")
        return None


def load_local_precalculated():
    if not _LOCAL_PRECALC:
        return None
    try:
        raw = _LOCAL_PRECALC[0].read_text(encoding="utf-8")
        data = json.loads(raw)
        return json.loads(data) if isinstance(data, str) else data
    except Exception as e:
        print(f"[Precalc local] error: {e}")
        return None


# ════════════════════════════════════════════════════════════
#  2. Carga local de CSVs
# ════════════════════════════════════════════════════════════

def _load_transactions(stores=("102", "103", "107", "110"), extra_dirs=None):
    parts = []
    dirs = [_TRANSACTIONS_DIR]
    if extra_dirs:
        dirs.extend(extra_dirs)
    for d in dirs:
        if not d.exists():
            continue
        for csv_path in sorted(d.glob("*_Tran.csv")):
            try:
                df = pd.read_csv(
                    csv_path, sep="|", header=None,
                    names=["date", "store_id", "customer_id", "products"],
                    dtype={"store_id": "int32", "customer_id": "int64", "products": "string"},
                )
                parts.append(df)
            except Exception as e:
                print(f"[CSV] Error en {csv_path.name}: {e}")
    if not parts:
        return pd.DataFrame(columns=["date", "store_id", "customer_id", "products"])
    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["transaction_id"] = df.index.astype("int64")
    return df


def _load_categories():
    path = _PRODUCTS_DIR / "Categories.csv"
    if not path.exists():
        return pd.DataFrame(columns=["category_id", "category_name"])
    df = pd.read_csv(path, sep="|", header=None,
                     names=["category_id", "category_name"],
                     dtype={"category_id": "int32", "category_name": "string"})
    return df


def _load_product_category_v2():
    """Carga ProductCategory.csv y deduplica (1 categoría por producto)."""
    path = _PRODUCTS_DIR / "ProductCategory.csv"
    if not path.exists():
        return pd.DataFrame(columns=["product_id", "category_id"])
    df = pd.read_csv(path, sep="|")
    df.columns = ["product_id", "category_id"]
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce").astype("Int64")
    df["category_id"] = pd.to_numeric(df["category_id"], errors="coerce").astype("Int32")
    df = df.dropna(subset=["product_id"])
    df = df.sort_values(["product_id", "category_id"])
    df = df.drop_duplicates(subset=["product_id"], keep="first")
    df = df.reset_index(drop=True)
    return df


# Alias por compatibilidad
_load_product_category = _load_product_category_v2


def _explode_products(transactions, product_category, categories):
    if transactions.empty:
        return pd.DataFrame(columns=[
            "transaction_id", "date", "store_id", "customer_id",
            "product_id", "category_id", "category_name",
        ])
    df = transactions[["transaction_id", "date", "store_id", "customer_id", "products"]].copy()
    df["product_id"] = df["products"].fillna("").astype(str).str.split()
    df = df.drop(columns=["products"]).explode("product_id")
    df = df[df["product_id"].astype(str).str.strip() != ""]
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["product_id"])

    # GUARDIA: deduplicar product_category aquí también (defensa contra .pyc viejos).
    if not product_category.empty:
        product_category = (
            product_category
            .sort_values(["product_id", "category_id"])
            .drop_duplicates(subset=["product_id"], keep="first")
            .reset_index(drop=True)
        )

    df = df.merge(product_category, on="product_id", how="left")
    df = df.merge(categories, on="category_id", how="left")
    return df


def build_full_dataset_local(include_new_data=True):
    extra = []
    if include_new_data and _NEW_DATA_DIR.exists():
        extra.append(_NEW_DATA_DIR)
    transactions = _load_transactions(extra_dirs=extra)
    categories = _load_categories()
    product_category = _load_product_category()
    exploded = _explode_products(transactions, product_category, categories)
    return transactions, exploded, categories


# ════════════════════════════════════════════════════════════
#  3. Pipeline principal
# ════════════════════════════════════════════════════════════

_cache = {}


def build_full_dataset(force_reload=False):
    """Retorna (transactions, exploded, categories, precalculated)."""
    if not force_reload and "data" in _cache:
        return _cache["data"]

    print("[ShopLens] Cargando dataset local...")
    transactions, exploded, categories = build_full_dataset_local()
    print(f"[ShopLens] Transacciones: {len(transactions):,} | Productos (exp): {len(exploded):,} | Categorías: {len(categories)}")

    precalculated = load_from_azure()
    if precalculated:
        print("[ShopLens] Usando precalculados de Azure.")
    else:
        precalculated = load_local_precalculated()
        if precalculated:
            print("[ShopLens] Usando precalculados locales (part-*.txt).")

    result = (transactions, exploded, categories, precalculated)
    _cache["data"] = result
    return result


def reload_dataset():
    _cache.clear()
    return build_full_dataset(force_reload=True)


def get_cached_data():
    return build_full_dataset()
