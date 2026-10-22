from pathlib import Path
import cv2
import numpy as np
from paddleocr import PaddleOCR
import pymupdf

from config.settings import PDF_RENDER_DPI
from core.ocr_engine import extract_lines_from_ocr_result


def extract_text_from_pdf(pdf_path: Path, ocr_engine: PaddleOCR) -> str:
  """Kinyeri a szöveget a PDF-ből (digitálisan vagy PaddleOCR segítségével)."""
  try:
    doc = pymupdf.open(str(pdf_path))

    # 1. Próbálkozás a digitális szöveggel
    digital_text = ""
    for page in doc:
      digital_text += (
          page.get_text(flags=pymupdf.TEXT_PRESERVE_WHITESPACE) + "\n"
      )

    if len(digital_text.strip()) >= 200:
      print(
          f"  [Info] Digitális szöveg kinyerve ({len(digital_text.strip())}"
          " karakter)."
      )
      # --- DEBUG KIÍRATÁS DIGITÁLIS ESETÉN ---
      print("\n" + "=" * 25 + " [NYERS DIGITÁLIS SZÖVEG] " + "=" * 25)
      print(digital_text)
      print("=" * 70 + "\n")
      return digital_text

    # 2. Ha szkennelt: az 1. oldal renderelése és OCR futtatása
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
    final_text = "\n".join(lines)

    # --- DEBUG KIÍRATÁS PADDLEOCR ESETÉN ---
    print("\n" + "=" * 25 + " [NYERS PADDLEOCR SZÖVEG] " + "=" * 25)
    print(final_text)
    print("=" * 70 + "\n")

    return final_text

  except Exception as e:
    print(f"  [Hiba] PDF feldolgozási hiba ({pdf_path.name}): {e}")
    return ""