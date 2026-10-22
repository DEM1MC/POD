from pathlib import Path
import cv2
import numpy as np
from paddleocr import PaddleOCR
import pymupdf

from config.settings import PDF_RENDER_DPI
from core.ocr_engine import extract_lines_from_ocr_result


def extract_text_from_file(file_path: Path, ocr_engine: PaddleOCR) -> str:
  """Kinyeri a szöveget PDF vagy Képfájlból (.png, .jpg, .jpeg) PaddleOCR segítségével."""
  suffix = file_path.suffix.lower()

  try:
    # ---------------------------------------------------------
    # 1. KÉPFÁJLOK KEZELÉSE (.png, .jpg, .jpeg)
    # ---------------------------------------------------------
    if suffix in [".png", ".jpg", ".jpeg"]:
      # OpenCV beolvasás ékezetes és speciális Windows útvonalak kezelésével:
      with open(str(file_path), "rb") as f:
        file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

      if img is None:
        print(f"  [Hiba] A képfájlt nem sikerült dekódolni: {file_path.name}")
        return ""

      try:
        results = ocr_engine.ocr(img)
      except Exception:
        results = ocr_engine.predict(img)

      lines = extract_lines_from_ocr_result(results)
      return "\n".join(lines)

    # ---------------------------------------------------------
    # 2. PDF DOKUMENTUMOK KEZELÉSE (.pdf)
    # ---------------------------------------------------------
    elif suffix == ".pdf":
      doc = pymupdf.open(str(file_path))

      # A) Digitális szövegréteg ellenőrzése
      digital_text = ""
      for page in doc:
        digital_text += (
            page.get_text(flags=pymupdf.TEXT_PRESERVE_WHITESPACE) + "\n"
        )

      if len(digital_text.strip()) >= 200:
        return digital_text

      # B) Szkennelt PDF: 1. oldal renderelése képpé és OCR
      if len(doc) == 0:
        return ""

      page = doc[0]
      pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
      img_np = np.frombuffer(pix.tobytes("png"), dtype=np.uint8)
      img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

      if img is None:
        return ""

      try:
        results = ocr_engine.ocr(img)
      except Exception:
        results = ocr_engine.predict(img)

      lines = extract_lines_from_ocr_result(results)
      return "\n".join(lines)

    else:
      print(f"  [Figyelem] Nem támogatott fájlformátum: {file_path.name}")
      return ""

  except Exception as e:
    print(f"  [Hiba] Fájl feldolgozási hiba ({file_path.name}): {e}")
    return ""