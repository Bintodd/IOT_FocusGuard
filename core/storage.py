"""
FocusGuard Storage Module
Menyimpan dan mengelola riwayat sesi belajar dalam format JSON terstruktur.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("FocusGuard.Storage")


class SessionStorage:
    """Mengelola penyimpanan file riwayat sesi FocusGuard."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def load_all_sessions(self) -> List[Dict[str, Any]]:
        """Membaca semua rekaman sesi dari disk."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Gagal memuat riwayat sesi: {e}")
            return []

    def save_session(self, session_record: Dict[str, Any]) -> bool:
        """Menyimpan satu sesi baru ke file riwayat."""
        try:
            sessions = self.load_all_sessions()
            # Cek apakah ID sesi sudah ada (update atau append)
            existing_idx = next(
                (i for i, s in enumerate(sessions) if s.get("session_id") == session_record.get("session_id")),
                None
            )
            if existing_idx is not None:
                sessions[existing_idx] = session_record
            else:
                sessions.append(session_record)

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
            logger.info(f"Sesi {session_record.get('session_id')} berhasil disimpan.")
            return True
        except Exception as e:
            logger.error(f"Gagal menyimpan sesi: {e}")
            return False

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Mencari sesi berdasarkan ID uniknya."""
        sessions = self.load_all_sessions()
        for s in sessions:
            if s.get("session_id") == session_id:
                return s
        return None

    def clear_all_sessions(self) -> bool:
        """Menghapus seluruh riwayat log sesi belajar."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            logger.info("Seluruh riwayat sesi berhasil dihapus.")
            return True
        except Exception as e:
            logger.error(f"Gagal menghapus riwayat sesi: {e}")
            return False
