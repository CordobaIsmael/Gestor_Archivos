from pathlib import Path
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Dict, Any
import os

from config.settings import settings
from models.database import Reparto, Caja
from services.pdf_reader import PDFReader
from services.file_manager import move_directory, get_organized_path

def find_pdf_folders(root_path: Path) -> List[Path]:
    """
    Recursively walks the directory tree starting at root_path
    and returns a list of all directories that contain at least one PDF file directly.
    The list is sorted by depth (deepest directories first) to ensure
    subfolders are processed and moved before their parent directories.
    """
    pdf_folders = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        has_pdf = any(f.lower().endswith('.pdf') for f in filenames)
        if has_pdf:
            pdf_folders.append(Path(dirpath))
            
    # Sort by depth descending (longer paths first)
    pdf_folders.sort(key=lambda p: len(p.parts), reverse=True)
    return pdf_folders

def clean_empty_directories(root_path: Path):
    """
    Recursively removes empty directories under root_path.
    """
    for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
        p = Path(dirpath)
        if p != root_path and p.exists() and p.is_dir():
            try:
                # Check if directory has no files or folders
                if not any(p.iterdir()):
                    p.rmdir()
                    print(f"Removed empty directory: {p}")
            except Exception as e:
                print(f"Error removing empty directory {p}: {e}")

