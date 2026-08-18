import sqlite3
import random
import os
import json
from datetime import datetime
from core.log_formatter import logger
import config

class DBManager:
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = config.DB_FILE
        else:
            self.db_path = db_path
            
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        """Initialize SQLite tables according to architectural plans."""
        logger.info(f"Initializing database at {self.db_path}")
        with self.get_connection() as conn:
            # 1. system_config table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. games table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                pan_url TEXT,
                access_password TEXT,
                extract_password TEXT,
                source_url TEXT UNIQUE,
                description TEXT,
                publish_date TEXT,
                download_links TEXT, -- JSON string representation
                crawl_status INTEGER DEFAULT 0, -- 0=pending, 1=completed, 2=needs_update, 3=dead_letter
                random_weight INTEGER,
                retry_count INTEGER DEFAULT 0,
                last_index_seen_time TEXT
            );
            """)

            # 3. game_assets table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS game_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                asset_type TEXT NOT NULL, -- 'cover' or 'content'
                local_path TEXT NOT NULL,
                original_url TEXT NOT NULL,
                md5_hash TEXT NOT NULL,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );
            """)
            
            # Create indexes on assets for quick deduplication checks
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_url ON game_assets(original_url);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_md5 ON game_assets(md5_hash);")

            # 4. wp_sync_log table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS wp_sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER UNIQUE,
                wp_post_id INTEGER NOT NULL,
                sync_status INTEGER DEFAULT 1, -- 1=synced
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );
            """)
            
            # 5. run_history table (automated run history for the run menu)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,            -- CLI command name (run/index/post/md/wp)
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_sec REAL,
                status TEXT DEFAULT 'running',   -- running/success/failed/interrupted
                summary TEXT                     -- human readable summary
            );
            """)

            # 6. md_export_log table (track games already exported as Markdown)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS md_export_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER UNIQUE,
                file_path TEXT NOT NULL,
                exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );
            """)
            
            conn.commit()
        logger.info("Database initialization completed successfully.")

    # ==========================================================
    # State Machine Variables (system_config)
    # ==========================================================
    def get_config(self, key, default=None):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM system_config WHERE key = ?;", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def set_config(self, key, value):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO system_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP;
            """, (key, str(value)))
            conn.commit()

    def get_index_scan_start_time(self):
        return self.get_config("index_scan_start_time")

    def set_index_scan_start_time(self, val):
        self.set_config("index_scan_start_time", val)

    def get_index_scan_end_time(self):
        return self.get_config("index_scan_end_time")

    def set_index_scan_end_time(self, val):
        self.set_config("index_scan_end_time", val)

    def get_index_scan_last_url(self):
        return self.get_config("index_scan_last_url")

    def set_index_scan_last_url(self, val):
        if val is None:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM system_config WHERE key = 'index_scan_last_url';")
                conn.commit()
        else:
            self.set_config("index_scan_last_url", val)

    # ==========================================================
    # Games Table Operations (Producer)
    # ==========================================================
    def find_by_source_url(self, source_url):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM games WHERE source_url = ?;", (source_url,))
            row = cur.fetchone()
            return dict(row) if row else None

    def upsert_game_producer(self, title, source_url, publish_date):
        """
        Dual-layer update check:
        If Name Check or Date Check changes, set crawl_status to 2 (needs_update).
        Else keep existing status.
        If it's a new game, set crawl_status to 0 (pending) and assign a random weight.
        """
        existing = self.find_by_source_url(source_url)
        now_str = datetime.now().isoformat()
        
        if existing:
            name_check = existing['title'] != title
            date_check = existing['publish_date'] != publish_date
            
            if name_check or date_check:
                logger.info(f"[Producer] Updating game: {title} (Status changed to NEEDS_UPDATE)")
                with self.get_connection() as conn:
                    conn.execute("""
                    UPDATE games 
                    SET title = ?, publish_date = ?, crawl_status = ?, last_index_seen_time = ?
                    WHERE id = ?;
                    """, (title, publish_date, config.CRAWL_STATUS_NEEDS_UPDATE, now_str, existing['id']))
                    conn.commit()
                return 'updated'
            else:
                # Keep last index seen time updated but don't touch crawl status
                with self.get_connection() as conn:
                    conn.execute("""
                    UPDATE games SET last_index_seen_time = ? WHERE id = ?;
                    """, (now_str, existing['id']))
                    conn.commit()
                return 'unchanged'
        else:
            random_weight = random.randint(1, 99)
            logger.info(f"[Producer] New game discovered: {title} (Status set to PENDING, Weight: {random_weight})")
            with self.get_connection() as conn:
                conn.execute("""
                INSERT INTO games (title, source_url, publish_date, crawl_status, random_weight, last_index_seen_time)
                VALUES (?, ?, ?, ?, ?, ?);
                """, (title, source_url, publish_date, config.CRAWL_STATUS_PENDING, random_weight, now_str))
                conn.commit()
            return 'inserted'

    # ==========================================================
    # Games Table Operations (Consumer)
    # ==========================================================
    def get_pending_or_needs_update_tasks(self, limit):
        """Retrieve consumer tasks sorted by random weight (anti-pattern detection)."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT * FROM games 
            WHERE crawl_status IN (?, ?)
            ORDER BY random_weight ASC 
            LIMIT ?;
            """, (config.CRAWL_STATUS_PENDING, config.CRAWL_STATUS_NEEDS_UPDATE, limit))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def update_game_consumer(self, game_id, pan_url, access_password, extract_password, description, download_links, crawl_status=1):
        """Update game with detailed extracted info from Consumer."""
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE games
            SET pan_url = ?, access_password = ?, extract_password = ?, description = ?, download_links = ?, crawl_status = ?, retry_count = 0
            WHERE id = ?;
            """, (pan_url, access_password, extract_password, description, json.dumps(download_links), crawl_status, game_id))
            conn.commit()

    def update_crawl_status(self, game_id, crawl_status):
        with self.get_connection() as conn:
            conn.execute("UPDATE games SET crawl_status = ? WHERE id = ?;", (crawl_status, game_id))
            conn.commit()

    def increment_retry_count(self, game_id):
        """Increment failure counter and transition to DEAD_LETTER if it exceeds limit."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT retry_count FROM games WHERE id = ?;", (game_id,))
            row = cur.fetchone()
            if not row:
                return
            
            new_count = row[0] + 1
            if new_count >= config.MAX_RETRY_COUNT:
                logger.error(f"[Consumer] Game ID {game_id} reached max retries ({config.MAX_RETRY_COUNT}). Marking as DEAD_LETTER.")
                conn.execute("UPDATE games SET retry_count = ?, crawl_status = ? WHERE id = ?;", (new_count, config.CRAWL_STATUS_DEAD_LETTER, game_id))
            else:
                logger.warn(f"[Consumer] Game ID {game_id} retry count incremented to {new_count}.")
                conn.execute("UPDATE games SET retry_count = ? WHERE id = ?;", (new_count, game_id))
            conn.commit()

    # ==========================================================
    # Game Assets Table Operations
    # ==========================================================
    def get_asset_by_url(self, original_url):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM game_assets WHERE original_url = ?;", (original_url,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_asset_by_md5(self, md5_hash):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM game_assets WHERE md5_hash = ? LIMIT 1;", (md5_hash,))
            row = cur.fetchone()
            return dict(row) if row else None

    def save_game_asset(self, game_id, asset_type, local_path, original_url, md5_hash, file_size=None, width=None, height=None):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO game_assets (game_id, asset_type, local_path, original_url, md5_hash, file_size, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (game_id, asset_type, local_path, original_url, md5_hash, file_size, width, height))
            conn.commit()

    def get_game_assets(self, game_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM game_assets WHERE game_id = ?;", (game_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    # ==========================================================
    # WordPress Sync Log Table Operations
    # ==========================================================
    def get_sync_log(self, game_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM wp_sync_log WHERE game_id = ?;", (game_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def save_sync_log(self, game_id, wp_post_id):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO wp_sync_log (game_id, wp_post_id)
            VALUES (?, ?)
            ON CONFLICT(game_id) DO UPDATE SET wp_post_id=excluded.wp_post_id, synced_at=CURRENT_TIMESTAMP;
            """, (game_id, wp_post_id))
            conn.commit()

    def get_completed_tasks_for_sync(self, limit):
        """Retrieve completed games that haven't been synchronized to WP yet."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT g.* FROM games g
            LEFT JOIN wp_sync_log l ON g.id = l.game_id
            WHERE g.crawl_status = ? AND l.id IS NULL
            LIMIT ?;
            """, (config.CRAWL_STATUS_COMPLETED, limit))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    # ==========================================================
    # Run History Table Operations (automated run history)
    # ==========================================================
    def start_run_history(self, command):
        """Insert a running record and return its id."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO run_history (command, started_at, status) VALUES (?, ?, 'running');",
                (command, datetime.now().isoformat(timespec="seconds"))
            )
            conn.commit()
            return cur.lastrowid

    def finish_run_history(self, run_id, status, summary=""):
        """Close a running record with duration, status and summary."""
        finished_at = datetime.now().isoformat(timespec="seconds")
        duration_sec = None
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT started_at FROM run_history WHERE id = ?;", (run_id,))
            row = cur.fetchone()
            if row:
                try:
                    started = datetime.fromisoformat(row[0])
                    duration_sec = round((datetime.now() - started).total_seconds(), 1)
                except (ValueError, TypeError):
                    duration_sec = None
            cur.execute(
                "UPDATE run_history SET finished_at = ?, duration_sec = ?, status = ?, summary = ? WHERE id = ?;",
                (finished_at, duration_sec, status, summary, run_id)
            )
            conn.commit()

    def get_run_history(self, limit=20):
        """Retrieve the most recent run history records (newest first)."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM run_history ORDER BY id DESC LIMIT ?;", (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_status_summary(self):
        """Snapshot of table counts and game crawl status distribution (for run summary / status view)."""
        summary = {"tables": {}, "statuses": {}}
        status_names = {
            config.CRAWL_STATUS_PENDING: "pending",
            config.CRAWL_STATUS_COMPLETED: "completed",
            config.CRAWL_STATUS_NEEDS_UPDATE: "needs_update",
            config.CRAWL_STATUS_DEAD_LETTER: "dead_letter",
        }
        with self.get_connection() as conn:
            cur = conn.cursor()
            tables = [t[0] for t in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            ).fetchall()]
            for t in tables:
                count = cur.execute(f"SELECT count(*) FROM {t};").fetchone()[0]
                summary["tables"][t] = count
            if "games" in tables:
                for code, name in status_names.items():
                    summary["statuses"][name] = cur.execute(
                        "SELECT count(*) FROM games WHERE crawl_status = ?;", (code,)
                    ).fetchone()[0]
        return summary

    # ==========================================================
    # MD Export Log Table Operations
    # ==========================================================
    def get_md_export_log(self, game_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM md_export_log WHERE game_id = ?;", (game_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def save_md_export_log(self, game_id, file_path):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO md_export_log (game_id, file_path)
            VALUES (?, ?)
            ON CONFLICT(game_id) DO UPDATE SET file_path=excluded.file_path, exported_at=CURRENT_TIMESTAMP;
            """, (game_id, file_path))
            conn.commit()

    def get_unexported_completed_games(self, limit=None):
        """Retrieve completed games not yet exported as Markdown (or whose file is gone)."""
        query = """
        SELECT g.* FROM games g
        LEFT JOIN md_export_log e ON g.id = e.game_id
        WHERE g.crawl_status = ? AND (e.id IS NULL OR e.file_path IS NULL)
        """
        params = [config.CRAWL_STATUS_COMPLETED]
        if limit:
            query += " LIMIT ?;"
            params.append(limit)
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
