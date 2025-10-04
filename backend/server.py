import socket
import threading
import json
from helpers.constants import *
from helpers.app_helpers import *

dbm = DatabaseManager()
acm = AccountManager(dbm)
dtm = DataManager(acm)

SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT) # giving port 0 lets the OS pick an available port

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
    match msg:
        case "Get Menu":
            print("Getting Menu")
            return dtm.get_menu()
        case "Create Order":
            print("Creating Order")
            return dtm.create_order()
    return "Test Response From Server"



start_server()



# run using python -m backend.server
# run sudo lsof -i :[PORTNUMBER] if Address already in use error occurs