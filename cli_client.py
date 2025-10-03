import click
import socket
from helpers.constants import PORT, FORMAT, HEADER_SIZE, DISCONNECT_MESSAGE


SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT) # giving port 0 lets the OS pick an available port
print(SERVER)
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



send("Hello World!")
send(DISCONNECT_MESSAGE) # must be sent when client is done communicating with server to close the connection
client.close()