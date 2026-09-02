from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Reparto(Base):
    __tablename__ = 'repartos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa = Column(String(100), nullable=False) # e.g., INTERPROVINCIAL, OTAPEYA
    sucursal = Column(String(50), nullable=True)   # e.g., BB, NQN, CF, MDP
    nro_reparto = Column(String(50), nullable=True) # e.g., 138232
    fecha = Column(Date, nullable=True)            # Date of the reparto
    
    ruta_original = Column(String(500), nullable=False) # Original path in Entrada/
    ruta_nueva = Column(String(500), nullable=True)     # Organized path in Salida/ or Revision/
    estado = Column(String(50), nullable=False)          # 'ORGANIZADO', 'EN_REVISION'
    fecha_procesamiento = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    guias_encontradas = Column(String(2000), nullable=True)
    guias_faltantes = Column(String(2000), nullable=True)
    guias_no_entregadas = Column(String(2000), nullable=True)
    resolucion_guias_faltantes = Column(String(4000), nullable=True)
    guias_sin_firma = Column(String(2000), nullable=True)
    resolucion_guias_sin_firma = Column(String(4000), nullable=True)
    
    # Relationship to Caja
    caja_id = Column(Integer, ForeignKey('cajas.id'), nullable=True)
    caja = relationship("Caja", back_populates="repartos")

    def to_dict(self):
        return {
            "id": self.id,
            "empresa": self.empresa,
            "sucursal": self.sucursal,
            "nro_reparto": self.nro_reparto,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "ruta_original": self.ruta_original,
            "ruta_nueva": self.ruta_nueva,
            "estado": self.estado,
            "guias_encontradas": self.guias_encontradas,
            "guias_faltantes": self.guias_faltantes,
            "guias_no_entregadas": self.guias_no_entregadas,
            "resolucion_guias_faltantes": self.resolucion_guias_faltantes,
            "guias_sin_firma": self.guias_sin_firma,
            "resolucion_guias_sin_firma": self.resolucion_guias_sin_firma,
            "caja_id": self.caja_id,
            "caja_codigo": self.caja.codigo if self.caja else None,
            "fecha_procesamiento": self.fecha_procesamiento.isoformat() if self.fecha_procesamiento else None
        }

class Caja(Base):
    __tablename__ = 'cajas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(100), unique=True, nullable=False)  # e.g. CAJA-101
    estado = Column(String(50), nullable=False, default="ACTIVA")  # 'ACTIVA', 'CERRADA'
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_cierre = Column(DateTime, nullable=True)

    repartos = relationship("Reparto", back_populates="caja")

    def to_dict(self):
        return {
            "id": self.id,
            "codigo": self.codigo,
            "estado": self.estado,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "fecha_cierre": self.fecha_cierre.isoformat() if self.fecha_cierre else None
        }
