# persistence/repository.py - Abstraction + SQLite implementation for v1.2
# SCOPE: video versions, operation logs, publications - source of truth is DB, in-memory is cache only if needed
# SQLite as local/dev backend, migration path to Postgres clear without redesign

import sqlite3
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

# === INTERFACE ===

class PersistenceRepository(ABC):
    @abstractmethod
    def init_schema(self): ...
    
    @abstractmethod
    def create_operation_log(self, log: Dict) -> Dict: ...
    
    @abstractmethod
    def list_operation_history(self, video_id: str) -> List[Dict]: ...
    
    @abstractmethod
    def get_operation_log(self, operation_id: str) -> Optional[Dict]: ...
    
    @abstractmethod
    def create_or_update_video_version(self, video_id: str, current_version: str, story_id: Optional[str] = None) -> Dict: ...
    
    @abstractmethod
    def get_video_version(self, video_id: str) -> Optional[Dict]: ...
    
    @abstractmethod
    def list_video_versions(self) -> List[Dict]: ...
    
    @abstractmethod
    def create_publication(self, publication: Dict) -> Dict: ...
    
    @abstractmethod
    def update_publication(self, publication_id: str, updates: Dict) -> Optional[Dict]: ...
    
    @abstractmethod
    def get_publication(self, publication_id: str) -> Optional[Dict]: ...
    
    @abstractmethod
    def list_publications(self, video_id: Optional[str] = None) -> List[Dict]: ...
    
    @abstractmethod
    def health_check(self) -> bool: ...

# === SQLITE IMPLEMENTATION ===

