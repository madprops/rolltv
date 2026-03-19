class Utils:
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


utils = Utils()