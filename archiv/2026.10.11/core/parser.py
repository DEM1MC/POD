from pathlib import Path
import re
from config.settings import KNOWN_CONSIGNEES
import pandas as pd


def load_dali_lookup(dali_path: Path) -> dict:
  if not dali_path.exists():
    return {}
  try:
    df_dali = pd.read_excel(dali_path)
    df_dali.columns = [str(c).strip() for c in df_dali.columns]
    trans_col = next(
        (c for c in df_dali.columns if "transport" in c.lower()),
        "transport szam",
    )
    inv_col = next(
        (
            c
            for c in df_dali.columns
            if "vbeln" in c.lower() or "szamla" in c.lower()
        ),
        "szamladelivery.VBELN",
    )

    lookup = {}
    for _, row in df_dali.iterrows():
      t = re.sub(r"\.0$", "", str(row[trans_col])).strip()
      i = re.sub(r"\.0$", "", str(row[inv_col])).strip()
      if t and t != "nan":
        lookup[t] = i
    return lookup
  except Exception:
    return {}


def extract_carrier(full_text: str, consignee_name: str) -> str:
  """Kinyeri a fuvarozó cégnevet úgy, hogy kizárja a címzettet és a sablonokat."""
  # Gyakori fuvarozók
  known_carriers = [
      ("KPS Intertransport", [r"kps\s+intertransport", r"kps"]),
      ("K&V Kft.", [r"k&v", r"k\s*&\s*v"]),
      ("Waberer's", [r"waberer", r"wabi"]),
      ("DHL Freight", [r"dhl\s+freight"]),
      ("DB Schenker", [r"schenker", r"db\s+schenker"]),
      ("Gebrüder Weiss", [r"gebr[uü]der\s+weiss"]),
      ("Duvenbeck", [r"duvenbeck"]),
      ("LKW Walter", [r"lkw\s+walter"]),
  ]
  for name, pats in known_carriers:
    # Ha a címzett neve megegyezik a fuvarozóval, azt kihagyjuk!
    if (
        name.lower() in consignee_name.lower()
        or consignee_name.lower() in name.lower()
    ):
      continue
    if any(re.search(p, full_text, re.IGNORECASE) for p in pats):
      return name

  # Ha cégforma vagy International Transport szerepel
  m = re.search(
      r"\b([A-Z0-9\.\s]{2,25}(?:Kft|Bt|Zrt|Sp\.\s*z\s*o\.o\.|GmbH|Transport))\b",
      full_text,
      re.IGNORECASE,
  )
  if m:
    cand = m.group(1).strip()
    if (
        consignee_name.lower() not in cand.lower()
        and "bosch" not in cand.lower()
    ):
      return cand

  return "Review Manually"


def parse_metadata(
    full_text: str, filename: str, invoice_lookup: dict
) -> dict:
  text_norm = full_text.replace("O", "0")

  def find_match(patterns, text_block):
    for p in patterns:
      m = re.search(p, text_block, re.IGNORECASE)
      if m:
        return m.group(1).strip().replace(" ", "").replace("+", "")
    return "Review Manually"

  shipment_num = find_match(
      [r"Shipment\s*[:\s]*([\d\s+]+)", r"\b(200\d{7,})\b", r"\b(160\d{7})\b"],
      text_norm,
  )
  invoice_num = invoice_lookup.get(
      shipment_num,
      invoice_lookup.get(
          shipment_num.lstrip("0"),
          invoice_lookup.get(
              re.sub(r"\.0$", "", shipment_num), "Not Found in DALI"
          ),
      ),
  )

  # Dátum
  date_str = find_match(
      [r"(\d{4}[-./]\d{2}[-./]\d{2})", r"(\d{2}[-./]\d{2}[-./]\d{4})"], full_text
  )

  # Címzett és Telephely / Ország szétbontás
  consignee, site_clean, country_clean, stamp = (
      "Unknown",
      "Unknown",
      "Unknown",
      "No",
  )
  for name, info in KNOWN_CONSIGNEES.items():
    if any(re.search(kw, full_text, re.IGNORECASE) for kw in info["keywords"]):
      consignee = name
      site_raw = info.get("site", "Unknown")
      stamp = "Yes"
      if "," in site_raw:
        site_clean, country_clean = [p.strip() for p in site_raw.split(",", 1)]
      else:
        site_clean = site_raw
      break

  to_val = find_match(
      [r"T[O0][:!]*\s*([A-Z]{2}\d+)", r"\b(EL\d{10})\b"], text_norm
  )
  loading_val = find_match(
      [
          r"\b(HU\d{2}[_\-\s]?[A-Z]{2}\d{10,})\b",
          r"Loading\s*list\s*[:\s]*([A-Z0-9_\-]{10,})",
      ],
      text_norm,
  )
  customs_seal_val = find_match(
      [
          r"V[aá]mz[aá]r[\s\S]{0,40}?\b(0[01](?:[\s]?[0-9O]){4,6})\b",
          r"\b(0[01]\d{4,5})\b",
      ],
      text_norm,
  )

  carrier_val = extract_carrier(full_text, consignee)

  return {
      "Eredeti Fájlnév": filename,
      "Dátum": date_str,
      "Invoice from DALI": invoice_num,
      "Shipment No.": shipment_num,
      "CMR Szám": find_match([r"N°\s*(\d{4}\s?/\s?\d+)"], full_text),
      "Transport Order (TO)": to_val,
      "Loading List (Box 5)": loading_val,
      "Customs Seal (Vámzár)": customs_seal_val,
      "Box 24 Bélyegző": stamp,
      "Címzett": consignee,
      "Átvevő Telephely": site_clean,
      "Ország": country_clean,
      "Fuvarozó": carrier_val,
      "Új Fájl Útvonala": "N/A",
  }
