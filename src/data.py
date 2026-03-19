import os
from info import info


class Data:
    def __init__(self) -> None:
        self.channels_url = "https://iptv-org.github.io/api/channels.json"
        self.streams_url = "https://iptv-org.github.io/api/streams.json"
        self.feeds_url = "https://iptv-org.github.io/api/feeds.json"
        self.countries_url = "https://iptv-org.github.io/api/countries.json"
        self.cache_channels = "/tmp/iptv_channels.json"
        self.cache_streams = "/tmp/iptv_streams.json"
        self.cache_feeds = "/tmp/iptv_feeds.json"
        self.cache_countries = "/tmp/iptv_countries.json"
        self.cache_expiry_seconds = 86400
        self.history_file = os.path.expanduser(f"~/.config/{info.name}/history.json")
        self.data_file = os.path.expanduser(f"~/.config/{info.name}/data.json")
        self.title = info.full_name
        self.tuning_timeout = 4 * 1000
        self.bg_color = "#1A1B26"
        self.fg_color = "#E2E2E2"
        self.accent_color = "#7AA2F7"
        self.btn_bg = "#1A1B26"
        self.btn_active = "#24283B"
        self.info_fg = "#888888"
        self.list_select_bg = "#33467C"
        self.btn_border = "#292E42"
        self.font_ui = ("sans-serif", 11)
        self.name_font = ("sans-serif", 14, "bold")
        self.roll_text = "🎲 Roll"
        self.any_language = "Language"
        self.max_history = 1000
        self.max_retries = 10
        self.width = 1200
        self.height = 800
        self.url_timeout = 3.0
        self.info_restore_delay = 10 * 1000
        self.url_timeout = 3.0


data = Data()
