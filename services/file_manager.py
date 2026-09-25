import shutil
from pathlib import Path
import os
from datetime import date
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
    "AZ": "AZUL"
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
    raw_suc_name = SUCURSAL_NAMES.get(suc_code, suc_code) # fallback to code if not in mapping
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
    Translates a physical storage path (on drive A:) to the corresponding mirror query path:
    - A:\AD_INTERPROVINCIAL\... -> Q:\AD_INTERPROVINCIAL\...
    - A:\AD_OTAPEYA\...         -> O:\AD_OTAPEYA\...
    """
    if not path_str:
        return path_str
        
    p_upper = path_str.upper().strip()
    
    # Interprovincial mirror in Q:
    if p_upper.startswith(r"A:\AD_INTERPROVINCIAL"):
        return "Q:" + path_str[2:]
    if p_upper.startswith(r"A:/AD_INTERPROVINCIAL"):
        return "Q:" + path_str[2:]
        
    # Otapeya mirror in O:
    if p_upper.startswith(r"A:\AD_OTAPEYA"):
        return "O:" + path_str[2:]
    if p_upper.startswith(r"A:/AD_OTAPEYA"):
        return "O:" + path_str[2:]
        
    return path_str
