import os
import oracledb

# --- Konfiguráció ---
DALI_TNS_NAME = "Redlake_zeusp_consumer_dali.world"
DALI_USER = "dem1mc"  # A te felhasználód
DALI_PASSWORD = os.getenv("DALI_DB_PASSWORD", "Strongbowgold.123") # Cseréld le a jelszavadra!

TABLE_NAME = "MARD_DALI_PT.VBRP_P13"
SHIPMENT_COLUMN = "Y16V_TKNUM"
INVOICE_COLUMN = "VBELN"

# --- Oracle Thick Mód Inicializálása ---
try:
    oracledb.init_oracle_client()
    print("✅ Oracle Client sikeresen inicializálva (Thick mód aktív).")
except Exception as e:
    print(f"❌ HIBA: Nem sikerült inicializálni az Oracle Client-et. Telepítve van a gépedre? Hiba: {e}")
    # A program folytatódhat, de a DALI lekérdezés valószínűleg hibát fog dobni.

def fetch_invoices_from_dali(shipment_numbers: list) -> dict:
    """
    Élő Oracle adatbázisból kéri le a számlaszámokat a talált Shipment számokhoz.
    Visszatérési érték: {'shipment_szam': ['invoice1', 'invoice2'], ...}
    """
    if not shipment_numbers:
        return {}

    # Shipment számok megtisztítása
    clean_shipments = [str(s).strip() for s in shipment_numbers if str(s).strip()]
    if not clean_shipments:
        return {}

    print(f"🔗 Kapcsolódás a DALI adatbázishoz {len(clean_shipments)} db shipment szám lekérdezéséhez...")
    
    connection = None
    try:
        connection = oracledb.connect(user=DALI_USER, password=DALI_PASSWORD, dsn=DALI_TNS_NAME)
    except Exception as e:
        print(f"🔥 KRITIKUS HIBA: Nem sikerült csatlakozni a DALI adatbázishoz: {e}")
        return {}

    # Paraméterezett lekérdezés felépítése
    placeholders = ",".join([f":{i+1}" for i in range(len(clean_shipments))])
    sql_query = f"SELECT {SHIPMENT_COLUMN}, {INVOICE_COLUMN} FROM {TABLE_NAME} WHERE {SHIPMENT_COLUMN} IN ({placeholders})"
    
    result_map = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_query, clean_shipments)
            rows = cursor.fetchall()

            for tknum, vbeln in rows:
                shipment_str = str(tknum).strip()
                invoice_str = str(vbeln).strip()

                if shipment_str not in result_map:
                    result_map[shipment_str] = []
                if invoice_str not in result_map[shipment_str]:
                    result_map[shipment_str].append(invoice_str)
        
        print(f"   ✅ DALI lekérdezés sikeres, {len(rows)} egyezés található.")
        return result_map

    except Exception as e:
        print(f"   🔥 HIBA az SQL lekérdezés közben: {e}")
        return {}
    finally:
        if connection:
            connection.close()

