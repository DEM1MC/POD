from pathlib import Path
import re
import pandas as pd
from config.settings import KNOWN_CONSIGNEES

def load_dali_lookup(dali_path: Path) -> dict:
  """Beolvassa és agresszívan megtisztítja a DALI keresőtáblát minden lehetséges adattípustól."""
  if not dali_path.exists():
    print(f"⚠️ A DALI tábla nem található itt: {dali_path}")
    return {}
  try:
    df_dali = pd.read_excel(dali_path)

    # Oszlopnevek megtisztítása a felesleges szóközöktől
    df_dali.columns = [str(c).strip() for c in df_dali.columns]

    # Megkeressük a megfelelő oszlopokat rugalmasan
    trans_col = next(
        (c for c in df_dali.columns if "transport" in c.lower()),
        "transport szam",
    )
    inv_col = next(
        (c for c in df_dali.columns if "vbeln" in c.lower() or "szamla" in c.lower()),
        "szamladelivery.VBELN",
    )

    lookup = {}
    for _, row in df_dali.iterrows():
      raw_trans = str(row[trans_col]).strip()
      raw_inv = str(row[inv_col]).strip()

      # Levágjuk a .0 végződést ha lebegőpontosként olvasta be
      clean_trans = re.sub(r"\.0$", "", raw_trans).strip()
      clean_inv = re.sub(r"\.0$", "", raw_inv).strip()

      if clean_trans and clean_trans != "nan":
        lookup[clean_trans] = clean_inv

    print(
        f"✔ DALI keresőtábla sikeresen betöltve ({len(lookup)} érvényes rekord)."
    )
    return lookup
  except Exception as e:
    print(f"⚠️ Hiba a DALI tábla beolvasásakor: {e}")
    return {}


def parse_metadata(
    full_text: str, filename: str, invoice_lookup: dict
) -> dict:
  """Kinyeri az összes strukturált mezőt a nyers szövegből regex minták alapján."""
  text = full_text.replace("O", "0")

  def find_match(patterns, text_block):
    for p in patterns:
      m = re.search(p, text_block, re.IGNORECASE)
      if m:
        return m.group(1).strip().replace(" ", "").replace("+", "")
    return "Review Manually"

  cmr_patterns = [
      r"N°\s*(\d{4}\s?/\s?\d+)",
      r"\b(\d{4}\s?/\s?\d+)\b",
      r"CMR\s*[:\s]*(\d+)",
  ]
  shipment_patterns = [
      r"Shipment\s*nr\.\s*:\s*([\d\s+]+)",
      r"Shipment\s*:\s*([\d\s+]+)",
      r"\b(2004\d{6,})\b",
      r"\b(200\d{7})\b",
      r"\b(160\d{7})\b",
  ]
  to_patterns = [
      r"T0[:!]*\s*([A-Z]{2}\d+)",
      r"\b(EL\d{10})\b",
      r"\b(\d{5,}\s*EL\d{10})\b",
      r"\b(TO\d+)\b",
  ]
  loading_list_patterns = [
      r"\b(HU\d{2}[_\-\s]?[A-Z]{2}\d{10,})\b",
      r"\b(HU[0-9O]{2}[_\-\s]?[A-Z]{2}[0-9O]{10,})\b",
      r"Loading\s*list\s*[:\s]*([A-Z0-9_\-]{10,25})",
      r"L[o0]ading\s*[l1]ist\s*[:\s]*([A-Z0-9_\-]{10,25})",
  ]
 # 1. SZUPER-RUGALMAS VÁMZÁR MINTÁK:
    # Kezeli a pecsét beékelődését, és a szóközzel tagolt számokat is (pl. 017 57 1)
  seal_patterns = [
        # Ha a Vámzár szó után legfeljebb 60 karakteren belül felbukkan egy 0-val kezdődő számcsoport:
        r'V[aá]mz[aá]r[\s\S]{0,60}?\b(0[01](?:[\s]?[0-9O]){4,6})\b',
        r'Seal[\s\S]{0,60}?\b(0[01](?:[\s]?[0-9O]){4,6})\b',
        # Önmagában álló 00 vagy 01 kezdetű, szóközökkel tagolt szám a szövegben:
        r'\b(0[01](?:[\s]?[0-9O]){4,6})\b',
        # Bármilyen 0-val kezdődő 6 jegyű kód:
        r'\b(0(?:[\s]?[0-9O]){5,6})\b',
    ]


  date_patterns = [
      r"(\d{4}-\d{2}-\d{2})",
      r"(\d{4}\.\d{2}\.\d{2})",
      r"(\d{2}[-./]\d{2}[-./]\d{4})",
      r"(\d{2}[-./]\d{2}[-./]\d{2})",
  ]

  shipment_num = find_match(shipment_patterns, text)
  # Intelligens DALI párosítás (kezeli ha szövegként vagy számként van eltérve)
  invoice_num = invoice_lookup.get(
        shipment_num,
        invoice_lookup.get(
            shipment_num.lstrip("0"),
            invoice_lookup.get(re.sub(r"\.0$", "", shipment_num), "Not Found in DALI"),
        ),
    )

  # Dátum normalizálás
  date_str = find_match(date_patterns, text)
  parsed_date = "Review Manually"
  if date_str != "Review Manually":
    try:
      parts = re.split(r"[-./]", date_str)
      if len(parts[0]) == 4 and int(parts[0]) > 2000:
        parsed_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
      elif len(parts[2]) == 4 and int(parts[2]) > 2000:
        parsed_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
      elif len(parts[2]) == 2:
        parsed_date = f"20{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
      pass

  # Partner azonosítás
  consignee, site, stamp = "Unknown", "Unknown", "No"
  for name, info in KNOWN_CONSIGNEES.items():
    if any(re.search(kw, text, re.IGNORECASE) for kw in info["keywords"]):
      consignee = name
      site = info["site"]
      stamp = "Yes"
      break

  to_val = find_match(to_patterns, text)
  loading_val = find_match(loading_list_patterns, text)
  if loading_val == to_val or loading_val.startswith(("EL", "TO")):
    loading_val = "Review Manually"
    
  customs_seal_val = find_match(seal_patterns, text)
  if customs_seal_val != "Review Manually":
      # Megtisztítjuk: kiszedjük a belső szóközöket és az O betűt 0-ra javítjuk
      customs_seal_val = (
          customs_seal_val.replace(" ", "").replace("O", "0").strip()
      )
  return {
      "Eredeti Fájlnév": filename,
      "Dátum": parsed_date,
      "Invoice from DALI": invoice_num,
      "Shipment No.": shipment_num,
      "CMR Szám": find_match(cmr_patterns, text),
      "Transport Order (TO)": to_val,
      "Loading List (Box 5)": loading_val,
      "Customs Seal (Vámzár)": find_match(seal_patterns, text),
      "Box 24 Bélyegző": stamp,
      "Címzett": consignee,
      "Átvevő Telephely": site,
      "Új Fájl Útvonala": "N/A",
  }