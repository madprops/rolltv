import os
import json
import mpv  # type: ignore
import random
import socket
import hashlib
import tempfile
import threading
import subprocess
import tkinter as tk
import urllib.request
from tkinter import ttk
from typing import Any, cast

from utils import utils
from data import data
from info import info
from args import args


class Player:
    def __init__(self, root: tk.Tk, channels: list[dict[str, Any]]) -> None:
        self.root = root
        self.channels = channels
        self.current_url = ""
        self.tuning = False
        self.is_roll = False
        self.search_id = 0
        self.player_search_ids = {0: -1, 1: -1}
        self.pending_channel: dict[str, Any] | None = None
        self.current_channel_name = f"{info.full_name} v{info.version}"
        self.current_country = "Unknown"
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
        self.roll_anim_job: str | None = None
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
        self.top_frame.pack(fill=tk.X, pady=10)
        self.info_frame = tk.Frame(self.top_frame, bg=data.bg_color)
        self.info_frame.pack(side=tk.LEFT, padx=(20, 0))

        self.name_label = tk.Label(
            self.info_frame,
            text=self.current_channel_name,
            font=data.name_font,
            bg=data.bg_color,
            fg=data.fg_color,
            cursor="hand2",
        )

        self.name_label.pack(anchor=tk.W)
        self.name_label.bind("<Button-1>", self.cancel_tuning)
        self.btn_frame = tk.Frame(self.top_frame, bg=data.bg_color)
        self.btn_frame.pack(side=tk.RIGHT, padx=(0, 20))

        if args.show_status:
            self.status_frame = tk.Frame(root, bg=data.btn_bg)
            self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

            self.status_label = tk.Label(
                self.status_frame,
                text="",
                font=data.status_font,
                bg=data.btn_bg,
                fg=data.info_fg,
            )

            self.status_label.pack(anchor=tk.W, padx=20, pady=4)

        self.saved_data = self.load_data()
        country_val = self.saved_data.get("country", self.country_placeholder)
        self.country_var = tk.StringVar(value=country_val)

        self.country_frame = tk.Frame(
            self.btn_frame,
            bg=data.btn_bg,
            highlightbackground=data.btn_border,
            highlightcolor=data.btn_border,
            highlightthickness=1,
            bd=0,
        )

        self.country_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.country_entry = tk.Entry(
            self.country_frame,
            textvariable=self.country_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray" if country_val == self.country_placeholder else data.fg_color,
            insertbackground=data.accent_color,
            width=18,
            relief=tk.FLAT,
            highlightthickness=0,
            bd=0,
        )

        self.country_entry.pack(side=tk.LEFT, padx=8, pady=4)
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
            padding=5,
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", data.btn_bg)],
            selectbackground=[("readonly", data.btn_bg)],
            selectforeground=[("readonly", data.accent_color)],
            background=[("readonly", data.btn_bg), ("active", data.btn_active)],
            bordercolor=[("readonly", data.btn_border)],
        )

        self.root.option_add("*TCombobox*Listbox.background", data.btn_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", data.fg_color)
        self.root.option_add("*TCombobox*Listbox.selectBackground", data.btn_active)
        self.root.option_add("*TCombobox*Listbox.selectForeground", data.accent_color)

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
            text="Copy",
            command=self.copy_link,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.accent_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=4,
        )

        self.copy_btn.pack(side=tk.LEFT, padx=5)

        self.paste_btn = tk.Button(
            self.btn_frame,
            text="Paste",
            command=self.paste_link,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.accent_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=4,
        )

        self.paste_btn.pack(side=tk.LEFT, padx=5)

        self.history_btn = tk.Button(
            self.btn_frame,
            text="History",
            command=self.toggle_history,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.accent_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=4,
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
            activeforeground=data.accent_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=4,
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

        self.history_filter_frame = tk.Frame(
            self.sidebar_frame,
            bg=data.btn_bg,
            highlightbackground=data.btn_border,
            highlightcolor=data.btn_border,
            highlightthickness=1,
            bd=0,
        )

        self.history_filter_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        self.history_filter_entry = tk.Entry(
            self.history_filter_frame,
            textvariable=self.history_filter_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray",
            insertbackground=data.accent_color,
            relief=tk.FLAT,
            highlightthickness=0,
            bd=0,
        )

        self.history_filter_entry.pack(fill=tk.X, padx=8, pady=4)
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
        self.root.bind("<Escape>", self.handle_escape)
        self.root.bind("<KeyPress-Up>", self.on_up_press)
        self.root.bind("<KeyRelease-Up>", self.on_up_release)
        self.root.bind("<KeyPress-Down>", self.on_down_press)
        self.root.bind("<KeyRelease-Down>", self.on_down_release)
        self.root.bind("<Return>", self.on_return_key)
        self.root.bind("<Key>", self.on_global_key_press)
        self.root.bind_all("<Button-1>", self.on_global_click, add="+")

        @self.players[0].property_observer("playback-time")  # type: ignore
        def check_ready_0(name: str, value: Any) -> None:
            if value is not None and value > 0.1:
                current_id = self.player_search_ids[0]
                self.root.after(0, self.commit_switch_if_valid, 0, current_id)

        @self.players[1].property_observer("playback-time")  # type: ignore
        def check_ready_1(name: str, value: Any) -> None:
            if value is not None and value > 0.1:
                current_id = self.player_search_ids[1]
                self.root.after(0, self.commit_switch_if_valid, 1, current_id)

        if len(self.history) > 0:
            last_channel = self.history[-1]
            self.root.after(500, self.play_specific, last_channel)

        for player in self.players:
            self.register_player_bindings(player)

        self.update_status_loop()
        self.start_ipc_listener()

    def show_name_message(self, text: str) -> None:
        self.name_label.config(text=text)

        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)

        self.msg_timeout_id = self.root.after(
            data.info_restore_delay, self.restore_channel_name
        )

    def set_status(self, text: str) -> None:
        if not args.show_status:
            return

        self.status_label.config(text=text)

    def restore_channel_name(self) -> None:
        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)

        self.msg_timeout_id = None
        self.name_label.config(text=self.current_channel_name)

    def update_status_loop(self) -> None:
        self.update_status()
        self.root.after(1000, self.update_status_loop)

    def update_status(self) -> None:
        if not args.show_status:
            return

        if self.tuning:
            self.show_name_message("Tuning...")
            return

        player = self.players[self.active_idx]

        if player and getattr(player, "playback_time", None) is not None:
            w = getattr(player, "width", None)
            h = getattr(player, "height", None)
            res = f"{w}x{h}" if w and h else "Unknown Res"

            fps = getattr(
                player, "container_fps", getattr(player, "estimated_vf_fps", None)
            )

            fps_str = f"{fps:.0f} fps" if fps else "Unknown fps"
            v_br = getattr(player, "video_bitrate", None) or 0
            a_br = getattr(player, "audio_bitrate", None) or 0
            tb = v_br + a_br

            def fmt_br(b: float) -> str:
                if b >= 1000000:
                    return f"{b / 1000000:.1f}M"
                elif b > 0:
                    return f"{b / 1000:.0f}K"
                return "0"

            if tb > 0:
                br_str = f"{fmt_br(tb)}bps (V:{fmt_br(v_br)} A:{fmt_br(a_br)})"
            else:
                br_str = "Unknown bitrate"

            vc = (
                getattr(player, "video_format", getattr(player, "video_codec", None))
                or "No Video"
            )

            ac = (
                getattr(
                    player, "audio_codec_name", getattr(player, "audio_codec", None)
                )
                or "No Audio"
            )

            vc = vc.upper() if isinstance(vc, str) else vc
            ac = ac.upper() if isinstance(ac, str) else ac
            audio_params = getattr(player, "audio_params", None)

            if isinstance(audio_params, dict) and "samplerate" in audio_params:
                sr = audio_params["samplerate"]
                ac += f" ({sr / 1000:.1f}kHz)"

            codecs = f"{vc} / {ac}"
            cache = getattr(player, "demuxer_cache_duration", None)
            cache_str = f"Buf: {cache:.1f}s" if cache is not None else "Buf: 0.0s"
            d_drops = getattr(player, "drop_frame_count", None) or 0
            vo_drops = getattr(player, "vo_drop_frame_count", None) or 0
            drops_str = f"Drops: {d_drops + vo_drops}"
            hwdec = getattr(player, "hwdec_current", None)
            hw_str = f"HW: {hwdec.upper()}" if hwdec and hwdec != "no" else "SW"
            status = f"{self.current_country} | {res} | {fps_str} | {br_str} | {codecs} | {hw_str} | {cache_str} | {drops_str}"
            self.set_status(status)
        else:
            self.set_status("")

    def register_player_bindings(self, player: mpv.MPV) -> None:
        @player.on_key_press("MBTN_LEFT_DBL")  # type: ignore
        def on_dbl_click() -> None:
            self.root.after(0, self.toggle_maximize)

        @player.on_key_press("WHEEL_UP")  # type: ignore
        @player.on_key_press("AXIS_UP")  # type: ignore
        def on_wheel_up() -> None:
            self.root.after(0, self.volume_up)

        @player.on_key_press("WHEEL_DOWN")  # type: ignore
        @player.on_key_press("AXIS_DOWN")  # type: ignore
        def on_wheel_down() -> None:
            self.root.after(0, self.volume_down)

        @player.on_key_press("MBTN_RIGHT")  # type: ignore
        def on_right_click() -> None:
            self.root.after(0, self.toggle_pause)

        @player.on_key_press("UP")  # type: ignore
        def on_up() -> None:
            self.root.after(0, self.move_up)

        @player.on_key_press("DOWN")  # type: ignore
        def on_down() -> None:
            self.root.after(0, self.move_down)

        @player.on_key_press("ENTER")  # type: ignore
        def on_enter() -> None:
            self.root.after(0, lambda: self.on_return_key(None))

        @player.on_key_press("ESC")  # type: ignore
        def on_esc() -> None:
            self.root.after(0, lambda: self.handle_escape(None))

    def toggle_maximize(self, event: Any = None) -> None:
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)

        if self.is_fullscreen:
            self.top_frame.pack_forget()
            self.status_frame.pack_forget()

            if self.sidebar_visible:
                self.sidebar_frame.pack_forget()
        else:
            self.top_frame.pack(fill=tk.X, pady=10, before=self.main_content_frame)

            self.status_frame.pack(
                side=tk.BOTTOM, fill=tk.X, after=self.main_content_frame
            )

            if self.sidebar_visible:
                self.sidebar_frame.pack(
                    side=tk.RIGHT, fill=tk.Y, before=self.video_container
                )

    def handle_escape(self, event: Any = None) -> None:
        focused = self.root.focus_get()

        if focused == self.country_entry:
            current_country = self.country_var.get()

            if current_country != self.country_placeholder and current_country != "":
                self.country_var.set("")
            else:
                self.root.focus_set()
            return

        if self.sidebar_visible and not self.is_fullscreen:
            current_filter = self.history_filter_var.get()

            if (
                current_filter != self.history_filter_placeholder
                and current_filter != ""
            ):
                if focused == self.history_filter_entry:
                    self.history_filter_var.set("")
                else:
                    self.history_filter_var.set(self.history_filter_placeholder)
                    self.history_filter_entry.config(fg="gray")

                return
            elif focused == self.history_filter_entry:
                self.root.focus_set()
                return

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

    def on_global_click(self, event: Any) -> None:
        if not isinstance(getattr(event, "widget", None), (tk.Entry, ttk.Combobox)):
            self.root.focus_set()

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

        self.animate_roll_button()

        if self.tuning:
            self.cancel_tuning()

        self.stall_retries = 0
        self.tuning = True
        self.is_roll = True
        self.search_id += 1

        thread = threading.Thread(
            target=self.find_live_stream, args=(self.search_id,), daemon=True
        )

        thread.start()

    def animate_roll_button(self) -> None:
        if self.roll_anim_job is not None:
            self.root.after_cancel(self.roll_anim_job)

        self.play_btn.config(highlightbackground=data.accent_color)

        def restore_style() -> None:
            self.play_btn.config(highlightbackground=data.btn_border)
            self.roll_anim_job = None

        self.roll_anim_job = self.root.after(500, restore_style)

    def play_specific(self, channel: dict[str, Any]) -> None:
        if self.tuning:
            self.cancel_tuning()

        if channel["url"] == self.current_url:
            return

        for db_ch in self.channels:
            if db_ch["url"] == channel["url"]:
                for key, value in db_ch.items():
                    if key not in channel or not channel[key]:
                        channel[key] = value

                break

        self.stall_retries = 0
        self.tuning = True
        self.is_roll = False
        self.search_id += 1
        self.prepare_switch(channel, self.search_id)

    def cancel_tuning(self, event: Any = None) -> None:
        if not self.tuning:
            return

        self.tuning = False

        if self.tuning_timeout is not None:
            self.root.after_cancel(self.tuning_timeout)
            self.tuning_timeout = None

        next_idx = 1 if self.active_idx == 0 else 0
        self.player_search_ids[next_idx] = -1
        self.players[next_idx].stop()
        self.restore_channel_name()

    def find_live_stream(self, my_search_id: int) -> None:
        working_channel = None
        sel_lang = self.selected_lang.get()
        valid_channels = self.channels

        if sel_lang != data.any_language:
            target_code = self.lang_map_rev.get(sel_lang, sel_lang)
            valid_channels = [
                ch
                for ch in valid_channels
                if target_code in (ch.get("languages") or [])
            ]

        target_country = self.country_var.get().strip().lower()

        if (target_country != "") and (
            target_country != self.country_placeholder.lower()
        ):
            valid_channels = [
                ch
                for ch in valid_channels
                if target_country == (ch.get("country_code") or "").lower()
                or target_country in (ch.get("country_name") or "").lower()
            ]

        recent_urls = {ch["url"] for ch in self.history[-data.recent_urls:]}
        fresh_channels = [ch for ch in valid_channels if ch["url"] not in recent_urls]

        if len(fresh_channels) > 0:
            valid_channels = fresh_channels

        if len(valid_channels) == 0:
            self.root.after(0, self.reset_button)

            self.root.after(
                0, lambda: self.show_name_message("No channels for this filter")
            )

            return

        candidates = random.sample(valid_channels, min(30, len(valid_channels)))

        for candidate in candidates:
            if not self.tuning or my_search_id != self.search_id:
                return

            if (
                self.is_roll
                and self.pending_channel
                and (candidate["url"] == self.pending_channel["url"])
                and (len(valid_channels) > 1)
            ):
                continue

            try:
                req = urllib.request.Request(
                    candidate["url"],
                    method="GET",
                    headers={"User-Agent": "mpv/0.34.0"},
                )

                with urllib.request.urlopen(req, timeout=data.url_timeout) as response:
                    if not self.tuning or (my_search_id != self.search_id):
                        return

                    if response.status in [200, 206, 301, 302]:
                        chunk = response.read(2048)

                        if len(chunk) > 0:
                            text_chunk = chunk.decode("utf-8", errors="ignore")

                            if "#EXTM3U" in text_chunk:
                                if (
                                    "#EXTINF" not in text_chunk
                                    and "#EXT-X" not in text_chunk
                                ):
                                    continue

                            working_channel = candidate
                            break
            except Exception:
                continue

        if not self.tuning or my_search_id != self.search_id:
            return

        if working_channel is not None:
            self.root.after(0, self.prepare_switch, working_channel, my_search_id)
        else:
            self.root.after(0, self.reset_button)

            self.root.after(
                0, lambda: self.show_name_message("Could not find a working stream.")
            )

    def prepare_switch(self, channel: dict[str, Any], search_id: int) -> None:
        if not self.tuning or search_id != self.search_id:
            return

        self.pending_channel = channel
        next_idx = 0

        if self.active_idx == 0:
            next_idx = 1

        if self.tuning_timeout is not None:
            self.root.after_cancel(self.tuning_timeout)

        self.tuning_timeout = self.root.after(
            data.tuning_timeout, lambda: self.handle_timeout(search_id)
        )

        self.player_search_ids[next_idx] = search_id
        self.players[next_idx].play(channel["url"])

    def handle_timeout(self, search_id: int) -> None:
        if not self.tuning or (search_id != self.search_id):
            return

        if self.is_roll or self.stall_retries < data.max_retries:
            if self.is_roll:
                self.stall_retries = 0
                self.show_name_message("Stalled. Trying a different stream...")
            else:
                self.stall_retries += 1

                self.show_name_message(
                    f"Stalled. Retrying... ({self.stall_retries}/{data.max_retries})"
                )

            next_idx = 0

            if self.active_idx == 0:
                next_idx = 1

            self.player_search_ids[next_idx] = -1
            self.players[next_idx].stop()

            self.search_id += 1
            new_search_id = self.search_id

            if self.is_roll:
                thread = threading.Thread(
                    target=self.find_live_stream, args=(new_search_id,), daemon=True
                )

                thread.start()
            elif self.pending_channel:
                self.prepare_switch(self.pending_channel, new_search_id)
        else:
            self.tuning = False
            next_idx = 0

            if self.active_idx == 0:
                next_idx = 1

            self.player_search_ids[next_idx] = -1
            self.players[next_idx].stop()

            self.show_name_message(
                f"Stream stalled {data.max_retries} times. Roll again."
            )

    def commit_switch_if_valid(self, ready_idx: int, search_id: int) -> None:
        if not self.tuning or search_id != self.search_id:
            return
        if self.active_idx == ready_idx:
            return

        self.commit_switch(ready_idx)

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

        self.player_search_ids[old_idx] = -1
        self.players[old_idx].stop()

        if self.pending_channel is None:
            return

        self.current_url = self.pending_channel["url"]
        c_name = self.pending_channel.get("country_name", "")
        self.current_country = c_name.title() if c_name else "Unknown"
        self.current_channel_name = self.pending_channel["name"]
        self.restore_channel_name()

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

    def start_ipc_listener(self) -> None:
        def listener() -> None:
            if os.name == "posix":
                # Unix Domain Socket for Linux/Mac (X11 & Wayland)
                socket_path = os.path.join(
                    tempfile.gettempdir(), f"{info.name}_ipc.sock"
                )

                if os.path.exists(socket_path):
                    try:
                        os.remove(socket_path)
                    except OSError:
                        pass

                server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                server.bind(socket_path)
            else:
                # Localhost TCP Socket for Windows
                port = (
                    50000 + int(hashlib.md5(info.name.encode()).hexdigest(), 16) % 10000
                )
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                try:
                    server.bind(("127.0.0.1", port))
                except OSError:
                    return

            server.listen(1)

            while True:
                try:
                    conn, _ = server.accept()
                    data = conn.recv(1024).decode("utf-8")

                    if data == "RAISE":
                        # Safely trigger the Tkinter event from the background thread
                        self.root.after(0, self.raise_window)

                    conn.close()
                except Exception:
                    break

        thread = threading.Thread(target=listener, daemon=True)
        thread.start()

    def raise_window(self) -> None:
        if self.root.state() == "iconic":
            self.root.deiconify()

        if os.name == "posix":
            self.root.withdraw()
            self.root.deiconify()

        self.root.attributes("-topmost", True)
        self.root.attributes("-topmost", False)
        self.root.lift()
        self.root.focus_force()
