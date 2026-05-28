"""
main.py — Entry point del backend ShopLens.

Ejecutar:
    cd ShopLens
    uvicorn app.api:app --reload --port 8000

O directamente:
    python app/main.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
