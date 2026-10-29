import shutil
from pathlib import Path
import os
from datetime import date
from typing import Optional
from config.settings import settings

SUCURSAL_NAMES = {
    "MP": "MAR_DEL_PLATA",
    "MDP": "MAR_DEL_PLATA",
    "TA": "TRES_ARROYOS",
    "AR": "TRES_ARROYOS",
    "CO": "CORDOBA",
    "COR": "CORDOBA",
    "CBA": "CORDOBA",
    "OL": "OLAVARRIA",
    "OLA": "OLAVARRIA",
    "VR": "VILLA_REGINA",
    "RE": "VILLA_REGINA",
    "REG": "VILLA_REGINA",
    "RC": "RIO_COLORADO",
    "CH": "CHOELE_CHOEL",
    "BB": "BAHIA_BLANCA",
    "NQ": "NEUQUEN",
    "NQN": "NEUQUEN",
    "CF": "CAPITAL_FEDERAL",
    "RO": "ROSARIO",
    "ROS": "ROSARIO",
    "AZ": "AZUL",
    "TD": "TANDIL",
    "TAN": "TANDIL",
    "GR": "GENERAL_ROCA",
    "ROC": "GENERAL_ROCA",
    "CC": "BAHIA_BLANCA",
    "BA": "CAPITAL_FEDERAL"
}

MONTH_NAMES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE"
}

def get_organized_path(empresa: str, fecha: date, sucursal: str, nro_reparto: str, base_salida: Path = None) -> Path:
    r"""
    Constructs the organized hierarchical path for a reparto:
    - INTERPROVINCIAL -> A:\AD_INTERPROVINCIAL / Year / Sucursal_Name / Month / Day / Sucursal_NroReparto
    - OTAPEYA -> A:\AD_OTAPEYA / Year / Sucursal_Name / Month / Day / Sucursal_NroReparto
    """
    empresa_str = empresa.upper().strip()
    
    if base_salida is not None:
        target_base = base_salida
    elif empresa_str == "INTERPROVINCIAL":
        target_base = settings.DIR_INTERPROVINCIAL
    elif empresa_str == "OTAPEYA":
        target_base = settings.DIR_OTAPEYA
    else:
        target_base = Path(settings.SALIDA) / empresa_str
        
    year_str = str(fecha.year)
    
    # Map sucursal code to full name with underscores
    suc_code = sucursal.upper().strip()
    
    # Enforce Otapeya sucursal rules: Bahia Blanca is CC, Capital Federal is BA
    if empresa_str == "OTAPEYA":
        if suc_code == "BB":
            suc_code = "CC"
        elif suc_code == "CF":
            suc_code = "BA"

    raw_suc_name = SUCURSAL_NAMES.get(suc_code, suc_code) # fallback to code if not in mapping

    # Check if storage has alternative folder naming for Casa Central or Buenos Aires
    if empresa_str == "OTAPEYA":
        if suc_code == "CC":
            try:
                if (target_base / year_str / "CASA_CENTRAL").exists():
                    raw_suc_name = "CASA_CENTRAL"
            except Exception:
                pass
        elif suc_code == "BA":
            try:
                if (target_base / year_str / "BUENOS_AIRES").exists():
                    raw_suc_name = "BUENOS_AIRES"
            except Exception:
                pass

    sucursal_name = raw_suc_name.replace(" ", "_")
    
    # Map month number to name in Spanish
    month_name = MONTH_NAMES.get(fecha.month, "DESCONOCIDO")
    
    day_str = f"{fecha.day:02d}"
    
    folder_name = f"{suc_code}_{nro_reparto}"
    
    return target_base / year_str / sucursal_name / month_name / day_str / folder_name


def generate_safe_dest_path(dest_path: Path) -> Path:
    """
    If the destination folder already exists, appends _1, _2, etc. to prevent overwrites.
    """
    if not dest_path.exists():
        return dest_path
    
    parent = dest_path.parent
    name = dest_path.name
    
    counter = 1
    new_dest = parent / f"{name}_{counter}"
    while new_dest.exists():
        counter += 1
        new_dest = parent / f"{name}_{counter}"
        
    return new_dest

def move_directory(src_dir: Path, dest_dir: Path) -> Path:
    """
    Moves a directory from src_dir to dest_dir safely.
    Creates parent directories if needed, and handles existing directories.
    Returns the final Path where it was moved.
    """
    if not src_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")
        
    # Generate safe path to avoid overwriting existing folders
    safe_dest = generate_safe_dest_path(dest_dir)
    
    # Ensure target parent directory exists
    safe_dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Move directory
    shutil.move(str(src_dir), str(safe_dest))
    return safe_dest


