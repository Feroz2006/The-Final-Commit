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

    pending_orders = []
    completed_orders = []

    def do_get_menu(self, arg):
        """Get and display the current menu"""
        menu_data = json.loads(send("Get Menu"))
        headers = ["item_id", "item_name", "item_price", "available"]
        rows = [[item["item_id"], item["item_name"], item["item_price"], "Yes" if item["enabled"] else "No"]
                for item in menu_data if item["enabled"]]
        print(tabulate(rows, headers=headers, tablefmt="grid"))

    def do_send_order(self, arg):
        """Create a new order interactively."""
        send("Create Order")
        order_items = []
        print("Enter your order (item_id and quantity). Type 'done' when finished.")
        while True:
            item_id = input("Enter item_id or 'done': ").strip()
            if item_id.lower() == 'done':
                break
            try:
                quantity = int(input("Enter quantity: ").strip())
            except ValueError:
                print("Invalid quantity, please enter a number.")
                continue
            order_items.append((item_id, quantity))

        if not order_items:
            print("No items ordered. Exiting.")
            return

        total_price, payment_link = self._send_order_to_backend(order_items)

        print("\nOrder Summary:")
        table_data = [(item_id, qty) for item_id, qty in order_items]
        print(tabulate(table_data, headers=["Item ID", "Quantity"], tablefmt="grid"))
        print(f"\nTotal Price: ${total_price}")
        print(f"Please proceed for payment: {payment_link}")

        proceed_payment = input("Have you completed the payment using the above link? (y/n): ").strip().lower()
        if proceed_payment == 'y':
            response = self._send_payment_complete_to_backend()
            print(response)
        else:
            print("Payment not completed. Order not confirmed.")

    def _send_order_to_backend(self, order_items):
        total_price = sum(qty * 10 for _, qty in order_items)
        payment_link = "http://mockpaymentgateway.com/pay/12345"
        return total_price, payment_link

    def _send_payment_complete_to_backend(self):
        return "Payment confirmation received by backend."

    def do_view_orders(self, arg):
        """View all pending orders"""
        if self.pending_orders:
            print("Pending Orders:")
            self._display_orders(self.pending_orders)
        else:
            print("No pending orders at the moment.")

    def do_complete(self, arg):
        """Complete an order by its order ID. Usage: complete [order_id]"""
        try:
            order_id = int(arg.strip())
        except ValueError:
            print("Please provide a valid order ID.")
            return
        order = next((o for o in self.pending_orders if o["order_id"] == order_id), None)
        if order:
            self.completed_orders.append(order)
            self.pending_orders = [o for o in self.pending_orders if o["order_id"] != order_id]
            print(f"Order {order_id} marked as completed.\n")
            print("Updated Pending Orders:")
            self.do_view_orders('')
        else:
            print(f"No pending order found with ID: {order_id}")

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
        # Do nothing on empty input line
        pass

if __name__ == "__main__":
    client.connect(ADDR)
    Cli().cmdloop()
