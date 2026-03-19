import tkinter as tk
from tkinter import ttk
import urllib.request
import random
import os
import threading
import subprocess
import mpv  # type: ignore
import json
from typing import Any, cast

from utils import utils
from data import data
from info import info


class Player:
    def __init__(self, root: tk.Tk, channels: list[dict[str, Any]]) -> None:
        self.root = root
        self.channels = channels
        self.current_url = ""
        self.tuning = False
        self.pending_channel: dict[str, Any] | None = None
        self.current_channel_name = f"{info.full_name} v{info.version}"
        self.tuning_timeout: str | None = None
        self.msg_timeout_id: str | None = None
        self.history = self.load_history()
        self.filtered_history: list[dict[str, Any]] = []
        self.history_active_index = 0
        self.history_scroll_delay = 200
        self.history_scroll_interval = 50
        self.up_job: str | None = None
        self.down_job: str | None = None
        self.up_release_job: str | None = None
        self.down_release_job: str | None = None
        self.is_up_pressed = False
        self.is_down_pressed = False
        self.sidebar_visible = False
        self.stall_retries = 0
        self.country_placeholder = "Country"
        self.root.title(data.title)
        self.root.geometry(f"{data.width}x{data.height}")
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

        self.name_label = tk.Label(
            self.top_frame,
            text=self.current_channel_name,
            font=data.font_ui,
            bg=data.bg_color,
            fg=data.fg_color,
        )

        self.name_label.pack(side=tk.LEFT)
        self.btn_frame = tk.Frame(self.top_frame, bg=data.bg_color)
        self.btn_frame.pack(side=tk.RIGHT)
        self.saved_data = self.load_data()
        country_val = self.saved_data.get("country", self.country_placeholder)
        self.country_var = tk.StringVar(value=country_val)

        self.country_entry = tk.Entry(
            self.btn_frame,
            textvariable=self.country_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray" if country_val == self.country_placeholder else data.fg_color,
            insertbackground=data.fg_color,
            width=18,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightcolor=data.btn_border,
            highlightthickness=1,
            bd=0,
        )

        self.country_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.country_entry.bind("<FocusIn>", self.on_country_focus_in)
        self.country_entry.bind("<FocusOut>", self.on_country_focus_out)
        self.country_entry.bind("<Return>", self.on_country_return)
        self.setup_languages()
        lang_val = self.saved_data.get("language", data.any_language)
        self.selected_lang = tk.StringVar(value=lang_val)
        style = ttk.Style()

        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            "TCombobox",
            fieldbackground=data.btn_bg,
            background=data.btn_bg,
            foreground=data.fg_color,
            arrowcolor=data.fg_color,
            bordercolor=data.btn_border,
            lightcolor=data.btn_bg,
            darkcolor=data.btn_bg,
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", data.btn_bg)],
            selectbackground=[("readonly", data.btn_bg)],
            selectforeground=[("readonly", data.fg_color)],
            background=[("readonly", data.btn_bg), ("active", data.btn_active)],
            bordercolor=[("readonly", data.btn_border)],
        )

        self.root.option_add("*TCombobox*Listbox.background", data.btn_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", data.fg_color)
        self.root.option_add("*TCombobox*Listbox.selectBackground", data.btn_active)
        self.root.option_add("*TCombobox*Listbox.selectForeground", data.fg_color)

        self.lang_cb = ttk.Combobox(
            self.btn_frame,
            textvariable=self.selected_lang,
            values=[data.any_language] + self.display_languages,
            state="readonly",
            font=data.font_ui,
            width=16,
        )

        self.lang_cb.pack(side=tk.LEFT, padx=(0, 10))
        self.lang_cb.bind("<<ComboboxSelected>>", self.on_language_selected)

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
        self.video_container.bind("<MouseWheel>", self.on_mouse_wheel)
        self.video_container.bind("<Button-3>", self.toggle_pause)
        self.video_container.bind("<Double-Button-1>", self.toggle_maximize)

        self.sidebar_frame = tk.Frame(
            self.main_content_frame, bg=data.btn_bg, width=300
        )

        self.sidebar_frame.pack_propagate(False)
        self.history_filter_placeholder = "Filter"
        self.history_filter_var = tk.StringVar(value=self.history_filter_placeholder)
        self.history_filter_var.trace_add("write", self.update_sidebar)

        self.history_filter_entry = tk.Entry(
            self.sidebar_frame,
            textvariable=self.history_filter_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray",
            insertbackground=data.fg_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightcolor=data.btn_border,
            highlightthickness=1,
            bd=0,
        )

        self.history_filter_entry.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.history_filter_entry.bind("<FocusIn>", self.on_history_filter_focus_in)
        self.history_filter_entry.bind("<FocusOut>", self.on_history_filter_focus_out)

        self.history_listbox = tk.Listbox(
            self.sidebar_frame,
            bg=data.btn_bg,
            fg=data.fg_color,
            font=data.font_ui,
            relief=tk.FLAT,
            highlightthickness=0,
            selectbackground=data.list_select_bg,
            selectforeground=data.fg_color,
            activestyle="none",
        )

        self.scrollbar = tk.Scrollbar(
            self.sidebar_frame, command=self.history_listbox.yview, bg=data.bg_color
        )

        self.history_listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_listbox.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10
        )

        self.history_listbox.bind("<Button-1>", self.on_history_click)
        self.frames = []
        self.players = []

        for i in range(2):
            frame = tk.Frame(self.video_container, bg="black")
            frame.grid(row=0, column=0, sticky="nsew")

            frame.bind("<Button-4>", self.volume_up)
            frame.bind("<Button-5>", self.volume_down)
            frame.bind("<MouseWheel>", self.on_mouse_wheel)
            frame.bind("<Button-3>", self.toggle_pause)
            frame.bind("<Double-Button-1>", self.toggle_maximize)

            player = mpv.MPV(
                wid=str(frame.winfo_id()),
                hwdec="auto",
                input_vo_keyboard=True,
            )

            self.frames.append(frame)
            self.players.append(player)

        self.active_idx = 0
        self.frames[0].tkraise()
        self.is_fullscreen = False
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.root.bind("<KeyPress-Up>", self.on_up_press)
        self.root.bind("<KeyRelease-Up>", self.on_up_release)
        self.root.bind("<KeyPress-Down>", self.on_down_press)
        self.root.bind("<KeyRelease-Down>", self.on_down_release)
        self.root.bind("<Return>", self.on_return_key)
        self.root.bind("<Key>", self.on_global_key_press)

        @self.players[0].property_observer("playback-time")  # type: ignore
        def check_ready_0(name: str, value: Any) -> None:
            if value is not None and value > 0.1:
                if self.tuning and self.active_idx != 0:
                    self.root.after(0, self.commit_switch, 0)

        @self.players[1].property_observer("playback-time")  # type: ignore
        def check_ready_1(name: str, value: Any) -> None:
            if value is not None and value > 0.1:
                if self.tuning and self.active_idx != 1:
                    self.root.after(0, self.commit_switch, 1)

        if len(self.history) > 0:
            last_channel = self.history[-1]
            self.root.after(500, self.play_specific, last_channel)

        for player in self.players:
            self.register_player_bindings(player)

    def show_info_message(self, text: str) -> None:
        self.name_label.config(text=text)
        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)
        self.msg_timeout_id = self.root.after(3000, self.restore_channel_name)

    def restore_channel_name(self) -> None:
        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)
        self.msg_timeout_id = None
        self.name_label.config(text=self.current_channel_name)

    def register_player_bindings(self, player: mpv.MPV) -> None:
        @player.on_key_press("MBTN_LEFT_DBL")  # type: ignore
        def _on_dbl_click() -> None:
            self.root.after(0, self.toggle_maximize)

        @player.on_key_press("WHEEL_UP")  # type: ignore
        @player.on_key_press("AXIS_UP")  # type: ignore
        def _on_wheel_up() -> None:
            self.root.after(0, self.volume_up)

        @player.on_key_press("WHEEL_DOWN")  # type: ignore
        @player.on_key_press("AXIS_DOWN")  # type: ignore
        def _on_wheel_down() -> None:
            self.root.after(0, self.volume_down)

        @player.on_key_press("MBTN_RIGHT")  # type: ignore
        def _on_right_click() -> None:
            self.root.after(0, self.toggle_pause)

        @player.on_key_press("UP")  # type: ignore
        def _on_up() -> None:
            self.root.after(0, self.move_up)

        @player.on_key_press("DOWN")  # type: ignore
        def _on_down() -> None:
            self.root.after(0, self.move_down)

        @player.on_key_press("ENTER")  # type: ignore
        def _on_enter() -> None:
            self.root.after(0, lambda: self.on_return_key(None))

        @player.on_key_press("ESC")  # type: ignore
        def _on_esc() -> None:
            self.root.after(0, lambda: self.exit_fullscreen(None))

    def toggle_maximize(self, event: Any = None) -> None:
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)

        if self.is_fullscreen:
            self.top_frame.pack_forget()
            if self.sidebar_visible:
                self.sidebar_frame.pack_forget()
        else:
            self.top_frame.pack(
                fill=tk.X, pady=10, padx=15, before=self.main_content_frame
            )

            if self.sidebar_visible:
                self.sidebar_frame.pack(
                    side=tk.RIGHT, fill=tk.Y, before=self.video_container
                )

    def exit_fullscreen(self, event: Any = None) -> None:
        if self.is_fullscreen:
            self.toggle_maximize()

    def on_country_focus_in(self, event: Any) -> None:
        if self.country_var.get() == self.country_placeholder:
            self.country_var.set("")
            self.country_entry.config(fg=data.fg_color)

    def on_country_focus_out(self, event: Any) -> None:
        if self.country_var.get().strip() == "":
            self.country_var.set(self.country_placeholder)
            self.country_entry.config(fg="gray")
        self.save_data()

    def on_history_filter_focus_in(self, event: Any) -> None:
        if self.history_filter_var.get() == self.history_filter_placeholder:
            self.history_filter_var.set("")
            self.history_filter_entry.config(fg=data.fg_color)

    def on_history_filter_focus_out(self, event: Any) -> None:
        if self.history_filter_var.get().strip() == "":
            self.history_filter_var.set(self.history_filter_placeholder)
            self.history_filter_entry.config(fg="gray")

    def on_global_key_press(self, event: Any) -> str | None:
        if not self.sidebar_visible:
            return None

        focused = self.root.focus_get()
        if focused in (self.country_entry, self.history_filter_entry, self.lang_cb):
            return None

        if getattr(event, "char", "") and event.char.isprintable():
            self.history_filter_entry.focus_set()
            if self.history_filter_var.get() == self.history_filter_placeholder:
                self.history_filter_var.set("")
                self.history_filter_entry.config(fg=data.fg_color)
            self.history_filter_entry.insert(tk.END, event.char)
            return "break"
        elif getattr(event, "keysym", "") == "BackSpace":
            self.history_filter_entry.focus_set()
            if self.history_filter_var.get() != self.history_filter_placeholder:
                current = self.history_filter_entry.get()
                if len(current) > 0:
                    self.history_filter_entry.delete(len(current) - 1, tk.END)
            return "break"

        return None

    def move_up(self) -> None:
        if self.sidebar_visible:
            if self.history_active_index > 0:
                self.history_active_index -= 1
                self.draw_history_selection()

    def move_down(self) -> None:
        if self.sidebar_visible:
            if self.history_active_index < len(self.filtered_history) - 1:
                self.history_active_index += 1
                self.draw_history_selection()

    def on_up_press(self, event: Any) -> str | None:
        if self.root.focus_get() == self.lang_cb:
            return None

        if self.up_release_job is not None:
            self.root.after_cancel(self.up_release_job)
            self.up_release_job = None

        if not self.is_up_pressed:
            self.is_up_pressed = True
            self.move_up()

            self.up_job = self.root.after(
                self.history_scroll_delay, self.scroll_up_fast
            )

        if self.sidebar_visible:
            return "break"

        return None

    def on_up_release(self, event: Any) -> str | None:
        if self.root.focus_get() == self.lang_cb:
            return None

        self.up_release_job = self.root.after(10, self.cancel_up_scroll)
        if self.sidebar_visible:
            return "break"

        return None

    def cancel_up_scroll(self) -> None:
        self.is_up_pressed = False
        if self.up_job is not None:
            self.root.after_cancel(self.up_job)
            self.up_job = None

    def scroll_up_fast(self) -> None:
        if self.is_up_pressed:
            self.move_up()

            self.up_job = self.root.after(
                self.history_scroll_interval, self.scroll_up_fast
            )

    def on_down_press(self, event: Any) -> str | None:
        if self.root.focus_get() == self.lang_cb:
            return None

        if self.down_release_job is not None:
            self.root.after_cancel(self.down_release_job)
            self.down_release_job = None

        if not self.is_down_pressed:
            self.is_down_pressed = True
            self.move_down()

            self.down_job = self.root.after(
                self.history_scroll_delay, self.scroll_down_fast
            )

        if self.sidebar_visible:
            return "break"

        return None

    def on_down_release(self, event: Any) -> str | None:
        if self.root.focus_get() == self.lang_cb:
            return None

        self.down_release_job = self.root.after(10, self.cancel_down_scroll)
        if self.sidebar_visible:
            return "break"

        return None

    def cancel_down_scroll(self) -> None:
        self.is_down_pressed = False
        if self.down_job is not None:
            self.root.after_cancel(self.down_job)
            self.down_job = None

    def scroll_down_fast(self) -> None:
        if self.is_down_pressed:
            self.move_down()

            self.down_job = self.root.after(
                self.history_scroll_interval, self.scroll_down_fast
            )

    def on_return_key(self, event: Any) -> str | None:
        focused = self.root.focus_get()

        if focused in (self.country_entry, self.lang_cb):
            return None

        if self.sidebar_visible:
            if len(self.filtered_history) > 0:
                ch = self.filtered_history[self.history_active_index]
                self.root.focus_set()
                self.root.after(0, self.play_specific, ch)
            return "break"

        return None

    def on_country_return(self, event: Any) -> str:
        self.root.focus_set()
        self.save_data()
        self.play_random()
        return "break"

    def on_language_selected(self, event: Any) -> None:
        self.root.focus_set()
        self.save_data()

    def setup_languages(self) -> None:
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

    def load_data(self) -> dict[str, str]:
        config_dir = os.path.dirname(data.data_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        if os.path.exists(data.data_file):
            try:
                with open(data.data_file, "r", encoding="utf-8") as f:
                    return cast(dict[str, str], json.load(f))
            except Exception as e:
                utils.print(f"Failed to load data: {e}")

        return {}

    def save_data(self) -> None:
        config_dir = os.path.dirname(data.data_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        try:
            with open(data.data_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "country": self.country_var.get(),
                        "language": self.selected_lang.get(),
                    },
                    f,
                    indent=4,
                )
        except Exception as e:
            utils.print(f"Failed to save data: {e}")

    def load_history(self) -> list[dict[str, Any]]:
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
                return cast(list[dict[str, Any]], json.load(f))
        except Exception as e:
            utils.print(f"Failed to load history: {e}")

        return []

    def save_history(self) -> None:
        config_dir = os.path.dirname(data.history_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        try:
            with open(data.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            utils.print(f"Failed to save history: {e}")

    def show_history(self) -> None:
        self.update_sidebar()
        self.sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.video_container)
        self.history_btn.config(bg=data.btn_active, relief=tk.SUNKEN)
        self.sidebar_visible = True
        self.root.focus_set()

    def hide_history(self) -> None:
        self.sidebar_frame.pack_forget()
        self.history_btn.config(bg=data.btn_bg, relief=tk.FLAT)
        self.sidebar_visible = False
        self.root.focus_set()

    def toggle_history(self) -> None:
        if self.sidebar_visible:
            self.hide_history()
        else:
            self.show_history()

    def update_sidebar(self, *args: Any) -> None:
        active_url = None

        if len(self.filtered_history) > self.history_active_index >= 0:
            active_url = self.filtered_history[self.history_active_index]["url"]

        self.history_listbox.delete(0, tk.END)
        self.filtered_history = []
        filter_text = self.history_filter_var.get().lower()

        if filter_text == self.history_filter_placeholder.lower():
            filter_text = ""

        for ch in reversed(self.history):
            if filter_text in ch["name"].lower():
                self.filtered_history.append(ch)
                self.history_listbox.insert(tk.END, ch["name"])

        new_active_index = 0

        if active_url:
            for i, ch in enumerate(self.filtered_history):
                if ch["url"] == active_url:
                    new_active_index = i
                    break

        self.history_active_index = new_active_index
        self.draw_history_selection()

    def draw_history_selection(self) -> None:
        self.history_listbox.selection_clear(0, tk.END)

        if len(self.filtered_history) > 0:
            if self.history_active_index >= len(self.filtered_history):
                self.history_active_index = len(self.filtered_history) - 1

            if self.history_active_index < 0:
                self.history_active_index = 0

            self.history_listbox.selection_set(self.history_active_index)
            self.history_listbox.see(self.history_active_index)

    def on_history_click(self, event: Any) -> str:
        index = self.history_listbox.nearest(event.y)  # type: ignore

        if index >= 0:
            bbox = self.history_listbox.bbox(index)

            if bbox:
                if bbox[1] <= event.y <= bbox[1] + bbox[3]:
                    if index < len(self.filtered_history):
                        self.history_active_index = index
                        self.draw_history_selection()
                        ch = self.filtered_history[index]
                        self.root.after(0, self.play_specific, ch)

        return "break"

    def play_random(self) -> None:
        if len(self.channels) == 0:
            return

        if self.tuning:
            self.cancel_tuning()
            return

        self.stall_retries = 0
        self.tuning = True
        self.play_btn.config(state=tk.NORMAL, text="❌ Cancel")
        thread = threading.Thread(target=self.find_live_stream, daemon=True)
        thread.start()

    def play_specific(self, channel: dict[str, Any]) -> None:
        if self.tuning:
            self.cancel_tuning()

        if channel["url"] == self.current_url:
            return

        self.stall_retries = 0
        self.tuning = True
        self.play_btn.config(state=tk.NORMAL, text="❌ Cancel")
        self.prepare_switch(channel)

    def cancel_tuning(self) -> None:
        self.tuning = False
        self.reset_button()
        if self.tuning_timeout is not None:
            self.root.after_cancel(self.tuning_timeout)
            self.tuning_timeout = None
        next_idx = 1 if self.active_idx == 0 else 0
        self.players[next_idx].stop()
        self.show_info_message("Tuning cancelled.")

    def find_live_stream(self) -> None:
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

        if (target_country != "") and (
            target_country != self.country_placeholder.lower()
        ):
            filtered_by_country = []

            for ch in valid_channels:
                c_code = (ch.get("country_code") or "").lower()
                c_name = (ch.get("country_name") or "").lower()

                if (target_country == c_code) or (target_country in c_name):
                    filtered_by_country.append(ch)

            valid_channels = filtered_by_country

        if len(valid_channels) == 0:
            self.root.after(0, self.reset_button)

            self.root.after(
                0, lambda: self.show_info_message("No channels for this filter")
            )

            return

        while working_channel is None:
            if not self.tuning:
                return

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
                    if not self.tuning:
                        return

                    if response.status in [200, 206, 301, 302]:
                        chunk = response.read(16)
                        if len(chunk) > 0:
                            working_channel = candidate
            except Exception:
                continue

        if not self.tuning:
            return

        if working_channel is not None:
            self.root.after(0, self.prepare_switch, working_channel)
        else:
            self.root.after(0, self.reset_button)

            self.root.after(
                0, lambda: self.show_info_message("Could not find a working stream.")
            )

    def prepare_switch(self, channel: dict[str, Any]) -> None:
        self.pending_channel = channel
        next_idx = 0

        if self.active_idx == 0:
            next_idx = 1

        self.tuning_timeout = self.root.after(data.tuning_timeout, self.handle_timeout)
        self.players[next_idx].play(channel["url"])

    def handle_timeout(self) -> None:
        if self.tuning:
            if self.stall_retries < data.max_retries:
                self.stall_retries += 1

                self.show_info_message(
                    f"Stalled. Retrying... ({self.stall_retries}/{data.max_retries})"
                )

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

                self.show_info_message(
                    f"Stream stalled {data.max_retries} times. Roll again."
                )

    def commit_switch(self, ready_idx: int) -> None:
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

        if self.pending_channel is None:
            return

        self.current_url = self.pending_channel["url"]
        self.current_channel_name = self.pending_channel["name"]
        self.restore_channel_name()
        self.play_btn.config(state=tk.NORMAL, text=data.roll_text)

        self.history = [
            ch for ch in self.history if ch["url"] != self.pending_channel["url"]
        ]

        self.history.append(self.pending_channel)

        if len(self.history) > data.max_history:
            self.history.pop(0)

        self.save_history()

        if self.sidebar_visible:
            self.update_sidebar()

    def reset_button(self) -> None:
        self.tuning = False
        self.play_btn.config(state=tk.NORMAL, text=data.roll_text)

    def copy_link(self) -> None:
        if self.current_url != "":
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=self.current_url.encode("utf-8"),
                    check=True,
                )
            except Exception as e:
                utils.print(f"Failed to copy to clipboard: {e}")

    def paste_link(self) -> None:
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

    def on_mouse_wheel(self, event: Any) -> None:
        if event.delta > 0:
            self.volume_up(event)
        elif event.delta < 0:
            self.volume_down(event)

    def volume_up(self, event: Any = None) -> None:
        player = self.players[self.active_idx]

        if player:
            current_vol = player.volume
            if current_vol is not None:
                player.volume = min(current_vol + 5, 100)
                player.show_text(f"Volume: {int(player.volume)}%")

    def volume_down(self, event: Any = None) -> None:
        player = self.players[self.active_idx]

        if player:
            current_vol = player.volume
            if current_vol is not None:
                player.volume = max(current_vol - 5, 0)
                player.show_text(f"Volume: {int(player.volume)}%")

    def toggle_pause(self, event: Any = None) -> None:
        player = self.players[self.active_idx]

        if player:
            if player.pause is not None:
                player.pause = not player.pause
                status = "Paused" if player.pause else "Playing"
                player.show_text(status)
