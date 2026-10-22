from pprint import pprint
from config import settings
from core.ocr_engine import get_ocr_engine
from core.parser import parse_metadata
from core.dali_connection import fetch_invoices_from_dali 
from core.pdf_processor import extract_text_from_file
from storage.database import initialize_database, save_reports
from storage.file_manager import organize_and_rename_file
import sqlite3
from pathlib import Path

DB_PATH = Path("c:/Users/DEM1MC/OneDrive - Bosch Group/Documents/POD/pod_database.db")

def save_or_update_records(metadata_list: list):
    """Ha a Shipment már létezik a táblában (DALI-ból), frissíti a fájl útvonalát és a Transport Ordert."""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            for r in metadata_list:
                shipment_no = str(r.get("Shipment No", "")).split(",")[0].strip()
                file_path = str(r.get("Uj Fajl Utvonala", "N/A"))
                cmr_date = str(r.get("CMR Date", ""))
                original_file = str(r.get("Eredeti Fajlnev", ""))
                transport_order = str(r.get("Transport Order", ""))

                # Megkeressük az összes olyan DALI-s sort, ami ehhez a Shipmenthez tartozik (lehet több Invoice is)
                cursor.execute("SELECT id FROM POD_Extractions WHERE Shipment_No = ?", (shipment_no,))
                rows = cursor.fetchall()

                if rows:
                    print(f"   🔄 Létező {len(rows)} db rekord frissítése a(z) {shipment_no} shipmenthez...")
                    for row in rows:
                        row_id = row[0]
                        # Frissítjük a fájl helyét, a CMR dátumot, az eredeti fájlnevet és a Transport Ordert is!
                        cursor.execute("""
                            UPDATE POD_Extractions 
                            SET Uj_Fajl_Utvonala = ?, 
                                CMR_Date = ?, 
                                Eredeti_Fajlnev = ?,
                                Transport_Order = ?
                            WHERE id = ?
                        """, (file_path, cmr_date, original_file, transport_order, row_id))
                else:
                    # Ha teljesen új, nem szinkronizált fuvar érkezett, beillesztjük
                    print(f"   ➕ Új rekord hozzáadása az adatbázishoz (Shipment: {shipment_no})...")
                    save_reports([r])
            conn.commit()
    except Exception as e:
        print(f"🔥 Hiba az adatbázis mentés/frissítés közben: {e}")

def run_pipeline():
    print("=" * 60)
    print("🚀 BOSCH POD AUTOMATA FELDOLGOZÓ (DALI-központú Mód)")
    print("=" * 60)

    initialize_database()

    ocr_engine = get_ocr_engine()
    print("✔ OCR motor betöltve.")

    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
    all_files = [p for p in settings.SOURCE_FOLDER.iterdir() if p.is_file() and p.suffix.lower() in supported_extensions]

    if not all_files:
        print(f"ℹ️ Nincsenek feldolgozandó fájlok a mappában: {settings.SOURCE_FOLDER}")
        return

    print(f"📋 Talált fáljok: {len(all_files)} db\n")
    all_records = []

    for file_path in all_files:
        print(f"▶ Feldolgozás indul: {file_path.name}")
        full_text = extract_text_from_file(file_path, ocr_engine)

        if not full_text or not full_text.strip():
            print(f"  ⚠️ Nem sikerült szöveget kinyerni: {file_path.name}\n")
            continue
        
        metadata = parse_metadata(full_text, file_path.name, fetch_invoices_from_dali)
        
        # Átnevezés az összes kinyert számlával és a kötőjeles dátummal
        new_path = organize_and_rename_file(file_path, metadata, settings.TARGET_BASE_FOLDER)
        metadata["Uj Fajl Utvonala"] = new_path
        all_records.append(metadata)
        print(f"  ✔ Kész: '{file_path.name}' átnevezve és áthelyezve.\n")

    if all_records:
        print("-" * 60)
        print("💾 Adatbázis frissítése...")
        save_or_update_records(all_records)
        print("-" * 60)

    print("\n✅ Minden dokumentum sikeresen feldolgozva.")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()
