from pathlib import Path
import sqlite3
from config import settings
import pandas as pd


def save_reports(records: list):
  """Egyszerre menti a rekordokat a Master Excel riportba és az SQLite adatbázisba."""
  if not records:
    return

  df_new = pd.DataFrame(records)

  # 1. Mentés a Master Excel riportba (settings.OUTPUT_EXCEL)
  excel_path = getattr(
      settings,
      "OUTPUT_EXCEL",
      settings.TARGET_BASE_FOLDER / "master_pod_extraction_report.xlsx",
  )
  try:
    if excel_path.exists():
      df_old = pd.read_excel(excel_path)
      df_combined = pd.concat([df_old, df_new], ignore_index=True)
      df_combined.drop_duplicates(
          subset=["Eredeti Fájlnév"], keep="last", inplace=True
      )
    else:
      df_combined = df_new

    excel_path.parent.mkdir(parents=True, exist_ok=True)
    df_combined.to_excel(excel_path, index=False)
    print(f"✔ Excel riport frissítve: {excel_path.name}")
  except Exception as e:
    print(f"⚠️ Hiba az Excel mentésekor: {e}")

  # 2. Mentés az SQLite adatbázisba (settings.DB_PATH)
  db_path = getattr(settings, "DB_PATH", settings.BASE_DIR / "pod_database.db")
  try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS POD_Extractions (
                Eredeti_Fajlnev TEXT PRIMARY KEY,
                Datum TEXT,
                Invoice_from_DALI TEXT,
                Shipment_No TEXT,
                CMR_Szam TEXT,
                Transport_Order TEXT,
                Loading_List TEXT,
                Customs_Seal TEXT,
                Box_24_Belyegzo TEXT,
                Cimzett TEXT,
                Atvevo_Telephely TEXT,
                Uj_Fajl_Utvonala TEXT
            )
        """)

    for r in records:
      cursor.execute(
          """
                INSERT OR REPLACE INTO POD_Extractions (
                    Eredeti_Fajlnev, Datum, Invoice_from_DALI, Shipment_No, CMR_Szam,
                    Transport_Order, Loading_List, Customs_Seal, Box_24_Belyegzo,
                    Cimzett, Atvevo_Telephely, Uj_Fajl_Utvonala
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              str(r.get("Eredeti Fájlnév", "")),
              str(r.get("Dátum", "")),
              str(r.get("Invoice from DALI", "")),
              str(r.get("Shipment No.", "")),
              str(r.get("CMR Szám", "")),
              str(r.get("Transport Order (TO)", r.get("Transport Order", ""))),
              str(r.get("Loading List (Box 5)", r.get("Loading List", ""))),
              str(
                  r.get("Customs Seal (Vámzár)", r.get("Customs Seal", ""))
              ),
              str(r.get("Box 24 Bélyegző", "")),
              str(r.get("Címzett", "")),
              str(r.get("Átvevő Telephely", "")),
              str(r.get("Új Fájl Útvonala", "")),
          ),
      )

    conn.commit()
    conn.close()
    print(f"✔ SQLite adatbázis frissítve: {db_path.name}")
  except Exception as e:
    print(f"⚠️ Hiba az SQLite mentésekor: {e}")