import sys
import ctypes
import ctypes.util


class Utils:
    def __init__(self) -> None:
        self.ansi_colors = {
            "black": "\033[30m",
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
            "cyan": "\033[36m",
            "white": "\033[37m",
            "reset": "\033[0m",
        }

        self.pr_set_name = 15

    def print(self, text: str, color: str = "") -> None:
        if color:
            color_key = color.lower()

            if color_key in self.ansi_colors:
                color_code = self.ansi_colors[color_key]
            else:
                color_code = ""

            print(f"{color_code}{text}{self.ansi_colors['reset']}")
        else:
            print(text)

    def set_proc_name(self, name: str) -> None:
        if sys.platform.startswith("linux"):
            libc_path = ctypes.util.find_library("c")

            if libc_path:
                libc = ctypes.CDLL(libc_path)
                name_bytes = name.encode("utf-8") + b"\0"
                libc.prctl(self.pr_set_name, ctypes.c_char_p(name_bytes), 0, 0, 0)
            else:
                pass

    def quote(self, items: list[str]) -> str:
        return ", ".join(f"'{item}'" for item in items)


utils = Utils()