class SQLiteRepository(PersistenceRepository):
    def __init__(self, db_path: str = "./data/video_agent.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = None
        self._init_connection()
    
    def _init_connection(self):
        # Single connection with check_same_thread=False + lock for single-bot process safety
        # Parameterized SQL only - no string interpolation for values
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.row_factory = sqlite3.Row
    
    def init_schema(self):
        with self._lock:
            cur = self._conn.cursor()
            # operation_logs table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    operation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    parent_version TEXT,
                    new_version TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    parsed_value TEXT,
                    generated_prompt TEXT,
                    preview_reference TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_operation_logs_video_id ON operation_logs(video_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_operation_logs_timestamp ON operation_logs(timestamp);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_operation_logs_user_id ON operation_logs(user_id);")
            
            # video_versions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS video_versions (
                    video_id TEXT PRIMARY KEY,
                    story_id TEXT,
                    current_version TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_video_versions_story_id ON video_versions(story_id);")
            
            # active Telegram video state - survives process restarts because it lives in the persistent DB
            cur.execute("""
                CREATE TABLE IF NOT EXISTS active_videos (
                    user_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    bytes INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_active_videos_updated_at ON active_videos(updated_at);")
            
            # publications table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS publications (
                    publication_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    story_id TEXT NOT NULL,
                    platforms TEXT NOT NULL,
                    state TEXT NOT NULL,
                    receipts TEXT,
                    attempts TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_publications_video_id ON publications(video_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_publications_state ON publications(state);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_publications_created_at ON publications(created_at);")
    
    def create_operation_log(self, log: Dict) -> Dict:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO operation_logs 
                (operation_id, user_id, video_id, timestamp, parent_version, new_version, operation_type, parsed_value, generated_prompt, preview_reference, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log["operation_id"],
                log["user_id"],
                log["video_id"],
                log["timestamp"],
                log.get("parent_version"),
                log["new_version"],
                log["operation_type"],
                log.get("parsed_value"),
                log.get("generated_prompt"),
                log["preview_reference"],
                log.get("status", "PENDING_PREVIEW")
            ))
            return log
    
    def list_operation_history(self, video_id: str) -> List[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM operation_logs WHERE video_id = ? ORDER BY timestamp ASC", (video_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    
    def get_operation_log(self, operation_id: str) -> Optional[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM operation_logs WHERE operation_id = ?", (operation_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    
    def create_or_update_video_version(self, video_id: str, current_version: str, story_id: Optional[str] = None) -> Dict:
        with self._lock:
            cur = self._conn.cursor()
            # Upsert
            cur.execute("""
                INSERT INTO video_versions (video_id, story_id, current_version, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(video_id) DO UPDATE SET
                    current_version = excluded.current_version,
                    story_id = COALESCE(excluded.story_id, video_versions.story_id),
                    updated_at = datetime('now')
            """, (video_id, story_id, current_version))
            return self.get_video_version(video_id)
    
    def get_video_version(self, video_id: str) -> Optional[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM video_versions WHERE video_id = ?", (video_id,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                # Also fetch history count
                cur.execute("SELECT COUNT(*) as cnt FROM operation_logs WHERE video_id = ?", (video_id,))
                d["history_count"] = cur.fetchone()["cnt"]
                return d
            return None
    
    def list_video_versions(self) -> List[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM video_versions ORDER BY updated_at DESC")
            return [dict(r) for r in cur.fetchall()]
    
    def create_publication(self, publication: Dict) -> Dict:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO publications
                (publication_id, video_id, story_id, platforms, state, receipts, attempts, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                publication["publication_id"],
                publication["video_id"],
                publication["story_id"],
                json.dumps(publication["platforms"]),
                publication["state"],
                json.dumps(publication.get("receipts", {})),
                json.dumps(publication.get("attempts", [])),
                publication["created_at"]
            ))
            return publication
    
    def update_publication(self, publication_id: str, updates: Dict) -> Optional[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            # Build dynamic update with parameterized SQL
            set_clauses = []
            values = []
            for k, v in updates.items():
                if k in ("platforms", "receipts", "attempts"):
                    set_clauses.append(f"{k} = ?")
                    values.append(json.dumps(v))
                elif k in ("state", "video_id", "story_id"):
                    set_clauses.append(f"{k} = ?")
                    values.append(v)
                # Ignore unknown keys
            if not set_clauses:
                return self.get_publication(publication_id)
            set_clauses.append("updated_at = datetime('now')")
            query = f"UPDATE publications SET {', '.join(set_clauses)} WHERE publication_id = ?"
            values.append(publication_id)
            cur.execute(query, tuple(values))
            return self.get_publication(publication_id)
    
    def get_publication(self, publication_id: str) -> Optional[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM publications WHERE publication_id = ?", (publication_id,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                # Parse JSON fields
                try:
                    d["platforms"] = json.loads(d["platforms"])
                except:
                    pass
                try:
                    d["receipts"] = json.loads(d["receipts"]) if d["receipts"] else {}
                except:
                    d["receipts"] = {}
                try:
                    d["attempts"] = json.loads(d["attempts"]) if d["attempts"] else []
                except:
                    d["attempts"] = []
                return d
            return None
    
    def list_publications(self, video_id: Optional[str] = None) -> List[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            if video_id:
                cur.execute("SELECT * FROM publications WHERE video_id = ? ORDER BY created_at DESC", (video_id,))
            else:
                cur.execute("SELECT * FROM publications ORDER BY created_at DESC")
            rows = cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["platforms"] = json.loads(d["platforms"])
                except:
                    pass
                try:
                    d["receipts"] = json.loads(d["receipts"]) if d["receipts"] else {}
                except:
                    d["receipts"] = {}
                try:
                    d["attempts"] = json.loads(d["attempts"]) if d["attempts"] else []
                except:
                    d["attempts"] = []
                result.append(d)
            return result
    
    def set_active_video(self, user_id: str, video_id: str, path: str, sha256: str, bytes: int) -> Dict:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO active_videos (user_id, video_id, path, sha256, bytes, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    video_id = excluded.video_id,
                    path = excluded.path,
                    sha256 = excluded.sha256,
                    bytes = excluded.bytes,
                    updated_at = datetime('now')
            """, (str(user_id), str(video_id), path, sha256, int(bytes)))
            return self.get_active_video(str(user_id))

    def get_active_video(self, user_id: str) -> Optional[Dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM active_videos WHERE user_id = ?", (str(user_id),))
            row = cur.fetchone()
            return dict(row) if row else None

    def clear_active_video(self, user_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM active_videos WHERE user_id = ?", (str(user_id),))

    def health_check(self) -> bool:
        try:
            with self._lock:
                cur = self._conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                # Check tables exist
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('operation_logs','video_versions','active_videos','publications')")
                tables = cur.fetchall()
                return len(tables) == 4
        except Exception:
            return False

# Factory - abstraction allows future Postgres implementation without domain redesign
def get_repository(db_path: Optional[str] = None) -> PersistenceRepository:
    # For v1.2: SQLite local/dev
    # Future: if DATABASE_URL env starts with postgres://, return PostgresRepository
    # Migration path documented in DEPLOYMENT.md
    path = db_path or os.getenv("DATABASE_PATH", "./data/video_agent.db")
    return SQLiteRepository(db_path=path)
