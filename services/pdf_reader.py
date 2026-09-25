import fitz  # PyMuPDF
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess
import shutil

class PDFReader:
    @staticmethod
    def normalize_sucursal(sucursal_raw: str) -> str:
        """Normalizes common OCR misread sucursales."""
        s = sucursal_raw.upper().strip()
        # Common OCR fixes for BB (Bahia Blanca)
        if s in ["8B", "88", "B8", "B6", "86", "6B", "66", "B0", "0B"]:
            return "BB"
        # Common OCR fixes for NQ (Neuquen)
        if s in ["NQN", "NQ1", "NQ0", "N9", "N0"]:
            return "NQ"
        # Common OCR fixes for MP (Mar del Plata)
        if s in ["MDP", "MP1", "MP0"]:
            return "MP"
        # Fixes for VR (Villa Regina)
        if s in ["RE", "REG", "VR1", "VR0", "V0"]:
            return "VR"
        # Fixes for CO (Cordoba)
        if s in ["COR", "CBA", "C0"]:
            return "CO"
        # Fixes for OL (Olavarria)
        if s in ["OLA", "0L"]:
            return "OL"
        # Fixes for TA (Tres Arroyos)
        if s in ["AR", "TAR"]:
            return "TA"
        # Fixes for RC (Rio Colorado)
        if s in ["RC1", "RC0", "R0"]:
            return "RC"
        # Fixes for CH (Choele Choel)
        if s in ["CH1", "CH0"]:
            return "CH"
        return s

    @classmethod
    def find_tesseract(cls) -> Optional[str]:
        """Finds the path to the Tesseract OCR executable on Windows."""
        paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for p in paths:
            if Path(p).exists():
                return p
        tess_path = shutil.which("tesseract")
        if tess_path:
            return tess_path
        return None

    @classmethod
    def ocr_pdf_page(cls, pdf_path: Path, page_num: int, tess_exe: str) -> str:
        """Performs Tesseract OCR on a specific PDF page and returns the text."""
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                doc.close()
                return ""
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150)
            
            # Save temp image in same directory
            temp_img_path = pdf_path.parent / f"temp_ocr_{pdf_path.stem}.png"
            pix.save(str(temp_img_path))
            doc.close()
            
            # Run Tesseract with Spanish and English packs
            cmd = [tess_exe, str(temp_img_path), "stdout", "-l", "spa+eng"]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            
            # Fallback if spa+eng fails
            if res.returncode != 0:
                cmd = [tess_exe, str(temp_img_path), "stdout"]
                res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
                
            # Clean up image
            if temp_img_path.exists():
                temp_img_path.unlink()
                
            if res.returncode == 0:
                return res.stdout
            else:
                print(f"Tesseract returned error code {res.returncode}: {res.stderr}")
                return ""
        except Exception as e:
            print(f"Error executing OCR fallback on {pdf_path.name}: {e}")
            return ""

    @classmethod
    def _parse_text_metadata(cls, text: str) -> Dict[str, Any]:
        """Helper to parse Empresa, Fecha, Sucursal and Nro Reparto from text string."""
        metadata = {
            "empresa": None,
            "fecha": None,
            "sucursal": None,
            "nro_reparto": None,
            "is_hoja_reparto": False
        }
        
        text_upper = text.upper()
        
        # 0. Anti-Factura / Anti-Guía Check:
        # If the document is an Invoice, Receipt or Guide, it is NEVER a Hoja de Reparto!
        is_invoice = (
            "FACTURA" in text_upper or 
            "CAE N" in text_upper or 
            "CAE Nº" in text_upper or 
            "FACTURA ELECTRONICA" in text_upper or 
            "TIPO DE IVA" in text_upper or 
            "CONDICIONES AL DORSO" in text_upper or
            "SEGUIMIENTO WEB" in text_upper or
            "DOCS. ASOCIADOS" in text_upper
        )
        if is_invoice:
            metadata["is_hoja_reparto"] = False
            return metadata
            
        # Must have positive indicators of Hoja de Reparto
        has_reparto_keywords = (
            "REPARTO" in text_upper or 
            "MERCADERIA A ENTREGAR" in text_upper or 
            "MERCADERÍA A ENTREGAR" in text_upper or
            "HOJA DE REPARTO" in text_upper
        )
        if not has_reparto_keywords:
            metadata["is_hoja_reparto"] = False
            return metadata

        # 1. Check for Empresa
        if "INTERPROVINCIAL" in text_upper:
            metadata["empresa"] = "INTERPROVINCIAL"
        elif "OTAPEYA" in text_upper:
            metadata["empresa"] = "OTAPEYA"
            
        if not metadata["empresa"]:
            return metadata
            
        # 2. Check for Reparto, Sucursal & Nro Reparto
        reparto_pattern = re.compile(r"Reparto\s+(\S+)\s+(\d+)", re.IGNORECASE)
        match = reparto_pattern.search(text)
        if match:
            raw_sucursal = match.group(1)
            metadata["sucursal"] = cls.normalize_sucursal(raw_sucursal)
            metadata["nro_reparto"] = match.group(2)
            metadata["is_hoja_reparto"] = True
        else:
            # Fallback: Look for standalone Sucursal code + Reparto number in text
            sucursal_candidates = [
                "MP", "MDP", "TA", "AR", "CO", "COR", "CBA", "OL", "OLA",
                "VR", "RE", "REG", "RC", "CH", "BB", "NQ", "NQN", "CF", 
                "RO", "ROS", "AZ"
            ]
            suc_regex = r"\b(" + "|".join(sucursal_candidates) + r")\s+(\d{4,8})\b"
            match_fallback = re.search(suc_regex, text, re.IGNORECASE)
            if match_fallback:
                raw_sucursal = match_fallback.group(1)
                metadata["sucursal"] = cls.normalize_sucursal(raw_sucursal)
                metadata["nro_reparto"] = match_fallback.group(2)
                metadata["is_hoja_reparto"] = True
            
        # 3. Check for Date
        date_pattern = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
        lines = text.split("\n")
        reparto_date_str = None
        for line in lines:
            if "emisi" in line.lower():
                continue
            match_date = date_pattern.search(line)
            if match_date:
                reparto_date_str = match_date.group(1)
                break
                
        if reparto_date_str:
            try:
                metadata["fecha"] = datetime.strptime(reparto_date_str, "%d/%m/%Y").date()
            except ValueError:
                pass
                
        return metadata

    @classmethod
    def extract_metadata(cls, pdf_path: Path) -> Dict[str, Any]:
        """
        Extracts metadata (Empresa, Fecha, Sucursal, Nro Reparto) from a PDF file.
        Returns a dictionary with the extracted fields.
        """
        metadata = {
            "empresa": None,
            "fecha": None,
            "sucursal": None,
            "nro_reparto": None,
            "is_hoja_reparto": False
        }

        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return metadata
            
            # Combine all text blocks from the first page in visual reading order
            page = doc[0]
            blocks = page.get_text("blocks", sort=True)
            full_text = "\n".join([b[4] for b in blocks])
            doc.close()
            
            # Parse metadata from native text
            metadata = cls._parse_text_metadata(full_text)
            
            # If any critical field is missing, trigger Tesseract OCR fallback!
            has_complete_metadata = (
                metadata["empresa"] and 
                metadata["sucursal"] and 
                metadata["nro_reparto"] and 
                metadata["fecha"]
            )
            
            if not has_complete_metadata:
                tess_exe = cls.find_tesseract()
                if tess_exe:
                    print(f"Missing critical metadata for {pdf_path.name}. Falling back to Tesseract OCR...")
                    ocr_text = cls.ocr_pdf_page(pdf_path, 0, tess_exe)
                    if ocr_text:
                        ocr_metadata = cls._parse_text_metadata(ocr_text)
                        for k, v in ocr_metadata.items():
                            if v is not None and metadata.get(k) is None:
                                metadata[k] = v
                        if metadata["empresa"] and metadata["sucursal"] and metadata["nro_reparto"]:
                            metadata["is_hoja_reparto"] = True
                            print(f"Successfully completed metadata via Tesseract OCR for {pdf_path.name}: {metadata}")
            
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
            
        return metadata

    @classmethod
    def extract_expected_guias_and_exclusions(cls, pdf_path: Path) -> Dict[str, list]:
        """
        Extracts all expected guias from the Hoja de Reparto.
        Automatically detects whether the sheet is OLD FORMAT (Orig./Dest. CO CC columns with printed X's)
        or NEW FORMAT (explicit 'NO' checkbox column).
        Only inspects the 'NO' checkbox column for exclusions if NEW FORMAT is detected.
        """
        result = {
            "todas_guias": [],
            "guias_a_controlar": [],
            "guias_no_entregadas": []
        }
        try:
            from PIL import Image
            import io
            
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                doc.close()
                return result
                
            page = doc[0]
            w, h = page.rect.width, page.rect.height
            words = page.get_text("words")
            
            # 1. Detect Format: Old Format vs New Format
            is_new_format = False
            no_x_pos = None
            
            for w_item in words:
                txt = w_item[4].strip().upper()
                if txt == "NO" and 60 < w_item[1] < 180:
                    no_x_pos = (w_item[0] + w_item[2]) / 2.0
                    is_new_format = True
                    break
                    
            # 2. Extract guide occurrences with their y-coordinates
            pattern = re.compile(r'([A-Z]\s*\.\s*\d+\s*\.\s*\d+)')
            guide_rows = []
            
            # Check text blocks
            blocks = page.get_text("blocks")
            for b in blocks:
                for m in pattern.finditer(b[4]):
                    code = re.sub(r'\s+', '', m.group(1))
                    guide_rows.append({
                        "code": code,
                        "y_center": (b[1] + b[3]) / 2.0
                    })
                    
            # Check adjacent words
            for i in range(len(words) - 1):
                w1 = words[i]
                w2 = words[i+1]
                m = pattern.search(f"{w1[4]}{w2[4]}")
                if m:
                    code = re.sub(r'\s+', '', m.group(1))
                    if not any(gr["code"] == code for gr in guide_rows):
                        guide_rows.append({
                            "code": code,
                            "y_center": (w1[1] + w1[3]) / 2.0
                        })
                        
            # If no matches in native text, fallback to OCR
            if not guide_rows:
                full_text = ""
                for p in doc:
                    full_text += p.get_text()
                matches = pattern.findall(full_text)
                if not matches:
                    tess_exe = cls.find_tesseract()
                    if tess_exe:
                        ocr_text = cls.ocr_pdf_page(pdf_path, 0, tess_exe)
                        matches = pattern.findall(ocr_text)
                norm_matches = sorted(list(set([re.sub(r'\s+', '', m) for m in matches])))
                doc.close()
                result["todas_guias"] = norm_matches
                result["guias_a_controlar"] = norm_matches
                return result

            todas = []
            a_controlar = []
            no_entregadas = []
            
            for gr in guide_rows:
                code = gr["code"]
                todas.append(code)
                yc = gr["y_center"]
                
                # Only check checkbox if it's the NEW FORMAT with the official 'NO' column
                if is_new_format and no_x_pos is not None:
                    # Checkbox ROI centered on no_x_pos
                    box_roi = fitz.Rect(no_x_pos - 15, yc - 10, no_x_pos + 15, yc + 10)
                    pix = page.get_pixmap(clip=box_roi, dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
                    w_img, h_img = img.size
                    
                    # Locate the bounding box of the square [ ] in the central area
                    min_x, max_x = w_img, 0
                    min_y, max_y = h_img, 0
                    y_start, y_end = int(h_img * 0.1), int(h_img * 0.85)
                    x_start, x_end = int(w_img * 0.15), int(w_img * 0.85)
                    
                    for y_p in range(y_start, y_end):
                        for x_p in range(x_start, x_end):
                            if img.getpixel((x_p, y_p)) < 160:
                                if x_p < min_x: min_x = x_p
                                if x_p > max_x: max_x = x_p
                                if y_p < min_y: min_y = y_p
                                if y_p > max_y: max_y = y_p
                                
                    box_w = max_x - min_x
                    box_h = max_y - min_y
                    
                    is_marked = False
                    if 10 <= box_w <= 45 and 10 <= box_h <= 45:
                        # Sample strictly inside the box interior, eroding 3px from borders
                        inner_x1 = min_x + 3
                        inner_x2 = max_x - 3
                        inner_y1 = min_y + 3
                        inner_y2 = max_y - 3
                        
                        if inner_x2 > inner_x1 and inner_y2 > inner_y1:
                            inner_pixels = [img.getpixel((xp, yp)) for yp in range(inner_y1, inner_y2 + 1) for xp in range(inner_x1, inner_x2 + 1)]
                            total_inner = len(inner_pixels)
                            dark_inner = sum(1 for p in inner_pixels if p < 160)
                            fill_pct = (dark_inner / total_inner) * 100 if total_inner > 0 else 0
                            if fill_pct >= 10.0:
                                is_marked = True
                                
                    if is_marked:
                        no_entregadas.append(code)
                        continue
                        
                a_controlar.append(code)
                
            doc.close()
            result["todas_guias"] = todas
            result["guias_a_controlar"] = a_controlar
            result["guias_no_entregadas"] = no_entregadas
            return result
        except Exception as e:
            print(f"Error extracting expected guias with exclusions from {pdf_path.name}: {e}")
            return result

    @classmethod
    def extract_expected_guias(cls, pdf_path: Path) -> list:
        """Extracts guias from Hoja de Reparto that must be controlled (ignoring those marked in 'NO' column)."""
        res = cls.extract_expected_guias_and_exclusions(pdf_path)
        return res.get("guias_a_controlar", [])

    @classmethod
    def check_pdf_contains_serial(cls, pdf_path: Path, serial: str) -> bool:
        """Checks if a PDF contains the given serial number string."""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text().upper()
            doc.close()
            
            # Normalize serial: strip leading zeros
            serial_norm = str(int(serial)) if serial.isdigit() else serial
            
            # Check native text
            if serial in text or serial_norm in text:
                return True
                
            # If not found, try Tesseract OCR fallback on page 0 as backup
            tess_exe = cls.find_tesseract()
            if tess_exe:
                ocr_text = cls.ocr_pdf_page(pdf_path, 0, tess_exe).upper()
                if serial in ocr_text or serial_norm in ocr_text:
                    print(f"Guide serial {serial} found via Tesseract OCR in {pdf_path.name}")
                    return True
                    
            return False
        except Exception:
            return False

    @classmethod
    def check_guia_signature(cls, pdf_path: Path) -> Dict[str, Any]:
        """
        Analyzes a delivery note / Guía PDF to verify whether it contains a client signature / conforme.
        Returns a dict: {"has_signature": bool, "confidence": float, "details": str}
        """
        result = {
            "has_signature": False,
            "confidence": 0.0,
            "details": "No signature detected"
        }
        try:
            from PIL import Image
            import io
            import numpy as np
            
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                doc.close()
                return result
                
            page = doc[0]
            w, h = page.rect.width, page.rect.height
            
            # Find signature-related text blocks in the lower 45% of page
            blocks = page.get_text("blocks")
            sig_blocks = [
                b for b in blocks 
                if b[1] > h * 0.55 and any(k in b[4].upper() for k in ["RECIB", "CONFORME", "FIRMA", "ACLARAC", "DOCUMENTO", "DNI", "FECHA"])
            ]
            
            if sig_blocks:
                min_x = min(b[0] for b in sig_blocks)
                min_y = min(b[1] for b in sig_blocks)
                max_x = max(b[2] for b in sig_blocks)
                max_y = max(b[3] for b in sig_blocks)
                # Define signature ROI around the found signature block
                roi = fitz.Rect(max(0, min_x - 5), max(0, min_y - 10), min(w, min_x + 240), min(h, max_y + 35))
            else:
                # Fallback to bottom-left 25% of the page
                roi = fitz.Rect(10, h * 0.70, min(w, 260), h * 0.98)
                
            pix = page.get_pixmap(clip=roi, dpi=150)
            doc.close()
            
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
            pixels = list(img.get_flattened_data())
            if not pixels:
                return result
                
            total_pixels = len(pixels)
            dark_pixels = sum(1 for p in pixels if p < 165)
            dark_ratio = (dark_pixels / total_pixels) * 100
            
            arr = np.array(pixels)
            std_dev = float(np.std(arr))
            
            # A blank template has a low dark ratio and low variance.
            # A signed document has pen strokes that increase dark pixel ratio and std_dev.
            # Typical signed guide has dark_ratio > 3.0% and std_dev > 25.0
            if dark_ratio >= 3.0 and std_dev >= 25.0:
                result["has_signature"] = True
                result["confidence"] = min(1.0, (dark_ratio / 6.0))
                result["details"] = f"Firma detectada (Densidad tinta: {dark_ratio:.1f}%, Varianza: {std_dev:.1f})"
            else:
                result["has_signature"] = False
                result["confidence"] = max(0.0, 1.0 - (dark_ratio / 3.0))
                result["details"] = f"Sin firma o recuadro en blanco (Densidad tinta: {dark_ratio:.1f}%, Varianza: {std_dev:.1f})"
                
            return result
        except Exception as e:
            print(f"Error analyzing signature on {pdf_path.name}: {e}")
            result["details"] = f"Error: {e}"
            return result
