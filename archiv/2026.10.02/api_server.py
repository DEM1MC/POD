from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import sqlite3
import pandas as pd
import urllib.parse
from config.settings import DB_PATH, TARGET_BASE_FOLDER

app = FastAPI(title="POD Kereső és Kezelő API")

# Engedélyezzük a helyi böngészős kapcsolatot
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/search")
def search_records(query: str):
    """Keresés számlaszám (Invoice) vagy Shipment szám alapján."""
    clean_query = query.strip()
    if not clean_query:
        return []

    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Az adatbázis (pod_database.db) még nem létezik.")

    sql = """
        SELECT * FROM POD_Extractions 
        WHERE Invoice_from_DALI LIKE ? 
           OR Shipment_No LIKE ?
        ORDER BY Datum DESC;
    """
    param = f"%{clean_query}%"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (param, param))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/all")
def get_all_records():
    """Visszaadja az összes rekordot csökkenő dátum szerint."""
    if not DB_PATH.exists():
        return []

    sql = "SELECT * FROM POD_Extractions ORDER BY Datum DESC;"
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@app.delete("/api/delete")
def delete_record(filename: str):
    """Biztonságosan törli a megadott rekordot az adatbázisból."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Az adatbázis nem található.")

    clean_filename = filename.strip()
    sql = "DELETE FROM POD_Extractions WHERE Eredeti_Fajlnev = ?;"

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (clean_filename,))
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="A megadott rekord nem található az adatbázisban.")

    return {"status": "success", "message": f"A(z) '{clean_filename}' sikeresen törölve lett az adatbázisból."}

@app.get("/api/file")
def get_pdf_file(path: str):
    """Kiszolgálja a PDF fájlt új lapon megnyitáshoz."""
    decoded_path = urllib.parse.unquote(path).strip().strip('"').strip("'")
    file_path = Path(decoded_path)

    if file_path.exists() and file_path.is_file():
        return FileResponse(
            path=str(file_path),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={file_path.name}"}
        )

    # Biztonsági keresés, ha a fájl elmozdult volna
    if TARGET_BASE_FOLDER.exists():
        found = list(TARGET_BASE_FOLDER.rglob(file_path.name))
        if found and found[0].is_file():
            return FileResponse(
                path=str(found[0]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename={found[0].name}"}
            )

    raise HTTPException(status_code=404, detail=f"A PDF fájl nem található a megadott helyen: {decoded_path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)