def process_incoming_folders(db: Session, custom_path: Path = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scans the specified folder (or settings.ENTRADA) recursively for folders containing PDFs,
    processes each one, organizes them, and records metadata in the database.
    """
    entrada_path = custom_path if custom_path is not None else Path(settings.ENTRADA)
    results = {
        "organizados": [],
        "revision": []
    }
    
    if not entrada_path.exists():
        print(f"Path does not exist: {entrada_path}")
        return results
        
    # Get active box
    active_caja = db.query(Caja).filter(Caja.estado == "ACTIVA").first()
    if not active_caja:
        raise ValueError("No hay una caja activa abierta. Debes abrir una caja antes de procesar entrada.")
    caja_id = active_caja.id
        
    # Find all folders containing PDF files directly, sorted by depth (deepest first)
    pdf_folders = find_pdf_folders(entrada_path)
    
    for folder in pdf_folders:
        print(f"Processing folder: {folder.name} (Path: {folder})")
        pdf_files = list(folder.glob("*.pdf"))  # scan only direct PDFs inside this folder
        
        metadata_found = None
        
        # Look for the Hoja de Reparto among the PDFs in the folder
        for pdf_path in pdf_files:
            metadata = PDFReader.extract_metadata(pdf_path)
            if metadata.get("is_hoja_reparto"):
                # Check if all critical fields are found
                if metadata.get("empresa") and metadata.get("fecha") and metadata.get("sucursal") and metadata.get("nro_reparto"):
                    metadata_found = metadata
                    break # Found the valid Hoja de Reparto
                else:
                    # Keep track of partially found metadata in case no perfect match is found
                    if not metadata_found:
                        metadata_found = metadata

        original_path_str = str(folder.resolve())

        # If a complete Hoja de Reparto was found with all metadata
        if (metadata_found and 
            metadata_found["empresa"] and 
            metadata_found["fecha"] and 
            metadata_found["sucursal"] and 
            metadata_found["nro_reparto"]):
            
            empresa = metadata_found["empresa"]
            sucursal = metadata_found["sucursal"]
            nro_reparto = metadata_found["nro_reparto"]
            
            dest_path = get_organized_path(
                base_salida=Path(settings.SALIDA),
                empresa=empresa,
                fecha=metadata_found["fecha"],
                sucursal=sucursal,
                nro_reparto=nro_reparto
            )
            
            try:
                final_dest = move_directory(folder, dest_path)
                
                # Add DB record
                reparto_db = Reparto(
                    empresa=empresa,
                    sucursal=sucursal,
                    nro_reparto=nro_reparto,
                    fecha=metadata_found["fecha"],
                    ruta_original=original_path_str,
                    ruta_nueva=str(final_dest.resolve()),
                    estado="ORGANIZADO",
                    caja_id=caja_id
                )
                db.add(reparto_db)
                db.commit()
                db.refresh(reparto_db)
                
                results["organizados"].append(reparto_db.to_dict())
                print(f"Successfully organized: {folder.name} -> {final_dest}")
                
            except Exception as e:
                # If moving failed, send to revision
                print(f"Error moving organized folder {folder.name}: {e}")
                send_to_revision(folder, db, results, metadata_found, original_path_str)
                
        else:
            # Metadata missing or no Hoja de Reparto found -> Move to REVISION
            send_to_revision(folder, db, results, metadata_found, original_path_str)
            
    # Clean up empty directories under the scanned path
    clean_empty_directories(entrada_path)
    
    return results

def send_to_revision(folder_path: Path, db: Session, results: dict, metadata_found: dict, original_path_str: str):
    """Helper to move a folder to REVISION and log it in the database."""
    dest_path = Path(settings.REVISION) / folder_path.name
    try:
        final_dest = move_directory(folder_path, dest_path)
        
        # Determine values to save (use partial metadata if available)
        empresa = "DESCONOCIDA"
        fecha = None
        sucursal = None
        nro_reparto = None
        
        if metadata_found:
            empresa = metadata_found.get("empresa") or "DESCONOCIDA"
            fecha = metadata_found.get("fecha")
            sucursal = metadata_found.get("sucursal")
            nro_reparto = metadata_found.get("nro_reparto")
            
        # Get active box if any
        active_caja = db.query(Caja).filter(Caja.estado == "ACTIVA").first()
        caja_id = active_caja.id if active_caja else None

        reparto_db = Reparto(
            empresa=empresa,
            sucursal=sucursal,
            nro_reparto=nro_reparto,
            fecha=fecha,
            ruta_original=original_path_str,
            ruta_nueva=str(final_dest.resolve()),
            estado="EN_REVISION",
            caja_id=caja_id
        )
        db.add(reparto_db)
        db.commit()
        db.refresh(reparto_db)
        
        results["revision"].append(reparto_db.to_dict())
        print(f"Folder sent to REVISION: {folder_path.name} -> {final_dest}")
    except Exception as e:
        print(f"Error moving folder {folder_path.name} to REVISION: {e}")
        db.rollback()

def resolve_revision_folder(
    reparto_id: int, 
    empresa: str, 
    fecha_obj: date, 
    sucursal: str, 
    nro_reparto: str, 
    db: Session
) -> Dict[str, Any]:
    """
    Manually resolves a folder that was in REVISION.
    Moves the folder to the organized structure and updates the DB record.
    """
    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise ValueError(f"Reparto with ID {reparto_id} not found.")
        
    if reparto.estado != "EN_REVISION":
        raise ValueError(f"Reparto with ID {reparto_id} is not in REVISION status.")
        
    src_path = Path(reparto.ruta_nueva)
    if not src_path.exists():
        raise FileNotFoundError(f"Source folder in Revision does not exist: {src_path}")
        
    dest_path = get_organized_path(
        base_salida=Path(settings.SALIDA),
        empresa=empresa,
        fecha=fecha_obj,
        sucursal=sucursal,
        nro_reparto=nro_reparto
    )
    
    # Move folder from Revision to Salida
    final_dest = move_directory(src_path, dest_path)
    
    # Update DB record
    reparto.empresa = empresa
    reparto.fecha = fecha_obj
    reparto.sucursal = sucursal
    reparto.nro_reparto = nro_reparto
    reparto.ruta_nueva = str(final_dest.resolve())
    reparto.estado = "ORGANIZADO"
    
    # If no box is assigned, assign the currently active one
    if not reparto.caja_id:
        active_caja = db.query(Caja).filter(Caja.estado == "ACTIVA").first()
        if not active_caja:
            raise ValueError("No hay una caja activa abierta. Debes abrir una caja antes de organizar el reparto.")
        reparto.caja_id = active_caja.id
    
    db.commit()
    db.refresh(reparto)
    
    print(f"Manually resolved Reparto #{reparto_id}: moved to {final_dest}")
    return reparto.to_dict()
