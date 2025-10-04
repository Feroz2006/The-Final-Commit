import sqlite3
import hashlib
from typing import Any, Optional, Tuple
from .constants import DB_PATH, USER_TABLE, PENDING_ORDERS_TABLE, COMPLETED_ORDERS_TABLE, MENU_TABLE

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def execute(self, query: str, params: Optional[Tuple[Any]] = None, fetch: bool = False) -> Optional[Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            if fetch:
                return cursor.fetchall()
            return None

class AccountManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logged_in: bool = False
        self._initialize_db()

    def _initialize_db(self):
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {USER_TABLE} (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        
    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def create_account(self, email_id: str, password: str) -> bool:
        password_hash = self._hash_password(password)
        try:
            self.db.execute(
                f"INSERT INTO {USER_TABLE} (email_id, password_hash) VALUES (?, ?)",
                (email_id, password_hash)
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def login(self, email_id: str, password: str) -> bool:
        password_hash = self._hash_password(password)
        result = self.db.execute(
            f"SELECT password_hash FROM {USER_TABLE} WHERE email_id = ?",
            (email_id,), fetch=True
        )
        if result and result[0][0] == password_hash:
            return True
        return False

    def delete_account(self, email_id: str, password: str) -> bool:
        if not self.login(email_id, password):
            return False
        self.db.execute(
            f"DELETE FROM {USER_TABLE} WHERE email_id = ?",
            (email_id,)
        )
        return True


class DataManager:
    def __init__(self, account_manager: AccountManager):
        self.am = account_manager # verify if staff is logged in, then allow staff-only operations
        self.db = account_manager.db
        self._initialize_db()

    def _initialize_db(self):
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PENDING_ORDERS_TABLE} (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_details TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES {USER_TABLE}(user_id)
            )
            """
        )
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {COMPLETED_ORDERS_TABLE} (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_details TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES {USER_TABLE}(user_id)
            )
            """
        )
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MENU_TABLE} (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                item_price DECIMAL NOT NULL,
                enabled BOOLEAN NOT NULL
            )
            """
        )
    

    def staff_only(func):
        def wrapper(self, *args, **kwargs):
            if self.am.logged_in:
                return func(self, *args, **kwargs)
            else:
                return "Access Denied: Staff Only Operation"
        return wrapper
            
    
    def add_order():
        pass
    
    
    @staff_only
    def set_order_complete():
        pass


    @staff_only
    def get_pending_orders(self):
        return self.db.execute(f"SELECT * FROM {PENDING_ORDERS_TABLE}", fetch=True)


    @staff_only
    def get_completed_orders():
        pass

    @staff_only
    def add_menu_item():
        pass

    @staff_only
    def remove_menu_item():
        pass

    @staff_only
    def modify_menu_item():
        pass


    def get_menu_items(self):
        return self.db.execute(f"SELECT * FROM {MENU_TABLE}", fetch=True)
    


    