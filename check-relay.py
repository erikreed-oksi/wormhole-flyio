#!/usr/bin/env python3
"""Check real Wormhole relay pairing and bidirectional forwarding."""
import secrets
import socket
import sys


def read_exact(sock, length):
    data = bytearray()
    while len(data) < length:
        part = sock.recv(length - len(data))
        if not part:
            raise RuntimeError("Relay closed the connection unexpectedly")
        data.extend(part)
    return bytes(data)


def main():
    if not 2 <= len(sys.argv) <= 3:
        raise SystemExit("Usage: python3 check-relay.py HOST [PORT]")
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) == 3 else 4001
    token = secrets.token_hex(32)
    with socket.create_connection((host, port), timeout=15) as a, \
            socket.create_connection((host, port), timeout=15) as b:
        for sock in (a, b):
            sock.settimeout(15)
            side = secrets.token_hex(8)
            sock.sendall(f"please relay {token} for side {side}\n".encode("ascii"))
        for sock in (a, b):
            if read_exact(sock, 3) != b"ok\n":
                raise RuntimeError("Relay did not acknowledge the matching handshakes")
        for sender, receiver in ((a, b), (b, a)):
            payload = secrets.token_bytes(4096)
            sender.sendall(payload)
            if read_exact(receiver, len(payload)) != payload:
                raise RuntimeError("Relayed bytes did not match")
    print(f"PASS: {host}:{port} paired two clients and forwarded data both ways")


if __name__ == "__main__":
    main()
