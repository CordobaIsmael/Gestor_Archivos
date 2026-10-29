from pathlib import Path
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Dict, Any
import os

from config.settings import settings, validate_nro_reparto_digits, is_valid_sucursal_for_empresa, SUCURSALES_INTERPROVINCIAL, SUCURSALES_OTAPEYA
from models.database import Reparto, Usuario
from services.pdf_reader import PDFReader
from services.file_manager import move_directory, get_organized_path, get_mirror_path

def find_folders_with_pdfs(root_path: Path) -> List[Path]:
    """
    Recursively walks the directory tree starting at root_path
    and returns a list of all directories that contain at least one PDF file directly.
    The list is sorted by depth (deepest directories first) to ensure
    subfolders are processed and moved before their parent directories.
    """
    pdf_folders = []
    # Check if root_path itself is a directory and has PDFs directly
    if root_path.exists() and root_path.is_dir():
        # Check if root_path has PDFs directly in it
        if any(f.name.lower().endswith('.pdf') for f in root_path.iterdir() if f.is_file()):
            pdf_folders.append(root_path)
            
        # Walk subdirectories
        for dirpath, dirnames, filenames in os.walk(root_path):
            p = Path(dirpath)
            if p == root_path:
                continue
            has_pdf = any(f.lower().endswith('.pdf') for f in filenames)
            if has_pdf:
                pdf_folders.append(p)
                
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

