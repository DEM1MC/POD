import pandas as pd
from config.settings import DALI_LOOKUP_TABLE, DB_PATH, OUTPUT_EXCEL, SOURCE_FOLDER, TARGET_BASE_FOLDER
from core.ocr_engine import get_ocr_engine
from core.parser import load_dali_lookup, parse_metadata
#from core.parser import parse_metadata, load_dali_lookup_from_oracle
from core.pdf_processor import extract_text_from_pdf
from storage.database import save_to_sqlite, update_master_excel
from storage.file_manager import organize_and_move_pdf


def run_pipeline():
  print("\n" + "=" * 60)
  print("🚀 POD FELDOLGOZÓ PIPELINE INDÍTÁSA")
  print("=" * 60)

  if not SOURCE_FOLDER.exists():
    return print(f"❌ Forrásmappa nem található: {SOURCE_FOLDER}")

  all_pdfs = [p for p in SOURCE_FOLDER.glob("*.pdf") if p.is_file()]
  if not all_pdfs:
    return print("ℹ️ Nincs feldolgozandó új PDF fájl a forrásmappában.")

  print(f"Talált PDF fájlok: {len(all_pdfs)} db")

  # 1. DALI és OCR inicializálás
  invoice_lookup = load_dali_lookup(DALI_LOOKUP_TABLE)
  print("⏳ PaddleOCR motor inicializálása...")
  ocr_engine = get_ocr_engine()
  print("✔ Motor kész, feldolgozás indul...\n")

  new_records = []
  for pdf_path in all_pdfs:
    print(f"📄 Feldolgozás: {pdf_path.name}")
    raw_text = extract_text_from_pdf(pdf_path, ocr_engine)
    data = parse_metadata(raw_text, pdf_path.name, invoice_lookup)

    # Fájl áthelyezése
    data["Új Fájl Útvonala"] = organize_and_move_pdf(
        pdf_path, data, TARGET_BASE_FOLDER
    )
    new_records.append(data)

    print(
        f"   -> Dátum: {data['Dátum']} | Invoice: {data['Invoice from DALI']} |"
        f" Shipment: {data['Shipment No.']} | TO: {data['Transport Order (TO)']}"
    )

  # 2. Mentés Excelbe és SQLite adatbázisba
  if new_records:
    df_new = pd.DataFrame(new_records)
    update_master_excel(new_records, OUTPUT_EXCEL, TARGET_BASE_FOLDER)
    save_to_sqlite(df_new, DB_PATH)

  print("\n" + "=" * 60)
  print(f"🎉 KÉSZ! Összesen {len(new_records)} PDF sikeresen feldolgozva.")


if __name__ == "__main__":
  run_pipeline()