import fitz  # PyMuPDF
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

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
            
            # The "Hoja de Reparto" is always on the first page
            page = doc[0]
            blocks = page.get_text("blocks")
            
            # Check for Empresa (always top-left or present in the page)
            # We search all blocks for known company names
            for block in blocks:
                text = block[4].strip()
                if "INTERPROVINCIAL" in text.upper():
                    metadata["empresa"] = "INTERPROVINCIAL"
                    break
                elif "OTAPEYA" in text.upper():
                    metadata["empresa"] = "OTAPEYA"
                    break

            # If no company name is found, it might not be a Hoja de Reparto
            if not metadata["empresa"]:
                return metadata

            # Find Reparto block (contains "Reparto")
            # Example: "Reparto BB 138232" or "Reparto 8B 138232"
            reparto_pattern = re.compile(r"Reparto\s+(\S+)\s+(\d+)", re.IGNORECASE)
            
            for block in blocks:
                text = block[4].strip()
                match = reparto_pattern.search(text)
                if match:
                    raw_sucursal = match.group(1)
                    metadata["sucursal"] = cls.normalize_sucursal(raw_sucursal)
                    metadata["nro_reparto"] = match.group(2)
                    metadata["is_hoja_reparto"] = True
                    break

            # Find Date block (DD/MM/YYYY)
            # Exclude dates associated with "Emisión:" or "Emision:"
            date_pattern = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
            
            reparto_date_str = None
            for block in blocks:
                text = block[4].strip()
                # If the block contains "Emisión" or "Emision", it's the emission date, so skip it
                if "emisi" in text.lower():
                    continue
                
                match = date_pattern.search(text)
                if match:
                    reparto_date_str = match.group(1)
                    break
            
            if reparto_date_str:
                try:
                    # Parse to date object
                    metadata["fecha"] = datetime.strptime(reparto_date_str, "%d/%m/%Y").date()
                except ValueError:
                    pass

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
            # Regex match allowing spaces
            matches = re.findall(r'[A-Z]\s*\.\s*\d+\s*\.\s*\d+', text)
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
            # Normalize serial: strip leading zeros
            serial_norm = str(int(serial))
            for page in doc:
                text = page.get_text().upper()
                if serial in text or serial_norm in text:
                    doc.close()
                    return True
            doc.close()
            return False
        except Exception:
            return False
