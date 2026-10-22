from config import settings
from core.ocr_engine import get_ocr_engine
from core.parser import load_dali_lookup, parse_metadata
from core.pdf_processor import extract_text_from_file
from storage.database import save_reports
from storage.file_manager import organize_and_rename_file


def run_pipeline():
  print("=" * 60)
  print("🚀 BOSCH POD AUTOMATA FELDOLGOZÓ")
  print("=" * 60)

  dali_lookup = load_dali_lookup(settings.DALI_LOOKUP_TABLE)
  ocr_engine = get_ocr_engine()

  supported_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
  all_files = [
      p
      for p in settings.SOURCE_FOLDER.iterdir()
      if p.is_file() and p.suffix.lower() in supported_extensions
  ]

  if not all_files:
    print(f"ℹ️ Nincsenek feldolgozandó fájlok: {settings.SOURCE_FOLDER}")
    return

  all_records = []
  for file_path in all_files:
    print(f"\n▶ Feldolgozás indul: {file_path.name}")
    full_text = extract_text_from_file(file_path, ocr_engine)

    if not full_text.strip():
      print(f"  ⚠️ Nem sikerült szöveget kinyerni: {file_path.name}")
      continue

    print("\n📄 [NYERS OCR SZÖVEG]:")
    print(full_text[:300] + "...\n")

    metadata = parse_metadata(full_text, file_path.name, dali_lookup)

    print("🔍 [KINYERT METAADATOK]:")
    for k, v in metadata.items():
      print(f"   • {k:<20}: {v}")

    new_path = organize_and_rename_file(
        file_path, metadata, settings.TARGET_BASE_FOLDER
    )
    metadata["Új Fájl Útvonala"] = new_path
    all_records.append(metadata)

  if all_records:
    print("\n💾 Mentés az SQLite adatbázisba és az Excel riportba...")
    save_reports(all_records)

  print("\n✅ Minden dokumentum feldolgozva.")


if __name__ == "__main__":
  run_pipeline()
