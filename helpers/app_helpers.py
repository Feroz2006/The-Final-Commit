import sqlite3
import hashlib
import json
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
        self.user_id: Optional[int] = None
        self.is_staff: bool = False
        self._initialize_db()

    def _initialize_db(self):
        self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {USER_TABLE} (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_staff BOOLEAN NOT NULL DEFAULT 0
            )
            """
        )
        
    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def create_account(self, email_id: str, password: str, is_staff: bool=False) -> bool:
        password_hash = self._hash_password(password)
        try:
            self.db.execute(
                f"INSERT INTO {USER_TABLE} (email_id, password_hash, is_staff) VALUES (?, ?, ?)",
                (email_id, password_hash, int(is_staff))
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def login(self, email_id: str, password: str) -> bool:
        password_hash = self._hash_password(password)
        result = self.db.execute(
            f"SELECT user_id, password_hash, is_staff FROM {USER_TABLE} WHERE email_id = ?",
            (email_id,), fetch=True
        )
        if result and result[0][1] == password_hash:
            self.logged_in = True
            self.user_id = result[0][0]
            self.is_staff = bool(result[0][2])
            return True
        return False

    def logout(self):
        self.logged_in = False
        self.user_id = None
        self.is_staff = False

    def delete_account(self, email_id: str, password: str) -> bool:
        if not self.login(email_id, password):
            return False
        self.db.execute(
            f"DELETE FROM {USER_TABLE} WHERE email_id = ?",
            (email_id,)
        )
        self.logout()
        return True


class DataManager:
    def __init__(self, account_manager: AccountManager):
        self.am = account_manager  # will check permissions
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
                item_price REAL NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )

    def staff_only(func):
        def wrapper(self, *args, **kwargs):
            if self.am.logged_in and self.am.is_staff:
                return func(self, *args, **kwargs)
            else:
                return "Access Denied: Staff Only Operation"
        return wrapper

    def get_menu(self):
        """Return list of menu items, including disabled ones."""
        rows = self.db.execute(
            f"SELECT item_id, item_name, item_price, enabled FROM {MENU_TABLE}",
            fetch=True
        )
        menu = []
        for item_id, name, price, enabled in rows:
            menu.append({
                "item_id": item_id,
                "item_name": name,
                "item_price": price,
                "enabled": bool(enabled)
            })
        return menu

    def create_order(self, order_json_str: str) -> dict:
        """Create an order from JSON string. Validate items enabled, calculate total."""
        if not self.am.logged_in:
            return {"error": "User must be logged in to create order"}

        try:
            order_data = json.loads(order_json_str)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

        # Validate items and quantities
        item_ids = []
        quantities = []
        for item in order_data:
            # Extract item id and quantity from keys like item1_id, item1_quantity etc
            keys = list(item.keys())
            if len(keys) != 2:
                return {"error": "Invalid item format"}
            id_key = [k for k in keys if k.endswith('_id')]
            qty_key = [k for k in keys if k.endswith('_quantity')]
            if not id_key or not qty_key:
                return {"error": "Item keys must include '_id' and '_quantity'"}
            item_id = item[id_key[0]]
            quantity = item[qty_key[0]]
            if not isinstance(item_id, int) or not isinstance(quantity, int):
                return {"error": "Item id and quantity must be integers"}
            item_ids.append(item_id)
            quantities.append(quantity)

        # Check if all item_ids exist and enabled
        placeholders = ",".join("?" for _ in item_ids)
        menu_items = self.db.execute(
            f"SELECT item_id, item_name, item_price FROM {MENU_TABLE} WHERE item_id IN ({placeholders}) AND enabled = 1",
            tuple(item_ids),
            fetch=True
        )
        menu_item_ids = [row[0] for row in menu_items]

        if sorted(menu_item_ids) != sorted(item_ids):
            return {"error": "Some items are not available or disabled"}

        # Calculate total price
        total_price = 0
        order_details = []
        for i, (item_id, quantity) in enumerate(zip(item_ids, quantities)):
            item = next((row for row in menu_items if row[0] == item_id), None)
            if item:
                _, name, price = item
                item_price = price * quantity
                total_price += item_price
                for _ in range(quantity):
                    order_details.append({"item_id": item_id, "item_name": name, "item_price": price})

        # Insert into pending orders
        self.db.execute(
            f"INSERT INTO {PENDING_ORDERS_TABLE} (user_id, order_details) VALUES (?, ?)",
            (self.am.user_id, json.dumps(order_details))
        )

        payment_link = "http://mockpaymentgateway.com/pay/12345"  # mocked payment link

        return {"total_price": total_price, "payment_link": payment_link}

    def payment_complete(self) -> dict:
        """Called when payment completes to confirm order."""
        if not self.am.logged_in:
            return {"error": "User must be logged in"}

        # Fetch last inserted pending order for this user as the one to confirm
        result = self.db.execute(
            f"""
            SELECT order_id, order_details FROM {PENDING_ORDERS_TABLE} 
            WHERE user_id = ? ORDER BY order_id DESC LIMIT 1
            """,
            (self.am.user_id,), fetch=True
        )
        if not result:
            return {"error": "No pending order found"}

        order_id, order_details_json = result[0]

        # Prepare receipt info
        order_details = json.loads(order_details_json)

        return {
            "order_id": order_id,
            "total_price": sum(item["item_price"] for item in order_details),
            "items_ordered": order_details
        }

    @staff_only
    def get_pending_orders(self):
        """Return list of pending orders for staff."""
        rows = self.db.execute(
            f"SELECT order_id, order_details FROM {PENDING_ORDERS_TABLE}",
            fetch=True
        )
        orders = []
        for order_id, order_details_json in rows:
            orders.append({
                "order_id": order_id,
                "order_details": json.loads(order_details_json)
            })
        return orders

    @staff_only
    def set_order_complete(self, order_id: int, status: bool):
        """Mark a pending order complete, moving it to completed orders."""
        pending_order = self.db.execute(
            f"SELECT user_id, order_details FROM {PENDING_ORDERS_TABLE} WHERE order_id = ?",
            (order_id,), fetch=True
        )
        if not pending_order:
            return "Order not found"
        user_id, order_details = pending_order[0]

        # Remove from pending
        self.db.execute(
            f"DELETE FROM {PENDING_ORDERS_TABLE} WHERE order_id = ?",
            (order_id,)
        )

        # Add to completed if status is True
        if status:
            self.db.execute(
                f"INSERT INTO {COMPLETED_ORDERS_TABLE} (order_id, user_id, order_details) VALUES (?, ?, ?)",
                (order_id, user_id, order_details)
            )

        # Return updated pending orders
        return self.get_pending_orders()

    @staff_only
    def get_completed_orders(self):
        rows = self.db.execute(
            f"SELECT order_id, order_details FROM {COMPLETED_ORDERS_TABLE}",
            fetch=True
        )
        orders = []
        for order_id, order_details_json in rows:
            orders.append({
                "order_id": order_id,
                "order_details": json.loads(order_details_json)
            })
        return orders

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