#!/usr/bin/env python

import os
import time
import tkinter as tk
import urllib.request

from utils import utils
from data import data
from player import Player
from info import info

def parse_m3u(lines):
    channels = []
    current_name = ""

    for line in lines:
        line = line.strip()

        if len(line) == 0:
            continue

        if line.startswith("#EXTINF"):
            parts = line.split(",")

            if len(parts) > 1:
                current_name = parts[-1].strip()
        elif not line.startswith("#"):
            if current_name:
                channels.append({"name": current_name, "url": line})
                current_name = ""

    return channels

def fetch_channels():
    if os.path.exists(data.cache_file):
        file_age = time.time() - os.path.getmtime(data.cache_file)

        if file_age < data.cache_expiry_seconds:
            with open(data.cache_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()

            return parse_m3u(lines)

    utils.print(f"Fetching latest playlist from {data.iptv_m3u_url}...")

    try:
        req = urllib.request.Request(data.iptv_m3u_url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode("utf-8")

        with open(data.cache_file, "w", encoding="utf-8") as f:
            f.write(raw_data)

        lines = raw_data.splitlines()
        return parse_m3u(lines)

    except Exception as e:
        utils.print(f"Failed to fetch playlist: {e}")
        return []


def main():
    channels = fetch_channels()

    if len(channels) == 0:
        utils.print("No channels found. Check your connection.")
        sys.exit(1)

    root = tk.Tk()
    app = Player(root, channels)
    root.mainloop()


if __name__ == "__main__":
    main()