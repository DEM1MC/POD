import os
from pathlib import Path
import re
import shutil


def organize_and_rename_file(
    source_path: Path, metadata: dict, target_base_folder: Path
) -> str:
  """Átnevezi és a megfelelő évszámos almappába mozgatja a PDF-et vagy képet."""
  try:
    date_val = metadata.get("Dátum", "Unknown")
    inv_val = metadata.get("Invoice from DALI", "NoInvoice")
    ship_val = metadata.get("Shipment No.", "NoShipment")

    # Évszám meghatározása a mappa struktúrához
    year_match = re.search(r"202\d", str(date_val))
    year = year_match.group(0) if year_match else "Ismeretlen_Ev"

    # Megtartjuk az eredeti fájlkiterjesztést (.png, .jpg, .pdf stb.)
    file_ext = source_path.suffix.lower()
    new_filename = f"{date_val}_{inv_val}_{ship_val}{file_ext}".replace(
        "/", "-"
    ).replace(":", "-")

    dest_folder = target_base_folder / year
    dest_folder.mkdir(parents=True, exist_ok=True)

    dest_path = dest_folder / new_filename

    # Ha már létezik ilyen nevű fájl, számozással elkerüljük a felülírást
    counter = 1
    while dest_path.exists():
      dest_path = (
          dest_folder
          / f"{date_val}_{inv_val}_{ship_val}_{counter}{file_ext}".replace(
              "/", "-"
          ).replace(":", "-")
      )
      counter += 1

    shutil.move(str(source_path), str(dest_path))
    return str(dest_path)
  except Exception as e:
    print(f"  [Hiba] Fájlmozgatási hiba ({source_path.name}): {e}")
    return "N/A"