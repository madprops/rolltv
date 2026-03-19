#!/usr/bin/env python

import tkinter as tk
import urllib.request
import random
import os
import time
import threading
import subprocess
import sys
import mpv
import json

from info import info

IPTV_M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
CACHE_FILE = "/tmp/iptv_channels.m3u"
CACHE_EXPIRY_SECONDS = 86400
HISTORY_FILE = os.path.expanduser(f"~/.config/{info.name}/history.json")
TITLE = info.full_name
TUNING_TIMEOUT = 4000
BG_COLOR = "#0f0f17"
FG_COLOR = "#00ffcc"
BTN_BG = "#1f1f2e"
BTN_ACTIVE = "#2a2a3f"
BTN_BORDER = "#28283d"
FONT_UI = ("Monospace", 12, "bold")
ROLL_TEXT = "🎲 Roll TV"
MAX_HISTORY = 100

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
    if os.path.exists(CACHE_FILE):
        file_age = time.time() - os.path.getmtime(CACHE_FILE)

        if file_age < CACHE_EXPIRY_SECONDS:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            return parse_m3u(lines)

    print(f"Fetching latest playlist from {IPTV_M3U_URL}...")

    try:
        req = urllib.request.Request(IPTV_M3U_URL, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode("utf-8")

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(raw_data)

        lines = raw_data.splitlines()
        return parse_m3u(lines)

    except Exception as e:
        print(f"Failed to fetch playlist: {e}")
        return []

class RandomIPTVPlayer:
    def __init__(self, root, channels):
        self.root = root
        self.channels = channels
        self.current_url = ""
        self.tuning = False
        self.pending_channel = None
        self.tuning_timeout = None
        self.history = self.load_history()
        self.sidebar_visible = False
        self.stall_retries = 0

        self.root.title(TITLE)
        self.root.geometry("1000x600")
        self.root.configure(bg=BG_COLOR)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.png")

        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
            except Exception as e:
                print(f"Could not load icon: {e}")

        self.top_frame = tk.Frame(root, bg=BG_COLOR)
        self.top_frame.pack(fill=tk.X, pady=10, padx=15)

        self.name_label = tk.Label(
            self.top_frame,
            text="Click the dice to tune in",
            font=FONT_UI,
            bg=BG_COLOR,
            fg=FG_COLOR
        )

        self.name_label.pack(side=tk.LEFT)
        self.btn_frame = tk.Frame(self.top_frame, bg=BG_COLOR)
        self.btn_frame.pack(side=tk.RIGHT)

        self.copy_btn = tk.Button(
            self.btn_frame,
            text="📋 Copy",
            command=self.copy_link,
            font=FONT_UI,
            bg=BTN_BG,
            fg=FG_COLOR,
            activebackground=BTN_ACTIVE,
            activeforeground=FG_COLOR,
            relief=tk.FLAT,
            highlightbackground=BTN_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10
        )

        self.copy_btn.pack(side=tk.LEFT, padx=5)

        self.paste_btn = tk.Button(
            self.btn_frame,
            text="📥 Paste",
            command=self.paste_link,
            font=FONT_UI,
            bg=BTN_BG,
            fg=FG_COLOR,
            activebackground=BTN_ACTIVE,
            activeforeground=FG_COLOR,
            relief=tk.FLAT,
            highlightbackground=BTN_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10
        )

        self.paste_btn.pack(side=tk.LEFT, padx=5)

        self.history_btn = tk.Button(
            self.btn_frame,
            text="📺 History",
            command=self.toggle_history,
            font=FONT_UI,
            bg=BTN_BG,
            fg=FG_COLOR,
            activebackground=BTN_ACTIVE,
            activeforeground=FG_COLOR,
            relief=tk.FLAT,
            highlightbackground=BTN_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10
        )

        self.history_btn.pack(side=tk.LEFT, padx=5)

        self.play_btn = tk.Button(
            self.btn_frame,
            text=ROLL_TEXT,
            command=self.play_random,
            font=FONT_UI,
            bg=BTN_BG,
            fg=FG_COLOR,
            activebackground=BTN_ACTIVE,
            activeforeground=FG_COLOR,
            relief=tk.FLAT,
            highlightbackground=BTN_BORDER,
            highlightthickness=1,
            bd=0,
            padx=10
        )

        self.play_btn.pack(side=tk.LEFT, padx=5)
        self.main_content_frame = tk.Frame(root, bg=BG_COLOR)
        self.main_content_frame.pack(fill=tk.BOTH, expand=True)
        self.video_container = tk.Frame(self.main_content_frame, bg="black")
        self.video_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_container.grid_rowconfigure(0, weight=1)
        self.video_container.grid_columnconfigure(0, weight=1)
        self.video_container.bind("<Button-4>", self.volume_up)
        self.video_container.bind("<Button-5>", self.volume_down)
        self.video_container.bind("<Button-3>", self.toggle_pause)
        self.sidebar_frame = tk.Frame(self.main_content_frame, bg=BTN_BG, width=300)
        self.sidebar_frame.pack_propagate(False)

        self.history_listbox = tk.Listbox(
            self.sidebar_frame,
            bg=BTN_BG,
            fg=FG_COLOR,
            font=FONT_UI,
            relief=tk.FLAT,
            highlightthickness=0,
            selectbackground=BTN_BG,
            selectforeground=FG_COLOR,
            activestyle="none"
        )

        self.scrollbar = tk.Scrollbar(self.sidebar_frame, command=self.history_listbox.yview, bg=BG_COLOR)
        self.history_listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.history_listbox.bind("<Button-1>", self.on_history_click)
        self.frames = []
        self.players = []

        for i in range(2):
            frame = tk.Frame(self.video_container, bg="black")
            frame.grid(row=0, column=0, sticky="nsew")

            player = mpv.MPV(wid=str(frame.winfo_id()), hwdec="auto")

            self.frames.append(frame)
            self.players.append(player)

        self.active_idx = 0
        self.frames[0].tkraise()

        @self.players[0].on_key_press("MBTN_LEFT_DBL")
        def on_dbl_click_0():
            self.root.after(0, self.play_random)

        @self.players[1].on_key_press("MBTN_LEFT_DBL")
        def on_dbl_click_1():
            self.root.after(0, self.play_random)

        @self.players[0].property_observer("playback-time")
        def check_ready_0(name, value):
            if value is not None and value > 0.1:

                if self.tuning and self.active_idx != 0:
                    self.root.after(0, self.commit_switch, 0)

        @self.players[1].property_observer("playback-time")
        def check_ready_1(name, value):
            if value is not None and value > 0.1:

                if self.tuning and self.active_idx != 1:
                    self.root.after(0, self.commit_switch, 1)

        if len(self.history) > 0:
            last_channel = self.history[-1]
            self.root.after(500, self.play_specific, last_channel)

    def load_history(self):
        config_dir = os.path.dirname(HISTORY_FILE)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        if not os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception as e:
                print(f"Failed to create history file: {e}")
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load history: {e}")
        return []

    def save_history(self):
        config_dir = os.path.dirname(HISTORY_FILE)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Failed to save history: {e}")

    def toggle_history(self):
        if self.sidebar_visible:
            self.sidebar_frame.pack_forget()
            self.history_btn.config(bg=BTN_BG, relief=tk.FLAT)
            self.sidebar_visible = False
        else:
            self.update_sidebar()
            self.sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.video_container)
            self.history_btn.config(bg=BTN_ACTIVE, relief=tk.SUNKEN)
            self.sidebar_visible = True

    def update_sidebar(self):
        self.history_listbox.delete(0, tk.END)

        for ch in reversed(self.history):
            self.history_listbox.insert(tk.END, ch["name"])

    def on_history_click(self, event):
        index = self.history_listbox.nearest(event.y)

        if index >= 0:
            bbox = self.history_listbox.bbox(index)

            if bbox:

                if bbox[1] <= event.y <= bbox[1] + bbox[3]:
                    real_index = len(self.history) - 1 - index
                    ch = self.history[real_index]
                    self.root.after(0, self.play_specific, ch)

        return "break"

    def play_random(self):
        if len(self.channels) == 0:
            return

        if self.tuning:
            return

        self.stall_retries = 0
        self.tuning = True
        self.play_btn.config(state=tk.DISABLED, text="⏳ Tuning")
        thread = threading.Thread(target=self.find_live_stream, daemon=True)
        thread.start()

    def play_specific(self, channel):
        if self.tuning:
            return

        if channel["url"] == self.current_url:
            return

        self.stall_retries = 0
        self.tuning = True
        self.play_btn.config(state=tk.DISABLED, text="⏳ Tuning")
        self.prepare_switch(channel)

    def find_live_stream(self):
        working_channel = None
        attempts = 0

        while working_channel is None:
            if attempts > 10:
                break

            candidate = random.choice(self.channels)
            attempts += 1

            try:
                req = urllib.request.Request(
                    candidate["url"],
                    method="GET",
                    headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-100"}
                )

                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200 or response.status == 206:
                        working_channel = candidate
            except Exception:
                continue

        if working_channel is not None:
            self.root.after(0, self.prepare_switch, working_channel)
        else:
            self.root.after(0, self.reset_button)

    def prepare_switch(self, channel):
        self.pending_channel = channel

        next_idx = 0

        if self.active_idx == 0:
            next_idx = 1

        self.tuning_timeout = self.root.after(TUNING_TIMEOUT, self.handle_timeout)
        self.players[next_idx].play(channel["url"])

    def handle_timeout(self):
        if self.tuning:
            if self.stall_retries < 5:
                self.stall_retries += 1
                self.name_label.config(text=f"Stalled. Retrying... ({self.stall_retries}/5)")

                next_idx = 0

                if self.active_idx == 0:
                    next_idx = 1

                self.players[next_idx].stop()

                thread = threading.Thread(target=self.find_live_stream, daemon=True)
                thread.start()
            else:
                self.tuning = False
                self.reset_button()

                next_idx = 0

                if self.active_idx == 0:
                    next_idx = 1

                self.players[next_idx].stop()
                self.name_label.config(text="Stream stalled 5 times. Roll again.")

    def commit_switch(self, ready_idx):
        if not self.tuning:
            return

        self.tuning = False
        self.stall_retries = 0

        if self.tuning_timeout is not None:
            self.root.after_cancel(self.tuning_timeout)
            self.tuning_timeout = None

        self.active_idx = ready_idx
        self.frames[ready_idx].tkraise()

        old_idx = 0

        if ready_idx == 0:
            old_idx = 1

        self.players[old_idx].stop()
        self.current_url = self.pending_channel["url"]
        self.name_label.config(text=self.pending_channel["name"])
        self.play_btn.config(state=tk.NORMAL, text=ROLL_TEXT)
        self.history = [ch for ch in self.history if ch["url"] != self.pending_channel["url"]]
        self.history.append(self.pending_channel)

        if len(self.history) > MAX_HISTORY:
            self.history.pop(0)

        # Save the updated history to the JSON file
        self.save_history()

        if self.sidebar_visible:
            self.update_sidebar()

    def reset_button(self):
        self.tuning = False
        self.play_btn.config(state=tk.NORMAL, text=ROLL_TEXT)

    def copy_link(self):
        if self.current_url != "":
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=self.current_url.encode("utf-8"),
                    check=True
                )
            except Exception as e:
                print(f"Failed to copy to clipboard: {e}")

    def paste_link(self):
        try:
            clip_text = self.root.clipboard_get().strip()

            if clip_text != "":
                found_name = "Pasted Stream"

                for ch in self.channels:
                    if ch["url"] == clip_text:
                        found_name = ch["name"]
                        break

                channel = {"name": found_name, "url": clip_text}
                self.play_specific(channel)
        except tk.TclError:
            print("Clipboard is empty or inaccessible.")

    def volume_up(self, event):
        player = self.players[self.active_idx]

        if player:
            current_vol = player.volume
            player.volume = min(current_vol + 5, 100)

    def volume_down(self, event):
        player = self.players[self.active_idx]
        print(player)

        if player:
            current_vol = player.volume
            player.volume = max(current_vol - 5, 0)

    def toggle_pause(self, event):
        player = self.players[self.active_idx]

        if player:
            player.pause = not player.pause


def main():
    channels = fetch_channels()

    if len(channels) == 0:
        print("No channels found. Check your connection.")
        sys.exit(1)

    root = tk.Tk()
    app = RandomIPTVPlayer(root, channels)
    root.mainloop()


if __name__ == "__main__":
    main()