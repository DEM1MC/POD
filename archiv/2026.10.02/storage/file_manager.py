from pathlib import Path
import re
import shutil


def organize_and_move_pdf(
    pdf_path: Path, metadata: dict, target_base: Path
) -> str:
  """Átnevezi és fizikailag áthelyezi a PDF-et a célkönyvtárba."""
  date = metadata.get("Dátum", "NA_D")
  invoice = metadata.get("Invoice from DALI", "NO_INV")
  shipment = metadata.get("Shipment No.", "NA_S")
  year = date.split("-")[0] if date.startswith("20") else "Vegyes"

  destination_dir = target_base / year
  destination_dir.mkdir(parents=True, exist_ok=True)

  clean_filename = re.sub(
      r'[\\/*?:"<>|]', "_", f"{date}_{invoice}_{shipment}.pdf"
  )
  dest_path = destination_dir / clean_filename

  try:
    shutil.move(str(pdf_path), str(dest_path))
    return str(dest_path)
  except Exception as e:
    print(f"   -> ❌ Fájl áthelyezési hiba: {e}")
    return "Áthelyezés sikertelen"