import shutil
from pathlib import Path
import re

def organize_and_rename_file(source_path: Path, metadata: dict, target_base_folder: Path) -> str:
    """
    Rendezi a fájlt az ÉV mappába, és átnevezi a kért formátum szerint.
    Formátum: [CMR Dátum (YYYY-MM-DD)]_[Első Shipment]_[Összes Invoice számlaszám].pdf
    """
    try:
        # 1. Célmappa meghatározása (CSAK ÉV)
        date_str = metadata.get("CMR Date", "")
        year = "Ismeretlen_Ev"
        
        # Próbálunk évet keresni (pl. 2026-10-08 vagy 2026.10.08)
        year_match = re.search(r"(\d{4})", date_str)
        if year_match:
            year = year_match.group(1)
        
        target_folder = target_base_folder / year
        target_folder.mkdir(parents=True, exist_ok=True)
        
        # 2. Dátum formázása YYYY-MM-DD-re kötőjelekkel
        formatted_date = "NoDate"
        # Ha yyyy.mm.dd vagy yyyy-mm-dd formátumú
        date_match = re.search(r"(\d{4})[-./](\d{2})[-./](\d{2})", date_str)
        if date_match:
            formatted_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        else:
            # Ha fordított sorrendű (pl. 08.10.2026)
            date_match_rev = re.search(r"(\d{2})[-./](\d{2})[-./](\d{4})", date_str)
            if date_match_rev:
                formatted_date = f"{date_match_rev.group(3)}-{date_match_rev.group(2)}-{date_match_rev.group(1)}"
            else:
                # Végső mentőöv: cseréljük a pontokat/perjeleket kötőjelre
                cleaned_date = re.sub(r"[^\w-]", "", date_str.replace(".", "-").replace("/", "-")).strip()
                if cleaned_date:
                    formatted_date = cleaned_date

        # 3. Első Shipment szám kinyerése
        shipment_raw = metadata.get("Shipment No", "NoShipment")
        shipments = [s.strip() for s in shipment_raw.split(",") if s.strip()]
        first_shipment = shipments[0] if shipments else "NoShipment"
        safe_shipment = re.sub(r'[\\/*?:"<>|]', "", first_shipment)

        # 4. ÖSSZES Invoice kinyerése és összefűzése kötőjellel
        invoice_raw = metadata.get("Invoice", "NoInvoice")
        invoices = [inv.strip() for inv in invoice_raw.split(",") if inv.strip() and inv.strip().lower() != "not found"]
        if invoices:
            # Összes invoice szám összefűzése kötőjellel
            all_invoices_str = "-".join(invoices)
        else:
            all_invoices_str = "NoInvoice"
        safe_invoice = re.sub(r'[\\/*?:"<>|]', "", all_invoices_str)

        # Eredeti kiterjesztés megtartása (pl. .pdf, .png stb.)
        original_extension = source_path.suffix

        new_filename = f"{formatted_date}_{safe_shipment}_{safe_invoice}{original_extension}"
        target_path = target_folder / new_filename
        
        # Fájl átmozgatása és átnevezése
        shutil.move(str(source_path), str(target_path))
        
        return str(target_path)
    except Exception as e:
        print(f"⚠️ Hiba a fájl áthelyezésekor ({source_path.name}): {e}")
        return str(source_path)
