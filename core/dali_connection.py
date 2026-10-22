# core/dali_connection.py teljes tartalma

import os
import oracledb
import sys

# --- Konfiguráció ---
DALI_TNS_NAME = "Redlake_zeusp_consumer_dali.world"
DALI_USER = "dem1mc"  # A felhasználód

# Írd be ide a valódi Power BI-os jelszavadat!
DALI_PASSWORD = "Strongbowgold.123" 

TABLE_NAME = "MARD_DALI_PT.VBRP_P13"
SHIPMENT_COLUMN = "Y16V_TKNUM"
INVOICE_COLUMN = "VBELN"
# --- Konfiguráció Vége ---

# --- ORACLE THICK MÓD INICIALIZÁLÁSA (KÖTELEZŐ A TITKOSÍTÁSHOZ) ---
try:
    # Ez a sor kényszeríti a Thick módot, ami támogatja a Bosch hálózati titkosítást (DPY-3001 hiba ellen)
    oracledb.init_oracle_client()
    print("✅ Oracle Client sikeresen inicializálva (Thick mód aktív).")
except Exception as e:
    print(f"❌ HIBA: Nem sikerült inicializálni az Oracle Client-et: {e}")

def get_dali_connection():
    """Megnyitja a kapcsolatot a Redlake DALI adatbázishoz (Thick módban)."""
    try:
        connection = oracledb.connect(
            user=DALI_USER,
            password=DALI_PASSWORD,
            dsn=DALI_TNS_NAME
        )
        return connection
    except Exception as e:
        print(f"⚠️ Nem sikerült kapcsolódni a DALI adatbázishoz: {e}")
        return None

def fetch_invoices_from_dali(shipment_numbers: list) -> dict:
    """
    Élő Oracle adatbázisból kéri le a számlaszámokat a talált Shipment számokhoz.
    Kimenet: {'shipment_szam': ['invoice1', 'invoice2'], ...}
    """
    if not shipment_numbers:
        return {}

    # Shipment számok megtisztítása
    clean_shipments = [str(s).strip() for s in shipment_numbers if str(s).strip()]
    if not clean_shipments:
        return {}

    conn = get_dali_connection()
    if not conn:
        print("⚠️ DALI kapcsolat sikertelen, nem sikerült lekérdezni a számlákat.")
        return {}

    # Paraméterezett lekérdezés felépítése
    placeholders = ",".join([f":{i+1}" for i in range(len(clean_shipments))])
    sql_query = f"SELECT {SHIPMENT_COLUMN}, {INVOICE_COLUMN} FROM {TABLE_NAME} WHERE {SHIPMENT_COLUMN} IN ({placeholders})"
    
    result_map = {}
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql_query, clean_shipments)
            rows = cursor.fetchall()

            for tknum, vbeln in rows:
                shipment_str = str(tknum).strip()
                invoice_str = str(vbeln).strip()

                if shipment_str not in result_map:
                    result_map[shipment_str] = []
                if invoice_str not in result_map[shipment_str]:
                    result_map[shipment_str].append(invoice_str)
        
        return result_map
    except Exception as e:
        print(f"⚠️ Hiba az SQL lekérdezés futtatásakor: {e}")
        return {}
    finally:
        if conn:
            conn.close()
