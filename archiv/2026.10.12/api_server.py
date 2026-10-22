import mimetypes
from pathlib import Path
import sqlite3
from urllib.parse import unquote
from config import settings
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI(title="Bosch POD Kereső API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_connection():
  conn = sqlite3.connect(str(settings.DB_PATH))
  conn.row_factory = sqlite3.Row
  return conn


@app.get("/api/search")
def search_records(query: str = Query(..., min_length=1)):
  clean_query = query.strip()
  conn = get_db_connection()
  cursor = conn.cursor()

  sql = """
        SELECT * FROM POD_Extractions 
        WHERE Invoice_from_DALI LIKE ? 
           OR Shipment_No LIKE ? 
           OR CMR_Szam LIKE ? 
           OR Transport_Order LIKE ?
           OR Loading_List LIKE ?
           OR Fuvarozo LIKE ?
           OR Cimzett LIKE ?
           OR Atvevo_Telephely LIKE ?
           OR Orszag LIKE ?
           OR Eredeti_Fajlnev LIKE ?
        ORDER BY Datum DESC
    """
  param = f"%{clean_query}%"
  cursor.execute(
      sql,
      (
          param,
          param,
          param,
          param,
          param,
          param,
          param,
          param,
          param,
          param,
      ),
  )
  rows = cursor.fetchall()
  conn.close()

  return [dict(row) for row in rows]


@app.get("/api/all")
def get_all_records():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT * FROM POD_Extractions ORDER BY rowid DESC"
  )  # A legfrissebb felül
  rows = cursor.fetchall()
  conn.close()
  return [dict(row) for row in rows]


@app.delete("/api/delete")
def delete_record(filename: str = Query(...)):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "DELETE FROM POD_Extractions WHERE Eredeti_Fajlnev = ?",
      (filename.strip(),),
  )
  deleted_count = cursor.rowcount
  conn.commit()
  conn.close()

  if deleted_count == 0:
    raise HTTPException(status_code=404, detail="A rekord nem található.")
  return {"status": "success", "deleted": filename}


@app.get("/api/file")
def get_file(path: str = Query(...), download: bool = False):
  """Kiszolgálja a fájlt.

  Ha download=True -> Kényszerített letöltés. Ha download=False -> CSAK
  MEGNYITÁS új lapon a beépített PDF nézegetővel!
  """
  raw_path = unquote(path).strip()
  file_path = Path(raw_path)

  # Fájl megkeresése, ha relatív vagy át lett helyezve
  if not file_path.is_file():
    candidate = settings.TARGET_BASE_FOLDER / file_path.name
    if candidate.is_file():
      file_path = candidate
    else:
      found = list(settings.TARGET_BASE_FOLDER.rglob(file_path.name))
      if found:
        file_path = found[0]
      else:
        raise HTTPException(
            status_code=404, detail=f"A fájl nem található: {file_path.name}"
        )

  ext = file_path.suffix.lower()

  # 1. HA KIFEJEZETTEN LETÖLTÉST KÉRTÜNK (Letöltés gomb)
  if download:
    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=file_path.name,
    )

  # 2. HA MEGNYITÁST KÉRTÜNK (Megnyitás link új lapon)
  # A tiszta "inline" fejléc garantálja, hogy a böngésző beépített nézegetője jelenítse meg, ne töltse le!
  if ext == ".pdf":
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )
  elif ext in [".png", ".jpg", ".jpeg"]:
    media_type = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )

  return FileResponse(path=str(file_path))


if __name__ == "__main__":
  import uvicorn

  uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
