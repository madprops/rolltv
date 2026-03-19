import os
from info import info

class Data:
    def __init__(self) -> None:
        self.channels_url = "https://iptv-org.github.io/api/channels.json"
        self.streams_url = "https://iptv-org.github.io/api/streams.json"
        self.cache_channels = "/tmp/iptv_channels.json"
        self.cache_streams = "/tmp/iptv_streams.json"
        self.cache_expiry_seconds = 86400
        self.history_file = os.path.expanduser(f"~/.config/{info.name}/history.json")
        self.title = info.full_name
        self.tuning_timeout = 4000
        self.bg_color = "#0f0f17"
        self.fg_color = "#00ffcc"
        self.btn_bg = "#1f1f2e"
        self.btn_active = "#2a2a3f"
        self.btn_border = "#28283d"
        self.font_ui = ("Monospace", 12, "bold")
        self.roll_text = "🎲 Roll TV"
        self.max_history = 100


data = Data()