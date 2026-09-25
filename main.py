from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from pydantic import BaseModel
import hashlib

from services.db import get_db, init_db
from models.database import Reparto, Usuario
from core.organizer import process_incoming_folders, resolve_revision_folder

app = FastAPI(
    title="GestorArchivo API",
    description="Backend API for processing, organizing, and manually resolving file transfers.",
    version="1.0.0"
)

# Startup event to initialize tables
@app.on_event("startup")
def on_startup():
    init_db()

# ----------------- AUTH SCHEMAS & ENDPOINTS -----------------
class LoginRequest(BaseModel):
    legajo: str
    password: str

class CreateUserRequest(BaseModel):
    legajo: str
    nombre: str
    password: str
    rol: Optional[str] = "OPERADOR"

class ResetPasswordRequest(BaseModel):
    password_nueva: str

class ChangePasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str

@app.post("/api/auth/login", summary="Login with Legajo and Password/DNI")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    legajo_clean = data.legajo.strip()
    user = db.query(Usuario).filter(Usuario.legajo == legajo_clean).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario / Legajo no encontrado.")
        
    if not user.activo:
        raise HTTPException(status_code=403, detail="El usuario se encuentra desactivado. Contacta al administrador.")
        
    pwd_hash = hashlib.sha256(data.password.strip().encode('utf-8')).hexdigest()
    if user.password_hash != pwd_hash:
        raise HTTPException(status_code=401, detail="Contraseña / DNI incorrecto.")
        
    return {
        "status": "success",
        "user": user.to_dict()
    }

@app.get("/api/auth/users", summary="List all operators/users (Admin only)")
def list_users(db: Session = Depends(get_db)):
    users = db.query(Usuario).order_by(Usuario.legajo.asc()).all()
    user_list = []
    for u in users:
        u_dict = u.to_dict()
        u_dict["total_repartos"] = db.query(Reparto).filter(Reparto.usuario_id == u.id).count()
        user_list.append(u_dict)
    return user_list

