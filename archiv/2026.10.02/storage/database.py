from pathlib import Path
import sqlite3
import pandas as pd


def save_to_sqlite(df_records: pd.DataFrame, db_path: Path):
  """Rekordok mentése SQLite-ba duplikáció-védelemmel (INSERT OR REPLACE)."""
  if df_records.empty:
    return

  column_mapping = {
      "Eredeti Fájlnév": "Eredeti_Fajlnev",
      "Dátum": "Datum",
      "Invoice from DALI": "Invoice_from_DALI",
      "Shipment No.": "Shipment_No",
      "CMR Szám": "CMR_Szam",
      "Transport Order (TO)": "Transport_Order",
      "Loading List (Box 5)": "Loading_List",
      "Customs Seal (Vámzár)": "Customs_Seal",
      "Box 24 Bélyegző": "Box_24_Belyegzo",
      "Címzett": "Cimzett",
      "Átvevő Telephely": "Atvevo_Telephely",
      "Új Fájl Útvonala": "Uj_Fajl_Utvonala",
  }

  df_sql = df_records.rename(columns=column_mapping)

  create_table_sql = """
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
    );
    """

  insert_sql = """
    INSERT OR REPLACE INTO POD_Extractions (
        Eredeti_Fajlnev, Datum, Invoice_from_DALI, Shipment_No, CMR_Szam,
        Transport_Order, Loading_List, Customs_Seal, Box_24_Belyegzo,
        Cimzett, Atvevo_Telephely, Uj_Fajl_Utvonala
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

  try:
    with sqlite3.connect(db_path) as conn:
      cursor = conn.cursor()
      cursor.execute(create_table_sql)
      cursor.execute(
          "CREATE INDEX IF NOT EXISTS idx_invoice ON"
          " POD_Extractions(Invoice_from_DALI);"
      )
      cursor.execute(
          "CREATE INDEX IF NOT EXISTS idx_shipment ON"
          " POD_Extractions(Shipment_No);"
      )

      records = df_sql[[
          "Eredeti_Fajlnev",
          "Datum",
          "Invoice_from_DALI",
          "Shipment_No",
          "CMR_Szam",
          "Transport_Order",
          "Loading_List",
          "Customs_Seal",
          "Box_24_Belyegzo",
          "Cimzett",
          "Atvevo_Telephely",
          "Uj_Fajl_Utvonala",
      ]].values.tolist()

      cursor.executemany(insert_sql, records)
      conn.commit()
    print("✔ SQLite adatbázis sikeresen frissítve.")
  except Exception as e:
    print(f"⚠️ SQLite hiba: {e}")


def update_master_excel(
    new_records: list, output_excel: Path, target_base: Path
):
  """Hozzáfűzi az új rekordokat a Master Excelhez duplikációk nélkül."""
  if not new_records:
    return

  column_order = [
      "Eredeti Fájlnév",
      "Dátum",
      "Invoice from DALI",
      "Shipment No.",
      "CMR Szám",
      "Transport Order (TO)",
      "Loading List (Box 5)",
      "Customs Seal (Vámzár)",
      "Box 24 Bélyegző",
      "Címzett",
      "Átvevő Telephely",
      "Új Fájl Útvonala",
  ]

  new_df = pd.DataFrame(new_records, columns=column_order)

  if output_excel.exists():
    try:
      old_df = pd.read_excel(output_excel)
      combined_df = pd.concat([old_df, new_df], ignore_index=True)
      combined_df.drop_duplicates(
          subset=["Eredeti Fájlnév"], keep="last", inplace=True
      )
    except Exception:
      combined_df = new_df
  else:
    combined_df = new_df

  try:
    combined_df.to_excel(output_excel, index=False, engine="openpyxl")
    print(f"✅ Excel riport frissítve: {output_excel.name}")
  except PermissionError:
    alt_excel = (
        target_base / f"master_report_{pd.Timestamp.now():%H%M%S}.xlsx"
    )
    combined_df.to_excel(alt_excel, index=False, engine="openpyxl")
    print(f"⚠️ Excel nyitva volt, ide mentve: {alt_excel.name}")