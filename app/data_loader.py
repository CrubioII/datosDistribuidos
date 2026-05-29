"""
data_loader.py — Pipeline para cargar datos desde Azure Blob Storage o local.

Implementa el patrón Storage-as-a-Database cargando un JSON consolidado
pre-calculado en Databricks.
"""

import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()

# Configuración de Azure
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "resultados")
BLOB_PATH = os.getenv("AZURE_BLOB_PATH")


def load_from_azure():
    """
    Descarga el archivo JSON consolidado desde Azure Blob Storage.
    Aplica doble deserialización para limpiar escapes de Spark.
    """
    if not AZURE_CONNECTION_STRING:
        print("⚠️ AZURE_STORAGE_CONNECTION_STRING no configurada. Usando local.")
        return None

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # Si no se especifica BLOB_PATH, intentar buscar el último part-* en resultados_base_tmp
        blob_path = BLOB_PATH
        if not blob_path:
            blobs = container_client.list_blobs(name_starts_with="resultados_base_tmp/part-")
            latest_blob = max(blobs, key=lambda b: b.last_modified)
            blob_path = latest_blob.name
            print(f"✅ Usando blob más reciente: {blob_path}")

        blob_client = container_client.get_blob_client(blob_path)
        stream = blob_client.download_blob()
        raw_data = stream.readall().decode("utf-8")

        # Doble deserialización requerida por el formato de exportación de Spark (string plano)
        first_pass = json.loads(raw_data)
        if isinstance(first_pass, str):
            final_data = json.loads(first_pass)
        else:
            final_data = first_pass
        
        return final_data
    except Exception as e:
        print(f"❌ Error cargando desde Azure: {e}")
        return None


def get_data_path() -> Path:
    """Retorna la ruta al directorio del dataset local (Fallback)."""
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "DataSet (1)" / "DataSet"
    if not data_dir.exists():
        data_dir = Path("DataSet (1)") / "DataSet"
    return data_dir


def load_local_fallback():
    """Carga datos desde archivos CSV locales (Legacy/Dev)."""
    from data_loader_legacy import build_full_dataset_local
    return build_full_dataset_local()


