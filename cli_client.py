import click
import socket
import requests # type: ignore
from helpers.constants import PORT, FORMAT, HEADER_SIZE, DISCONNECT_MESSAGE
from tabulate import tabulate # type: ignore


SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT) # giving port 0 lets the OS pick an available port
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(ADDR)

def send(msg: str) -> str:
    message_encoded = msg.encode(FORMAT)
    msg_length = len(message_encoded)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER_SIZE - len(send_length)) # adding paddding to header message to make it HEADER_SIZE bytes long
    client.send(send_length)
    client.send(message_encoded)
    response_length = client.recv(HEADER_SIZE).decode(FORMAT)
    if response_length:
        response_length = int(response_length)
        response = client.recv(response_length).decode(FORMAT)
        return response
    return ""


def get_menu():
    send("Get Menu")
    @click.command()
    @click.option()
    def get_menu(server_url):
        try:
            # response = requests.get() ?
            # response.raise_for_status() ?
            # menu_data = response.json() ?
            menu_data = send("Get Menu")

            # Define table headers
            headers = ["item_id", "item_name", "item_price"]

            # errors so commenting out for now
            # # Prepare data rows from the response
            # rows = [[item[headers[0]], item[headers[1]], item[headers[2]]] for item in menu_data]

            # # Print the table to terminal
            # click.echo(tabulate(rows, headers=headers, tablefmt="grid"))

        except requests.RequestException as e:
            click.echo(f"Failed to get menu from server: {e}")



def send_order_to_backend(order_items):
    total_price = sum(qty * 10 for _, qty in order_items)
    payment_link = "http://mockpaymentgateway.com/pay/12345"
    return total_price, payment_link

def send_payment_complete_to_backend():
    # Mock backend confirmation on payment
    return "Payment confirmation received by backend."

@click.command()
def create_order():
    send("Create Order")
    """Create an order by entering item_id and quantity, then proceed with payment."""
    order_items = []

    click.echo("Enter your order (item_id and quantity). Type 'done' when finished.")

    while True:
        item_id = click.prompt("Enter item_id or 'done'", type=str)
        if item_id.lower() == 'done':
            break
        quantity = click.prompt("Enter quantity", type=int)
        order_items.append((item_id, quantity))

    if not order_items:
        click.echo("No items ordered. Exiting.")
        return

    # Send order to backend and get total price and payment link
    total_price, payment_link = send_order_to_backend(order_items)

    # Display order summary in tabular form
    click.echo("\nOrder Summary:")
    table_data = [(item_id, qty) for item_id, qty in order_items]
    click.echo(tabulate(table_data, headers=["Item ID", "Quantity"], tablefmt="grid"))

    click.echo(f"\nTotal Price: ${total_price}")
    click.echo(f"Please proceed for payment: {payment_link}")

    # Prompt for payment completion
    proceed_payment = click.confirm("Have you completed the payment using the above link?", default=False)

    if proceed_payment:
        response = send_payment_complete_to_backend()
        click.echo(response)
    else:
        click.echo("Payment not completed. Order not confirmed.")


pending_orders = []

completed_orders = []

def display_orders(orders):
    """Helper function to display orders in tabular form"""
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
    click.echo(tabulate(table, headers=headers, tablefmt="fancy_grid"))

@click.group()
def cli():
    """CLI for Staff to Manage Orders"""
    pass

@cli.command()
def view_orders():
    """View all pending orders"""
    if pending_orders:
        click.echo("Pending Orders:")
        display_orders(pending_orders)
    else:
        click.echo("No pending orders at the moment.")

@cli.command()
@click.argument("order_id", type=int)
def complete_order(order_id):
    """Complete an order by its order ID"""
    global pending_orders, completed_orders
    order = next((o for o in pending_orders if o["order_id"] == order_id), None)
    if order:
        completed_orders.append(order)
        pending_orders = [o for o in pending_orders if o["order_id"] != order_id]
        click.echo(f"Order {order_id} marked as completed.\n")
        click.echo("Updated Pending Orders:")
        view_orders()
    else:
        click.echo(f"No pending order found with ID: {order_id}")


if __name__ == "__main__":
    send(DISCONNECT_MESSAGE) # must be sent when client is done communicating with server to close the connection
    client.close()