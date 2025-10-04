import socket
import json
from helpers.constants import PORT, FORMAT, HEADER_SIZE, DISCONNECT_MESSAGE
from tabulate import tabulate
import cmd

SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def send(msg: str) -> str:
    message_encoded = msg.encode(FORMAT)
    msg_length = len(message_encoded)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER_SIZE - len(send_length))
    client.send(send_length)
    client.send(message_encoded)
    response_length = client.recv(HEADER_SIZE).decode(FORMAT)
    if response_length:
        response_length = int(response_length)
        response = client.recv(response_length).decode(FORMAT)
        return response
    return ""

class Cli(cmd.Cmd):
    intro = "Welcome to SmartServe. Type help or ? to list commands.\n"
    prompt = "SmartServe> "

    def __init__(self):
        super().__init__()
        self.logged_in = False

    def do_login(self, arg):
        """Login as staff user."""
        email = input("Enter email: ").strip()
        password = input("Enter password: ").strip()

        login_data = json.dumps({"action": "login", "email": email, "password": password})
        response_str = send(login_data)
        try:
            response = json.loads(response_str)
        except json.JSONDecodeError:
            print("Error decoding server response.")
            return

        if response.get("status") == "success":
            print("Login successful.")
            self.logged_in = True
        else:
            print("Login failed:", response.get("error", "Invalid login credentials"))

    def do_get_menu(self, arg):
        """Get and display the current menu with unavailable items at bottom"""
        raw_response = send("Get Menu")
        try:
            menu_data = json.loads(raw_response)
            if isinstance(menu_data, str):
                menu_data = json.loads(menu_data)
        except json.JSONDecodeError:
            print("Error decoding server response.")
            return
        headers = ["item_id", "item_name", "item_price", "available"]
        enabled_items = [item for item in menu_data if item["enabled"]]
        disabled_items = [item for item in menu_data if not item["enabled"]]
        rows = []
        rows.extend([[item["item_id"], item["item_name"], item["item_price"], "Yes"] for item in enabled_items])
        rows.extend([[item["item_id"], item["item_name"], item["item_price"], "No"] for item in disabled_items])
        print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))

    def _get_menu_data(self, ids_only=False):
        raw_response = send("Get Menu")
        try:
            menu_data = json.loads(raw_response)
            if isinstance(menu_data, str):
                menu_data = json.loads(menu_data)
        except json.JSONDecodeError:
            print("Error decoding server response.")
            return []

        if ids_only:
            return [item["item_id"] for item in menu_data if item["enabled"]]
        return menu_data

    def do_send_order(self, arg):
        """Create a new order using item ID and quantity."""
        order_items = []
        available_ids = self._get_menu_data(ids_only=True)
        print("Enter your order (item_id and quantity). Type 'done' when finished.")
        while True:
            item_id_input = input("Enter item_id or 'done': ").strip()
            if item_id_input.lower() == 'done':
                break
            if not item_id_input.isdigit():
                print("Invalid id, please enter a proper number.")
                continue
            item_id = int(item_id_input)
            if item_id not in available_ids:
                print("Invalid item_id, item not available.")
                continue
            try:
                quantity = int(input("Enter quantity: ").strip())
            except ValueError:
                print("Invalid quantity, please enter a number.")
                continue
            order_items.append({"item_id": item_id, "item_quantity": quantity})

        if not order_items:
            print("No items ordered. Exiting.")
            return

        response_str = send(json.dumps(order_items))
        try:
            response = json.loads(response_str)
        except json.JSONDecodeError:
            print("Error decoding server response.")
            return

        if "error" in response:
            print("Server error:", response["error"])
            return

        total_price = response.get("total_price")
        payment_link = response.get("payment_link")
        print("\nOrder Summary:")
        for item in order_items:
            print(f"Item ID: {item['item_id']}, Quantity: {item['item_quantity']}")
        print(f"\nTotal Price: ${total_price}")
        print(f"Please proceed for payment at: {payment_link}")

        proceed_payment = input("Have you completed the payment? (y/n): ").strip().lower()
        if proceed_payment == 'y':
            payment_complete_msg = json.dumps({"payment_complete": True})
            receipt_str = send(payment_complete_msg)

            try:
                receipt = json.loads(receipt_str)
                if isinstance(receipt, str):
                    receipt = json.loads(receipt)
            except json.JSONDecodeError:
                print("Error decoding receipt from server.")
                return

            print("Payment confirmed.\nReceipt:")
            print(f"Total Price: {receipt.get('total_price', 'N/A')}")
            for item in receipt.get("items_ordered", []):
                print(f"Item ID: {item.get('item_id')}, Name: {item.get('item_name')}, Price: {item.get('item_price')}")
        else:
            print("Payment not completed. Order not confirmed.")

    def do_view_orders(self, arg):
        """View all pending orders (staff only)."""
        if not self.logged_in:
            print("You must login to view orders.")
            return
        response_str = send(json.dumps({"action": "view_pending_orders"}))
        try:
            orders = json.loads(response_str)
            if isinstance(orders, dict) and "error" in orders:
                print("Error:", orders["error"])
            elif orders:
                print("Pending Orders:")
                self._display_orders(orders)
            else:
                print("No pending orders at the moment.")
        except json.JSONDecodeError:
            print("Error decoding server response.")

    def do_complete_order(self, arg):
        """Complete an order by its order ID. Usage: complete [order_id] (staff only)."""
        if not self.logged_in:
            print("You must login to complete orders.")
            return
        try:
            order_id = int(arg.strip())
        except ValueError:
            print("Please provide a valid order ID.")
            return

        msg = json.dumps({"order_id": order_id, "status": True})
        response_str = send(msg)
        try:
            updated_orders = json.loads(response_str)
            if isinstance(updated_orders, str):
                print(updated_orders)
                return
            print(f"Order {order_id} marked as completed.\n")
            print("Updated Pending Orders:")
            self._display_orders(updated_orders)
        except json.JSONDecodeError:
            print("Error decoding server response.")

    def _display_orders(self, orders):
        table = []
        for order in orders:
            for item in order["order_details"]:
                table.append([
                    order["order_id"],
                    item["item_id"],
                    item["item_name"],
                    item["item_price"]
                ])
        headers = ["Order ID", "Item ID", "Item Name", "Item Price"]
        print(tabulate(table, headers=headers, tablefmt="fancy_grid"))

    def do_exit(self, arg):
        """Exit the CLI"""
        print("Disconnecting client and exiting...")
        send(DISCONNECT_MESSAGE)
        client.close()
        return True

    def emptyline(self):
        pass

if __name__ == "__main__":
    client.connect(ADDR)
    Cli().cmdloop()


