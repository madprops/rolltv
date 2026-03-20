import os
import tkinter as tk
import urllib.request
from typing import Any

from info import info


class Flags:
    def __init__(self, player: Any) -> None:
        self.player = player
        self.flag_images: dict[str, tk.PhotoImage] = {}

    def get_path(self, c_code: str) -> str:
        flag_dir = os.path.expanduser(f"~/.config/{info.name}/flags")
        os.makedirs(flag_dir, exist_ok=True)
        return os.path.join(flag_dir, f"{c_code}.png")

    def load_or_fetch(self, c_code: str, expected_name: str) -> None:
        flag_path = self.get_path(c_code)

        if not os.path.exists(flag_path):
            try:
                url = f"https://flagcdn.com/24x18/{c_code}.png"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200:
                        with open(flag_path, "wb") as f:
                            f.write(response.read())
            except Exception:
                self.player.root.after(0, self.clear)
                return

        self.player.root.after(0, self.apply, flag_path, expected_name)

    def apply(self, flag_path: str, expected_name: str) -> None:
        if self.player.current_channel_name != expected_name:
            return
        try:
            self.player.current_flag_img = tk.PhotoImage(file=flag_path)
            self.player.flag_label.config(image=self.player.current_flag_img)
        except Exception:
            self.clear()

    def clear(self) -> None:
        self.player.current_flag_img = None
        self.player.flag_label.config(image="")

    def fetch_only(self, c_code: str) -> None:
        flag_path = self.get_path(c_code)

        if not os.path.exists(flag_path):
            try:
                url = f"https://flagcdn.com/24x18/{c_code}.png"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200:
                        with open(flag_path, "wb") as f:
                            f.write(response.read())

                        def update_images() -> None:
                            try:
                                self.flag_images[c_code] = tk.PhotoImage(file=flag_path)
                            except Exception:
                                return
                            if self.player.active_sidebar:
                                self.player.update_sidebar()

                        self.player.root.after(0, update_images)
            except Exception:
                pass
