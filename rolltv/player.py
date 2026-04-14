import os
import sys
import time
import datetime
import mpv  # type: ignore
import threading
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk
from typing import Any

from rolltv.utils import utils
from rolltv.data import data
from rolltv.info import info
from rolltv.args import args
from rolltv.sidebar import Sidebar
from rolltv.topbar import Topbar
from rolltv.store import store
from rolltv.ipc import IPCListener
from rolltv.flags import Flags
from rolltv.status import Status
from rolltv.tuner import Tuner


class Player:
    sidebar_frame: tk.Frame
    menu_sidebar_frame: tk.Frame
    sidebar_filter_placeholder: str
    history_filter_var: tk.StringVar
    country_filter_var: tk.StringVar
    sidebar_filter_frame: tk.Frame
    sidebar_filter_entry: tk.Entry
    sidebar_listbox_frame: tk.Frame
    sidebar_listbox: ttk.Treeview
    scrollbar: tk.Scrollbar
    sidebar_version_label: tk.Label
    name_label: tk.Label
    flag_label: tk.Label
    top_frame: tk.Frame
    country_entry: tk.Entry
    lang_cb: ttk.Combobox
    history_btn: tk.Button
    country_btn: tk.Button
    play_btn: tk.Button

    def __init__(self, root: tk.Tk, channels: list[dict[str, Any]]) -> None:
        self.original_env = os.environ.copy()

        self.is_wayland = (
            os.environ.get("XDG_SESSION_TYPE") == "wayland"
            or "WAYLAND_DISPLAY" in os.environ
        )

        if self.is_wayland:
            # Tkinter runs via XWayland on Wayland systems.
            # Force libmpv to also use X11/XWayland so it can embed successfully using 'wid'.
            os.environ.pop("WAYLAND_DISPLAY", None)

        self.root = root
        self.channels = channels
        self.current_url = ""
        self.tuning = False
        self.is_roll = False
        self.search_id = 0
        self.player_search_ids = {0: -1, 1: -1}
        self.menu_sidebar_visible = False
        self.globe_visible = False
        self.globe_process: Any = None
        self.current_flag_img: tk.PhotoImage | None = None
        self.pending_channel: dict[str, Any] | None = None
        self.current_channel_name = f"{info.full_name} v{info.version}"
        self.current_country = "Unknown"
        self.current_country_code = ""
        self.tuning_timeout: str | None = None
        self.country_count_job: str | None = None
        self.msg_timeout_id: str | None = None
        self.history = store.load_history()
        self.sidebar_items: list[dict[str, Any]] = []
        self.sidebar_active_index = 0
        self.history_scroll_delay = 200
        self.history_scroll_interval = 50
        self.up_job: str | None = None
        self.down_job: str | None = None
        self.up_release_job: str | None = None
        self.down_release_job: str | None = None
        self.roll_anim_job: str | None = None
        self.sidebar_update_job: str | None = None
        self.stall_timeout_id: str | None = None
        self.is_up_pressed = False
        self.is_down_pressed = False
        self.active_sidebar: str | None = None
        self.stall_retries = 0
        self.country_placeholder = "Country"
        self.playback_start_time = time.time()
        self.root.title(data.title)
        self.root.geometry(f"{data.width}x{data.height}")
        self.root.configure(bg=data.bg_color)
        self.saved_data = store.load_data()
        country_val = self.saved_data.get("country", self.country_placeholder)
        self.country_var = tk.StringVar(value=country_val)
        self.country_var.trace_add("write", self.on_country_var_change)
        self.setup_languages()
        lang_val = self.saved_data.get("language", data.any_language)
        self.selected_lang = tk.StringVar(value=lang_val)
        self.flags = Flags(self)
        self.tuner = Tuner(self)
        Topbar(self)
        self.status = Status(self)
        self.schedule_update_country_count()
        self.main_content_frame = tk.Frame(root, bg=data.bg_color)
        self.main_content_frame.pack(fill=tk.BOTH, expand=True)

        Sidebar(self)

        self.video_container = tk.Frame(self.main_content_frame, bg="black")
        self.video_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_container.grid_rowconfigure(0, weight=1)
        self.video_container.grid_columnconfigure(0, weight=1)
        self.video_container.bind("<Button-4>", self.volume_up)
        self.video_container.bind("<Button-5>", self.volume_down)
        self.video_container.bind("<MouseWheel>", self.on_mouse_wheel)
        self.video_container.bind("<Button-3>", self.toggle_pause)
        self.video_container.bind("<Double-Button-1>", self.toggle_maximize)
        self.current_volume = 100
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
                hwdec="auto-safe",
                input_vo_keyboard=True,
                demuxer_max_bytes=1207959552,  # 1.125 GB total buffer (1GB back + 128MB forward)
                demuxer_max_back_bytes=1073741824,  # 1 GB backward buffer (approx 15-20 mins HD)
                cache="yes",
                network_timeout=3,  # Force immediate disconnect for dead links
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64 AppleWebKit/537.36)",  # Bypass 403s
            )

            player.volume = self.current_volume

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
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        @self.players[0].property_observer("playback-time")  # type: ignore
        def check_ready_0(name: str, value: Any) -> None:
            if value is not None and value > 0.1:
                current_id = self.player_search_ids[0]
                self.root.after(0, self.tuner.commit_switch_if_valid, 0, current_id)

        @self.players[1].property_observer("playback-time")  # type: ignore
        def check_ready_1(name: str, value: Any) -> None:
            if value is not None and value > 0.1:
                current_id = self.player_search_ids[1]
                self.root.after(0, self.tuner.commit_switch_if_valid, 1, current_id)

        @self.players[0].property_observer("core-idle")  # type: ignore
        def check_idle_0(name: str, value: Any) -> None:
            if value is not None:
                self.root.after(0, self.handle_idle_change, 0, value)

        @self.players[1].property_observer("core-idle")  # type: ignore
        def check_idle_1(name: str, value: Any) -> None:
            if value is not None:
                self.root.after(0, self.handle_idle_change, 1, value)

        if len(self.history) > 0:
            last_channel = self.history[-1]
            self.root.after(500, self.play_specific, last_channel)

        for player in self.players:
            self.register_player_bindings(player)

        self.ipc_listener = IPCListener(self.root, self)
        self.ipc_listener.start()

    def save_capture(self, duration: int) -> None:
        player = self.players[self.active_idx]

        if not player or getattr(player, "playback_time", None) is None:
            self.show_message("No active stream")
            return

        current_time = getattr(player, "playback_time", 0)

        if current_time is None:
            current_time = 0

        start_time = max(0, current_time - duration)
        end_time = current_time
        captures_dir = args.captures or f"~/.config/{info.name}/captures"
        capture_dir = os.path.expanduser(captures_dir)
        os.makedirs(capture_dir, exist_ok=True)
        now = datetime.datetime.now()
        filename = now.strftime("%d_%m_%Y") + f"_{int(time.time())}.mp4"
        filepath = os.path.join(capture_dir, filename)

        try:
            utils.print(f"Saving to: {filepath}")

            player.command(
                "dump-cache", f"{start_time:.3f}", f"{end_time:.3f}", filepath
            )

            if duration <= 60:
                duration_str = f"{duration}s"
            else:
                duration_str = f"{duration // 60}m"

            self.show_message(f"Saved {duration_str} capture")
        except Exception as e:
            utils.print(f"Capture failed: {e}")
            self.show_message("Capture failed")

    def show_message(self, text: str, auto_restore: bool = True) -> None:
        self.name_label.config(text=text)
        self.flag_label.config(image="")

        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)
            self.msg_timeout_id = None

        if auto_restore:
            self.msg_timeout_id = self.root.after(
                data.info_restore_delay, self.restore_channel_name
            )

    def restore_channel_name(self) -> None:
        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)

        self.msg_timeout_id = None
        self.name_label.config(text=self.current_channel_name)

        if getattr(self, "current_flag_img", None):
            self.flag_label.config(image=self.current_flag_img)  # type: ignore

    def register_player_bindings(self, player: mpv.MPV) -> None:
        @player.on_key_press("MBTN_LEFT_DBL")  # type: ignore
        def on_dbl_click() -> None:
            self.root.after(0, self.toggle_maximize)

        @player.on_key_press("MBTN_LEFT")  # type: ignore
        def on_left_click() -> None:
            self.root.after(0, self.root.focus_set)

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
                self.status.frame.pack_forget()

            if self.active_sidebar:
                self.sidebar_frame.pack_forget()

            if self.menu_sidebar_visible:
                self.menu_sidebar_frame.pack_forget()
        else:
            self.top_frame.pack(fill=tk.X, pady=10, before=self.main_content_frame)

            if args.show_status:
                self.status.frame.pack(
                    side=tk.BOTTOM, fill=tk.X, before=self.main_content_frame
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
            active_var = (
                self.history_filter_var
                if self.active_sidebar == "history"
                else self.country_filter_var
            )

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
        active_var = (
            self.history_filter_var
            if self.active_sidebar == "history"
            else self.country_filter_var
        )

        if active_var.get() == self.sidebar_filter_placeholder:
            active_var.set("")
            self.sidebar_filter_entry.config(fg=data.fg_color)

    def on_sidebar_filter_focus_out(self, event: Any) -> None:
        active_var = (
            self.history_filter_var
            if self.active_sidebar == "history"
            else self.country_filter_var
        )

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

            active_var = (
                self.history_filter_var
                if self.active_sidebar == "history"
                else self.country_filter_var
            )

            if active_var.get() == self.sidebar_filter_placeholder:
                active_var.set("")
                self.sidebar_filter_entry.config(fg=data.fg_color)

            self.sidebar_filter_entry.insert(tk.END, event.char)
            return "break"
        elif getattr(event, "keysym", "") == "BackSpace":
            self.sidebar_filter_entry.focus_set()

            active_var = (
                self.history_filter_var
                if self.active_sidebar == "history"
                else self.country_filter_var
            )

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
                self.root.after(0, self.play_specific, ch, True)

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

        self.schedule_update_country_count()

    def schedule_update_country_count(self, *args: Any) -> None:
        if self.country_count_job is not None:
            self.root.after_cancel(self.country_count_job)

        self.country_count_job = self.root.after(1000, self.update_country_count)

    def update_country_count(self) -> None:
        self.country_count_job = None
        target_country = self.country_var.get().strip().lower()

        if target_country == self.country_placeholder.lower():
            target_country = ""

        if target_country == "" and self.current_country_code != "":
            target_country = self.current_country_code

        if target_country == "":
            self.country_btn.config(text="Country")
            return

        count = sum(
            1
            for ch in self.channels
            if target_country == (ch.get("country_code") or "").lower()
            or (
                len(target_country) > 2
                and target_country in (ch.get("country_name") or "").lower()
            )
        )

        self.country_btn.config(text=f"Country ({count})" if count > 0 else "Country")

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

    def save_data(self) -> None:
        store.save_data(
            {
                "country": self.country_var.get(),
                "language": self.selected_lang.get(),
                "show_status": args.show_status,
                "sound_fx": args.sound_fx,
            }
        )

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

        self.sidebar_filter_frame.pack(
            fill=tk.X, padx=10, pady=(10, 0), before=self.sidebar_listbox_frame
        )

        self.update_sidebar(immediate=True)
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
        self.save_data()

        if args.show_status:
            if not self.is_fullscreen:
                self.status.frame.pack(
                    side=tk.BOTTOM, fill=tk.X, before=self.main_content_frame
                )
            self.status.update()
        else:
            self.status.frame.pack_forget()

        self.show_message(
            "Status Bar Enabled" if args.show_status else "Status Bar Disabled"
        )

    def toggle_sound_fx(self) -> None:
        args.sound_fx = not args.sound_fx
        self.save_data()
        self.show_message("Sound FX Enabled" if args.sound_fx else "Sound FX Disabled")

    def exit_app(self) -> None:
        self.hide_globe()
        self.root.destroy()

    def update_sidebar(self, *args: Any, immediate: bool = False) -> None:
        if self.sidebar_update_job is not None:
            self.root.after_cancel(self.sidebar_update_job)
            self.sidebar_update_job = None

        if immediate:
            self.update_sidebar_impl()
        else:
            delay = 1000 if self.active_sidebar == "country" else 150
            self.sidebar_update_job = self.root.after(delay, self.update_sidebar_impl)

    def update_sidebar_impl(self) -> None:
        self.sidebar_update_job = None

        if not self.active_sidebar:
            return

        active_url = None

        if len(self.sidebar_items) > self.sidebar_active_index >= 0:
            active_url = self.sidebar_items[self.sidebar_active_index]["url"]

        self.sidebar_listbox.delete(*self.sidebar_listbox.get_children())
        self.sidebar_items = []

        active_var = (
            self.history_filter_var
            if self.active_sidebar == "history"
            else self.country_filter_var
        )

        filter_text = active_var.get().lower()

        if filter_text == self.sidebar_filter_placeholder.lower():
            filter_text = ""

        if self.active_sidebar == "history":
            for ch in reversed(self.history):
                name_match = filter_text in ch["name"].lower()
                country_name_match = filter_text in ch.get("country_name", "").lower()

                if name_match or country_name_match:
                    self.sidebar_items.append(ch)

                    if len(self.sidebar_items) >= 200:
                        break

        elif self.active_sidebar == "country":
            target_country = self.country_var.get().strip().lower()

            if target_country == self.country_placeholder.lower():
                target_country = ""

            if target_country == "" and self.current_country_code != "":
                target_country = self.current_country_code

            for ch in self.channels:
                country_match = True

                if target_country != "":
                    c_code = (ch.get("country_code") or "").lower()
                    c_name = (ch.get("country_name") or "").lower()

                    if target_country != c_code and not (
                        len(target_country) > 2 and target_country in c_name
                    ):
                        country_match = False

                if country_match:
                    name_match = filter_text in ch["name"].lower()

                    country_name_match = (
                        filter_text in ch.get("country_name", "").lower()
                    )

                    if name_match or country_name_match:
                        self.sidebar_items.append(ch)

                        if len(self.sidebar_items) >= 200:
                            break

        if not hasattr(self, "fetching_flags"):
            self.fetching_flags: set[Any] = set()

        for ch in self.sidebar_items:
            img = None
            c_code = ch.get("country_code", "")

            if isinstance(c_code, str) and len(c_code) == 2:
                c_code = "gb" if c_code.lower() == "uk" else c_code.lower()
                flag_path = self.flags.get_path(c_code)

                if os.path.exists(flag_path):
                    if c_code not in self.flags.flag_images:
                        try:
                            self.flags.flag_images[c_code] = tk.PhotoImage(
                                file=flag_path
                            )
                        except Exception:
                            pass
                    img = self.flags.flag_images.get(c_code)
                else:
                    if c_code not in self.fetching_flags:
                        self.fetching_flags.add(c_code)

                        threading.Thread(
                            target=self.flags.fetch_only, args=(c_code,), daemon=True
                        ).start()

            if img:
                self.sidebar_listbox.insert(
                    "", tk.END, text=f"   {ch['name']}", image=img
                )
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
                self.root.after(0, self.play_specific, ch, True)
            except ValueError:
                pass

        return "break"

    def play_random(self) -> None:
        self.is_roll = True
        utils.print("[Roll] Loading random stream...")
        self.tuner.play_random()

    def animate_roll_button(self) -> None:
        if self.roll_anim_job is not None:
            self.root.after_cancel(self.roll_anim_job)

        self.play_btn.config(highlightbackground=data.accent_color)

        def restore_style() -> None:
            self.play_btn.config(highlightbackground=data.btn_border)
            self.roll_anim_job = None

        self.roll_anim_job = self.root.after(500, restore_style)

    def play_specific(self, channel: dict[str, Any], manual: bool = False) -> None:
        if manual:
            self.is_roll = False

        self.tuner.play_specific(channel, manual)

    def cancel_tuning(self, event: Any = None) -> None:
        self.tuner.cancel_tuning(event)

    def copy_link(self) -> None:
        if self.current_url != "":
            try:
                if self.is_wayland and shutil.which("wl-copy"):
                    subprocess.run(
                        ["wl-copy"],
                        input=self.current_url.encode("utf-8"),
                        check=True,
                    )
                else:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=self.current_url.encode("utf-8"),
                        check=True,
                    )

                self.show_message("URL Copied")
            except Exception as e:
                utils.print(f"Failed to copy to clipboard: {e}")

    def paste_link(self) -> None:
        clip_text = ""

        if self.is_wayland and shutil.which("wl-paste"):
            try:
                res = subprocess.run(
                    ["wl-paste", "--no-newline"], capture_output=True, text=True
                )

                if res.returncode == 0:
                    clip_text = res.stdout.strip()
            except Exception:
                pass

        if not clip_text:
            try:
                clip_text = self.root.clipboard_get().strip()
            except tk.TclError:
                utils.print("Clipboard is empty or inaccessible.")
                return

        if clip_text != "":
            found_name = "Pasted Stream"

            for ch in self.channels:
                if ch["url"] == clip_text:
                    found_name = ch["name"]
                    break

            channel = {"name": found_name, "url": clip_text}
            self.play_specific(channel, True)

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
                self.current_volume = min(current_vol + 5, 100)

                for p in self.players:
                    p.volume = self.current_volume

                player.show_text(f"Volume: {int(self.current_volume)}%")

    def volume_down(self, event: Any = None) -> None:
        player = self.players[self.active_idx]

        if player:
            current_vol = player.volume

            if current_vol is not None:
                self.current_volume = max(current_vol - 5, 0)

                for p in self.players:
                    p.volume = self.current_volume

                player.show_text(f"Volume: {int(self.current_volume)}%")

    def toggle_pause(self, event: Any = None) -> None:
        player = self.players[self.active_idx]

        if player:
            if player.pause is not None:
                player.pause = not player.pause
                status = "Paused" if player.pause else "Playing"
                player.show_text(status)

                if not player.pause:
                    is_idle = getattr(player, "core_idle", False)
                    self.handle_idle_change(self.active_idx, is_idle)
                else:
                    if getattr(self, "stall_timeout_id", None) is not None:
                        self.root.after_cancel(self.stall_timeout_id)  # type: ignore
                        self.stall_timeout_id = None

    def handle_idle_change(self, idx: int, is_idle: bool) -> None:
        # Check if the inactive (tuning) player threw an idle status
        if self.tuning and idx != self.active_idx:
            if is_idle:
                self.root.after(50, self.handle_tuning_failure)

            return

        if self.active_idx != idx or self.tuning:
            return

        player = self.players[idx]
        if is_idle and not getattr(player, "pause", False):
            if getattr(self, "stall_timeout_id", None) is None:
                self.stall_timeout_id = self.root.after(
                    data.tuning_timeout, self.reconnect_stream
                )
        else:
            if getattr(self, "stall_timeout_id", None) is not None:
                self.root.after_cancel(self.stall_timeout_id)  # type: ignore
                self.stall_timeout_id = None

    def handle_tuning_failure(self) -> None:
        if not self.tuning:
            return

        self.cancel_tuning()

        if getattr(self, "is_roll", False):
            utils.print("[Roll] Stream unreachable or timed out. Fast-rolling next...")
            self.play_random()
        else:
            utils.print("[Player] Stream offline.")
            self.show_message("Stream Offline")

    def reconnect_stream(self) -> None:
        self.stall_timeout_id = None

        if self.tuning or not self.pending_channel:
            return

        if self.is_roll:
            self.play_random()
        else:
            self.play_specific(self.pending_channel)

    def toggle_globe(self) -> None:
        if self.globe_visible:
            self.hide_globe()
        else:
            self.show_globe()

    def show_globe(self) -> None:
        if self.globe_visible:
            return

        self.globe_visible = True
        script_path = os.path.join(os.path.dirname(__file__), "globe.py")
        cmd = [sys.executable, script_path, info.name]
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        self.globe_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=env)
        self.check_globe_process()

        def send_initial_country(retries: int = 5) -> None:
            if self.globe_visible and retries > 0:
                globe_code = self.current_country_code
                if globe_code == "uk":
                    globe_code = "gb"
                self.update_globe_country(globe_code)
                self.root.after(1000, send_initial_country, retries - 1)

        self.root.after(1000, send_initial_country)

    def hide_globe(self) -> None:
        if not self.globe_visible:
            return

        self.globe_visible = False

        if self.globe_process:
            try:
                if self.globe_process.stdin:
                    self.globe_process.stdin.close()

                self.globe_process.terminate()
                self.globe_process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.globe_process.kill()
            except Exception:
                pass

            self.globe_process = None

    def update_globe_country(self, code: str) -> None:
        if self.globe_visible and self.globe_process and self.globe_process.stdin:
            try:
                self.globe_process.stdin.write(f"COUNTRY:{code}\n".encode("utf-8"))
                self.globe_process.stdin.flush()
            except Exception:
                pass

    def set_country_from_globe(self, country_name: str) -> None:
        self.country_var.set(country_name)
        self.country_entry.config(fg=data.fg_color)
        self.on_country_var_change()
        self.play_random()

    def check_globe_process(self) -> None:
        if self.globe_visible and self.globe_process:
            if self.globe_process.poll() is not None:
                self.hide_globe()
            else:
                self.root.after(500, self.check_globe_process)