def get_mirror_path(path_str: str) -> str:
    r"""
    Translates a physical storage path to the corresponding mirror query path:
    - \\192.168.0.99\ad_interprovincial_red\2026\... or A:\AD_INTERPROVINCIAL\2026\... -> Q:\2026\...
    - \\192.168.0.99\ad_otapeya_red\2026\... or A:\AD_OTAPEYA\2026\...                 -> O:\2026\...
    """
    if not path_str:
        return path_str
        
    p_norm = path_str.replace("/", "\\")
    p_upper = p_norm.upper().strip()
    
    # Interprovincial mirror in Q:\
    for prefix in [r"\\192.168.0.99\AD_INTERPROVINCIAL_RED", r"\\192.168.0.99\AD_INTERPROVINCIAL", r"A:\AD_INTERPROVINCIAL", r"Q:\AD_INTERPROVINCIAL"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):]
            if not rel.startswith("\\"):
                rel = "\\" + rel
            return "Q:" + rel
            
    # Otapeya mirror in O:\
    for prefix in [r"\\192.168.0.99\AD_OTAPEYA_RED", r"\\192.168.0.99\AD_OTAPEYA", r"A:\AD_OTAPEYA", r"O:\AD_OTAPEYA"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):]
            if not rel.startswith("\\"):
                rel = "\\" + rel
            return "O:" + rel
            
    # If already Q:\... or O:\...
    if p_upper.startswith("Q:") or p_upper.startswith("O:"):
        return p_norm

    return path_str


def get_network_unc_path(path_str: str, server_ip: str = None) -> str:
    r"""
    Converts a local or mirror drive path into a standard Windows SMB network share path (UNC):
    - Q:\... or A:\AD_INTERPROVINCIAL\... -> \\192.168.0.99\ad_interprovincial_red\...
    - O:\... or A:\AD_OTAPEYA\...         -> \\192.168.0.99\ad_otapeya_red\...
    """
    if not path_str:
        return path_str
        
    p_norm = path_str.replace("/", "\\")
    p_upper = p_norm.upper()
    
    # If it is already a network share path, return directly
    if p_norm.startswith(r"\\"):
        return p_norm

    host = server_ip or getattr(settings, "STORAGE_SERVER_IP", "192.168.0.99")
    
    # Interprovincial:
    for prefix in [r"A:\AD_INTERPROVINCIAL", r"Q:\AD_INTERPROVINCIAL"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):].lstrip("\\")
            return f"\\\\{host}\\ad_interprovincial_red" + (f"\\{rel}" if rel else "")
    if p_upper.startswith("Q:"):
        rel = p_norm[2:].lstrip("\\")
        return f"\\\\{host}\\ad_interprovincial_red" + (f"\\{rel}" if rel else "")
        
    # Otapeya:
    for prefix in [r"A:\AD_OTAPEYA", r"O:\AD_OTAPEYA"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):].lstrip("\\")
            return f"\\\\{host}\\ad_otapeya_red" + (f"\\{rel}" if rel else "")
    if p_upper.startswith("O:"):
        rel = p_norm[2:].lstrip("\\")
        return f"\\\\{host}\\ad_otapeya_red" + (f"\\{rel}" if rel else "")
        
    return p_norm


def get_local_server_path(path_str: str) -> str:
    r"""
    Translates a UNC or mirror path back to the physical local drive A:\ on the local server:
    - \\192.168.0.99\ad_interprovincial_red\... -> A:\AD_INTERPROVINCIAL\...
    - \\192.168.0.99\ad_otapeya_red\...         -> A:\AD_OTAPEYA\...
    - \\192.168.0.99\base_gestor_archivos\...    -> A:\BASE_GESTOR_ARCHIVOS\...
    - Q:\...                                     -> A:\AD_INTERPROVINCIAL\...
    - O:\...                                     -> A:\AD_OTAPEYA\...
    """
    if not path_str:
        return path_str
    p_norm = path_str.replace("/", "\\")
    p_upper = p_norm.upper().strip()
    
    # Interprovincial
    for prefix in [r"\\192.168.0.99\AD_INTERPROVINCIAL_RED", r"\\192.168.0.99\AD_INTERPROVINCIAL", r"Q:\AD_INTERPROVINCIAL", r"Q:"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):].lstrip("\\")
            return r"A:\AD_INTERPROVINCIAL" + (f"\\{rel}" if rel else "")
            
    # Otapeya
    for prefix in [r"\\192.168.0.99\AD_OTAPEYA_RED", r"\\192.168.0.99\AD_OTAPEYA", r"O:\AD_OTAPEYA", r"O:"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):].lstrip("\\")
            return r"A:\AD_OTAPEYA" + (f"\\{rel}" if rel else "")

    # Base de datos
    for prefix in [r"\\192.168.0.99\BASE_GESTOR_ARCHIVOS"]:
        if p_upper.startswith(prefix):
            rel = p_norm[len(prefix):].lstrip("\\")
            return r"A:\BASE_GESTOR_ARCHIVOS" + (f"\\{rel}" if rel else "")

    return p_norm


def resolve_accessible_folder(folder_str: str, estado: str = "ORGANIZADO") -> Optional[Path]:
    r"""
    Finds the first physically accessible directory for a reparto across:
    1. Mirror path (Q:\ or O:\)
    2. Given physical path (folder_str)
    3. Network UNC path (\\192.168.0.99\...)
    4. Local server drive path (A:\...)
    """
    if not folder_str:
        return None
        
    candidates = []
    if estado == "ORGANIZADO":
        mirror = get_mirror_path(folder_str)
        if mirror and mirror != folder_str:
            candidates.append(Path(mirror))
            
    candidates.append(Path(folder_str))
    
    unc = get_network_unc_path(folder_str)
    if unc and unc != folder_str:
        candidates.append(Path(unc))
        
    local = get_local_server_path(folder_str)
    if local and local != folder_str:
        candidates.append(Path(local))
        
    for cand in candidates:
        try:
            if cand.exists() and cand.is_dir():
                return cand
        except Exception:
            continue
            
    return None