def process_incoming_folders(
    db: Session, 
    custom_path: Path = None, 
    custom_salida: Path = None,
    modo_historico: bool = False,
    usuario_id: int = None,
    usuario_legajo: str = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scans the specified folder (or settings.ENTRADA) recursively for folders containing PDFs,
    processes each one, organizes them, and records metadata in the database.
    """
    entrada_path = custom_path if custom_path is not None else Path(settings.ENTRADA)
    salida_base = custom_salida if custom_salida is not None else Path(settings.SALIDA)
    results = {
        "organizados": [],
        "revision": []
    }
    
    if not entrada_path.exists():
        print(f"Path does not exist: {entrada_path}")
        return results
        
    # Find all folders containing PDF files directly, sorted by depth (deepest first)
    pdf_folders = find_folders_with_pdfs(entrada_path)
    
    for folder in pdf_folders:
        print(f"Processing folder: {folder.name} (Path: {folder})")
        pdf_files = list(folder.glob("*.pdf"))  # scan only direct PDFs inside this folder
        
        metadata_found = None
        hoja_pdf_path = None
        
        # Look for the Hoja de Reparto among the PDFs in the folder
        for pdf_path in pdf_files:
            metadata = PDFReader.extract_metadata(pdf_path)
            if metadata.get("is_hoja_reparto"):
                # Check if all critical fields are found
                if metadata.get("empresa") and metadata.get("fecha") and metadata.get("sucursal") and metadata.get("nro_reparto"):
                    metadata_found = metadata
                    hoja_pdf_path = pdf_path
                    break # Found the valid Hoja de Reparto
                else:
                    # Keep track of partially found metadata in case no perfect match is found
                    if not metadata_found:
                        metadata_found = metadata
                        hoja_pdf_path = pdf_path

        original_path_str = str(folder.resolve())

        # Check expected vs physical guias and signatures if a Hoja de Reparto was found
        guias_encontradas_str = None
        guias_faltantes_str = None
        guias_sin_firma_str = None
        guias_no_entregadas_str = None
        has_missing_guias = False
        has_unsigned_guias = False
        
        if hoja_pdf_path:
            guias_info = PDFReader.extract_expected_guias_and_exclusions(hoja_pdf_path)
            expected_guias = guias_info.get("guias_a_controlar", [])
            no_entregadas_list = guias_info.get("guias_no_entregadas", [])
            guias_no_entregadas_str = ",".join(no_entregadas_list) if no_entregadas_list else None
            
            other_pdfs = [p for p in pdf_files if p != hoja_pdf_path]
            
            encontradas_acc = []
            faltantes_acc = []
            sin_firma_acc = []
            
            for g in expected_guias:
                parts = g.split(".")
                if len(parts) >= 3:
                    serial = parts[2]
                    matched_pdf = None
                    for other_pdf in other_pdfs:
                        if PDFReader.check_pdf_contains_serial(other_pdf, serial):
                            matched_pdf = other_pdf
                            break
                    if matched_pdf:
                        encontradas_acc.append(g)
                        # Check signature on the matched guide PDF
                        sig_res = PDFReader.check_guia_signature(matched_pdf)
                        if not sig_res.get("has_signature", False):
                            sin_firma_acc.append(g)
                    else:
                        faltantes_acc.append(g)
                else:
                    faltantes_acc.append(g)
            
            guias_encontradas_str = ",".join(encontradas_acc) if encontradas_acc else None
            guias_faltantes_str = ",".join(faltantes_acc) if faltantes_acc else None
            guias_sin_firma_str = ",".join(sin_firma_acc) if sin_firma_acc else None
            
            has_missing_guias = len(faltantes_acc) > 0
            has_unsigned_guias = len(sin_firma_acc) > 0
            
            # In Historical Mode, we don't block organization for missing guias/signatures
            if modo_historico:
                has_missing_guias = False
                has_unsigned_guias = False

        # Check if this reparto was already organized previously (duplicate detection)
        is_duplicate = False
        duplicate_reason = None
        if metadata_found and metadata_found.get("sucursal") and metadata_found.get("nro_reparto"):
            suc_chk = metadata_found["sucursal"].upper().strip()
            num_chk = metadata_found["nro_reparto"].strip()
            existing_rep = db.query(Reparto).filter(
                Reparto.sucursal == suc_chk,
                Reparto.nro_reparto == num_chk,
                Reparto.estado == "ORGANIZADO"
            ).first()
            if existing_rep:
                is_duplicate = True
                op_info = existing_rep.usuario_legajo or "S/A"
                fecha_info = existing_rep.fecha.isoformat() if existing_rep.fecha else "S/F"
                duplicate_reason = f"POSIBLE DUPLICADO: El reparto {suc_chk}_{num_chk} ya fue organizado previamente (Operador: {op_info}, Fecha: {fecha_info})."

        # Check if the detected sucursal is officially valid for this specific empresa
        emp_ext = metadata_found.get("empresa") if metadata_found else None
        suc_ext = metadata_found.get("sucursal") if metadata_found else None
        num_ext = metadata_found.get("nro_reparto") if metadata_found else None

        # Otapeya normalization if BB or CF was read
        if emp_ext == "OTAPEYA" and suc_ext:
            if suc_ext == "BB":
                suc_ext = "CC"
            elif suc_ext == "CF":
                suc_ext = "BA"
            metadata_found["sucursal"] = suc_ext

        is_valid_sucursal = is_valid_sucursal_for_empresa(emp_ext, suc_ext) if (emp_ext and suc_ext) else False

        # Check if nro_reparto has valid digits (Otapeya is exempt from minimum digits)
        is_valid_nro_digits, act_digits, req_min_digits = validate_nro_reparto_digits(suc_ext, num_ext, empresa=emp_ext)

        # If a complete Hoja de Reparto was found with all metadata, valid sucursal, valid digits, no missing guias, no unsigned guias, AND NOT a duplicate
        if (metadata_found and 
            metadata_found["empresa"] and 
            metadata_found["fecha"] and 
            is_valid_sucursal and 
            metadata_found["nro_reparto"] and
            is_valid_nro_digits and
            not has_missing_guias and
            not has_unsigned_guias and
            not is_duplicate):
            
            empresa = metadata_found["empresa"]
            sucursal = metadata_found["sucursal"]
            nro_reparto = metadata_found["nro_reparto"]

            # Enforce Otapeya sucursal rules: Bahia is CC, Capital is BA
            if empresa == "OTAPEYA":
                if sucursal == "BB":
                    sucursal = "CC"
                elif sucursal == "CF":
                    sucursal = "BA"
            
            dest_path = get_organized_path(
                empresa=empresa,
                fecha=metadata_found["fecha"],
                sucursal=sucursal,
                nro_reparto=nro_reparto,
                base_salida=custom_salida
            )
            
            try:
                final_dest = move_directory(folder, dest_path)
                
                # Rename organized files
                try:
                    rename_organized_files(final_dest, sucursal, nro_reparto)
                except Exception as re_err:
                    print(f"Error renaming organized files: {re_err}")
                
                final_dest_str = str(final_dest.resolve())
                reparto_db = Reparto(
                    empresa=empresa,
                    sucursal=sucursal,
                    nro_reparto=nro_reparto,
                    fecha=metadata_found["fecha"],
                    ruta_original=original_path_str,
                    ruta_nueva=final_dest_str,
                    ruta_espejo=get_mirror_path(final_dest_str),
                    estado="ORGANIZADO",
                    usuario_id=usuario_id,
                    usuario_legajo=usuario_legajo,
                    guias_encontradas=guias_encontradas_str,
                    guias_faltantes=guias_faltantes_str,
                    guias_no_entregadas=guias_no_entregadas_str,
                    guias_sin_firma=guias_sin_firma_str,
                    es_duplicado=False,
                    motivo_revision=None
                )
                db.add(reparto_db)
                db.commit()
                db.refresh(reparto_db)
                
                results["organizados"].append(reparto_db.to_dict())
                print(f"Successfully organized: {folder.name} -> {final_dest}")
                
            except Exception as e:
                # If moving failed, send to revision
                print(f"Error moving organized folder {folder.name}: {e}")
                send_to_revision(folder, db, results, metadata_found, original_path_str, guias_encontradas_str, guias_faltantes_str, guias_sin_firma_str, guias_no_entregadas_str, usuario_id, usuario_legajo, motivo_revision=f"Error al mover carpeta: {e}")
                
        else:
            # Metadata missing, invalid sucursal, invalid digits, missing guias, unsigned guias or duplicate -> Move to REVISION
            motivo = duplicate_reason
            if not motivo:
                if not is_valid_sucursal:
                    motivo = "Sucursal inválida o no identificada"
                elif not is_valid_nro_digits:
                    motivo = f"Número de reparto incompleto ({num_ext}): sucursal {suc_ext} requiere como mínimo {req_min_digits} dígitos (se detectaron {act_digits})"
                elif has_missing_guias:
                    motivo = f"Guías faltantes ({guias_faltantes_str})"
                elif has_unsigned_guias:
                    motivo = f"Guías sin firma ({guias_sin_firma_str})"
                else:
                    motivo = "Metadatos incompletos"
                    
            send_to_revision(folder, db, results, metadata_found, original_path_str, guias_encontradas_str, guias_faltantes_str, guias_sin_firma_str, guias_no_entregadas_str, usuario_id, usuario_legajo, motivo_revision=motivo)
            
    # Clean up empty directories under the scanned path
    clean_empty_directories(entrada_path)
    
    return results

def send_to_revision(
    folder_path: Path, 
    db: Session, 
    results: dict, 
    metadata_found: dict, 
    original_path_str: str,
    guias_encontradas: str = None,
    guias_faltantes: str = None,
    guias_sin_firma: str = None,
    guias_no_entregadas: str = None,
    usuario_id: int = None,
    usuario_legajo: str = None,
    motivo_revision: str = None
):
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
            emp_raw = metadata_found.get("empresa")
            empresa = emp_raw if emp_raw in ["INTERPROVINCIAL", "OTAPEYA"] else "DESCONOCIDA"
            fecha = metadata_found.get("fecha")
            
            suc_raw = metadata_found.get("sucursal")
            suc_clean = suc_raw.upper().strip() if suc_raw else None
            if empresa == "OTAPEYA" and suc_clean:
                if suc_clean == "BB":
                    suc_clean = "CC"
                elif suc_clean == "CF":
                    suc_clean = "BA"
            sucursal = suc_clean if suc_clean in settings.VALID_SUCURSALES else None
            
            nro_reparto = metadata_found.get("nro_reparto")
            
        reparto_db = Reparto(
            empresa=empresa,
            sucursal=sucursal,
            nro_reparto=nro_reparto,
            fecha=fecha,
            ruta_original=original_path_str,
            ruta_nueva=str(final_dest.resolve()),
            estado="EN_REVISION",
            usuario_id=usuario_id,
            usuario_legajo=usuario_legajo,
            guias_encontradas=guias_encontradas,
            guias_faltantes=guias_faltantes,
            guias_sin_firma=guias_sin_firma,
            guias_no_entregadas=guias_no_entregadas,
            es_duplicado=False,
            motivo_revision=motivo_revision
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
    db: Session,
    custom_salida: Path = None,
    resolucion_guias_faltantes: dict = None,
    resolucion_guias_sin_firma: dict = None,
    modo_historico: bool = False,
    usuario_id: int = None,
    usuario_legajo: str = None,
    permitir_duplicado: bool = False
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

    # Restrict editing returned repartos strictly to administrators
    if reparto.motivo_revision and "Devuelto" in reparto.motivo_revision:
        if not usuario_id:
            raise ValueError("ACCESO DENEGADO: Solo los Administradores tienen autorización para editar y organizar repartos devueltos a revisión.")
        user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not user or user.rol != "ADMIN":
            raise ValueError("ACCESO DENEGADO: Solo los Administradores tienen autorización para editar y organizar repartos devueltos a revisión.")
        
    empresa_clean = empresa.strip().upper() if empresa else ""
    sucursal_clean = sucursal.strip().upper()
    
    # Strict enterprise segregation:
    if empresa_clean == "OTAPEYA":
        if sucursal_clean == "BB":
            sucursal_clean = "CC"
        elif sucursal_clean == "CF":
            sucursal_clean = "BA"
        if sucursal_clean not in ["CC", "BA", "NQ"]:
            raise ValueError(f"Para OTAPEYA, las únicas sucursales válidas son CC (Bahía), BA (Capital) y NQ (Neuquén). Se ingresó: '{sucursal}'")
    elif empresa_clean == "INTERPROVINCIAL":
        if sucursal_clean in ["CC", "BA"]:
            raise ValueError("Las siglas CC y BA pertenecen exclusivamente a Otapeya. Para INTERPROVINCIAL debe ser BB (Bahía Blanca) o CF (Capital Federal).")
        if not is_valid_sucursal_for_empresa("INTERPROVINCIAL", sucursal_clean):
            valid_list = ", ".join(SUCURSALES_INTERPROVINCIAL.keys())
            raise ValueError(f"La sucursal '{sucursal}' no es válida para INTERPROVINCIAL. Debe ser una de: {valid_list}")
    else:
        if sucursal_clean not in settings.VALID_SUCURSALES:
            valid_list = ", ".join(settings.VALID_SUCURSALES.keys())
            raise ValueError(f"La sucursal '{sucursal}' no es válida. Debe ser una de: {valid_list}")

    num_clean = nro_reparto.strip()
    
    # Check minimum required digits (Otapeya is exempt from minimum digits)
    is_valid_dig, act_dig, req_min = validate_nro_reparto_digits(sucursal_clean, num_clean, empresa=empresa_clean)
    if not is_valid_dig:
        raise ValueError(
            f"El número de reparto '{num_clean}' es inválido para la sucursal {sucursal_clean}. "
            f"Requiere como mínimo {req_min} dígitos numéricos (se ingresaron: {act_dig})."
        )
    
    # Check if this reparto code already exists in organized repartos
    existing_dup = db.query(Reparto).filter(
        Reparto.id != reparto_id,
        Reparto.sucursal == sucursal_clean,
        Reparto.nro_reparto == num_clean,
        Reparto.estado == "ORGANIZADO"
    ).first()
    
    if existing_dup and not permitir_duplicado:
        op_code = existing_dup.usuario_legajo or "S/A"
        fecha_dup = existing_dup.fecha.isoformat() if existing_dup.fecha else "S/F"
        raise ValueError(
            f"DUPLICADO_DETECTADO: Ya existe un reparto organizado con el código '{sucursal_clean}_{num_clean}' "
            f"(Operador: {op_code}, Fecha: {fecha_dup}). "
            f"Verifica el número o tilda la opción para permitir guardar como duplicado."
        )

    is_marked_dup = bool(existing_dup and permitir_duplicado)

    src_path = Path(reparto.ruta_nueva)
    if not src_path.exists():
        raise FileNotFoundError(f"Source folder in Revision does not exist: {src_path}")
        
    # Re-evaluate guias completeness using the PDFs in src_path before we move it
    pdf_files = list(src_path.glob("*.pdf"))
    hoja_pdf_path = None
    for pdf_path in pdf_files:
        meta = PDFReader.extract_metadata(pdf_path)
        if meta.get("is_hoja_reparto"):
            hoja_pdf_path = pdf_path
            break
            
    guias_encontradas_str = None
    guias_faltantes_str = None
    guias_sin_firma_str = None
    guias_no_entregadas_str = None
    if hoja_pdf_path:
        guias_info = PDFReader.extract_expected_guias_and_exclusions(hoja_pdf_path)
        expected_guias = guias_info.get("guias_a_controlar", [])
        no_entregadas_list = guias_info.get("guias_no_entregadas", [])
        guias_no_entregadas_str = ",".join(no_entregadas_list) if no_entregadas_list else None
        
        other_pdfs = [p for p in pdf_files if p != hoja_pdf_path]
        
        encontradas_acc = []
        faltantes_acc = []
        sin_firma_acc = []
        for g in expected_guias:
            parts = g.split(".")
            if len(parts) >= 3:
                serial = parts[2]
                matched_pdf = None
                for other_pdf in other_pdfs:
                    if PDFReader.check_pdf_contains_serial(other_pdf, serial):
                        matched_pdf = other_pdf
                        break
                if matched_pdf:
                    encontradas_acc.append(g)
                    sig_res = PDFReader.check_guia_signature(matched_pdf)
                    if not sig_res.get("has_signature", False):
                        sin_firma_acc.append(g)
                else:
                    faltantes_acc.append(g)
            else:
                faltantes_acc.append(g)
        
        guias_encontradas_str = ",".join(encontradas_acc) if encontradas_acc else None
        guias_faltantes_str = ",".join(faltantes_acc) if faltantes_acc else None
        guias_sin_firma_str = ",".join(sin_firma_acc) if sin_firma_acc else None

    dest_path = get_organized_path(
        empresa=empresa,
        fecha=fecha_obj,
        sucursal=sucursal,
        nro_reparto=nro_reparto,
        base_salida=custom_salida
    )
    
    # Move folder from Revision to Salida
    final_dest = move_directory(src_path, dest_path)
    
    # Rename organized files
    try:
        rename_organized_files(final_dest, sucursal, nro_reparto)
    except Exception as re_err:
        print(f"Error renaming organized files: {re_err}")
    
    # Update DB record
    reparto.empresa = empresa
    reparto.fecha = fecha_obj
    reparto.sucursal = sucursal
    reparto.nro_reparto = nro_reparto
    final_dest_str = str(final_dest.resolve())
    reparto.ruta_nueva = final_dest_str
    reparto.ruta_espejo = get_mirror_path(final_dest_str)
    reparto.estado = "ORGANIZADO"
    reparto.guias_encontradas = guias_encontradas_str
    reparto.guias_faltantes = guias_faltantes_str
    reparto.guias_sin_firma = guias_sin_firma_str
    reparto.guias_no_entregadas = guias_no_entregadas_str
    reparto.es_duplicado = is_marked_dup
    reparto.motivo_revision = None
    
    if usuario_id:
        reparto.usuario_id = usuario_id
    if usuario_legajo:
        reparto.usuario_legajo = usuario_legajo
    
    import json
    if resolucion_guias_faltantes:
        reparto.resolucion_guias_faltantes = json.dumps(resolucion_guias_faltantes)
    else:
        reparto.resolucion_guias_faltantes = None

    if resolucion_guias_sin_firma:
        reparto.resolucion_guias_sin_firma = json.dumps(resolucion_guias_sin_firma)
    else:
        reparto.resolucion_guias_sin_firma = None
    
    db.commit()
    db.refresh(reparto)
    
    print(f"Manually resolved Reparto #{reparto_id}: moved to {final_dest}")
    return reparto.to_dict()

def rename_organized_files(organized_dir: Path, sucursal: str, nro_reparto: str):
    """
    Renames the PDFs in the organized folder.
    The Hoja de Reparto is identified and can be renamed to {sucursal}{nro_reparto}_reparto.pdf
    The rest of the PDFs are matched against expected guias and renamed to {sucursal}{nro_reparto}_{guia}.pdf
    """
    pdf_files = list(organized_dir.glob("*.pdf"))
    if not pdf_files:
        return
        
    # 1. Identify the Hoja de Reparto (first file containing critical metadata)
    hoja_pdf_path = None
    metadata_found = None
    
    for pdf_path in pdf_files:
        metadata = PDFReader.extract_metadata(pdf_path)
        if metadata.get("empresa") and metadata.get("fecha") and metadata.get("sucursal") and metadata.get("nro_reparto"):
            metadata_found = metadata
            hoja_pdf_path = pdf_path
            break
            
    # If no perfect match, fallback to search partially
    if not hoja_pdf_path:
        for pdf_path in pdf_files:
            metadata = PDFReader.extract_metadata(pdf_path)
            if metadata.get("nro_reparto"):
                hoja_pdf_path = pdf_path
                break
                
    if not hoja_pdf_path:
        # Fallback to the first PDF alphabetically
        pdf_files.sort()
        hoja_pdf_path = pdf_files[0]
        
    # 2. Extract expected guias
    expected_guias = PDFReader.extract_expected_guias(hoja_pdf_path)
    other_pdfs = [p for p in pdf_files if p != hoja_pdf_path]
    
    # 3. Match and rename guias
    renamed_paths = set()
    suc_clean = sucursal.upper().strip()
    nro_clean = nro_reparto.strip()
    
    for g in expected_guias:
        parts = g.split(".")
        if len(parts) >= 3:
            serial = parts[2]
            for other_pdf in other_pdfs:
                if other_pdf in renamed_paths:
                    continue
                if PDFReader.check_pdf_contains_serial(other_pdf, serial):
                    # Rename it to Guia_{g}.pdf (e.g. Guia_BB.1.845563.pdf)
                    safe_guia_name = g.replace("/", "_").replace("\\", "_")
                    new_name = f"Guia_{safe_guia_name}.pdf"
                    new_path = organized_dir / new_name
                    try:
                        # Ensure we don't overwrite if it somehow already has that name
                        if other_pdf != new_path:
                            # If new_path already exists, generate safe name
                            if new_path.exists():
                                new_path = new_path.with_name(f"{new_path.stem}_dup.pdf")
                            other_pdf.rename(new_path)
                            renamed_paths.add(new_path)
                            print(f"Renamed guide PDF: {other_pdf.name} -> {new_path.name}")
                        else:
                            renamed_paths.add(other_pdf)
                    except Exception as e:
                        print(f"Error renaming guide PDF {other_pdf.name}: {e}")
                    break
                    
    # 4. Finally, rename the Hoja de Reparto to Hoja_Reparto_{sucursal}_{nro_reparto}.pdf
    try:
        new_hoja_name = f"Hoja_Reparto_{suc_clean}_{nro_clean}.pdf"
        new_hoja_path = organized_dir / new_hoja_name
        if hoja_pdf_path != new_hoja_path:
            if new_hoja_path.exists():
                new_hoja_path = new_hoja_path.with_name(f"{new_hoja_path.stem}_dup.pdf")
            hoja_pdf_path.rename(new_hoja_path)
            print(f"Renamed Hoja de Reparto: {hoja_pdf_path.name} -> {new_hoja_path.name}")
    except Exception as e:
        print(f"Error renaming Hoja de Reparto {hoja_pdf_path.name}: {e}")

def return_reparto_to_revision(db: Session, reparto_id: int, usuario_id: int = None) -> dict:
    """
    Returns an already ORGANIZADO reparto back to REVISION.
    Moves the physical folder from Salida back to Revision,
    and updates the database status to EN_REVISION so it can be edited and re-organized.
    Only administrators are permitted to perform this operation.
    """
    if usuario_id:
        user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not user or user.rol != "ADMIN":
            raise ValueError("ACCESO DENEGADO: Solo los Administradores tienen autorización para devolver un reparto a revisión.")

    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise ValueError(f"No se encontró el reparto con ID {reparto_id}")
        
    src_path = Path(reparto.ruta_nueva)
    if not src_path.exists():
        if reparto.ruta_original and Path(reparto.ruta_original).exists():
            src_path = Path(reparto.ruta_original)
        else:
            raise FileNotFoundError(f"No se encontró la carpeta física en el disco: {reparto.ruta_nueva}")

    # Destination in Revision folder
    folder_base_name = f"{reparto.sucursal or 'REV'}_{reparto.nro_reparto or reparto.id}"
    dest_path = Path(settings.REVISION) / folder_base_name
    
    # Safely move directory
    final_dest = move_directory(src_path, dest_path)
    
    # Try cleaning up empty parent folders in Salida
    try:
        curr = src_path.parent
        for _ in range(5):
            if curr.exists() and not any(curr.iterdir()):
                curr.rmdir()
                curr = curr.parent
            else:
                break
    except Exception as cleanup_err:
        print(f"Warning cleaning empty parent folders: {cleanup_err}")

    # Update DB record
    reparto.estado = "EN_REVISION"
    reparto.ruta_nueva = str(final_dest.resolve())
    reparto.ruta_espejo = None
    reparto.motivo_revision = "Devuelto manualmente a revisión para corrección de datos"
    
    db.commit()
    db.refresh(reparto)
    
    print(f"Reparto #{reparto_id} returned to revision: moved to {final_dest}")
    return reparto.to_dict()

def anular_y_borrar_reparto(
    db: Session,
    reparto_id: int,
    usuario_id: int = None,
    usuario_legajo: str = None,
    motivo: str = "Anulado para re-escaneo"
) -> dict:
    """
    Cancels a reparto (Soft Delete in DB: estado='ANULADO') and permanently deletes
    its physical folder and PDF documents on disk.
    This frees up the reparto number so it can be re-scanned and processed cleanly.
    Restricted to ADMINISTRATORS only.
    """
    import shutil
    from datetime import datetime

    if usuario_id:
        user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not user or user.rol != "ADMIN":
            raise ValueError("ACCESO DENEGADO: Solo los Administradores tienen autorización para anular y borrar repartos.")

    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise ValueError(f"No se encontró el reparto con ID {reparto_id}")

    # Protected root directories that must NEVER be deleted
    protected_roots = {
        Path(settings.ENTRADA).resolve(),
        Path(settings.SALIDA).resolve(),
        Path(settings.REVISION).resolve(),
        Path(settings.DIR_BASE_DATOS).resolve(),
        Path(settings.DIR_INTERPROVINCIAL).resolve(),
        Path(settings.DIR_OTAPEYA).resolve(),
        Path(r"A:\AD_INTERPROVINCIAL"),
        Path(r"A:\AD_OTAPEYA"),
        Path(r"A:\BASE_GESTOR_ARCHIVOS"),
        Path(r"\\192.168.0.99\ad_interprovincial_red"),
        Path(r"\\192.168.0.99\ad_otapeya_red"),
        Path(r"\\192.168.0.99\base_gestor_archivos"),
    }
    for drv in ["C:\\", "D:\\", "A:\\", "Q:\\", "O:\\"]:
        try:
            protected_roots.add(Path(drv).resolve())
        except Exception:
            pass

    # Find target directories to remove
    target_dirs = set()
    for path_str in [reparto.ruta_nueva, reparto.ruta_original, reparto.ruta_espejo]:
        if path_str:
            try:
                p = Path(path_str).resolve()
                if p not in protected_roots and p.exists() and p.is_dir():
                    target_dirs.add(p)
            except Exception:
                pass

    deleted_paths = []
    for p in target_dirs:
        try:
            shutil.rmtree(p, ignore_errors=False)
            deleted_paths.append(str(p))
            print(f"Directorio de reparto eliminado permanentemente: {p}")

            # Clean up empty parents in Salida / Revision (up to 4 levels)
            curr = p.parent
            for _ in range(4):
                if curr not in protected_roots and curr.exists() and curr.is_dir() and not any(curr.iterdir()):
                    curr.rmdir()
                    curr = curr.parent
                else:
                    break
        except Exception as err_del:
            print(f"Aviso al eliminar directorio físico {p}: {err_del}")

    # Soft delete in Database
    reparto.estado = "ANULADO"
    reparto.fecha_anulacion = datetime.utcnow()
    reparto.usuario_anulacion = usuario_legajo or (user.legajo if (usuario_id and user) else "ADMIN")
    reparto.motivo_anulacion = motivo or "Anulado para re-escaneo"
    reparto.ruta_nueva = None
    reparto.ruta_espejo = None

    db.commit()
    db.refresh(reparto)

    return {
        "id": reparto.id,
        "nro_reparto": reparto.nro_reparto,
        "sucursal": reparto.sucursal,
        "estado": reparto.estado,
        "motivo_anulacion": reparto.motivo_anulacion,
        "carpetas_eliminadas": deleted_paths
    }

