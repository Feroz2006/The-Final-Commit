import socket
import threading
import json
from helpers.constants import *
from helpers.app_helpers import *

dbm = DatabaseManager()
acm = AccountManager(dbm)
dtm = DataManager(acm)

SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)

def start_server() -> None:
    try:
        server.listen()
        print(f"[LISTENING] Server is listening on {SERVER}:{PORT}")
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server is shutting down...")
        server.close()

def handle_client(conn, addr) -> None:
    print(f"[NEW CONNECTION] {addr} connected.")
    connected = True
    while connected:
        msg_length = conn.recv(HEADER_SIZE).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)
            if msg == DISCONNECT_MESSAGE:
                connected = False
            print(f"[{addr}] {msg}")
            response = json.dumps(process_message(msg))
            response_encoded = response.encode(FORMAT)
            response_length = len(response_encoded)
            response_length = str(response_length).encode(FORMAT)
            response_length += b' ' * (HEADER_SIZE - len(response_length))
            conn.send(response_length)
            conn.send(response_encoded)
    conn.close()
    print(f"[DISCONNECTED] {addr} disconnected.")

def process_message(msg) -> str:
    try:
        data = json.loads(msg)
        # Create Order
        if (
            isinstance(data, list) and
            all(isinstance(item, dict) and "item_id" in item and "item_quantity" in item for item in data)
        ):
            print("Creating Order")
            return dtm.create_order(msg)
        # Payment complete
        if isinstance(data, dict) and data.get("payment_complete") is True:
            print("Processing payment completion")
            receipt = dtm.payment_complete()
            return json.dumps(receipt)
        # Login
        if isinstance(data, dict) and data.get("action") == "login":
            email = data.get("email")
            password = data.get("password")
            success = acm.login(email, password)
            return json.dumps({"status": "success" if success else "failure"})
        # View pending orders
        if isinstance(data, dict) and data.get("action") == "view_pending_orders":
            print("Fetching pending orders")
            orders = dtm.get_pending_orders()
            return json.dumps(orders)
        # Complete order
        if isinstance(data, dict) and "order_id" in data and "status" in data:
            print(f"Completing order {data['order_id']} with status {data['status']}")
            result = dtm.set_order_complete(data["order_id"], data["status"])
            return json.dumps(result)
    except json.JSONDecodeError:
        pass
    match msg:
        case "Get Menu":
            print("Getting Menu")
            return json.dumps(dtm.get_menu())
    return json.dumps({"error": "Invalid request"})

start_server()
