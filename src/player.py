import tkinter as tk
from tkinter import ttk
import urllib.request
import random
import os
import time
import threading
import subprocess
import sys
import mpv
import json

from utils import utils
from data import data

class Player:
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
        self.placeholder_text = "Country name or code"
        self.root.title(data.title)
        self.root.geometry("1000x600")
        self.root.configure(bg=data.bg_color)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.png")

        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
            except Exception as e:
                utils.print(f"Could not load icon: {e}")

        self.top_frame = tk.Frame(root, bg=data.bg_color)
        self.top_frame.pack(fill=tk.X, pady=10, padx=15)
        self.setup_languages()
        self.selected_lang = tk.StringVar(value=data.any_language)

        self.lang_cb = ttk.Combobox(
            self.top_frame,
            textvariable=self.selected_lang,
            values=[data.any_language] + self.display_languages,
            state="readonly",
            font=data.font_ui,
            width=15,
        )
        self.lang_cb.pack(side=tk.LEFT, padx=(0, 10))

        self.country_var = tk.StringVar(value=self.placeholder_text)

        self.country_entry = tk.Entry(
            self.top_frame,
            textvariable=self.country_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray",
            insertbackground=data.fg_color,
            width=22,
        )
        self.country_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.country_entry.bind("<FocusIn>", self.on_country_focus_in)
        self.country_entry.bind("<FocusOut>", self.on_country_focus_out)

        self.name_label = tk.Label(
            self.top_frame,
            text="Click the dice to tune in",
            font=data.font_ui,
            bg=data.bg_color,
            fg=data.fg_color,
        )
        self.name_label.pack(side=tk.LEFT)

        self.btn_frame = tk.Frame(self.top_frame, bg=data.bg_color)
        self.btn_frame.pack(side=tk.RIGHT)

        self.copy_btn = tk.Button(
            self.btn_frame,
            text="📋 Copy",
            command=self.copy_link,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.fg_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=10,
        )
        self.copy_btn.pack(side=tk.LEFT, padx=5)

        self.paste_btn = tk.Button(
            self.btn_frame,
            text="📝 Paste",
            command=self.paste_link,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.fg_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=10,
        )
        self.paste_btn.pack(side=tk.LEFT, padx=5)

        self.history_btn = tk.Button(
            self.btn_frame,
            text="🕒 History",
            command=self.toggle_history,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.fg_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=10,
        )
        self.history_btn.pack(side=tk.LEFT, padx=5)

        self.play_btn = tk.Button(
            self.btn_frame,
            text=data.roll_text,
            command=self.play_random,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.fg_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=10,
        )
        self.play_btn.pack(side=tk.LEFT, padx=5)

        self.main_content_frame = tk.Frame(root, bg=data.bg_color)
        self.main_content_frame.pack(fill=tk.BOTH, expand=True)
        self.video_container = tk.Frame(self.main_content_frame, bg="black")
        self.video_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_container.grid_rowconfigure(0, weight=1)
        self.video_container.grid_columnconfigure(0, weight=1)
        self.video_container.bind("<Button-4>", self.volume_up)
        self.video_container.bind("<Button-5>", self.volume_down)
        self.video_container.bind("<Button-3>", self.toggle_pause)
        self.sidebar_frame = tk.Frame(self.main_content_frame, bg=data.btn_bg, width=300)
        self.sidebar_frame.pack_propagate(False)

        self.history_listbox = tk.Listbox(
            self.sidebar_frame,
            bg=data.btn_bg,
            fg=data.fg_color,
            font=data.font_ui,
            relief=tk.FLAT,
            highlightthickness=0,
            selectbackground=data.btn_bg,
            selectforeground=data.fg_color,
            activestyle="none"
        )
        self.scrollbar = tk.Scrollbar(self.sidebar_frame, command=self.history_listbox.yview, bg=data.bg_color)
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

    def on_country_focus_in(self, event):
        if self.country_var.get() == self.placeholder_text:
            self.country_var.set("")
            self.country_entry.config(fg=data.fg_color)

    def on_country_focus_out(self, event):
        if self.country_var.get().strip() == "":
            self.country_var.set(self.placeholder_text)
            self.country_entry.config(fg="gray")

    def setup_languages(self):
        self.lang_map = {
            "eng": "English",
            "spa": "Spanish",
            "zho": "Chinese",
            "rus": "Russian",
            "swe": "Swedish",
            "fra": "French",
            "deu": "German",
            "jpn": "Japanese",
            "por": "Portuguese",
            "ita": "Italian",
            "ara": "Arabic",
            "hin": "Hindi",
            "kor": "Korean",
            "nld": "Dutch",
            "tur": "Turkish",
            "pol": "Polish",
        }
        self.lang_map_rev = {v: k for k, v in self.lang_map.items()}
        self.display_languages = list(self.lang_map.values())

    def load_history(self):
        config_dir = os.path.dirname(data.history_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        if not os.path.exists(data.history_file):
            try:
                with open(data.history_file, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception as e:
                utils.print(f"Failed to create history file: {e}")

        try:
            with open(data.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            utils.print(f"Failed to load history: {e}")

        return []

    def save_history(self):
        config_dir = os.path.dirname(data.history_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        try:
            with open(data.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            utils.print(f"Failed to save history: {e}")

    def toggle_history(self):
        if self.sidebar_visible:
            self.sidebar_frame.pack_forget()
            self.history_btn.config(bg=data.btn_bg, relief=tk.FLAT)
            self.sidebar_visible = False
        else:
            self.update_sidebar()
            self.sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.video_container)
            self.history_btn.config(bg=data.btn_active, relief=tk.SUNKEN)
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
        sel_lang = self.selected_lang.get()
        valid_channels = self.channels

        if sel_lang != data.any_language:
            target_code = self.lang_map_rev.get(sel_lang, sel_lang)
            filtered_by_lang = []

            for ch in self.channels:
                langs = ch.get("languages") or []

                if target_code in langs:
                    filtered_by_lang.append(ch)

            valid_channels = filtered_by_lang

        target_country = self.country_var.get().strip().lower()

        if (target_country != "") and (target_country != self.placeholder_text):
            filtered_by_country = []

            for ch in valid_channels:
                c_code = (ch.get("country_code") or "").lower()
                c_name = (ch.get("country_name") or "").lower()

                if (target_country == c_code) or (target_country in c_name):
                    filtered_by_country.append(ch)

            valid_channels = filtered_by_country

        if len(valid_channels) == 0:
            self.root.after(0, self.reset_button)
            self.root.after(0, lambda: self.name_label.config(text="No channels for this filter"))
            return

        while working_channel is None:
            if attempts > 30:
                break

            candidate = random.choice(valid_channels)
            attempts += 1

            try:
                req = urllib.request.Request(
                    candidate["url"],
                    method="GET",
                    headers={"User-Agent": "mpv/0.34.0"},
                )

                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status in [200, 206, 301, 302]:
                        chunk = response.read(16)
                        if len(chunk) > 0:
                            working_channel = candidate
            except Exception:
                continue

        if working_channel is not None:
            self.root.after(0, self.prepare_switch, working_channel)
        else:
            self.root.after(0, self.reset_button)
            self.root.after(0, lambda: self.name_label.config(text="Could not find a working stream."))

    def prepare_switch(self, channel):
        self.pending_channel = channel
        next_idx = 0

        if self.active_idx == 0:
            next_idx = 1

        self.tuning_timeout = self.root.after(data.tuning_timeout, self.handle_timeout)
        self.players[next_idx].play(channel["url"])

    def handle_timeout(self):
        if self.tuning:
            if self.stall_retries < data.max_retries:
                self.stall_retries += 1
                self.name_label.config(text=f"Stalled. Retrying... ({self.stall_retries}/{data.max_retries})")
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
                self.name_label.config(text=f"Stream stalled {data.max_retries} times. Roll again.")

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
        self.play_btn.config(state=tk.NORMAL, text=data.roll_text)
        self.history = [ch for ch in self.history if ch["url"] != self.pending_channel["url"]]
        self.history.append(self.pending_channel)

        if len(self.history) > data.max_history:
            self.history.pop(0)

        self.save_history()

        if self.sidebar_visible:
            self.update_sidebar()

    def reset_button(self):
        self.tuning = False
        self.play_btn.config(state=tk.NORMAL, text=data.roll_text)

    def copy_link(self):
        if self.current_url != "":
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=self.current_url.encode("utf-8"),
                    check=True,
                )
            except Exception as e:
                utils.print(f"Failed to copy to clipboard: {e}")

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
            utils.print("Clipboard is empty or inaccessible.")

    def volume_up(self, event):
        player = self.players[self.active_idx]

        if player:
            current_vol = player.volume
            player.volume = min(current_vol + 5, 100)

    def volume_down(self, event):
        player = self.players[self.active_idx]
        utils.print(player)

        if player:
            current_vol = player.volume
            player.volume = max(current_vol - 5, 0)

    def toggle_pause(self, event):
        player = self.players[self.active_idx]

        if player:
            player.pause = not player.pause