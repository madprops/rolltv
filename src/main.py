#!/usr/bin/env python

import os
import sys
import json
import time
import tkinter as tk
import urllib.request
from typing import Any

from info import info
from data import data
from utils import utils
from player import Player

LOCKS = []


def fetch_json(url: str, cache_file: str) -> Any:
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


def get_channels_data() -> list[dict[str, Any]]:
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
        if st.get("status") not in ("online", None):
            continue

        ch_id = st.get("channel")
        feed_id = st.get("feed")

        if ch_id:
            if ch_id in channel_dict:
                ch_info = channel_dict[ch_id]
                langs = ch_info.get("languages") or []

                if feed_id:
                    if feed_id in feed_dict:
                        feed_langs = feed_dict[feed_id].get("languages") or []
                        langs = list(set(langs + feed_langs))

                c_code = ch_info.get("country") or ""
                c_name = country_dict.get(c_code.lower()) or ""

                merged.append(
                    {
                        "name": ch_info.get("name", "Unknown"),
                        "url": st.get("url", ""),
                        "languages": langs,
                        "country_code": c_code,
                        "country_name": c_name,
                    }
                )

    return merged


def singleton() -> None:
    app_name = info.name

    if os.name == "nt":
        import ctypes

        mutex_name = f"Global\\{app_name}_mutex"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)  # type: ignore
        last_error = ctypes.windll.kernel32.GetLastError()  # type: ignore

        if last_error == 183:
            print(f"An instance of {app_name} is already running.")
            sys.exit(1)

        LOCKS.append(mutex)
    else:
        import fcntl
        import tempfile

        lock_path = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        lock_file = open(lock_path, "w")

        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(f"An instance of {app_name} is already running.")
            trigger_raise()
            sys.exit(1)

        LOCKS.append(lock_file)


def trigger_raise() -> None:
    import socket
    import tempfile
    import hashlib

    app_name = info.name

    try:
        if os.name == "posix":
            socket_path = os.path.join(tempfile.gettempdir(), f"{app_name}_ipc.sock")
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(socket_path)
        else:
            port = 50000 + int(hashlib.md5(app_name.encode()).hexdigest(), 16) % 10000
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("127.0.0.1", port))

        client.sendall("RAISE".encode("utf-8"))
        client.close()
    except Exception:
        pass


def main() -> None:
    singleton()
    channels = get_channels_data()

    if len(channels) == 0:
        utils.print("No channels found. Check your connection.")
        sys.exit(1)

    utils.set_proc_name(info.name)
    root = tk.Tk(className=info.name)
    Player(root, channels)
    root.mainloop()


if __name__ == "__main__":
    main()
