import os
from pathlib import Path

# 1. Hardveres környezeti változók a stabilitásért és sebességért
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["CPU_NUM"] = "1"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

# 2. Elérési utak
BASE_DIR = Path(r"C:\Users\DEM1MC\OneDrive - Bosch Group\Documents\POD")
SOURCE_FOLDER = BASE_DIR / "Proba PoD automata"
TARGET_BASE_FOLDER = BASE_DIR / "Rendezett POD-k"
OUTPUT_EXCEL = TARGET_BASE_FOLDER / "master_pod_extraction_report.xlsx"
DALI_LOOKUP_TABLE = BASE_DIR / "podtabla.xlsx"
DB_PATH = BASE_DIR / "pod_database.db"

# =================================================================
# ORACLE ADATBÁZIS KAPCSOLAT (DALI)
# =================================================================
# A jelszót és felhasználónevet biztonsági okokból környezeti változókból olvassuk be.
# Ezeket a futtatás előtt be kell állítani a Windows-ban.
DALI_USER = "rs89mc"  # Ezt cseréld le a saját Oracle felhasználónevedre
DALI_PASSWORD = "QYMBQ171X_Pnck2"       # Ezt cseréld le a saját Oracle jelszavadra
DALI_DSN = "REDLake_ZeusP_Consumer_DALI.world"
# 3. Képfeldolgozási paraméterek
PDF_RENDER_DPI = 120

# 4. Ismert partnerek és telephelyek
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
            "orphee", "beinoglou", "elefsina", "athina", "athens", "ορφευσ", "0pφεyσ"
        ],
        "site": "Elefsina, GR",
    },
    "DSV Solutions": {"keywords": ["dsv"], "site": "Norrköping, SE"},
    "Dagendatrans Speed S.R.L.": {
        "keywords": ["dagenda"],
        "site": "Cezieni, Olt",
    },
}
