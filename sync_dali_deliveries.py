print("1. [START] A sync_dali_deliveries.py szkript elindult...")

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    from config import settings
    from core.dali_connection import get_dali_connection
    print("✅ Konfiguráció és DALI kapcsolat sikeresen importála.")
except Exception as e:
    print(f"❌ IMPORTÁLÁSI HIBA: {e}")
    sys.exit(1)

DB_PATH = Path("c:/Users/DEM1MC/OneDrive - Bosch Group/Documents/POD/pod_database.db")

# Dátum, Plant, VSTEL, és Invoice előtag szűrők
TARGET_DATE_FORMAT_1 = "20260918"
TARGET_DATE_FORMAT_2 = "2026-09-18"
TARGET_PLANT = "2120"
INVOICE_PREFIX = "00506"
TARGET_VSTEL = "2000"

def sync_deliveries_from_dali():
    print("\n" + "=" * 60)
    print(f"🔄 DALI ADATBÁZIS SZINKRONIZÁCIÓ ({TARGET_DATE_FORMAT_2})...")
    print("=" * 60)

    conn_oracle = get_dali_connection()
    if not conn_oracle:
        print("❌ Sikertelen csatlakozás a DALI adatbázishoz.")
        return

    # Szigorú, minden kért táblát összekötő SQL lekérdezés
    sql_dali = f"""
        SELECT DISTINCT
            v.VBELN as Invoice,
            v.ERDAT as Billing_Date,
            h.KUNAG as Sold_To,
            k.NAME1 as Customer,
            h.SPE_GEOROUTE as Country,
            v.Y16V_TKNUM as Shipment_No,
            l.VBELN as DN
        FROM mard_dali_pt.VBRP_P13 v
        INNER JOIN mard_dali_pt.LIPS_P13 l ON v.VGBEL = l.VBELN AND v.VGPOS = l.POSNR
        INNER JOIN mard_dali_pt.LIKP_P13 h ON l.VBELN = h.VBELN
        LEFT JOIN mard_dali_pt.KNA1_P13 k ON h.KUNAG = k.KUNNR
        WHERE (v.ERDAT = '{TARGET_DATE_FORMAT_1}' OR v.ERDAT = '{TARGET_DATE_FORMAT_2}')
          AND v.Y16V_TKNUM IS NOT NULL
          AND l.WERKS = '{TARGET_PLANT}'
          AND v.VBELN LIKE '{INVOICE_PREFIX}%'
          AND v.VSTEL = '{TARGET_VSTEL}'
    """

    try:
        print("📥 Adatok lekérése az Oracle DALI adatbázisból...")
        cursor_oracle = conn_oracle.cursor()
        cursor_oracle.execute(sql_dali)
        rows = cursor_oracle.fetchall()
        print(f"✅ Lekérdezés sikeres, {len(rows)} db sor beolvasva.")

        if not rows:
            print("ℹ️ Nincs a szűrésnek megfelelő rekord a DALI-ban.")
            return

        # --- Python csoportosító logika ---
        aggregated = {}
        for r in rows:
            invoice = str(r[0]).strip()
            # JAVÍTÁS: r használata a teljes r helyett, így csak a tiszta dátum kerül átvitelre!
            billing_date = str(r[1]).strip() 
            sold_to = str(r[2]).strip()
            customer = str(r[3]).strip()
            country = str(r[4]).strip()
            shipment_no = str(r[5]).strip()
            dn = str(r[6]).strip()

            key = (shipment_no, invoice)
            if key not in aggregated:
                aggregated[key] = {
                    "Invoice": invoice,
                    "Billing_Date": billing_date,
                    "Sold_To": sold_to,
                    "Customer": customer,
                    "Country": country,
                    "Shipment_No": shipment_no,
                    "DNs": set()
                }
            if dn and dn.lower() != "none" and dn.lower() != "nan":
                aggregated[key]["DNs"].add(dn)

        # Mentés az SQLite adatbázisba
        print("10. Helyi SQLite adatbázis megnyitása...")
        with sqlite3.connect(str(DB_PATH)) as conn_sqlite:
            cursor_sqlite = conn_sqlite.cursor()
            
            from storage.database import initialize_database
            initialize_database()

            synced_count = 0
            for key, data in aggregated.items():
                shipment_no, invoice = key
                dns_str = ", ".join(sorted(list(data["DNs"]))) if data["DNs"] else ""

                # Megnézzük, létezik-e már ez a konkrét Shipment + Invoice párosítás
                cursor_sqlite.execute(
                    "SELECT id FROM POD_Extractions WHERE Shipment_No = ? AND Invoice = ?", 
                    (shipment_no, invoice)
                )
                exists = cursor_sqlite.fetchone()
                
                if not exists:
                    cursor_sqlite.execute("""
                        INSERT INTO POD_Extractions (
                            Invoice, Billing_Date, Sold_To, Customer, Country, 
                            Upload_Date, Shipment_No, DN, Uj_Fajl_Utvonala
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        invoice, 
                        data["Billing_Date"], 
                        data["Sold_To"], 
                        data["Customer"], 
                        data["Country"],
                        datetime.now().strftime("%Y.%m.%d %H:%M"),
                        shipment_no,
                        dns_str,
                        "N/A"
                    ))
                    synced_count += 1
            
            conn_sqlite.commit()
            print(f"✔ Szinkronizáció kész! {synced_count} db új rekord rögzítve az SQLite-ban.")

    except Exception as e:
        print(f"🔥 HIBA a szinkronizáció folyamat közben: {e}")
    finally:
        if conn_oracle:
            conn_oracle.close()
        print("=" * 60)

# Futtatás
sync_deliveries_from_dali()
