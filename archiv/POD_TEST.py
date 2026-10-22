import io
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
from pathlib import Path
import sqlite3
import pandas as pd

# ==========================================
# 1. KÖRNYEZETI BEÁLLÍTÁSOK
# ==========================================
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["CPU_NUM"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import cv2
import numpy as np
import pandas as pd
from PIL import Image
import pymupdf

import paddle
from paddleocr import PaddleOCR

# Az adatbázis elérési útja a POD főkönyvtárában
DB_PATH = Path(r"C:\Users\DEM1MC\OneDrive - Bosch Group\Documents\POD\pod_database.db")

def save_to_sqlite(df_records: pd.DataFrame):
    """
    A kinyert metaadatok mentése az SQLite adatbázisba duplikáció-védelemmel.
    Ha egy fájl már szerepel az adatbázisban, frissíti a rekordot ahelyett, hogy duplikálná.
    """
    if df_records.empty:
        print("ℹ Nincs mentendő új rekord az SQLite adatbázisba.")
        return

    column_mapping = {
        "Eredeti Fájlnév": "Eredeti_Fajlnev",
        "Dátum": "Datum",
        "Invoice from DALI": "Invoice_from_DALI",
        "Shipment No.": "Shipment_No",
        "CMR Szám": "CMR_Szam",
        "Transport Order (TO)": "Transport_Order",
        "Loading List (Box 5)": "Loading_List",
        "Customs Seal (Vámzár)": "Customs_Seal",
        "Box 24 Bélyegző": "Box_24_Belyegzo",
        "Címzett": "Cimzett",
        "Átvevő Telephely": "Atvevo_Telephely",
        "Új Fájl Útvonala": "Uj_Fajl_Utvonala"
    }

    df_sql = df_records.rename(columns=column_mapping)
    # Csak azokat az oszlopokat tartjuk meg, amik a sémában szerepelnek
    valid_cols = list(column_mapping.values())
    df_sql = df_sql[[c for c in valid_cols if c in df_sql.columns]]

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # 1. Tábla létrehozása UNIQUE kulccsal az Eredeti_Fajlnev mezőre
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS POD_Extractions (
                    Eredeti_Fajlnev TEXT PRIMARY KEY,
                    Datum TEXT,
                    Invoice_from_DALI TEXT,
                    Shipment_No TEXT,
                    CMR_Szam TEXT,
                    Transport_Order TEXT,
                    Loading_List TEXT,
                    Customs_Seal TEXT,
                    Box_24_Belyegzo TEXT,
                    Cimzett TEXT,
                    Atvevo_Telephely TEXT,
                    Uj_Fajl_Utvonala TEXT
                );
            """)

            # 2. Beszúrás INSERT OR REPLACE logikával (felülírja a duplikátumot, nem duplázza!)
            cols = list(df_sql.columns)
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            sql = f"INSERT OR REPLACE INTO POD_Extractions ({col_names}) VALUES ({placeholders})"

            rows = df_sql.values.tolist()
            cursor.executemany(sql, rows)

            # 3. Gyorskeresési indexek létrehozása
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice ON POD_Extractions(Invoice_from_DALI);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipment ON POD_Extractions(Shipment_No);")
            conn.commit()

        print(f"✔ Adatok sikeresen szinkronizálva az SQLite adatbázissal ({len(rows)} rekord feldolgozva, duplikációk nélkül)!")
    except Exception as e:
        print(f"❌ SQLite mentési hiba: {e}")

# ==========================================
# 2. ELÉRÉSI UTAK
# ==========================================
SOURCE_FOLDER = Path(
    r"C:\Users\DEM1MC\OneDrive - Bosch Group\Documents\POD\Proba PoD automata"
)
TARGET_BASE_FOLDER = Path(
    r"C:\Users\DEM1MC\OneDrive - Bosch Group\Documents\POD\Rendezett POD-k"
)
OUTPUT_EXCEL = TARGET_BASE_FOLDER / "master_pod_extraction_report.xlsx"
DALI_LOOKUP_TABLE = SOURCE_FOLDER.parent / "podtabla.xlsx"

KNOWN_CONSIGNEES = {
    "Dhl Supply Chain (Italy) S.p.A.": {
        "keywords": ["dhl", "lacchiarella"],
        "site": "Logistic Center - Lacchiarella (MI)",
    },
    "Kuehne + Nagel": {
        "keywords": ["kuehne", "nagel", r"k\+n"],
        "site": "Partner Site",
    },
    "Fiege Deutschland Stiftung & Co. KG": {
        "keywords": ["fiege"],
        "site": "Worms, DE",
    },
    "Quehenberger Logistics": {
        "keywords": ["quehenberger"],
        "site": "Clinceni, RO",
    },
    "ID Logistics": {"keywords": ["id logistics"], "site": "Guadalajara, ES"},
    "Barsan Global Lojistik": {"keywords": ["barsan"], "site": "Tuzla, TR"},
    "Orphee Beinoglou S.A.": {
        "keywords": [
            "orphee",
            "beinoglou",
            "elefsina",
            "athina",
            "athens",
            "ορφευσ",
            "0pφεyσ",
        ],
        "site": "Elefsina, GR",
    },
    "DSV Solutions": {"keywords": ["dsv"], "site": "Norrköping, SE"},
    "Dagendatrans Speed S.R.L.": {
        "keywords": ["dagenda"],
        "site": "Cezieni, Olt",
    },
}

# ==========================================
# 3. DEBUG SZÖVEGKINYERŐ FÜGGVÉNY
# ==========================================


def extract_text_from_pdf_debug(pdf_path: Path, ocr_engine: PaddleOCR) -> str:
  print(f"\n{'='*70}")
  print(f"🔍 [DEBUG START] Fájl vizsgálata: {pdf_path.name}")
  print(f"   Méret: {pdf_path.stat().st_size / 1024:.1f} KB")

  full_text = ""
  try:
    doc = pymupdf.open(str(pdf_path))
    print(f"   Oldalak száma: {len(doc)}")

    # 1. Lépés: Digitális szöveg vizsgálata
    embedded_text = ""
    for idx, page in enumerate(doc):
      t = page.get_text()
      if t.strip():
        embedded_text += f"[Oldal {idx+1}] {t}\n"

    print(
        f"   Beágyazott digitális karakterek száma: {len(embedded_text.strip())}"
    )

    if len(embedded_text.strip()) >= 200:
      print("   -> Digitális PDF-ként kezelve (nincs szükség OCR-re).")
      return embedded_text

    print(
        "   -> Kevés/nincs beágyazott szöveg. PaddleOCR futtatása következik..."
    )
    ocr_extracted_lines = []

    # Csak az első oldalt elemezzük a teszthez
    page = doc[0]
    pix = page.get_pixmap(dpi=105)
    print(f"   Renderelt kép mérete: {pix.width}x{pix.height} pixel (105 DPI)")

    img_np = np.frombuffer(pix.tobytes("png"), dtype=np.uint8)
    img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    if img is None:
      print("   ❌ [HIBA] A kép dekódolása nem sikerült (cv2.imdecode None)!")
      return ""

    print(f"   Kép mátrix alakja (NumPy shape): {img.shape}")
    print("   PaddleOCR motor hívása folyamatban (kérlek várj)...")

    # 2. Lépés: PaddleOCR közvetlen meghívása hibaelkapással
    results = None
    try:
      results = ocr_engine.predict(img)
      print("   ✔ ocr_engine.ocr(img) sikeresen lefutott.")
    except Exception as e1:
      print(f"   ⚠️ ocr_engine.ocr(img) hibát dobott: {e1}")
      print("   Alternatív megközelítés: ocr_engine.predict(img)...")
      try:
        results = ocr_engine.predict(img)
        print("   ✔ ocr_engine.predict(img) sikeresen lefutott.")
      except Exception as e2:
        print(f"   ❌ Mindkét hívási mód elbukott!")
        traceback.print_exc()
        return ""

    # 3. Lépés: Visszaadott struktúra elemzése
    print(f"\n   [VISSZAADOTT EREDMÉNY STRUKTÚRA]")
    print(f"   Típus: {type(results)}")

    if results is None:
      print("   ❌ results értéke None!")
      return ""

    if isinstance(results, list):
      print(f"   Lista hossza: {len(results)}")
      if len(results) > 0:
        print(f"   Első elem típusa: {type(results[0])}")

    # Eredmények kibontása
    print("\n   [FELISMERT SZÖVEGEK KINYERÉSE]")
    if isinstance(results, list):
      for idx, page_res in enumerate(results):
        if page_res is None:
          print(f"   Oldal {idx}: None")
          continue
        if isinstance(page_res, list):
          for line in page_res:
            if (
                isinstance(line, (list, tuple))
                and len(line) >= 2
                and isinstance(line[1], (tuple, list))
            ):
              txt = line[1][0]
              conf = line[1][1]
              print(f"      [Sor] (pontosság: {conf:.2f}): {txt}")
              ocr_extracted_lines.append(str(txt))
            elif isinstance(line, (list, tuple)) and len(line) >= 1:
              print(f"      [Sor]: {line[0]}")
              ocr_extracted_lines.append(str(line[0]))
            elif isinstance(line, dict):
              txt = line.get("text", str(line))
              print(f"      [Dict]: {txt}")
              ocr_extracted_lines.append(txt)
            else:
              print(f"      [Egyéb]: {line}")
              ocr_extracted_lines.append(str(line))
        elif isinstance(page_res, dict):
          for k, v in page_res.items():
            print(f"      Key: {k} -> {str(v)[:80]}")
            if "rec_text" in k or "text" in k:
              ocr_extracted_lines.append(str(v))

    full_text = "\n".join(ocr_extracted_lines)
    print(
        f"\n   Összes kinyert szövegsor: {len(ocr_extracted_lines)} db,"
        f" {len(full_text)} karakter"
    )

  except Exception as e:
    print(f"\n❌ [VÁRATLAN KIVÉTEL]: {e}")
    traceback.print_exc()

  return full_text


# ==========================================
# 4. METADATA ÉS REGEX VIZSGÁLAT
# ==========================================


def parse_metadata_debug(
    full_text: str, filename: str, invoice_lookup: dict
) -> dict:
  print(f"\n--- [REGEX VIZSGÁLAT]: {filename} ---")
  text = full_text.replace("O", "0")

  def find_match(name, patterns, text_block):
    for p in patterns:
      m = re.search(p, text_block, re.IGNORECASE)
      if m:
        val = m.group(1).strip().replace(" ", "").replace("+", "")
        print(f"   ✔ {name}: '{val}' (minta: {p})")
        return val
    print(f"   ✖ {name}: Nem található illeszkedés!")
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
      # 1. HU03_RO... vagy HU03-RO... vagy HU03 RO... vagy HU03RO...
        r'\b(HU\d{2}[_\-\s]?[A-Z]{2}\d{10,})\b',
        # 2. Ha az elején a 0 O-nak látszik: HUO3_RO...
        r'\b(HU[0-9O]{2}[_\-\s]?[A-Z]{2}[0-9O]{10,})\b',
        # 3. Ha közvetlenül a Loading list szó után áll bármilyen formátumban:
        r'Loading\s*list\s*[:\s]*([A-Z0-9_\-]{10,25})',
        r'L[o0]ading\s*[l1]ist\s*[:\s]*([A-Z0-9_\-]{10,25})',
        # 4. Általános 14-18 karakteres kód az 5-ös rovatból:
        r'\b([A-Z]{2}\d{2}[_\-][A-Z]{2}\d{8,12})\b',
    ]

  seal_patterns = [
      r"Vámzár\s*[:\s]*(\d+)",
      r"Seal\s*[:\s]*(\d+)",
      r"\b(00\d{4,6})\b",
  ]
  date_patterns = [
      r"(\d{4}-\d{2}-\d{2})",
      r"(\d{4}\.\d{2}\.\d{2})",
      r"(\d{2}[-./]\d{2}[-./]\d{4})",
      r"(\d{2}[-./]\d{2}[-./]\d{2})",
  ]

  shipment_num = find_match("Shipment No.", shipment_patterns, text)
  invoice_from_dali = invoice_lookup.get(shipment_num, "Not Found in DALI")
  print(f"   ℹ DALI párosítás ({shipment_num}): {invoice_from_dali}")

  date_str = find_match("Dátum", date_patterns, text)
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

  consignee, site, stamp = "Unknown", "Unknown", "No"
  for name, info in KNOWN_CONSIGNEES.items():
    if any(re.search(kw, text, re.IGNORECASE) for kw in info["keywords"]):
      consignee = name
      site = info["site"]
      stamp = "Yes"
      print(f"   ✔ Partner beazonosítva: {consignee} ({site})")
      break
 # Transport Order és Loading List különválasztása
  to_val = find_match("Transport Order (TO)", to_patterns, text)
  loading_val = find_match("Loading List (Box 5)", loading_list_patterns, text)

  # Kizárjuk, hogy a TO véletlenül bekerüljön a Loading List mezőbe
  if loading_val == to_val or loading_val.startswith(("EL", "TO")):
    loading_val = "Review Manually"

  return {
      "Eredeti Fájlnév": filename,
      "Dátum": parsed_date,
      "Invoice from DALI": invoice_from_dali,
      "Shipment No.": shipment_num,
      "CMR Szám": find_match("CMR Szám", cmr_patterns, text),
      "Transport Order (TO)": to_val,
      "Loading List (Box 5)": loading_val,
      "Customs Seal (Vámzár)": find_match("Customs Seal", seal_patterns, text),
      "Box 24 Bélyegző": stamp,
      "Címzett": consignee,
      "Átvevő Telephely": site,
      "Új Fájl Útvonala": "N/A",
  }

def organize_and_rename_file(pdf_path: Path, metadata: dict, target_base: Path):
    """
    Létrehozza a célmappát, majd a sikeres feldolgozás után
    ÁTHELYEZI a fájlt a forrásmappából a célmappába az új nevén.
    """
    date = metadata.get("Dátum", "NA_D")
    invoice = metadata.get("Invoice from DALI", "NO_INV")
    shipment = metadata.get("Shipment No.", "NA_S")
    year = date.split("-")[0] if date.startswith("20") else "Vegyes"
    
    destination_dir = target_base / year
    destination_dir.mkdir(parents=True, exist_ok=True)
    
    clean_filename = re.sub(r'[\\/*?:"<>|]', "_", f"{date}_{invoice}_{shipment}.pdf")
    dest_path = destination_dir / clean_filename
    
    try:
        # A shutil.copy2 helyett shutil.move-ot használunk, ami áthelyezi a fájlt.
        shutil.move(str(pdf_path), str(dest_path))
        print(f"   -> ✔️ Fájl sikeresen áthelyezve ide: {dest_path}")
        return str(dest_path)
    except Exception as e:
        print(f"   -> ❌ [HIBA] A fájl áthelyezése nem sikerült: {e}")
        # Hiba esetén a fájl a helyén marad, így a következő futáskor újra próbálkozhat.
        return "Áthelyezés sikertelen"


# ==========================================
# 5. FŐPROGRAM
# ==========================================
def main():
  print("\n" + "=" * 70)
  print("🚀 PADDLEOCR HIBAKERESŐ ÉS RÉSZLETES DIAGNOSZTIKAI FUTÁS")
  print("=" * 70)

  if not SOURCE_FOLDER.exists():
    return print(f"❌ Forrásmappa nem található: {SOURCE_FOLDER}")

  all_pdfs = [p for p in SOURCE_FOLDER.glob("*.pdf") if p.is_file()]
  print(f"Mappában talált PDF fájlok ({len(all_pdfs)} db):")
  for p in all_pdfs:
    print(f"  • {p.name}")

  if not all_pdfs:
    return print("Nincs PDF a mappában!")

  invoice_lookup = {}
  if DALI_LOOKUP_TABLE.exists():
    try:
        df_dali = pd.read_excel(DALI_LOOKUP_TABLE)
        df_dali['transport szam'] = (
        df_dali['transport szam']
                .astype(str)
                .str.replace(r'\.0$', '', regex=True)
                .str.strip()
            )
        df_dali['szamladelivery.VBELN'] = (
                df_dali['szamladelivery.VBELN']
                .astype(str)
                .str.replace(r'\.0$', '', regex=True)
                .str.strip()
            )
        invoice_lookup = pd.Series(
        df_dali['szamladelivery.VBELN'].values, index=df_dali['transport szam']).to_dict()
        print(f"✔ DALI tábla betöltve ({len(invoice_lookup)} rekord).")
    except Exception as e:
      print(f"⚠️ Hiba a DALI tábla beolvasásakor: {e}")

  print("\n⏳ PaddleOCR inicializálása...")
  try:
    ocr_engine = PaddleOCR(
            lang="en",
            # --- Stabilitási és sebességoptimalizálási paraméterek ---
            enable_mkldnn=False,              # Megelőzi a C++ szintű összeomlást
            use_angle_cls=True,               # Bekapcsolja a szövegirány-észlelést
            
            # --- HIVATALOS, ÚJ PARAMÉTERNEVEK A GYORSÍTÁSHOZ ---
            text_det_limit_side_len=960,    # Korlátozza a kép felbontását a detektálás előtt (kulcsfontosságú a sebességhez!)
            text_recognition_batch_size=8,  # Egyszerre 8 szövegdobozt dolgoz fel párhuzamosan
    )
    print("✔ PaddleOCR inicializálva.")
  except Exception as e:
    print(f"❌ Nem sikerült elindítani a PaddleOCR-t: {e}")
    traceback.print_exc()
    return

  all_records = []
  for pdf_path in all_pdfs:
    raw_text = extract_text_from_pdf_debug(pdf_path, ocr_engine)
    data = parse_metadata_debug(raw_text, pdf_path.name, invoice_lookup)

    # Fájl átmásolása az új néven
    data["Új Fájl Útvonala"] = organize_and_rename_file(
        pdf_path, data, TARGET_BASE_FOLDER
    )
    all_records.append(data)

     # =================================================================
    # 4. LÉPÉS: EREDMÉNYEK HOZZÁFŰZÉSE ÉS MENTÉSE
    # =================================================================
    print("\n" + "=" * 60)
    print("💾 Riport frissítése...")

    column_order = [
        "Eredeti Fájlnév", "Dátum", "Invoice from DALI", "Shipment No.", "CMR Szám", "Transport Order (TO)", 
        "Loading List (Box 5)", "Customs Seal (Vámzár)", "Box 24 Bélyegző", "Címzett", "Átvevő Telephely", "Új Fájl Útvonala"
    ]

    # Hozzunk létre egy DataFrame-et az új adatokból
    new_df = pd.DataFrame(all_records, columns=column_order)

    # Ellenőrizzük, létezik-e a régi riport
    if OUTPUT_EXCEL.exists():
        print(f"   -> Meglévő riport ({OUTPUT_EXCEL.name}) beolvasása...")
        try:
            old_df = pd.read_excel(OUTPUT_EXCEL)
            # Összefésüljük a régi és új adatokat, és kiszűrjük a duplikátumokat
            combined_df = pd.concat([old_df, new_df], ignore_index=True)
            combined_df.drop_duplicates(subset=['Eredeti Fájlnév'], keep='last', inplace=True)
            print(f"   -> Riport frissítve. Összesen {len(combined_df)} egyedi rekord.")
        except Exception as e:
            print(f"   -> ⚠️ Hiba a régi riport olvasásakor ({e}), felülírás új adatokkal.")
            combined_df = new_df
    else:
        print("   -> Új riport létrehozása...")
        combined_df = new_df

    # A teljes, frissített DataFrame mentése
    try:
        combined_df.to_excel(OUTPUT_EXCEL, index=False, engine="openpyxl")
        print(f"✅ Riport sikeresen elmentve: {OUTPUT_EXCEL}")
    except PermissionError:
        alt_excel = TARGET_BASE_FOLDER / f"master_report_{pd.Timestamp.now():%H%M%S}.xlsx"
        combined_df.to_excel(alt_excel, index=False, engine="openpyxl")
        print(f"⚠️ Az eredeti Excel nyitva volt, ezért ide mentve: {alt_excel.name}")
    

    save_to_sqlite(new_df)



if __name__ == "__main__":
  main()
