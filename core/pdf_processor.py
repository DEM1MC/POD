from pathlib import Path
import cv2
import numpy as np
from paddleocr import PaddleOCR
import pymupdf
from config.settings import PDF_RENDER_DPI


def extract_text_from_file(file_path: Path, ocr_engine: PaddleOCR) -> str:
  """Kinyeri a nyers szöveget PDF vagy képfájlból egyszerűen és stabilan."""
  suffix = file_path.suffix.lower()

  try:
    img = None
    # 1. Képfájlok kezelése
    if suffix in [".png", ".jpg", ".jpeg"]:
      with open(str(file_path), "rb") as f:
        img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)

    # 2. PDF fájlok kezelése
    elif suffix == ".pdf":
      doc = pymupdf.open(str(file_path))
      if len(doc) == 0:
        return ""
      page = doc[0]
      pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
      img = cv2.imdecode(
          np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR
      )

    if img is None:
      return ""

    # Futtatjuk az OCR-t
    ocr_results = ocr_engine.ocr(img)
    if not ocr_results:
      return ""

    # Szövegek kinyerése bármilyen formátumból (szótár vagy lista)
    lines = []
    # Ha szótáras formátum (új PaddleX / PaddleOCR)
    if (
        isinstance(ocr_results, list)
        and ocr_results
        and isinstance(ocr_results[0], dict)
    ):
      lines = ocr_results[0].get("rec_texts", [])
    # Ha beágyazott lista
    elif (
        isinstance(ocr_results, list)
        and ocr_results
        and isinstance(ocr_results[0], list)
    ):
      for item in ocr_results[0]:
        if (
            isinstance(item, (list, tuple))
            and len(item) > 1
            and isinstance(item[1], (list, tuple))
        ):
          lines.append(str(item[1][0]))
        elif isinstance(item, dict) and "rec_texts" in item:
          lines.extend(item["rec_texts"])

    return "\n".join(str(l).strip() for l in lines if str(l).strip())

  except Exception as e:
    print(f"  [Hiba] Fájl feldolgozási hiba ({file_path.name}): {e}")
    return ""
