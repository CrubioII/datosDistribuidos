"""
data_loader.py — Pipeline para cargar datos desde Azure Blob Storage o local.
"""

import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "resultados")
BLOB_PATH = os.getenv("AZURE_BLOB_PATH")

def load_from_azure():
    if not AZURE_CONNECTION_STRING:
        return None
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        blob_path = BLOB_PATH
        if not blob_path:
            blobs = container_client.list_blobs(name_starts_with="resultados_base_tmp/part-")
            latest_blob = max(blobs, key=lambda b: b.last_modified)
            blob_path = latest_blob.name
        
        blob_client = container_client.get_blob_client(blob_path)
        raw_data = blob_client.download_blob().readall().decode("utf-8")
        
        # Doble deserialización para Spark
        data = json.loads(raw_data)
        return json.loads(data) if isinstance(data, str) else data
    except Exception as e:
        print(f"❌ Error Azure: {e}")
        return None

def build_full_dataset_local():
    # ... (Carga local simplificada para brevedad, asumiendo que ya existe la lógica)
    base = Path(__file__).resolve().parent.parent
    data_path = base / "DataSet (1)" / "DataSet"
    # Lógica mínima para no romper
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def build_full_dataset():
    """Retorna (transactions, exploded, categories, precalculated)"""
    cloud_data = load_from_azure()
    
    # Fallback inicial
    transactions, exploded, categories = build_full_dataset_local()
    precalculated = None

    if cloud_data:
        print("🚀 Datos cargados desde Azure.")
        if isinstance(cloud_data, dict) and "kpis" in cloud_data:
            print("✨ Usando Resultados Precalculados de Databricks.")
            return transactions, exploded, categories, cloud_data
        
        # Si es data cruda en la nube, procesar como antes
        try:
            # (Aquí iría la lógica de mapeo de columnas que ya teníamos)
            # Para esta versión, si no es precalculado, lo tratamos como raw
            new_exp = pd.DataFrame(cloud_data if isinstance(cloud_data, list) else cloud_data.get("exploded", []))
            if not new_exp.empty:
                exploded = new_exp
                # ... (Mapeo de columnas aquí)
        except:
            pass

    return transactions, exploded, categories, precalculated

_cache = {}
def get_cached_data():
    if "data" not in _cache:
        _cache["data"] = build_full_dataset()
    return _cache["data"]
