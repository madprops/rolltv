import os
import json
import mpv  # type: ignore
import random
import socket
import hashlib
import tempfile
import threading
import emoji
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
        self.menu_sidebar_visible = False
        self.current_flag_img: tk.PhotoImage | None = None
        self.pending_channel: dict[str, Any] | None = None
        self.current_channel_name = f"{info.full_name} v{info.version}"
        self.current_country = "Unknown"
        self.tuning_timeout: str | None = None
        self.msg_timeout_id: str | None = None
        self.history = self.load_history()
        self.sidebar_items: list[dict[str, Any]] = []
        self.sidebar_active_index = 0
        self.history_scroll_delay = 200
        self.history_scroll_interval = 50
        self.up_job: str | None = None
        self.down_job: str | None = None
        self.up_release_job: str | None = None
        self.down_release_job: str | None = None
        self.roll_anim_job: str | None = None
        self.is_up_pressed = False
        self.is_down_pressed = False
        self.active_sidebar: str | None = None
        self.stall_retries = 0
        self.country_placeholder = "Country"
        self.root.title(data.title)
        self.root.geometry(f"{data.width}x{data.height}")
        self.root.configure(bg=data.bg_color)
        self.top_frame = tk.Frame(root, bg=data.bg_color)
        self.top_frame.pack(fill=tk.X, pady=10)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.png")

        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
            except Exception as e:
                utils.print(f"Could not load icon: {e}")

        self.menu_btn = tk.Label(
            self.top_frame,
            text=info.full_name,
            font=data.name_font,
            fg=data.accent_color,
            bg=data.bg_color,
            cursor="hand2",
        )

        self.menu_btn.pack(side=tk.LEFT, padx=(20, 5))
        self.menu_btn.bind("<Button-1>", self.toggle_menu)
        self.info_frame = tk.Frame(self.top_frame, bg=data.bg_color)
        self.info_frame.pack(side=tk.LEFT, padx=(10, 0))

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
        self.country_var.trace_add("write", self.on_country_var_change)

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

        self.country_btn = tk.Button(
            self.btn_frame,
            text="Country",
            command=self.toggle_country,
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

        self.country_btn.pack(side=tk.LEFT, padx=5)

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

        self.menu_sidebar_frame = tk.Frame(
            self.main_content_frame, bg=data.btn_bg, width=200, bd=0, highlightthickness=0
        )

        self.menu_sidebar_frame.pack_propagate(False)

        self.toggle_status_btn = tk.Button(
            self.menu_sidebar_frame,
            text="Toggle Status",
            command=self.toggle_status,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.accent_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=0,
            bd=0,
            padx=12,
            pady=4,
            anchor="w",
        )

        self.toggle_status_btn.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.exit_btn = tk.Button(
            self.menu_sidebar_frame,
            text="Exit",
            command=self.exit_app,
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.btn_active,
            activeforeground=data.accent_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=0,
            bd=0,
            padx=12,
            pady=4,
            anchor="w",
        )

        self.exit_btn.pack(fill=tk.X, padx=10, pady=5)

        self.sidebar_version_label = tk.Label(
            self.menu_sidebar_frame,
            text=f"v{info.version}",
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.info_fg,
            anchor="w",
        )

        self.sidebar_version_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
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
            self.main_content_frame, bg=data.btn_bg, width=300, bd=0, highlightthickness=0
        )

        self.sidebar_frame.pack_propagate(False)
        self.sidebar_filter_placeholder = "Filter"
        self.history_filter_var = tk.StringVar(value=self.sidebar_filter_placeholder)
        self.history_filter_var.trace_add("write", self.update_sidebar)
        self.country_filter_var = tk.StringVar(value=self.sidebar_filter_placeholder)
        self.country_filter_var.trace_add("write", self.update_sidebar)

        self.sidebar_filter_frame = tk.Frame(
            self.sidebar_frame,
            bg=data.btn_bg,
            highlightbackground=data.btn_border,
            highlightcolor=data.btn_border,
            highlightthickness=0,
            bd=0,
        )

        self.sidebar_filter_entry = tk.Entry(
            self.sidebar_filter_frame,
            textvariable=self.history_filter_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray",
            insertbackground=data.accent_color,
            relief=tk.FLAT,
            highlightthickness=0,
            bd=0,
        )

        self.sidebar_filter_entry.pack(fill=tk.X, padx=8, pady=4)
        self.sidebar_filter_entry.bind("<FocusIn>", self.on_sidebar_filter_focus_in)
        self.sidebar_filter_entry.bind("<FocusOut>", self.on_sidebar_filter_focus_out)
        self.sidebar_listbox_frame = tk.Frame(self.sidebar_frame, bg=data.btn_bg)
        self.sidebar_listbox_frame.pack(fill=tk.BOTH, expand=True)

        style.configure(
            "Sidebar.Treeview",
            background=data.btn_bg,
            foreground=data.fg_color,
            fieldbackground=data.btn_bg,
            borderwidth=0,
            bordercolor=data.btn_bg,
            lightcolor=data.btn_bg,
            darkcolor=data.btn_bg,
            font=data.font_ui,
            rowheight=24,
        )

        style.map(
            "Sidebar.Treeview",
            background=[("selected", data.list_select_bg)],
            foreground=[("selected", data.fg_color)],
        )

        self.sidebar_listbox = ttk.Treeview(
            self.sidebar_listbox_frame,
            style="Sidebar.Treeview",
            show="tree",
            selectmode="browse",
        )

        self.scrollbar = tk.Scrollbar(
            self.sidebar_listbox_frame,
            command=self.sidebar_listbox.yview,
            bg=data.bg_color,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
        )

        self.sidebar_listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.sidebar_listbox.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10
        )

        self.sidebar_listbox.bind("<Button-1>", self.on_sidebar_click)
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
        self.name_label.config(text=text, image="", compound=tk.NONE)

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
        if getattr(self, "current_flag_img", None):
            self.name_label.config(image=self.current_flag_img, compound=tk.RIGHT)

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

            if args.show_status:
                self.status_frame.pack_forget()

            if self.active_sidebar:
                self.sidebar_frame.pack_forget()
            if self.menu_sidebar_visible:
                self.menu_sidebar_frame.pack_forget()
        else:
            self.top_frame.pack(fill=tk.X, pady=10, before=self.main_content_frame)

            if args.show_status:
                self.status_frame.pack(
                    side=tk.BOTTOM, fill=tk.X, after=self.main_content_frame
                )

            if self.menu_sidebar_visible:
                self.menu_sidebar_frame.pack(
                    side=tk.LEFT, fill=tk.Y, before=self.video_container
                )

            if self.active_sidebar:
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

        if self.active_sidebar and not self.is_fullscreen:
            active_var = self.history_filter_var if self.active_sidebar == "history" else self.country_filter_var
            current_filter = active_var.get()

            if (
                current_filter != self.sidebar_filter_placeholder
                and current_filter != ""
            ):
                if focused == self.sidebar_filter_entry:
                    active_var.set("")
                else:
                    active_var.set(self.sidebar_filter_placeholder)
                    self.sidebar_filter_entry.config(fg="gray")

                return
            elif focused == self.sidebar_filter_entry:
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

    def on_sidebar_filter_focus_in(self, event: Any) -> None:
        active_var = self.history_filter_var if self.active_sidebar == "history" else self.country_filter_var
        if active_var.get() == self.sidebar_filter_placeholder:
            active_var.set("")
            self.sidebar_filter_entry.config(fg=data.fg_color)

    def on_sidebar_filter_focus_out(self, event: Any) -> None:
        active_var = self.history_filter_var if self.active_sidebar == "history" else self.country_filter_var
        if active_var.get().strip() == "":
            active_var.set(self.sidebar_filter_placeholder)
            self.sidebar_filter_entry.config(fg="gray")

    def on_global_key_press(self, event: Any) -> str | None:
        if not self.active_sidebar:
            return None

        focused = self.root.focus_get()

        if focused in (self.country_entry, self.sidebar_filter_entry, self.lang_cb):
            return None

        if getattr(event, "char", "") and event.char.isprintable():
            self.sidebar_filter_entry.focus_set()

            active_var = self.history_filter_var if self.active_sidebar == "history" else self.country_filter_var
            if active_var.get() == self.sidebar_filter_placeholder:
                active_var.set("")
                self.sidebar_filter_entry.config(fg=data.fg_color)

            self.sidebar_filter_entry.insert(tk.END, event.char)
            return "break"
        elif getattr(event, "keysym", "") == "BackSpace":
            self.sidebar_filter_entry.focus_set()

            active_var = self.history_filter_var if self.active_sidebar == "history" else self.country_filter_var
            if active_var.get() != self.sidebar_filter_placeholder:
                current = self.sidebar_filter_entry.get()

                if len(current) > 0:
                    self.sidebar_filter_entry.delete(len(current) - 1, tk.END)

            return "break"

        return None

    def on_global_click(self, event: Any) -> None:
        if not isinstance(getattr(event, "widget", None), (tk.Entry, ttk.Combobox)):
            self.root.focus_set()

    def move_up(self) -> None:
        if self.active_sidebar:
            if self.sidebar_active_index > 0:
                self.sidebar_active_index -= 1
                self.draw_sidebar_selection()

    def move_down(self) -> None:
        if self.active_sidebar:
            if self.sidebar_active_index < len(self.sidebar_items) - 1:
                self.sidebar_active_index += 1
                self.draw_sidebar_selection()

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

        if self.active_sidebar:
            return "break"

        return None

    def on_up_release(self, event: Any) -> str | None:
        if self.root.focus_get() == self.lang_cb:
            return None

        self.up_release_job = self.root.after(10, self.cancel_up_scroll)

        if self.active_sidebar:
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

        if self.active_sidebar:
            return "break"

        return None

    def on_down_release(self, event: Any) -> str | None:
        if self.root.focus_get() == self.lang_cb:
            return None

        self.down_release_job = self.root.after(10, self.cancel_down_scroll)

        if self.active_sidebar:
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

        if self.active_sidebar:
            if len(self.sidebar_items) > 0:
                ch = self.sidebar_items[self.sidebar_active_index]
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

    def on_country_var_change(self, *args: Any) -> None:
        if self.active_sidebar == "country":
            self.update_sidebar()

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

    def toggle_sidebar(self, sidebar_type: str) -> None:
        if self.active_sidebar == sidebar_type:
            self.hide_sidebar()
        else:
            self.show_sidebar(sidebar_type)

    def show_sidebar(self, sidebar_type: str) -> None:
        self.active_sidebar = sidebar_type

        if sidebar_type == "history":
            self.history_btn.config(bg=data.btn_active, relief=tk.SUNKEN)
            self.country_btn.config(bg=data.btn_bg, relief=tk.FLAT)
            self.sidebar_filter_entry.config(textvariable=self.history_filter_var)

            if self.history_filter_var.get() == self.sidebar_filter_placeholder:
                self.sidebar_filter_entry.config(fg="gray")
            else:
                self.sidebar_filter_entry.config(fg=data.fg_color)
        elif sidebar_type == "country":
            self.country_btn.config(bg=data.btn_active, relief=tk.SUNKEN)
            self.history_btn.config(bg=data.btn_bg, relief=tk.FLAT)
            self.sidebar_filter_entry.config(textvariable=self.country_filter_var)

            if self.country_filter_var.get() == self.sidebar_filter_placeholder:
                self.sidebar_filter_entry.config(fg="gray")
            else:
                self.sidebar_filter_entry.config(fg=data.fg_color)

        self.sidebar_filter_frame.pack(fill=tk.X, padx=10, pady=(10, 0), before=self.sidebar_listbox_frame)

        self.update_sidebar()
        self.sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.video_container)
        self.root.focus_set()

    def hide_sidebar(self) -> None:
        self.active_sidebar = None
        self.sidebar_frame.pack_forget()
        self.history_btn.config(bg=data.btn_bg, relief=tk.FLAT)
        self.country_btn.config(bg=data.btn_bg, relief=tk.FLAT)
        self.root.focus_set()

    def toggle_history(self) -> None:
        self.toggle_sidebar("history")

    def toggle_country(self) -> None:
        self.toggle_sidebar("country")

    def toggle_menu(self, event: Any = None) -> None:
        if self.menu_sidebar_visible:
            self.hide_menu()
        else:
            self.show_menu()

    def show_menu(self) -> None:
        self.menu_sidebar_frame.pack(
            side=tk.LEFT, fill=tk.Y, before=self.video_container
        )

        self.menu_sidebar_visible = True

    def hide_menu(self) -> None:
        self.menu_sidebar_frame.pack_forget()
        self.menu_sidebar_visible = False

    def toggle_status(self) -> None:
        args.show_status = not args.show_status

        if args.show_status:
            self.toggle_status_btn.config(bg=data.btn_active)
            if not self.is_fullscreen:
                self.status_frame.pack(
                    side=tk.BOTTOM, fill=tk.X, after=self.main_content_frame
                )
        else:
            self.toggle_status_btn.config(bg=data.btn_bg)
            self.status_frame.pack_forget()

    def exit_app(self) -> None:
        self.root.destroy()

    def update_sidebar(self, *args: Any) -> None:
        if not self.active_sidebar:
            return

        active_url = None

        if len(self.sidebar_items) > self.sidebar_active_index >= 0:
            active_url = self.sidebar_items[self.sidebar_active_index]["url"]

        self.sidebar_listbox.delete(*self.sidebar_listbox.get_children())
        self.sidebar_items = []

        if not hasattr(self, "flag_images"):
            self.flag_images = {}

        active_var = self.history_filter_var if self.active_sidebar == "history" else self.country_filter_var
        filter_text = active_var.get().lower()

        if filter_text == self.sidebar_filter_placeholder.lower():
            filter_text = ""

        if self.active_sidebar == "history":
            for ch in reversed(self.history):
                name_match = filter_text in ch["name"].lower()
                country_name_match = filter_text in ch.get("country_name", "").lower()

                if name_match or country_name_match:
                    self.sidebar_items.append(ch)

        elif self.active_sidebar == "country":
            target_country = self.country_var.get().strip().lower()

            if target_country == self.country_placeholder.lower():
                target_country = ""

            for ch in self.channels:
                country_match = True

                if target_country != "":
                    c_code = (ch.get("country_code") or "").lower()
                    c_name = (ch.get("country_name") or "").lower()

                    if target_country != c_code and target_country not in c_name:
                        country_match = False

                if country_match:
                    name_match = filter_text in ch["name"].lower()
                    country_name_match = filter_text in ch.get("country_name", "").lower()

                    if name_match or country_name_match:
                        self.sidebar_items.append(ch)

        for ch in self.sidebar_items:
            img = None
            c_code = ch.get("country_code", "")

            if isinstance(c_code, str) and len(c_code) == 2:
                c_code = "gb" if c_code.lower() == "uk" else c_code.lower()
                flag_path = os.path.expanduser(f"~/.config/{info.name}/flags/{c_code}.png")

                if os.path.exists(flag_path):
                    if c_code not in self.flag_images:
                        try:
                            self.flag_images[c_code] = tk.PhotoImage(file=flag_path)
                        except Exception:
                            pass
                    img = self.flag_images.get(c_code)
                else:
                    threading.Thread(target=self.fetch_flag_only, args=(c_code,), daemon=True).start()

            if img:
                self.sidebar_listbox.insert("", tk.END, text=f"   {ch['name']}", image=img)
            else:
                self.sidebar_listbox.insert("", tk.END, text=f"   {ch['name']}")

        new_active_index = 0

        if active_url:
            for i, ch in enumerate(self.sidebar_items):
                if ch["url"] == active_url:
                    new_active_index = i
                    break

        self.sidebar_active_index = new_active_index
        self.draw_sidebar_selection()

    def draw_sidebar_selection(self) -> None:
        sel = self.sidebar_listbox.selection()

        if sel:
            self.sidebar_listbox.selection_remove(*sel)

        if len(self.sidebar_items) > 0:
            if self.sidebar_active_index >= len(self.sidebar_items):
                self.sidebar_active_index = len(self.sidebar_items) - 1

            if self.sidebar_active_index < 0:
                self.sidebar_active_index = 0

            children = self.sidebar_listbox.get_children()

            if self.sidebar_active_index < len(children):
                item_id = children[self.sidebar_active_index]
                self.sidebar_listbox.selection_set(item_id)
                self.sidebar_listbox.see(item_id)

    def on_sidebar_click(self, event: Any) -> str:
        item_id = self.sidebar_listbox.identify_row(event.y)

        if item_id:
            children = self.sidebar_listbox.get_children()
            try:
                index = children.index(item_id)
                self.sidebar_active_index = index
                self.draw_sidebar_selection()
                ch = self.sidebar_items[index]
                self.root.after(0, self.play_specific, ch)
            except ValueError:
                pass

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

        recent_urls = {ch["url"] for ch in self.history[-data.recent_urls :]}
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
        self.players[next_idx].mute = True
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
        self.players[ready_idx].mute = False
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
        name = self.pending_channel.get("name", "Unknown")
        self.current_channel_name = f"{name}   "
        c_code = self.pending_channel.get("country_code", "")

        if isinstance(c_code, str) and len(c_code) == 2:
            c_code = "gb" if c_code.lower() == "uk" else c_code.lower()
            threading.Thread(target=self.load_or_fetch_flag, args=(c_code, self.current_channel_name), daemon=True).start()
        else:
            self.clear_flag_image()
        self.restore_channel_name()

        self.history = [
            ch for ch in self.history if ch["url"] != self.pending_channel["url"]
        ]

        self.history.append(self.pending_channel)

        if len(self.history) > data.max_history:
            self.history.pop(0)

        self.save_history()

        if self.active_sidebar:
            self.update_sidebar()

    def load_or_fetch_flag(self, c_code: str, expected_name: str) -> None:
        flag_dir = os.path.expanduser(f"~/.config/{info.name}/flags")
        os.makedirs(flag_dir, exist_ok=True)
        flag_path = os.path.join(flag_dir, f"{c_code}.png")

        if not os.path.exists(flag_path):
            try:
                url = f"https://flagcdn.com/24x18/{c_code}.png"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200:
                        with open(flag_path, "wb") as f:
                            f.write(response.read())
            except Exception:
                self.root.after(0, self.clear_flag_image)
                return

        self.root.after(0, self.apply_flag_image, flag_path, expected_name)

    def apply_flag_image(self, flag_path: str, expected_name: str) -> None:
        if self.current_channel_name != expected_name:
            return
        try:
            self.current_flag_img = tk.PhotoImage(file=flag_path)
            self.name_label.config(image=self.current_flag_img, compound=tk.RIGHT)
        except Exception:
            self.clear_flag_image()

    def clear_flag_image(self) -> None:
        self.current_flag_img = None
        self.name_label.config(image="", compound=tk.NONE)

    def fetch_flag_only(self, c_code: str) -> None:
        flag_dir = os.path.expanduser(f"~/.config/{info.name}/flags")
        os.makedirs(flag_dir, exist_ok=True)
        flag_path = os.path.join(flag_dir, f"{c_code}.png")

        if not os.path.exists(flag_path):
            try:
                url = f"https://flagcdn.com/24x18/{c_code}.png"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200:
                        with open(flag_path, "wb") as f:
                            f.write(response.read())

                        def update_images() -> None:
                            try:
                                if not hasattr(self, "flag_images"):
                                    self.flag_images = {}
                                self.flag_images[c_code] = tk.PhotoImage(file=flag_path)
                            except Exception:
                                return
                            if self.active_sidebar:
                                self.update_sidebar()

                        self.root.after(0, update_images)
            except Exception:
                pass

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