def build_full_dataset():
    """
    Intenta cargar desde Azure. Si falla o no hay config, usa local.
    Retorna DataFrames compatibles con la API actual.
    """
    cloud_data = load_from_azure()
    
    if cloud_data:
        print("🚀 Datos cargados exitosamente desde Azure.")
        try:
            transactions = pd.DataFrame()
            exploded = pd.DataFrame()
            categories = pd.DataFrame()

            if isinstance(cloud_data, dict):
                print(f"ℹ️ Teclas encontradas en JSON: {list(cloud_data.keys())}")
                
                # Buscar exploded/transacciones_expandidas
                for k in ["exploded", "transacciones_expandidas", "data", "results"]:
                    if k in cloud_data and isinstance(cloud_data[k], list):
                        print(f"✅ Encontrado '{k}' con {len(cloud_data[k])} registros.")
                        exploded = pd.DataFrame(cloud_data[k])
                        break
                
                # Buscar transactions
                for k in ["transactions", "transacciones", "base"]:
                    if k in cloud_data and isinstance(cloud_data[k], list):
                        transactions = pd.DataFrame(cloud_data[k])
                        break
                
                # Buscar categories
                for k in ["categories", "categorias", "catalog"]:
                    if k in cloud_data and isinstance(cloud_data[k], list):
                        categories = pd.DataFrame(cloud_data[k])
                        break

            elif isinstance(cloud_data, list):
                print(f"ℹ️ JSON es una lista de {len(cloud_data)} registros.")
                exploded = pd.DataFrame(cloud_data)
            
            # Si se encontró exploded pero no transactions, derivar
            if exploded.empty and isinstance(cloud_data, dict):
                # Intento desesperado: ver si alguna llave tiene muchos datos
                max_len = 0
                for k, v in cloud_data.items():
                    if isinstance(v, list) and len(v) > max_len:
                        max_len = len(v)
                        exploded = pd.DataFrame(v)
                        print(f"⚠️ Usando llave '{k}' como dataset principal por volumen.")

            # --- NORMALIZACIÓN DE COLUMNAS PARA LA API ---
            if not exploded.empty:
                print(f"📊 Columnas detectadas en el dataset: {list(exploded.columns)}")
                
                # Mapeo insensitivo a mayúsculas/minúsculas y variaciones comunes
                col_map = {
                    "store_id": ["store_id", "storeid", "tienda", "id_tienda", "id_store"],
                    "customer_id": ["customer_id", "customerid", "cliente", "id_cliente", "id_customer"],
                    "product_id": ["product_id", "productid", "producto", "id_producto", "id_product"],
                    "date": ["date", "fecha", "timestamp", "dt"],
                    "transaction_id": ["transaction_id", "transactionid", "transaccion", "id_transaccion", "id_txn"],
                    "category_name": ["category_name", "categoryname", "categoria", "nombre_categoria", "category"],
                    "category_id": ["category_id", "categoryid", "id_categoria"]
                }
                
                # Aplicar mapeo
                new_cols = {}
                for standard, variations in col_map.items():
                    for var in variations:
                        # Buscar coincidencia exacta o case-insensitive
                        match = next((c for c in exploded.columns if c.lower() == var.lower()), None)
                        if match:
                            new_cols[match] = standard
                            break
                
                if new_cols:
                    print(f"🔄 Renombrando columnas: {new_cols}")
                    exploded = exploded.rename(columns=new_cols)
                    if not transactions.empty:
                        transactions = transactions.rename(columns=new_cols)

                # Asegurar que existan columnas mínimas para no romper la API
                for col in ["store_id", "customer_id", "product_id", "date", "category_name"]:
                    if col not in exploded.columns:
                        print(f"⚠️ Columna '{col}' faltante. Creando columna vacía/dummy.")
                        exploded[col] = "N/A" if col == "category_name" else 0
                
                # Si falta transaction_id, crearlo
                if "transaction_id" not in exploded.columns or exploded["transaction_id"].isna().all():
                    print("⚠️ 'transaction_id' no encontrado o vacío. Generando identificadores...")
                    # Intentar agrupar por lo que define una visita
                    cols_to_group = [c for c in ["date", "store_id", "customer_id"] if c in exploded.columns]
                    if cols_to_group:
                        exploded["transaction_id"] = exploded.groupby(cols_to_group).ngroup()
                    else:
                        exploded["transaction_id"] = range(len(exploded))

                if transactions.empty:
                    transactions = exploded.drop_duplicates("transaction_id")

            # Asegurar tipos y columnas derivadas
            if not exploded.empty:
                if "date" in transactions.columns:
                    transactions["date"] = pd.to_datetime(transactions["date"])
                if "date" in exploded.columns:
                    exploded["date"] = pd.to_datetime(exploded["date"])
                    exploded["day_of_week"] = exploded["date"].dt.day_name()
                    exploded["week"] = exploded["date"].dt.isocalendar().week.astype("int32")
                    exploded["month"] = exploded["date"].dt.month
            
            return transactions, exploded, categories
        except Exception as e:
            print(f"⚠️ Error procesando JSON de Azure: {e}. Usando local.")
    # Pero para no romper la API si no hay Azure, mantendré la lógica original aquí o en otro archivo.
    return build_full_dataset_local()

# --- Lógica original movida a build_full_dataset_local para claridad ---

def build_full_dataset_local():
    data_path = get_data_path()
    
    # Re-implementación rápida de la lógica anterior para el fallback
    stores = ["102", "103", "107", "110"]
    dfs = []
    for store in stores:
        fp = data_path / "Transactions" / f"{store}_Tran.csv"
        if fp.exists():
            df = pd.read_csv(fp, sep="|", header=None, names=["date", "store_id", "customer_id", "products"])
            dfs.append(df)
    
    if not dfs:
        # Si no hay archivos locales tampoco, retornar DataFrames vacíos para no romper la API
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    transactions = pd.concat(dfs, ignore_index=True)
    transactions["date"] = pd.to_datetime(transactions["date"])
    transactions["transaction_id"] = range(len(transactions))
    
    # Explode
    exploded = transactions.copy()
    exploded["product_id"] = exploded["products"].str.strip().str.split(r"\s+")
    exploded = exploded.explode("product_id")
    exploded = exploded[exploded["product_id"].notna() & (exploded["product_id"] != "")].copy()
    exploded["product_id"] = pd.to_numeric(exploded["product_id"]).astype(int)
    
    # Categories
    cat_path = data_path / "Products" / "Categories.csv"
    pc_path = data_path / "Products" / "ProductCategory.csv"
    
    if cat_path.exists() and pc_path.exists():
        categories = pd.read_csv(cat_path, sep="|", header=None, names=["category_id", "category_name"])
        pc = pd.read_csv(pc_path, sep="|")
        pc.columns = ["product_id", "category_id"]
        exploded = exploded.merge(pc, on="product_id", how="left")
        exploded = exploded.merge(categories, on="category_id", how="left")
    else:
        categories = pd.DataFrame(columns=["category_id", "category_name"])
        
    return transactions, exploded, categories

# Cache para la aplicación
_cache = {}

def get_cached_data():
    if "data" not in _cache:
        _cache["data"] = build_full_dataset()
    return _cache["data"]
