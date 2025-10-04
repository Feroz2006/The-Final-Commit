import sqlite3
import hashlib
import json
from functools import wraps
from .constants import *

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def execute(self, query: str, params: tuple = None, fetch: bool = False):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            if fetch:
                return cursor.fetchall()

class AccountManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logged_in = False
        self.user_id = None
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

    def create_account(self, email: str, password: str) -> bool:
        try:
            self.db.execute(
                f"INSERT INTO {USER_TABLE} (email_id, password_hash) VALUES (?, ?)",
                (email, self._hash_password(password))
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def login(self, email: str, password: str) -> bool:
        result = self.db.execute(
            f"SELECT user_id, password_hash FROM {USER_TABLE} WHERE email_id = ?",
            (email,), fetch=True
        )
        if result and result[0][1] == self._hash_password(password):
            self.logged_in = True
            self.user_id = result[0][0]
            return True
        return False

    def logout(self):
        self.logged_in = False
        self.user_id = None

    def delete_account(self, email: str, password: str) -> bool:
        if not self.login(email, password):
            return False
        self.db.execute(
            f"DELETE FROM {USER_TABLE} WHERE email_id = ?",
            (email,)
        )
        self.logout()
        return True

class DataManager:
    def __init__(self, account_manager: AccountManager):
        self.am = account_manager
        self.db = account_manager.db
        self._initialize_db()
        self._last_order = None

    def _initialize_db(self):
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PENDING_ORDERS_TABLE} (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                order_details TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES {USER_TABLE}(user_id)
            )
            """
        )
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {COMPLETED_ORDERS_TABLE} (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
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
                item_price REAL NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )

    def staff_only(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.am.logged_in:
                return func(self, *args, **kwargs)
            else:
                return "Access Denied: Staff Only Operation"
        return wrapper

    def get_menu(self):
        rows = self.db.execute(
            f"SELECT item_id, item_name, item_price, enabled FROM {MENU_TABLE}",
            fetch=True
        )
        return [
            {
                "item_id": row[0],
                "item_name": row[1],
                "item_price": row[2],
                "enabled": bool(row[3])
            }
            for row in rows
        ]

    def create_order(self, order_json_str: str) -> dict:
        try:
            order_data = json.loads(order_json_str)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

        item_ids = []
        quantities = []
        for item in order_data:
            keys = list(item.keys())
            if len(keys) != 2:
                return {"error": "Invalid item format"}
            id_key = [k for k in keys if k.endswith('_id')]
            qty_key = [k for k in keys if k.endswith('_quantity')]
            if not id_key or not qty_key:
                return {"error": "Missing '_id' and '_quantity'"}
            item_id = item[id_key[0]]
            quantity = item[qty_key[0]]
            if not isinstance(item_id, int) or not isinstance(quantity, int):
                return {"error": "Item id and quantity must be integers"}
            item_ids.append(item_id)
            quantities.append(quantity)

        # Check availability of requested items: set for uniqueness
        placeholders = ",".join("?" for _ in item_ids)
        menu_items = self.db.execute(
            f"SELECT item_id, item_name, item_price FROM {MENU_TABLE} WHERE item_id IN ({placeholders}) AND enabled = 1",
            tuple(set(item_ids)),
            fetch=True
        )

        enabled_ids = {row[0] for row in menu_items}
        requested_ids = set(item_ids)
        if not requested_ids.issubset(enabled_ids):
            return {"error": "Some items are not available or disabled"}

        total_price = 0
        order_details = []
        for item_id, quantity in zip(item_ids, quantities):
            item = next((row for row in menu_items if row[0] == item_id), None)
            if item:
                _, name, price = item
                total_price += price * quantity
                for _ in range(quantity):
                    order_details.append({"item_id": item_id, "item_name": name, "item_price": price})

        self._last_order = {
            "user_id": None,
            "order_details": json.dumps(order_details),
            "total_price": total_price,
            "payment_link": "http://mockpaymentgateway.com/pay/12345"
        }
        return {
            "total_price": total_price,
            "payment_link": self._last_order["payment_link"],
            "order_details": order_details
        }

    def payment_complete(self) -> dict:
        if not self._last_order:
            return {"error": "No order to complete"}
        order = self._last_order
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO {PENDING_ORDERS_TABLE} (user_id, order_details) VALUES (?, ?)",
                (order["user_id"], order["order_details"])
            )
            order_id = cursor.lastrowid
            conn.commit()
        self._last_order = None
        return {
            "order_id": order_id,
            "total_price": order["total_price"],
            "items_ordered": json.loads(order["order_details"]),
        }

    @staff_only
    def get_pending_orders(self):
        rows = self.db.execute(
            f"SELECT order_id, order_details FROM {PENDING_ORDERS_TABLE}",
            fetch=True
        )
        return [
            {
                "order_id": row[0],
                "order_details": json.loads(row[1])
            }
            for row in rows
        ]

    @staff_only
    def set_order_complete(self, order_id: int, status: bool):
        row = self.db.execute(
            f"SELECT user_id, order_details FROM {PENDING_ORDERS_TABLE} WHERE order_id = ?",
            (order_id,), fetch=True
        )
        if not row:
            return "Order not found"
        user_id, order_details = row[0]
        self.db.execute(
            f"DELETE FROM {PENDING_ORDERS_TABLE} WHERE order_id = ?",
            (order_id,)
        )
        if status:
            self.db.execute(
                f"INSERT INTO {COMPLETED_ORDERS_TABLE} (order_id, user_id, order_details) VALUES (?, ?, ?)",
                (order_id, user_id, order_details)
            )
        return self.get_pending_orders()

    @staff_only
    def get_completed_orders(self):
        rows = self.db.execute(
            f"SELECT order_id, order_details FROM {COMPLETED_ORDERS_TABLE}",
            fetch=True
        )
        return [
            {
                "order_id": row[0],
                "order_details": json.loads(row[1])
            }
            for row in rows
        ]

    @staff_only
    def add_menu_item(self, item_name: str, price: float):
        self.db.execute(
            f"INSERT INTO {MENU_TABLE} (item_name, item_price, enabled) VALUES (?, ?, 1)",
            (item_name, price)
        )
        return "Menu item added"

    @staff_only
    def remove_menu_item(self, item_id: int):
        self.db.execute(
            f"DELETE FROM {MENU_TABLE} WHERE item_id = ?",
            (item_id,)
        )
        return "Menu item removed"

    @staff_only
    def modify_menu_item(self, item_id: int, new_price: float = None, enabled: bool = None):
        if new_price is not None:
            self.db.execute(
                f"UPDATE {MENU_TABLE} SET item_price = ? WHERE item_id = ?",
                (new_price, item_id)
            )
        if enabled is not None:
            self.db.execute(
                f"UPDATE {MENU_TABLE} SET enabled = ? WHERE item_id = ?",
                (int(enabled), item_id)
            )
        return "Menu item updated"


