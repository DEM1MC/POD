import sqlite3
from config import settings
import pandas as pd
from pathlib import Path

# Kényszerített abszolút útvonal
DB_PATH = Path("c:/Users/DEM1MC/OneDrive - Bosch Group/Documents/POD/pod_database.db")

def initialize_database():
    """Létrehozza a POD_Extractions táblát, HA MÉG NEM LÉTEZIK. (A DROP TABLE parancs véglegesen kivéve!)"""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS POD_Extractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Invoice TEXT,
                    Billing_Date TEXT,
                    Sold_To TEXT,
                    Customer TEXT,
                    Country TEXT,
                    Document_Type TEXT,
                    Upload_Date TEXT,
                    CMR_Date TEXT,
                    Comment TEXT,
                    DN TEXT,
                    Transport_Order TEXT,
                    Shipment_No TEXT,
                    CMR_Szam TEXT,
                    Customs_Seal TEXT,
                    Fuvarozo TEXT,
                    Box_24_Belyegzo TEXT,
                    Eredeti_Fajlnev TEXT UNIQUE,
                    Uj_Fajl_Utvonala TEXT
                )
            """)
            conn.commit()
            print(f"✔ Adatbázis tábla ellenőrizve az abszolút útvonalon: {DB_PATH}")
    except Exception as e:
        print(f"🔥 KRITIKUS HIBA az adatbázis inicializálásakor: {e}")

def save_reports(records: list):
    """Új rekordokat ment az adatbázisba biztonságos adatmegtartással."""
    if not records:
        return

    initialize_database()

    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            for r in records:
                cols = [
                    'Invoice', 'Billing_Date', 'Sold_To', 'Customer', 'Country', 
                    'Document_Type', 'Upload_Date', 'CMR_Date', 'Comment', 'DN', 
                    'Transport_Order', 'Shipment_No', 'CMR_Szam', 'Customs_Seal', 
                    'Fuvarozo', 'Box_24_Belyegzo', 'Eredeti_Fajlnev', 'Uj_Fajl_Utvonala'
                ]
                
                # JAVÍTÁS: Pontos, ékezetmentes kulcsok leképezése, hogy ne üres "" névvel mentsen!
                key_map = {
                    'Eredeti_Fajlnev': 'Eredeti Fajlnev', 
                    'Uj_Fajl_Utvonala': 'Uj Fajl Utvonala',
                    'Box_24_Belyegzo': 'Box 24 Belyegzo', 
                    'Billing_Date': 'Billing Date',
                    'Sold_To': 'Sold-To', 
                    'Document_Type': 'Document Type', 
                    'CMR_Date': 'CMR Date',
                    'Transport_Order': 'Transport Order', 
                    'Shipment_No': 'Shipment No', 
                    'Upload_Date': 'Upload Date'
                }
                values = [str(r.get(key_map.get(col, col), "")) for col in cols]
                
                cursor.execute(f"""
                    INSERT OR REPLACE INTO POD_Extractions ({', '.join(cols)}) 
                    VALUES ({', '.join(['?'] * len(cols))})
                """, tuple(values))
            
            conn.commit()
            print(f"✔ {len(records)} db rekord sikeresen elmentve az adatbázisba.")
    except Exception as e:
        print(f"🔥 HIBA a rekordok mentésekor: {e}")

def export_to_excel():
    """A teljes adatbázis tartalmát Excel fájlba exportálja."""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            df = pd.read_sql_query("SELECT * FROM POD_Extractions ORDER BY Upload_Date DESC", conn)
            if 'id' in df.columns:
                df = df.drop(columns=['id'])

            excel_path = settings.TARGET_BASE_FOLDER / "master_pod_report.xlsx"
            df.to_excel(excel_path, index=False)
            print(f"✔ Adatbázis exportálva: {excel_path.name}")
    except Exception as e:
        print(f"⚠️ Hiba az Excel exportálásakor: {e}")
