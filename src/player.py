import os
import mpv  # type: ignore
import threading
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Any

from utils import utils
from data import data
from info import info
from args import args
from sidebar import Sidebar
from topbar import Topbar
from store import store
from ipc import IPCListener
from flags import Flags
from status import Status
from tuner import Tuner


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
    top_frame: tk.Frame
    country_entry: tk.Entry
    lang_cb: ttk.Combobox
    history_btn: tk.Button
    country_btn: tk.Button
    play_btn: tk.Button

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
        self.is_up_pressed = False
        self.is_down_pressed = False
        self.active_sidebar: str | None = None
        self.stall_retries = 0
        self.country_placeholder = "Country"
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
                hwdec="auto",
                input_vo_keyboard=True,
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

        if len(self.history) > 0:
            last_channel = self.history[-1]
            self.root.after(500, self.play_specific, last_channel)

        for player in self.players:
            self.register_player_bindings(player)

        self.ipc_listener = IPCListener(self.root)
        self.ipc_listener.start()

    def show_name_message(self, text: str) -> None:
        self.name_label.config(text=text, image="", compound=tk.NONE)

        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)

        self.msg_timeout_id = self.root.after(
            data.info_restore_delay, self.restore_channel_name
        )

    def restore_channel_name(self) -> None:
        if self.msg_timeout_id is not None:
            self.root.after_cancel(self.msg_timeout_id)

        self.msg_timeout_id = None
        self.name_label.config(text=self.current_channel_name)

        if getattr(self, "current_flag_img", None):
            self.name_label.config(image=self.current_flag_img, compound=tk.RIGHT)  # type: ignore

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
                self.status.frame.pack_forget()

            if self.active_sidebar:
                self.sidebar_frame.pack_forget()
            if self.menu_sidebar_visible:
                self.menu_sidebar_frame.pack_forget()
        else:
            self.top_frame.pack(fill=tk.X, pady=10, before=self.main_content_frame)

            if args.show_status:
                self.status.frame.pack(
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
            if not self.is_fullscreen:
                self.status.frame.pack(
                    side=tk.BOTTOM, fill=tk.X, after=self.main_content_frame
                )
        else:
            self.status.frame.pack_forget()

        self.show_name_message(
            "Status Bar Enabled" if args.show_status else "Status Bar Disabled"
        )

    def toggle_sound_fx(self) -> None:
        args.sound_fx = not args.sound_fx

        self.show_name_message(
            "Sound FX Enabled" if args.sound_fx else "Sound FX Disabled"
        )

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

                    country_name_match = (
                        filter_text in ch.get("country_name", "").lower()
                    )

                    if name_match or country_name_match:
                        self.sidebar_items.append(ch)

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
        self.tuner.play_specific(channel, manual)

    def cancel_tuning(self, event: Any = None) -> None:
        self.tuner.cancel_tuning(event)

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
                self.play_specific(channel, True)
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
