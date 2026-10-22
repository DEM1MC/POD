from datetime import datetime
from pathlib import Path
import re
from config.settings import KNOWN_CONSIGNEES

def find_all_matches(pattern: str, text: str) -> list:
    """Kigyűjti egy kifejezés összes előfordulását duplikátumok nélkül."""
    try:
        matches = re.findall(pattern, text, re.IGNORECASE)
        return sorted(list(set([re.sub(r"[\s\+]", "", m) for m in matches if m])))
    except Exception:
        return []

def extract_customs_seal(text: str) -> str:
    """Kinyeri az EGYETLEN vámzár számot a nyers szövegből (rugalmasan kezelve a szóközt, kettőspontot, sortörést)."""
    patterns = [
        # 1. Kifejezett kulcsszó utáni 5-10 számjegy vagy alfanumerikus azonosító (akár sortöréssel elválasztva)
        r"(?:V[aá]mz[aá]r|Customs\s*seal|Seal)\s*[:\s-]*\n?\s*([A-Z0-9]{5,10})\b",
        # 2. Kezdőnullás 6 számjegyű kódok (jellemző vámzár formátum: 017575, 021294)
        r"\b(0[0-9]{5})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Kiszűrjük, ha véletlenül egy évszámot vagy egyéb sablont találna meg
            if not val.startswith(("2024", "2025", "2026")):
                return val
    return "Review Manually"

def extract_carrier(full_text: str, consignee_name: str) -> str:
    """Kinyeri a fuvarozó cégnevet a címzett kizárásával."""
    known_carriers = [
        ("K&V Kft.", [r"k&v\s*kft", r"\bk&v\b"]),
        ("KPS Intertransport", [r"kps\s+intertransport", r"\bkps\b"]),
        ("Waberer's", [r"waberer", r"wabi"]),
        ("DHL Freight", [r"dhl\s+freight"]),
        ("DB Schenker", [r"db\s+schenker", r"\bschenker\b"]),
        ("Gebrüder Weiss", [r"gebr[uü]der\s+weiss"]),
        ("Duvenbeck", [r"duvenbeck"]),
        ("LKW Walter", [r"lkw\s+walter"]),
    ]
    for name, patterns in known_carriers:
        if name.lower() not in consignee_name.lower() and any(re.search(p, full_text, re.IGNORECASE) for p in patterns):
            return name

    m = re.search(r"\b([A-Z0-9\.\s-]{3,30}(?:Kft|Bt|Zrt|Sp\.\s*z\s*o\.o|GmbH|s\.r\.o|Transport))\b", full_text, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        if consignee_name.lower() not in candidate.lower() and "bosch" not in candidate.lower():
            return candidate
    return "Review Manually"

def parse_metadata(full_text: str, filename: str, fetch_invoices_func) -> dict:
    """Kinyeri az összes mezőt, a gyűjtőfuvaros mezőket az élő DALI adatbázisból lekérve."""
    text_norm = full_text.replace("O", "0")

    # Címzett, Telephely és Ország azonosítása
    consignee, site_clean, country_clean = "Unknown", "Unknown", "Unknown"
    for name, info in KNOWN_CONSIGNEES.items():
        if any(re.search(kw, full_text, re.IGNORECASE) for kw in info["keywords"]):
            consignee = name
            site_raw = info.get("site", "Unknown")
            if "," in site_raw:
                site_clean, country_clean = [p.strip() for p in site_raw.split(",", 1)]
            else:
                site_clean = site_raw
            break

    # 1. Shipment és direct invoice számok olvasása a dokumentumról
    shipments_from_text = find_all_matches(r"\b(200\d{7,}|160\d{7,})\b", text_norm)
    invoices_from_text = find_all_matches(r"\b(22\d{6,}|33\d{6,})\b", text_norm)

    # 2. ÉLŐ LEKÉRDEZÉS A DALI ADATBÁZISBÓL (Nincs visszaeső Excel ág!)
    invoices_from_dali = []
    if shipments_from_text and callable(fetch_invoices_func):
        dali_results = fetch_invoices_func(shipments_from_text)
        for s in shipments_from_text:
            if s in dali_results:
                invoices_from_dali.extend(dali_results[s])

    # 3. Összefésülés és szűrés (DALI-ból lekértek + közvetlenül kiolvasottak)
    all_invoices = set(invoices_from_text + invoices_from_dali)
    
    final_shipments = ", ".join(shipments_from_text) if shipments_from_text else "Review Manually"
    final_invoices = ", ".join(sorted(all_invoices)) if all_invoices else "Not Found"

    # Loading list kinyerése (támogatja a görög/török gyűjtők elválasztóit is)
    loading_list_pattern = r"Loading\s*list\s*[:\s]*([A-Z0-9_ /\\-]{10,})"
    loading_lists = ", ".join(find_all_matches(loading_list_pattern, full_text))

    # Egyetlen tiszta Vámzár kinyerése
    customs_seal_val = extract_customs_seal(full_text)

    return {
        "Eredeti Fájlnév": filename,
        "Dátum": ", ".join(find_all_matches(r"(\d{4}[-./]\d{2}[-./]\d{2})", full_text)),
        "Invoice from DALI": final_invoices,
        "Shipment No.": final_shipments,
        "CMR Szám": ", ".join(find_all_matches(r"N°\s*(\d{4}\s?/\s?\d+)", full_text)),
        "Transport Order (TO)": ", ".join(find_all_matches(r"T[O0][:!]*\s*([A-Z]{2}\d+)", text_norm)),
        "Loading List (Box 5)": loading_lists if loading_lists else "Review Manually",
        "Customs Seal (Vámzár)": customs_seal_val,
        "Box 24 Bélyegző": "Yes",  # Fixen Yes
        "Címzett": consignee,
        "Átvevő Telephely": site_clean,
        "Ország": country_clean,
        "Fuvarozó": extract_carrier(full_text, consignee),
        "Feltöltés Ideje": datetime.now().strftime("%Y.%m.%d %H:%M"),
        "Új Fájl Útvonala": "N/A",
    }
