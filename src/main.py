#!/usr/bin/env python

import os
import sys
import time
import tkinter as tk
import urllib.request
import json

from utils import utils
from data import data
from player import Player
from info import info


def fetch_json(url, cache_file):
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)

        if file_age < data.cache_expiry_seconds:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    utils.print(f"Fetching {url}...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode("utf-8")
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(raw_data)
        return json.loads(raw_data)
    except Exception as e:
        utils.print(f"Failed to fetch {url}: {e}")
        return []

def get_channels_data():
    channels_raw = fetch_json(data.channels_url, data.cache_channels)
    streams_raw = fetch_json(data.streams_url, data.cache_streams)

    channel_dict = {}

    for ch in channels_raw:
        channel_dict[ch["id"]] = ch

    merged = []

    for st in streams_raw:
        ch_id = st.get("channel")

        if ch_id:
            if ch_id in channel_dict:
                ch_info = channel_dict[ch_id]

                merged.append({
                    "name": ch_info.get("name", "Unknown"),
                    "url": st.get("url", ""),
                    "languages": ch_info.get("languages", []),
                })

    return merged

def main():
    channels = get_channels_data()
    if len(channels) == 0:
        utils.print("No channels found. Check your connection.")
        sys.exit(1)

    root = tk.Tk()
    app = Player(root, channels)
    root.mainloop()


if __name__ == "__main__":
    main()