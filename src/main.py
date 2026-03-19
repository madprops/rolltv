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
    feeds_raw = fetch_json(data.feeds_url, data.cache_feeds)
    countries_raw = fetch_json(data.countries_url, data.cache_countries)
    channel_dict = {}

    for ch in channels_raw:
        channel_dict[ch["id"]] = ch
    feed_dict = {}

    for f in feeds_raw:
        feed_dict[f["id"]] = f
    country_dict = {}

    for c in countries_raw:
        country_dict[c.get("code", "").lower()] = c.get("name", "").lower()
    merged = []

    for st in streams_raw:
        ch_id = st.get("channel")
        feed_id = st.get("feed")

        if ch_id:
            if ch_id in channel_dict:
                ch_info = channel_dict[ch_id]
                langs = []

                if feed_id:
                    if feed_id in feed_dict:
                        langs = feed_dict[feed_id].get("languages", [])

                c_code = ch_info.get("country") or ""
                c_name = country_dict.get(c_code.lower()) or ""
                merged.append({"name": ch_info.get("name", "Unknown"), "url": st.get("url", ""), "languages": langs, "country_code": c_code, "country_name": c_name})
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