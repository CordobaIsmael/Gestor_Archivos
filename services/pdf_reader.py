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
        """Normalizes common OCR misread sucursales (e.g. 8B, 88 -> BB)."""
        s = sucursal_raw.upper().strip()
        # Common OCR fixes for BB
        if s in ["8B", "88", "B8", "B6", "86", "6B", "66", "B0", "0B"]:
            return "BB"
        # Common OCR fixes for NQ (Neuquen)
        if s in ["NQN", "NQ1", "NQ0", "N9", "N0"]:
            return "NQ"
        # Common OCR fixes for MP (Mar del Plata)
        if s in ["MDP", "MP1", "MP0"]:
            return "MP"
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
        
        # 1. Check for Empresa
        if "INTERPROVINCIAL" in text.upper():
            metadata["empresa"] = "INTERPROVINCIAL"
        elif "OTAPEYA" in text.upper():
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
            
            # Combine all text blocks from the first page
            page = doc[0]
            blocks = page.get_text("blocks")
            full_text = "\n".join([b[4] for b in blocks])
            doc.close()
            
            # Parse metadata from native text
            metadata = cls._parse_text_metadata(full_text)
            
            # If native text extraction failed to find the Empresa, try Tesseract OCR fallback!
            if not metadata["empresa"]:
                tess_exe = cls.find_tesseract()
                if tess_exe:
                    print(f"Native text extraction failed for {pdf_path.name}. Falling back to Tesseract OCR...")
                    ocr_text = cls.ocr_pdf_page(pdf_path, 0, tess_exe)
                    if ocr_text:
                        metadata = cls._parse_text_metadata(ocr_text)
                        if metadata["empresa"]:
                            print(f"Successfully extracted metadata via Tesseract OCR for {pdf_path.name}: {metadata}")
            
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
            
        return metadata

    @classmethod
    def extract_expected_guias(cls, pdf_path: Path) -> list:
        """Extracts expected guias (format A.34.123456 or X. 2.4623) from the Hoja de Reparto."""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            
            # Try matching expected guias in native text
            pattern = r'[A-Z]\s*\.\s*\d+\s*\.\s*\d+'
            matches = re.findall(pattern, text)
            
            # If no matches in native text, try Tesseract OCR fallback on page 0
            if not matches:
                tess_exe = cls.find_tesseract()
                if tess_exe:
                    print(f"No expected guias found in native text of {pdf_path.name}. Trying Tesseract OCR...")
                    ocr_text = cls.ocr_pdf_page(pdf_path, 0, tess_exe)
                    if ocr_text:
                        matches = re.findall(pattern, ocr_text)
            
            # Normalize by removing all spaces
            normalized_matches = [re.sub(r'\s+', '', m) for m in matches]
            return sorted(list(set(normalized_matches)))
        except Exception as e:
            print(f"Error extracting expected guias: {e}")
            return []

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
