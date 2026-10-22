import sys
print("🔍 API Server modulok betöltése...")

try:
    from fastapi import FastAPI, HTTPException, Query, Body
    from fastapi.responses import FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    import sqlite3
    from pathlib import Path
    from config import settings
    print("   ✅ Modulok sikeresen betöltve.")
except Exception as e:
    print(f"   ❌ MODUL BETÖLTÉSI HIBA: {e}")
    sys.exit(1)

app = FastAPI(title="Bosch POD Kereső API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

DB_PATH = getattr(settings, "DB_PATH", settings.BASE_DIR / "pod_database.db")

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/all")
async def get_all_records():
    try:
        with get_db_connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM POD_Extractions ORDER BY id DESC").fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search")
async def search_records(query: str = Query(..., min_length=2)):
    search_pattern = f"%{query}%"
    with get_db_connection() as conn:
        sql = """
            SELECT * FROM POD_Extractions 
            WHERE Invoice LIKE ? 
               OR Shipment_No LIKE ? 
               OR Customer LIKE ? 
               OR Country LIKE ? 
            ORDER BY id DESC
        """
        return [dict(row) for row in conn.execute(sql, (search_pattern, search_pattern, search_pattern, search_pattern)).fetchall()]

@app.post("/api/update")
async def update_record(update_data: dict = Body(...)):
    pk = update_data.get("pk")
    column_to_update = update_data.get("column")
    new_value = update_data.get("value")

    if not all([pk, column_to_update, new_value is not None]):
        raise HTTPException(status_code=400, detail="Hiányos adatok.")

    allowed_columns = ["Billing_Date", "Sold_To", "Document_Type", "Comment", "DN", "Box_24_Belyegzo"]
    if column_to_update not in allowed_columns:
        raise HTTPException(status_code=403, detail="A mező nem szerkeszthető.")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            sql = f"UPDATE POD_Extractions SET {column_to_update} = ? WHERE id = ?"
            cursor.execute(sql, (new_value, pk))
            conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adatbázis hiba: {e}")

@app.delete("/api/delete")
async def delete_record(pk: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM POD_Extractions WHERE id = ?", (pk,))
        conn.commit()
        if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Rekord nem található")
    return {"status": "success"}

@app.get("/api/file")
async def get_file(path: str, download: bool = False):
    file_path = Path(path)
    if not file_path.exists(): 
        raise HTTPException(status_code=404, detail="A fájl nem található")
    
    if download:
        # --- JAVÍTÁS: attachment fejléc kényszeríti a letöltést új fül megnyitása nélkül ---
        return FileResponse(
            path=file_path, 
            media_type='application/octet-stream',
            filename=file_path.name,
            headers={"Content-Disposition": f"attachment; filename={file_path.name}"}
        )
    else:
        return FileResponse(
            path=file_path, 
            media_type='application/pdf',
            headers={"Content-Disposition": "inline"}
        )

if __name__ == "__main__":
    import uvicorn
    print("🚀 API Server indítása...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
