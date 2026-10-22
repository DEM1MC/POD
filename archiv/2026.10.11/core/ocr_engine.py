import cv2
import numpy as np
import paddle
from paddleocr import PaddleOCR


def get_ocr_engine() -> PaddleOCR:
  """Létrehozza a stabil és gyorsított PaddleOCR motort."""
  paddle.set_flags({
      "FLAGS_use_onednn": False,
      "FLAGS_use_mkldnn": False,
      "FLAGS_enable_pir_api": False,
      "FLAGS_enable_pir_in_executor": False,
  })

  return PaddleOCR(
      lang="en",
      enable_mkldnn=False,
      use_doc_orientation_classify=False,
      use_doc_unwarping=False,
      use_textline_orientation=False,
      text_det_limit_side_len=960,
      text_recognition_batch_size=8,
  )


# Biztosítjuk a kompatibilitást mindkét névre:
initialize_ocr = get_ocr_engine


def extract_lines_from_ocr_result(results) -> list[str]:
  """Univerzális kicsomagoló: bármilyen PaddleOCR formátumból kinyeri a szöveget."""
  ocr_lines = []
  if not results:
    return ocr_lines

  if isinstance(results, list):
    for item in results:
      if isinstance(item, list):
        for sub in item:
          if (
              isinstance(sub, (list, tuple))
              and len(sub) >= 2
              and isinstance(sub[1], (tuple, list))
          ):
            ocr_lines.append(str(sub[1][0]))
          elif isinstance(sub, (list, tuple)) and len(sub) >= 1:
            ocr_lines.append(str(sub[0]))
          elif isinstance(sub, str):
            ocr_lines.append(sub)
      elif isinstance(item, dict):
        if "rec_texts" in item and isinstance(item["rec_texts"], list):
          ocr_lines.extend(item["rec_texts"])
        elif "text" in item:
          ocr_lines.append(item["text"])
      elif hasattr(item, "text"):
        ocr_lines.append(item.text)

  return ocr_lines