@app.post("/api/auth/users/create", summary="Create new operator user")
def create_user(data: CreateUserRequest, db: Session = Depends(get_db)):
    legajo_clean = data.legajo.strip()
    existing = db.query(Usuario).filter(Usuario.legajo == legajo_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un usuario con el Legajo '{legajo_clean}'.")
        
    pwd_hash = hashlib.sha256(data.password.strip().encode('utf-8')).hexdigest()
    new_user = Usuario(
        legajo=legajo_clean,
        nombre=data.nombre.strip(),
        password_hash=pwd_hash,
        rol=data.rol.upper() if data.rol else "OPERADOR",
        activo=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "user": new_user.to_dict()}

@app.post("/api/auth/users/{user_id}/toggle", summary="Toggle operator active status")
def toggle_user_active(user_id: int, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    user.activo = not user.activo
    db.commit()
    return {"status": "success", "user": user.to_dict()}

@app.post("/api/auth/users/{user_id}/reset-password", summary="Admin reset operator password")
def reset_user_password(user_id: int, data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    user.password_hash = hashlib.sha256(data.password_nueva.strip().encode('utf-8')).hexdigest()
    db.commit()
    return {"status": "success", "message": f"Contraseña actualizada para el usuario {user.legajo}."}

@app.post("/api/auth/users/{user_id}/change-password", summary="Operator change own password")
def change_own_password(user_id: int, data: ChangePasswordRequest, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    current_hash = hashlib.sha256(data.password_actual.strip().encode('utf-8')).hexdigest()
    if user.password_hash != current_hash:
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta.")
    user.password_hash = hashlib.sha256(data.password_nueva.strip().encode('utf-8')).hexdigest()
    db.commit()
    return {"status": "success", "message": "Contraseña cambiada exitosamente."}

# ----------------- REPARTOS & PROCESS SCHEMAS -----------------
class ResolveRequest(BaseModel):
    empresa: str
    fecha: date
    sucursal: str
    nro_reparto: str
    salida_path: Optional[str] = None
    resolucion_guias_faltantes: Optional[dict] = None
    resolucion_guias_sin_firma: Optional[dict] = None
    modo_historico: Optional[bool] = False
    usuario_id: Optional[int] = None
    usuario_legajo: Optional[str] = None
    permitir_duplicado: Optional[bool] = False

class ProcessRequest(BaseModel):
    path: Optional[str] = None
    salida_path: Optional[str] = None
    modo_historico: Optional[bool] = False
    usuario_id: Optional[int] = None
    usuario_legajo: Optional[str] = None

@app.post("/api/process", summary="Process incoming folders")
def process_folders(data: Optional[ProcessRequest] = None, db: Session = Depends(get_db)):
    try:
        custom_path = None
        custom_salida = None
        modo_historico = False
        usuario_id = None
        usuario_legajo = None
        
        if data:
            from pathlib import Path
            if data.path:
                p = Path(data.path)
                if not p.exists() or not p.is_dir():
                    raise HTTPException(
                        status_code=400, 
                        detail=f"La ruta especificada no existe o no es un directorio: {data.path}"
                    )
                custom_path = p
                
            if data.salida_path:
                custom_salida = Path(data.salida_path)
            
            modo_historico = data.modo_historico or False
            usuario_id = data.usuario_id
            usuario_legajo = data.usuario_legajo
            
        results = process_incoming_folders(
            db, 
            custom_path=custom_path, 
            custom_salida=custom_salida,
            modo_historico=modo_historico,
            usuario_id=usuario_id,
            usuario_legajo=usuario_legajo
        )
        return {
            "status": "success",
            "message": "Procesamiento completado.",
            "data": results
        }
    except HTTPException as he:
        raise he
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repartos", summary="Get list of repartos")
def get_repartos(
    estado: Optional[str] = Query(None, description="Filter by status: ORGANIZADO, EN_REVISION"),
    usuario_id: Optional[int] = Query(None, description="Filter by operator user ID"),
    db: Session = Depends(get_db)
):
    from services.file_manager import get_mirror_path
    query = db.query(Reparto)
    if estado:
        query = query.filter(Reparto.estado == estado.upper())
    if usuario_id:
        query = query.filter(Reparto.usuario_id == usuario_id)
    
    repartos = query.order_by(Reparto.fecha_procesamiento.desc()).all()
    results = []
    for r in repartos:
        d = r.to_dict()
        if r.estado == "ORGANIZADO" and r.ruta_nueva:
            d["ruta_espejo"] = get_mirror_path(r.ruta_nueva)
        else:
            d["ruta_espejo"] = r.ruta_nueva or r.ruta_original
        results.append(d)
    return results

@app.post("/api/repartos/{reparto_id}/resolve", summary="Resolve a folder in REVISION status")
def resolve_reparto(
    reparto_id: int, 
    data: ResolveRequest, 
    db: Session = Depends(get_db)
):
    try:
        from pathlib import Path
        custom_salida = Path(data.salida_path) if data.salida_path else None
        
        updated_reparto = resolve_revision_folder(
            reparto_id=reparto_id,
            empresa=data.empresa,
            fecha_obj=data.fecha,
            sucursal=data.sucursal,
            nro_reparto=data.nro_reparto,
            db=db,
            custom_salida=custom_salida,
            resolucion_guias_faltantes=data.resolucion_guias_faltantes,
            resolucion_guias_sin_firma=data.resolucion_guias_sin_firma,
            modo_historico=data.modo_historico or False,
            usuario_id=data.usuario_id,
            usuario_legajo=data.usuario_legajo,
            permitir_duplicado=data.permitir_duplicado or False
        )
        return {
            "status": "success",
            "message": f"Reparto #{reparto_id} organizado exitosamente.",
            "data": updated_reparto
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/repartos/{reparto_id}/open", summary="Open folder in File Explorer")
def open_reparto_folder(reparto_id: int, db: Session = Depends(get_db)):
    try:
        reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
        if not reparto:
            raise HTTPException(status_code=404, detail="Reparto no encontrado.")
            
        path_to_open = reparto.ruta_nueva if reparto.ruta_nueva else reparto.ruta_original
        if not path_to_open:
            raise HTTPException(status_code=400, detail="La carpeta no tiene una ruta válida asignada.")
            
        from pathlib import Path
        import os
        from services.file_manager import get_mirror_path

        # If organized, route strictly to mirror path (Q: or O:)
        target_path_str = get_mirror_path(path_to_open) if reparto.estado == "ORGANIZADO" else path_to_open
        p = Path(target_path_str)
        if not p.exists():
            if reparto.estado == "ORGANIZADO":
                raise HTTPException(
                    status_code=404, 
                    detail=f"El reparto fue organizado con éxito en el servidor maestro, pero aún está pendiente de sincronización en el disco de consulta '{p.drive}' (se sincroniza cada 1 hora). Ruta: {target_path_str}"
                )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail=f"La carpeta no existe físicamente en el sistema: {target_path_str}"
                )
            
        # Open folder in Windows File Explorer
        os.startfile(str(p.resolve()))
        return {
            "status": "success",
            "message": f"Carpeta abierta en el explorador: {target_path_str}"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir la carpeta: {str(e)}")

@app.get("/api/repartos/{reparto_id}/files", summary="List PDF files in reparto folder")
def list_reparto_files(reparto_id: int, db: Session = Depends(get_db)):
    from pathlib import Path
    from services.file_manager import get_mirror_path
    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise HTTPException(status_code=404, detail="Reparto no encontrado.")
    folder_str = reparto.ruta_nueva if reparto.ruta_nueva else reparto.ruta_original
    if not folder_str:
        return []
    target_folder = get_mirror_path(folder_str) if reparto.estado == "ORGANIZADO" else folder_str
    p = Path(target_folder)
    if not p.exists() or not p.is_dir():
        return []
    
    files = []
    for f in p.glob("*.pdf"):
        files.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "is_hoja": "HOJA" in f.name.upper() or f.name.upper().startswith(f"{reparto.sucursal or ''}_{reparto.nro_reparto or ''}".upper())
        })
    files.sort(key=lambda x: (not x["is_hoja"], x["name"]))
    return files

@app.get("/api/repartos/{reparto_id}/files/{filename}", summary="Download / View PDF file directly")
def get_reparto_file(reparto_id: int, filename: str, db: Session = Depends(get_db)):
    from pathlib import Path
    from fastapi.responses import FileResponse
    from services.file_manager import get_mirror_path
    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise HTTPException(status_code=404, detail="Reparto no encontrado.")
    folder_str = reparto.ruta_nueva if reparto.ruta_nueva else reparto.ruta_original
    if not folder_str:
        raise HTTPException(status_code=404, detail="Ruta no disponible.")
    target_folder = get_mirror_path(folder_str) if reparto.estado == "ORGANIZADO" else folder_str
    file_path = Path(target_folder) / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"El archivo '{filename}' aún no se encuentra sincronizado en el disco de consulta (se sincroniza cada 1 hora)."
        )
    
    return FileResponse(
        path=str(file_path.resolve()), 
        media_type="application/pdf", 
        filename=filename,
        headers={"Content-Disposition": f"inline; filename=\"{filename}\""}
    )
