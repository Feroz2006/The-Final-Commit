import socket
import threading
import os
from helpers.constants import PORT, FORMAT, HEADER_SIZE, DISCONNECT_MESSAGE


SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT) # giving port 0 lets the OS pick an available port

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)

def start_server() -> None:
    server.listen()
    print(f"[LISTENING] Server is listening on {SERVER}:{PORT}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")


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
            response = process_message(msg)
            response_encoded = response.encode(FORMAT)
            response_length = len(response_encoded)
            response_length = str(response_length).encode(FORMAT)
            response_length += b' ' * (HEADER_SIZE - len(response_length))
            conn.send(response_length)
            conn.send(response_encoded)
    conn.close()
    print(f"[DISCONNECTED] {addr} disconnected.")

def process_message(msg) -> str:
    return "Test Response From Server"



start_server()



# run using python -m backend.server