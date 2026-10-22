from pprint import pprint
from config import settings
from core.ocr_engine import get_ocr_engine
from core.parser import parse_metadata
from core.dali_connection import fetch_invoices_from_dali 
from core.pdf_processor import extract_text_from_file
from storage.database import initialize_database, save_reports
from storage.file_manager import organize_and_rename_file

def run_pipeline():
    print("=" * 60)
    print("🚀 BOSCH POD AUTOMATA FELDOLGOZÓ (v2.0 - Stabil)")
    print("=" * 60)

    # --- EGYSZERI ADATBÁZIS INICIALIZÁLÁS A PROGRAM ELEJÉN ---
    initialize_database()
    # --- JAVÍTÁS VÉGE ---

    ocr_engine = get_ocr_engine()
    print("✔ OCR motor betöltve.")

    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
    all_files = [p for p in settings.SOURCE_FOLDER.iterdir() if p.is_file() and p.suffix.lower() in supported_extensions]

    if not all_files:
        print(f"ℹ️ Nincsenek feldolgozandó fájlok a mappában: {settings.SOURCE_FOLDER}")
        return

    print(f"📋 Talált fájlok: {len(all_files)} db\n")
    all_records = []

    for file_path in all_files:
        print(f"▶ Feldolgozás indul: {file_path.name}")
        full_text = extract_text_from_file(file_path, ocr_engine)

        if not full_text or not full_text.strip():
            print(f"  ⚠️ Nem sikerült szöveget kinyerni: {file_path.name}\n")
            continue
        
        metadata = parse_metadata(full_text, file_path.name, fetch_invoices_from_dali)
        
        print("🔍 [KINYERT METAADATOK]")
        pprint(metadata)

        new_path = organize_and_rename_file(file_path, metadata, settings.TARGET_BASE_FOLDER)
        metadata["Új Fájl Útvonala"] = new_path
        all_records.append(metadata)
        print(f"\n  ✔ Kész: '{file_path.name}' átmozgatva ide: '{new_path}'\n")

    if all_records:
        print("-" * 60)
        print("💾 Adatok mentése az adatbázisba...")
        save_reports(all_records)
        print("-" * 60)

    print("\n✅ Minden dokumentum sikeresen feldolgozva.")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()
