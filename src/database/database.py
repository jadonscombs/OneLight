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


logger = logging.getLogger("onelight-app")


DATABASE = "DATABASE"
ONELIGHT_DB_DB = "onelight-db.db"
INIT_SCHEMA_PATH = "onelight_init_schema.sql"
SQLITE_DB = "sqlite_db"
USERS_TABLE = "users"
DEVICES_TABLE = "devices"


class OneLightDB:
    def __init__(
        self,
        app: Quart,
        overwrite_if_exists: bool = False
    ):
        self.app = app
        self.root = self.app.root_path
        app.config.update({
            DATABASE: Path(self.root) / ONELIGHT_DB_DB
        })

        self.init_db(overwrite_if_exists=overwrite_if_exists)


    def init_db(self, overwrite_if_exists: bool = False) -> None:
        if (
            (self.db_file_exists() and overwrite_if_exists)
            or not self.db_file_exists()
        ):
            db = self._connect_db()
            with open(Path(self.root) / INIT_SCHEMA_PATH, mode="r") as file_:
                db.cursor().executescript(file_.read())
            db.commit()
            logger.info("Database initialized")
            return
        logger.info("Database was not initialized")

    
    def db_file_exists(self) -> bool:
        db_file = self.app.config[DATABASE]
        if Path(db_file).exists():
            logger.debug(f"DB file '{db_file}' exists")
            return True
        logger.debug(f"DB file '{db_file}' does not exist")
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
        return res[0]


    def add_user_account(
        self,
        username: str,
        email: str,
        hashed_password_str: str
    ) -> int:
        """
        Add new user account to the database.
        """
        try:
            db = self._get_db()
            cur = db.cursor()
            stmt: str = (
                f"INSERT INTO {USERS_TABLE} VALUES (?, ?, ?, ?)"
            )
            cur.execute(stmt, (None, username, email, hashed_password_str))
            db.commit()
            return 0
        except Exception:
            logger.exception("Exception while adding new user account!")
            return -1


    def add_smart_device(self, name: str, model: str, owner: str) -> int:
        """
        Add new smart device (each device must only have one owner)
        """
        try:
            db = self._get_db()
            cur = db.cursor()
            stmt: str = (
                f"INSERT INTO {DEVICES_TABLE} VALUES (?, ?, ?, ?)"
            )
            cur.execute(stmt, (None, name, model, owner))
            db.commit()
            return 0
        except Exception:
            logger.exception("Exception while adding new smart device!")
            return -1
