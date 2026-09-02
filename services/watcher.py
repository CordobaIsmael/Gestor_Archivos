import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import os

from config.settings import settings, get_persisted_paths
from services.db import SessionLocal
from core.organizer import process_incoming_folders, find_folders_with_pdfs

class AutoScanWatcher:
    def __init__(self, check_interval_seconds: float = 4.0):
        self.check_interval = check_interval_seconds
        self.enabled = True
        self._thread = None
        self._stop_event = threading.Event()
        self.last_check = None
        self.last_processed_count = 0
        self.is_processing = False
        self._file_sizes_snapshot = {}

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AutoScanWatcherThread")
            self._thread.start()
            print("AutoScanWatcher: Servicio de vigilancia en tiempo real iniciado.")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        print("AutoScanWatcher: Servicio detenido.")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._thread.is_alive() if self._thread else False,
            "enabled": self.enabled,
            "is_processing": self.is_processing,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_processed_count": self.last_processed_count
        }

    def _is_folder_settled(self, folder: Path) -> bool:
        """
        Verifies that files inside folder are not currently being written by a scanner
        by checking that their sizes are stable over 1.5 seconds.
        """
        try:
            pdfs = list(folder.glob("*.pdf"))
            if not pdfs:
                return False
            
            # Record sizes now
            current_sizes = {str(p): p.stat().st_size for p in pdfs if p.exists()}
            time.sleep(1.2)
            # Record sizes after 1.2s
            new_sizes = {str(p): p.stat().st_size for p in pdfs if p.exists()}
            
            # Check if sizes match and no file is 0 bytes (still opening)
            for path_str, size in current_sizes.items():
                if size == 0 or new_sizes.get(path_str) != size:
                    return False
            return True
        except Exception:
            return False

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                if self.enabled:
                    self.last_check = datetime.utcnow()
                    paths = get_persisted_paths()
                    entrada_path = Path(paths.get("entrada_path", settings.ENTRADA))
                    salida_path = Path(paths.get("salida_path", settings.SALIDA))
                    modo_hist = paths.get("modo_historico", False)
                    
                    if entrada_path.exists() and entrada_path.is_dir():
                        folders = find_folders_with_pdfs(entrada_path)
                        
                        # If folders found, verify they are settled (scanner finished writing)
                        ready_folders = []
                        for f in folders:
                            if self._is_folder_settled(f):
                                ready_folders.append(f)
                                
                        if ready_folders:
                            self.is_processing = True
                            print(f"AutoScanWatcher: Detectadas {len(ready_folders)} carpetas listas para procesar...")
                            
                            with SessionLocal() as db:
                                res = process_incoming_folders(
                                    db=db,
                                    custom_path=entrada_path,
                                    custom_salida=salida_path,
                                    modo_historico=modo_hist
                                )
                                total = len(res.get("organizados", [])) + len(res.get("revision", []))
                                self.last_processed_count = total
                                if total > 0:
                                    print(f"AutoScanWatcher: Auto-procesados {total} repartos.")
                                    
                            self.is_processing = False
                            
            except Exception as e:
                print(f"AutoScanWatcher Error: {e}")
                self.is_processing = False
                
            # Wait for next cycle
            self._stop_event.wait(self.check_interval)

# Global singleton watcher instance
watcher_instance = AutoScanWatcher()
