from pprint import pprint
from config import settings
from core.ocr_engine import get_ocr_engine
from core.parser import parse_metadata
# Az Exceles beolvasó helyett az új, élő DALI kapcsolatot importáljuk!
from core.dali_connection import fetch_invoices_from_dali 
from core.pdf_processor import extract_text_from_file
from storage.database import save_reports
from storage.file_manager import organize_and_rename_file

def run_pipeline():
    """Végigfuttatja a feldolgozást ÉLŐ DALI adatbázis-kapcsolattal."""
    print("=" * 60)
    print("🚀 BOSCH POD AUTOMATA FELDOLGOZÓ (ÉLŐ DALI MÓDBAN)")
    print("=" * 60)

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
        
        print("\n" + "-"*20 + " [NYERS OCR SZÖVEG] " + "-"*20)
        print(full_text[:500] + "...") # Csak az első 500 karaktert írjuk ki
        print("-" * (42 + len(" [NYERS OCR SZÖVEG] ")) + "\n")

        # Itt már nem egy előre betöltött szótárat, hanem magát a lekérdező függvényt adjuk át!
        # Így a parser minden dokumentumhoz friss, élő adatokat fog lekérni.
        metadata = parse_metadata(full_text, file_path.name, fetch_invoices_from_dali)
        
        print("🔍 [KINYERT METAADATOK]")
        pprint(metadata)

        new_path = organize_and_rename_file(file_path, metadata, settings.TARGET_BASE_FOLDER)
        metadata["Új Fájl Útvonala"] = new_path
        all_records.append(metadata)
        print(f"\n  ✔ Kész: '{file_path.name}' átmozgatva ide: '{new_path}'\n")

    if all_records:
        print("-" * 60)
        print("💾 Adatok mentése az adatbázisba és az Excel riportba...")
        save_reports(all_records)
        print("-" * 60)

    print("\n✅ Minden dokumentum sikeresen feldolgozva.")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()
