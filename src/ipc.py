import os
import socket
import tempfile
import hashlib
import threading
from typing import Any

from info import info


class IPCListener:
    def __init__(self, root: Any, player: Any = None) -> None:
        self.root = root
        self.player = player

    def start(self) -> None:
        def listener() -> None:
            if os.name == "posix":
                # Unix Domain Socket for Linux/Mac (X11 & Wayland)
                socket_path = os.path.join(
                    tempfile.gettempdir(), f"{info.name}_ipc.sock"
                )

                if os.path.exists(socket_path):
                    try:
                        os.remove(socket_path)
                    except OSError:
                        pass

                server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                server.bind(socket_path)
            else:
                # Localhost TCP Socket for Windows
                port = (
                    50000 + int(hashlib.md5(info.name.encode()).hexdigest(), 16) % 10000
                )

                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                try:
                    server.bind(("127.0.0.1", port))
                except OSError:
                    return

            server.listen(1)

            while True:
                try:
                    conn, _ = server.accept()
                    req_data = conn.recv(1024).decode("utf-8")

                    if req_data == "RAISE":
                        # Safely trigger the Tkinter event from the background thread
                        self.root.after(0, self.raise_window)
                    elif req_data.startswith("COUNTRY:"):
                        if self.player:
                            country_name = req_data.split(":", 1)[1]
                            self.root.after(
                                0, self.player.set_country_from_globe, country_name
                            )

                    conn.close()
                except Exception:
                    break

        thread = threading.Thread(target=listener, daemon=True)
        thread.start()

    def raise_window(self) -> None:
        if self.root.state() == "iconic":
            self.root.deiconify()

        if os.name == "posix":
            self.root.withdraw()
            self.root.deiconify()

        self.root.attributes("-topmost", True)
        self.root.attributes("-topmost", False)
        self.root.lift()
        self.root.focus_force()
