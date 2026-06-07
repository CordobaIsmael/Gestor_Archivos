import shutil
from pathlib import Path
import os
from datetime import date

SUCURSAL_NAMES = {
    "BB": "BAHIA BLANCA",
    "NQN": "NEUQUEN",
    "CF": "CAPITAL FEDERAL",
    "MDP": "MAR DEL PLATA",
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

def get_organized_path(base_salida: Path, empresa: str, fecha: date, sucursal: str, nro_reparto: str) -> Path:
    """
    Constructs the organized hierarchical path for a reparto:
    base_salida / Year / Company / Sucursal Name / Month / Day / Sucursal_NroReparto
    """
    year_str = str(fecha.year)
    empresa_str = empresa.upper().strip()
    
    # Map sucursal code to full name
    suc_code = sucursal.upper().strip()
    sucursal_name = SUCURSAL_NAMES.get(suc_code, suc_code) # fallback to code if not in mapping
    
    # Map month number to name in Spanish
    month_name = MONTH_NAMES.get(fecha.month, "DESCONOCIDO")
    
    day_str = f"{fecha.day:02d}"
    
    folder_name = f"{suc_code}_{nro_reparto}"
    
    return base_salida / year_str / empresa_str / sucursal_name / month_name / day_str / folder_name


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
