from pprint import pprint
from config import settings
from core.ocr_engine import get_ocr_engine
from core.parser import load_dali_lookup, parse_metadata
from core.pdf_processor import extract_text_from_file
from storage.database import save_reports
from storage.file_manager import organize_and_rename_file

def run_pipeline():
    """Végigfuttatja a PDF és képfájlok feldolgozási folyamatát, kiírva a nyers OCR adatot."""
    print("=" * 60)
    print("🚀 BOSCH POD AUTOMATA FELDOLGOZÓ (Diagnosztikai Módban)")
    print("=" * 60)

    # 1. Rendszer inicializálása
    dali_lookup = load_dali_lookup(settings.DALI_LOOKUP_TABLE)
    ocr_engine = get_ocr_engine()
    print("✔ OCR motor és DALI tábla betöltve.")

    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
    all_files = [
        p
        for p in settings.SOURCE_FOLDER.iterdir()
        if p.is_file() and p.suffix.lower() in supported_extensions
    ]

    if not all_files:
        print(f"ℹ️ Nincsenek feldolgozandó fájlok a mappában: {settings.SOURCE_FOLDER}")
        return

    print(f"📋 Talált fájlok: {len(all_files)} db\n")
    all_records = []

    # 2. Fájlok feldolgozása egyenként
    for file_path in all_files:
        print(f"▶ Feldolgozás indul: {file_path.name}")
        
        full_text = extract_text_from_file(file_path, ocr_engine)

        if not full_text or not full_text.strip():
            print(f"  ⚠️ Nem sikerült szöveget kinyerni: {file_path.name}\n")
            continue
        
        # --- NYERS OCR SZÖVEG KIÍRÁSA A KONZOLRA ---
        print("\n" + "-"*20 + " [NYERS OCR SZÖVEG] " + "-"*20)
        print(full_text)
        print("-" * (42 + len(" [NYERS OCR SZÖVEG] ")) + "\n")
        # --- KIÍRÁS VÉGE ---

        # 3. Adatok kinyerése a szövegből
        metadata = parse_metadata(full_text, file_path.name, dali_lookup)
        
        print("🔍 [KINYERT METAADATOK]")
        pprint(metadata)

        # 4. Fájl átnevezése és mozgatása
        new_path = organize_and_rename_file(file_path, metadata, settings.TARGET_BASE_FOLDER)
        metadata["Új Fájl Útvonala"] = new_path
        all_records.append(metadata)
        print(f"\n  ✔ Kész: '{file_path.name}' átmozgatva ide: '{new_path}'\n")

    # 5. Mentés az adatbázisba és Excelbe
    if all_records:
        print("-" * 60)
        print("💾 Adatok mentése az adatbázisba és az Excel riportba...")
        save_reports(all_records)
        print("-" * 60)

    print("\n✅ Minden dokumentum sikeresen feldolgozva.")
    print("=" * 60)

if __name__ == "__main__":
    run_pipeline()

