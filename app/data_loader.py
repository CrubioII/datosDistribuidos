"""
data_loader.py — Pipeline ETL para cargar y transformar el dataset de transacciones.

Carga los 4 archivos de transacciones, explota la columna de productos,
une con categorías y genera un DataFrame limpio listo para análisis.
"""

import pandas as pd
import os
from pathlib import Path


def get_data_path() -> Path:
    """Retorna la ruta al directorio del dataset."""
    # Buscar la carpeta del dataset relativa a este archivo
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "DataSet (1)" / "DataSet"
    if not data_dir.exists():
        # Fallback: buscar en el directorio actual
        data_dir = Path("DataSet (1)") / "DataSet"
    return data_dir


def load_transactions(data_path: Path) -> pd.DataFrame:
    """
    Carga y combina los 4 archivos de transacciones.
    Retorna un DataFrame con columnas: date, store_id, customer_id, products
    """
    stores = ["102", "103", "107", "110"]
    dfs = []

    for store in stores:
        filepath = data_path / "Transactions" / f"{store}_Tran.csv"
        if not filepath.exists():
            raise FileNotFoundError(f"No se encontró: {filepath}")

        df = pd.read_csv(
            filepath,
            sep="|",
            header=None,
            names=["date", "store_id", "customer_id", "products"],
            dtype={"store_id": "int32", "customer_id": "int32", "products": "str"},
        )
        dfs.append(df)

    transactions = pd.concat(dfs, ignore_index=True)
    transactions["date"] = pd.to_datetime(transactions["date"])
    transactions["transaction_id"] = range(len(transactions))
    return transactions


def load_categories(data_path: Path) -> pd.DataFrame:
    """Carga el catálogo de categorías."""
    filepath = data_path / "Products" / "Categories.csv"
    categories = pd.read_csv(
        filepath, sep="|", header=None, names=["category_id", "category_name"]
    )
    return categories


def load_product_category(data_path: Path) -> pd.DataFrame:
    """Carga la relación producto-categoría."""
    filepath = data_path / "Products" / "ProductCategory.csv"
    pc = pd.read_csv(filepath, sep="|")
    pc.columns = ["product_id", "category_id"]
    return pc


def explode_products(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Explota la columna 'products' (string de IDs separados por espacio)
    en filas individuales con un product_id por fila.
    """
    df = transactions.copy()
    df["products"] = df["products"].str.strip()
    df["product_id"] = df["products"].str.split(r"\s+")
    df = df.explode("product_id")
    # Limpiar: eliminar vacíos y convertir a numérico
    df = df[df["product_id"].str.len() > 0].copy()
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce")
    df = df.dropna(subset=["product_id"])
    df["product_id"] = df["product_id"].astype("int32")
    return df


def build_full_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Pipeline completo: carga, transforma y retorna los DataFrames principales.

    Returns:
        transactions: DataFrame original (1 fila = 1 transacción)
        transactions_exploded: DataFrame explotado (1 fila = 1 producto comprado)
        categories: DataFrame de categorías
    """
    data_path = get_data_path()

    # Cargar datos base
    transactions = load_transactions(data_path)
    categories = load_categories(data_path)
    product_category = load_product_category(data_path)

    # Explotar productos
    exploded = explode_products(transactions)

    # Unir con categorías
    exploded = exploded.merge(product_category, on="product_id", how="left")
    exploded = exploded.merge(categories, on="category_id", how="left")

    # Agregar columnas derivadas útiles
    exploded["day_of_week"] = exploded["date"].dt.day_name()
    exploded["week"] = exploded["date"].dt.isocalendar().week.astype("int32")
    exploded["month"] = exploded["date"].dt.month

    return transactions, exploded, categories


# Cache para Streamlit
_cache = {}


def get_cached_data():
    """Retorna datos cacheados o los carga por primera vez."""
    if "data" not in _cache:
        transactions, exploded, categories = build_full_dataset()
        _cache["data"] = (transactions, exploded, categories)
    return _cache["data"]
