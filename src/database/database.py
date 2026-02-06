"""
Database component for OneLight


TABLE: devices
    id:
    name:
    model:
    owner:

TABLE: users
    id:
    username:
    email:
    password_hash:
"""

import logging
from pathlib import Path
from sqlite3 import dbapi2 as sqlite3
from typing import Optional

from quart import Quart, g

from constants import ONELIGHT_LOG_NAME


logger = logging.getLogger(ONELIGHT_LOG_NAME)


DATABASE = "DATABASE"
ONELIGHT_DB_DB = "onelight-db.db"
INIT_SCHEMA_PATH = "onelight_init_schema.sql"
SQLITE_DB = "sqlite_db"
USERS_TABLE = "users"
DEVICES_TABLE = "devices"


class OneLightDB:
    def __init__(self, app: Quart, overwrite_if_exists: bool = False):
        self.app = app
        self.root = self.app.root_path
        app.config.update({DATABASE: Path(self.root) / ONELIGHT_DB_DB})

        self.init_db(overwrite_if_exists=overwrite_if_exists)

    def init_db(self, overwrite_if_exists: bool = False) -> None:
        if (self.db_file_exists() and overwrite_if_exists) or not self.db_file_exists():
            db = self._connect_db()
            with open(Path(self.root) / INIT_SCHEMA_PATH, mode="r") as file_:
                db.cursor().executescript(file_.read())
            db.commit()
            logger.debug("Database initialized")
            return
        logger.debug("Database not initialized")

    def db_file_exists(self) -> bool:
        db_file = self.app.config[DATABASE]
        if Path(db_file).exists():
            logger.debug(f"DB file exists ('{db_file}')")
            return True
        logger.debug(f"DB file does not exist ('{db_file}')")
        return False

    def _connect_db(self):
        engine = sqlite3.connect(self.app.config[DATABASE])
        engine.row_factory = sqlite3.Row
        return engine

    def _get_db(self):
        if not hasattr(g, SQLITE_DB):
            g.sqlite_db = self._connect_db()
        return g.sqlite_db

    def username_in_use(self, username: str) -> bool:
        db = self._get_db()
        query = "SELECT COUNT(*) FROM users WHERE username = ?"
        cur = db.execute(query, (username,))
        res = cur.fetchone()
        return res[0] > 0

    def email_in_use(self, email: str) -> bool:
        db = self._get_db()
        query = "SELECT COUNT(*) FROM users WHERE email = ?"
        cur = db.execute(query, (email,))
        res = cur.fetchone()
        return res[0] > 0

    def fetch_password_hash_for_username(self, username: str) -> Optional[str]:
        db = self._get_db()
        query = "SELECT password_hash FROM users WHERE username = ? LIMIT 1"
        cur = db.execute(query, (username,))
        res = cur.fetchone()
        if not res:
            return None
        return res[0]

    def fetch_user_by_username(self, username: str) -> Optional[dict]:
        """Return user record as a dict for given username, or None if not found."""
        db = self._get_db()
        query = "SELECT id, username, email FROM users WHERE username = ? LIMIT 1"
        cur = db.execute(query, (username,))
        res = cur.fetchone()
        if not res:
            return None
        # sqlite3.Row supports mapping protocol
        return dict(res)

    def add_user_account(
        self, username: str, email: str, hashed_password_str: str
    ) -> int:
        """
        Add new user account to the database.
        """
        try:
            db = self._get_db()
            cur = db.cursor()
            # Insert specific columns to allow created_at DEFAULT to apply
            stmt: str = (
                f"INSERT INTO {USERS_TABLE} (username, email, password_hash) VALUES (?, ?, ?)"
            )
            cur.execute(stmt, (username, email, hashed_password_str))
            db.commit()
            return 0
        except Exception:
            logger.exception("Exception while adding new user account!")
            return -1

    def add_smart_device(self, name: str, model: str, owner: str) -> int:
        """
        Add new smart device (each device must only have one owner)
        """
        # Backwards-compatible wrapper: attempt to resolve owner (username) to owner_id
        try:
            db = self._get_db()
            # Try to resolve owner as username -> id
            cur = db.execute(
                "SELECT id FROM users WHERE username = ? LIMIT 1", (owner,)
            )
            row = cur.fetchone()
            if row:
                owner_id = row[0]
            else:
                # If owner is not a username, and looks like an integer, try to use it
                try:
                    owner_id = int(owner)
                except Exception:
                    logger.error("add_smart_device: could not resolve owner to user id")
                    return -1
            return self.add_device(name, model, owner_id)
        except Exception:
            logger.exception("Exception while adding new smart device wrapper!")
            return -1

    def add_device(
        self,
        name: str,
        model: str,
        owner_id: int,
        ip: Optional[str] = None,
        mac: Optional[str] = None,
        provisioned: bool = False,
    ) -> int:
        """Insert a new device and return the new device id, or -1 on error."""
        try:
            db = self._get_db()
            cur = db.cursor()
            stmt = "INSERT INTO devices (name, model, owner_id, ip, mac, provisioned) VALUES (?, ?, ?, ?, ?, ?)"
            cur.execute(stmt, (name, model, owner_id, ip, mac, int(bool(provisioned))))
            db.commit()
            return cur.lastrowid
        except Exception:
            logger.exception("Exception while adding device to devices table")
            return -1

    def get_devices_for_user(self, owner_id: int):
        """Return list of device dicts owned by given user id."""
        db = self._get_db()
        query = "SELECT * FROM devices WHERE owner_id = ? ORDER BY id"
        cur = db.execute(query, (owner_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_device_by_id(self, device_id: int) -> Optional[dict]:
        db = self._get_db()
        query = "SELECT * FROM devices WHERE id = ? LIMIT 1"
        cur = db.execute(query, (device_id,))
        res = cur.fetchone()
        if not res:
            return None
        return dict(res)

    def get_device_by_ip(self, ip: str) -> Optional[dict]:
        """Find a device by IP address."""
        db = self._get_db()
        query = "SELECT * FROM devices WHERE ip = ? LIMIT 1"
        cur = db.execute(query, (ip,))
        res = cur.fetchone()
        if not res:
            return None
        return dict(res)

    def get_device_by_mac(self, mac: str) -> Optional[dict]:
        """Find a device by MAC address."""
        db = self._get_db()
        query = "SELECT * FROM devices WHERE mac = ? LIMIT 1"
        cur = db.execute(query, (mac,))
        res = cur.fetchone()
        if not res:
            return None
        return dict(res)

    def update_device_info(self, device_id: int, **fields) -> bool:
        """Update allowed device fields. Returns True on success."""
        allowed = {"name", "model", "ip", "mac", "status", "provisioned"}
        updates = []
        params = []
        for k, v in fields.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                params.append(v)
        if not updates:
            return False
        params.append(device_id)
        stmt = f"UPDATE devices SET {', '.join(updates)} WHERE id = ?"
        try:
            db = self._get_db()
            db.execute(stmt, tuple(params))
            db.commit()
            return True
        except Exception:
            logger.exception("Exception while updating device info")
            return False

    def update_device_status(
        self, device_id: int, status: str, last_seen: Optional[str] = None
    ) -> bool:
        """Convenience to update status and optionally last_seen timestamp."""
        try:
            if last_seen:
                return self.update_device_info(
                    device_id, status=status, last_seen=last_seen
                )
            return self.update_device_info(device_id, status=status)
        except Exception:
            logger.exception("Exception while updating device status")
            return False
