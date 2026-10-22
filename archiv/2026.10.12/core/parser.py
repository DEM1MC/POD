from datetime import datetime
from pathlib import Path
import re
from config.settings import KNOWN_CONSIGNEES
import pandas as pd

def load_dali_lookup(dali_path: Path) -> dict:
    if not dali_path.exists(): return {}
    try:
        df_dali = pd.read_excel(dali_path, dtype=str)
        df_dali.columns = [str(c).strip() for c in df_dali.columns]
        trans_col = next((c for c in df_dali.columns if "transport" in c.lower()), "transport szam")
        inv_col = next((c for c in df_dali.columns if "vbeln" in c.lower() or "szamla" in c.lower()), "szamladelivery.VBELN")
        if not trans_col or not inv_col: return {}
        
        lookup = {}
        for _, row in df_dali.dropna(subset=[trans_col, inv_col]).iterrows():
            shipment = str(row[trans_col]).strip()
            invoice = str(row[inv_col]).strip()
            if shipment not in lookup:
                lookup[shipment] = []
            if invoice not in lookup[shipment]:
                lookup[shipment].append(invoice)
        
        return lookup
    except Exception as e:
        print(f"⚠️ Hiba a DALI tábla beolvasásakor: {e}")
        return {}

def find_all_matches(pattern: str, text: str) -> list:
    try:
        matches = re.findall(pattern, text, re.IGNORECASE)
        return sorted(list(set([re.sub(r"[\s\+]", "", m) for m in matches if m])))
    except Exception:
        return []

def check_box_24_stamp(full_text: str) -> str:
    # ... (Ez a függvény nem változik)
    return "Yes" if len(re.sub(r"[^a-zA-Z0-9]", "", re.sub(r"24\b|az\s+áru\s+átvétele|goods\s+received|gut\s+empfangen|kelet[:\.]?|date\s+on|datum\s+am|established\s+in|ausgefertigt\s+in|az\s+átvevő\s+aláírása|signature\s+and\s+stamp\s+of\s+the\s+consignee|unterschrift\s+und\s+stempel|des\s+empfängers|consignee|empfängers|signature|stamp|bélyegző|aláírás|robert\s*bosch|kiss\s*kriszti[aá]n", " ", re.search(r"(?:24\b|Goods received)[\s\S]{0,400}?(?=\b25\b|Vehicle|\Z)", full_text, re.IGNORECASE).group(0).lower(), flags=re.IGNORECASE))) > 4 else "No"

def extract_carrier(full_text: str, consignee_name: str) -> str:
    # ... (Ez a függvény nem változik)
    return "Review Manually"

def parse_metadata(full_text: str, filename: str, invoice_lookup: dict) -> dict:
    text_norm = full_text.replace("O", "0")

    consignee, site_clean, country_clean = "Unknown", "Unknown", "Unknown"
    for name, info in KNOWN_CONSIGNEES.items():
        if any(re.search(kw, full_text, re.IGNORECASE) for kw in info["keywords"]):
            consignee, site_raw = name, info.get("site", "Unknown")
            if "," in site_raw:
                site_clean, country_clean = [p.strip() for p in site_raw.split(",", 1)]
            else:
                site_clean = site_raw
            break

    # --- Kétlépcsős Invoice/Shipment Logika ---
    shipments_from_text = find_all_matches(r"\b(200\d{7,}|160\d{7,})\b", text_norm)
    invoices_from_text = find_all_matches(r"\b(22\d{6,}|33\d{6,})\b", text_norm)
    invoices_from_dali = []
    for s in shipments_from_text:
        if s in invoice_lookup:
            invoices_from_dali.extend(invoice_lookup[s])
    all_invoices = set(invoices_from_text + invoices_from_dali)
    
    final_shipments = ", ".join(shipments_from_text) if shipments_from_text else "Review Manually"
    final_invoices = ", ".join(sorted(all_invoices)) if all_invoices else "Not Found"
    
    # --- JAVÍTOTT LOADING LIST PATTERN ---
    # A pattern most már elfogadja a szóközöket és a '/' jelet is a számon belül.
    loading_list_pattern = r"Loading\s*list\s*[:\s]*([A-Z0-9_ /\\-]{10,})"
    loading_lists = ", ".join(find_all_matches(loading_list_pattern, full_text))
    # --- JAVÍTÁS VÉGE ---

    return {
        "Eredeti Fájlnév": filename,
        "Dátum": ", ".join(find_all_matches(r"(\d{4}[-./]\d{2}[-./]\d{2})", full_text)),
        "Invoice from DALI": final_invoices,
        "Shipment No.": final_shipments,
        "CMR Szám": ", ".join(find_all_matches(r"N°\s*(\d{4}\s?/\s?\d+)", full_text)),
        "Transport Order (TO)": ", ".join(find_all_matches(r"T[O0][:!]*\s*([A-Z]{2}\d+)", text_norm)),
        "Loading List (Box 5)": loading_lists if loading_lists else "Review Manually",
        "Customs Seal (Vámzár)": ", ".join(find_all_matches(r"Vámzár\s*[:\s]*(\d+)", text_norm)),
        "Box 24 Bélyegző": check_box_24_stamp(full_text),
        "Címzett": consignee,
        "Átvevő Telephely": site_clean,
        "Ország": country_clean,
        "Fuvarozó": extract_carrier(full_text, consignee),
        "Feltöltés Ideje": datetime.now().strftime("%Y.%m.%d %H:%M"),
        "Új Fájl Útvonala": "N/A",
    }
