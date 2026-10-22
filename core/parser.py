from datetime import datetime
from pathlib import Path
import re
from config.settings import KNOWN_CONSIGNEES

def find_all_matches(pattern: str, text: str) -> list:
    try:
        matches = re.findall(pattern, text, re.IGNORECASE)
        return sorted(list(set([re.sub(r"[\s\+]", "", m) for m in matches if m])))
    except Exception:
        return []

def parse_metadata(full_text: str, filename: str, fetch_invoices_func) -> dict:
    """
    Kizárólag a legfontosabb, megbízható mezőket olvassa ki OCR-rel,
    a többit előkészíti a DALI-ból vagy manuális bevitelre.
    """
    text_norm = full_text.replace("O", "0")

    # --- Címzett és Ország ---
    customer, country = "Unknown", "Unknown"
    for name, info in KNOWN_CONSIGNEES.items():
        if any(re.search(kw, full_text, re.IGNORECASE) for kw in info["keywords"]):
            customer, site_raw = name, info.get("site", "Unknown")
            if "," in site_raw:
                _, country = [p.strip() for p in site_raw.split(",", 1)]
            break

    # --- OCR-ből Olvasott Mezők ---
    shipments_from_text = find_all_matches(r"\b(200\d{7,}|160\d{7,})\b", text_norm)
    invoices_from_text = find_all_matches(r"\b(22\d{6,}|33\d{6,})\b", text_norm)
    
    # --- DALI Lekérdezés ---
    invoices_from_dali = []
    if shipments_from_text and callable(fetch_invoices_func):
        dali_results = fetch_invoices_func(shipments_from_text)
        for s in shipments_from_text:
            if s in dali_results:
                invoices_from_dali.extend(dali_results[s])

    # --- Összefésülés ---
    all_invoices = set(invoices_from_text + invoices_from_dali)
    final_invoices = ", ".join(sorted(all_invoices)) if all_invoices else "Not Found"
    final_shipments = ", ".join(shipments_from_text) if shipments_from_text else "Review Manually"

    return {
        # Új, DALI-ból vagy manuálisan töltendő mezők (üresen indulnak)
        "Invoice": final_invoices,
        "Billing Date": "",
        "Sold-To": "",
        "DN": "",
        
        # Átnevezett és megmaradt mezők
        "Customer": customer,
        "Country": country,
        
        # Új, manuálisan töltendő mezők
        "Document Type": "",
        "Comment": "",
        "Box 24 Belyegzo": "", # Manuálisan szerkeszthetővé tesszük
        
        # OCR-ből továbbra is olvasott mezők
        "Upload Date": datetime.now().strftime("%Y.%m.%d %H:%M"),
        "CMR Date": ", ".join(find_all_matches(r"(\d{4}[-./]\d{2}[-./]\d{2})", full_text)),
        "Transport Order": ", ".join(find_all_matches(r"T[O0][:!]*\s*([A-Z]{2}\d+)", text_norm)),
        "Shipment No": final_shipments,
        
        # Kikommentezett (jövőre félretett) mezők
        "CMR Szam": "", # ", ".join(find_all_matches(r"N°\s*(\d{4}\s?/\s?\d+)", full_text)),
        "Customs Seal": "", # extract_customs_seal(full_text),
        "Fuvarozo": "", # extract_carrier(full_text, customer),

        # Technikai mezők
        "Eredeti Fajlnev": filename,
        "Uj Fajl Utvonala": "N/A",
    }
