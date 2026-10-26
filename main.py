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

@app.get("/api/auth/user-by-legajo/{legajo}", summary="Get active user by legajo")
def get_user_by_legajo(legajo: str, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.legajo == legajo.strip(), Usuario.activo == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo.")
    return {"status": "success", "user": user.to_dict()}

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

class AnularRepartoRequest(BaseModel):
    usuario_id: Optional[int] = None
    usuario_legajo: Optional[str] = None
    motivo: Optional[str] = "Anulado para re-escaneo"

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
        if r.estado == "ORGANIZADO" and (r.ruta_espejo or r.ruta_nueva):
            d["ruta_espejo"] = get_mirror_path(r.ruta_espejo or r.ruta_nueva)
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

@app.post("/api/repartos/{reparto_id}/return-to-revision", summary="Return an organized reparto back to REVISION")
def return_to_revision_endpoint(reparto_id: int, usuario_id: Optional[int] = None, db: Session = Depends(get_db)):
    try:
        from core.organizer import return_reparto_to_revision
        updated_reparto = return_reparto_to_revision(db=db, reparto_id=reparto_id, usuario_id=usuario_id)
        return {
            "status": "success",
            "message": f"Reparto #{reparto_id} devuelto a Revisión exitosamente.",
            "data": updated_reparto
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al devolver a revisión: {str(e)}")

@app.post("/api/repartos/{reparto_id}/anular", summary="Cancel reparto and permanently delete its physical folder")
def anular_reparto_endpoint(
    reparto_id: int, 
    data: Optional[AnularRepartoRequest] = None, 
    db: Session = Depends(get_db)
):
    try:
        from core.organizer import anular_y_borrar_reparto
        u_id = data.usuario_id if data else None
        u_legajo = data.usuario_legajo if data else None
        motivo = data.motivo if data and data.motivo else "Anulado para re-escaneo"
        
        result = anular_y_borrar_reparto(
            db=db,
            reparto_id=reparto_id,
            usuario_id=u_id,
            usuario_legajo=u_legajo,
            motivo=motivo
        )
        return {
            "status": "success",
            "message": f"Reparto #{reparto_id} anulado en la base de datos y carpeta física eliminada de disco.",
            "data": result
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al anular reparto: {str(e)}")

@app.post("/api/repartos/{reparto_id}/open", summary="Open folder in File Explorer")
def open_reparto_folder(reparto_id: int, db: Session = Depends(get_db)):
    try:
        reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
        if not reparto:
            raise HTTPException(status_code=404, detail="Reparto no encontrado.")
            
        path_to_open = reparto.ruta_nueva if reparto.ruta_nueva else reparto.ruta_original
        if not path_to_open:
            raise HTTPException(status_code=400, detail="La carpeta no tiene una ruta válida asignada.")
            
        import os
        from services.file_manager import resolve_accessible_folder

        target_dir = resolve_accessible_folder(path_to_open, reparto.estado)
        if not target_dir:
            if reparto.estado == "ORGANIZADO":
                raise HTTPException(
                    status_code=404, 
                    detail=f"El reparto fue organizado con éxito, pero la carpeta física no es accesible desde este equipo. Ruta registrada: {path_to_open}"
                )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail=f"La carpeta no existe físicamente en el sistema: {path_to_open}"
                )
            
        # Open folder in Windows File Explorer
        os.startfile(str(target_dir.resolve()))
        return {
            "status": "success",
            "message": f"Carpeta abierta en el explorador: {str(target_dir)}"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo abrir la carpeta: {str(e)}")

@app.get("/api/repartos/{reparto_id}/files", summary="List PDF files in reparto folder")
def list_reparto_files(reparto_id: int, db: Session = Depends(get_db)):
    from services.file_manager import resolve_accessible_folder
    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise HTTPException(status_code=404, detail="Reparto no encontrado.")
    folder_str = reparto.ruta_nueva if reparto.ruta_nueva else reparto.ruta_original
    if not folder_str:
        return []
    target_dir = resolve_accessible_folder(folder_str, reparto.estado)
    if not target_dir:
        return []
    
    files = []
    for f in target_dir.glob("*.pdf"):
        files.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "is_hoja": "HOJA" in f.name.upper() or f.name.upper().startswith(f"{reparto.sucursal or ''}_{reparto.nro_reparto or ''}".upper())
        })
    files.sort(key=lambda x: (not x["is_hoja"], x["name"]))
    return files

@app.get("/api/repartos/{reparto_id}/files/{filename}", summary="Download / View PDF file directly")
def get_reparto_file(reparto_id: int, filename: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    from services.file_manager import resolve_accessible_folder
    reparto = db.query(Reparto).filter(Reparto.id == reparto_id).first()
    if not reparto:
        raise HTTPException(status_code=404, detail="Reparto no encontrado.")
    folder_str = reparto.ruta_nueva if reparto.ruta_nueva else reparto.ruta_original
    if not folder_str:
        raise HTTPException(status_code=404, detail="Ruta no disponible.")
    target_dir = resolve_accessible_folder(folder_str, reparto.estado)
    if not target_dir:
        raise HTTPException(status_code=404, detail="Ruta no accesible desde este equipo.")
    file_path = target_dir / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"El archivo '{filename}' no se encuentra en el directorio accesible ({target_dir})."
        )
    
    return FileResponse(
        path=str(file_path.resolve()), 
        media_type="application/pdf", 
        filename=filename,
        headers={"Content-Disposition": f"inline; filename=\"{filename}\""}
    )

@app.get("/api/system/status", summary="Get system status and storage configuration")
def get_system_status():
    from config.settings import settings
    return {
        "status": "online",
        "storage_mode": settings.STORAGE_MODE,
        "is_local_server": settings.IS_LOCAL_SERVER,
        "database_file": str(settings.DATABASE_FILE),
        "dir_interprovincial": str(settings.DIR_INTERPROVINCIAL),
        "dir_otapeya": str(settings.DIR_OTAPEYA),
        "server_ip": settings.SERVER_IP
    }

# ----------------- METRICS & PDF REPORT ENDPOINTS -----------------
@app.get("/api/metrics", summary="Get operational and operator metrics summary")
def get_metrics_endpoint(
    desde: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    hasta: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    from services.metrics_service import get_metrics_summary
    return get_metrics_summary(db=db, desde=desde, hasta=hasta)

@app.get("/api/metrics/pdf", summary="Generate and download executive PDF metrics report")
def download_metrics_pdf(
    desde: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    hasta: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    filter_label: Optional[str] = Query("Histórico Total", description="Label for the active filter"),
    admin_name: Optional[str] = Query("Administrador", description="Admin name requesting the report"),
    db: Session = Depends(get_db)
):
    import io
    from fastapi import Response
    from services.metrics_service import get_metrics_summary, generate_metrics_pdf
    
    summary = get_metrics_summary(db=db, desde=desde, hasta=hasta)
    pdf_bytes = generate_metrics_pdf(summary, filter_label=filter_label, admin_name=admin_name)
    
    filename = f"reporte_metricas_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )

@app.get("/api/metrics/sucursales", summary="List available sucursales with their min and max repartos")
def get_sucursales_stats_endpoint(db: Session = Depends(get_db)):
    from services.metrics_service import get_available_sucursales_stats
    return get_available_sucursales_stats(db=db)

@app.get("/api/metrics/faltantes", summary="Get missing delivery numbers gap analysis for a sucursal")
def get_faltantes_endpoint(
    sucursal: str = Query(..., description="Sucursal code (e.g. BB, CF, NQ)"),
    desde: Optional[int] = Query(None, description="Starting delivery number (optional)"),
    hasta: Optional[int] = Query(None, description="Ending delivery number (optional)"),
    db: Session = Depends(get_db)
):
    from services.metrics_service import get_missing_repartos_analysis
    return get_missing_repartos_analysis(db=db, sucursal=sucursal, desde=desde, hasta=hasta)

@app.get("/api/metrics/faltantes/pdf", summary="Generate and download PDF audit report of missing repartos")
def download_faltantes_pdf(
    sucursal: str = Query(..., description="Sucursal code (e.g. BB, CF, NQ)"),
    desde: Optional[int] = Query(None, description="Starting delivery number (optional)"),
    hasta: Optional[int] = Query(None, description="Ending delivery number (optional)"),
    admin_name: Optional[str] = Query("Administrador", description="Admin name requesting the report"),
    db: Session = Depends(get_db)
):
    from fastapi import Response
    from services.metrics_service import get_missing_repartos_analysis, generate_missing_repartos_pdf
    
    analysis = get_missing_repartos_analysis(db=db, sucursal=sucursal, desde=desde, hasta=hasta)
    pdf_bytes = generate_missing_repartos_pdf(analysis, admin_name=admin_name)
    
    filename = f"faltantes_{sucursal}_{analysis.get('desde')}_{analysis.get('hasta')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )

@app.post("/api/metrics/audit/run", summary="Run manual integrity audit comparing database vs physical disk")
def run_audit_endpoint(
    dias_atras: Optional[int] = Query(None, description="Number of days in the past (None = Histórico Total)"),
    db: Session = Depends(get_db)
):
    from services.metrics_service import run_integrity_audit
    return run_integrity_audit(db=db, dias_atras=dias_atras)

@app.post("/api/metrics/audit/pdf", summary="Generate and download PDF audit report of DB vs disk irregularities")
def download_audit_pdf(
    dias_atras: Optional[int] = Query(None, description="Number of days in the past (None = Histórico Total)"),
    admin_name: str = Query("Administrador", description="Admin name requesting the audit report"),
    db: Session = Depends(get_db)
):
    from fastapi import Response
    from services.metrics_service import run_integrity_audit, generate_audit_report_pdf
    
    results = run_integrity_audit(db=db, dias_atras=dias_atras)
    pdf_bytes = generate_audit_report_pdf(results, admin_name=admin_name)
    
    filename = f"auditoria_integridad_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )





