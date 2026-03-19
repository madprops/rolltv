import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from data import data
from info import info
from utils import utils


class Topbar:
    def __init__(self, player: Any) -> None:
        self.player = player
        self.create_topbar()

    def bind_hover(self, btn: tk.Button) -> None:
        def on_enter(e: Any) -> None:
            if str(btn.cget("relief")) != tk.SUNKEN:
                btn.config(bg=data.btn_active)

        def on_leave(e: Any) -> None:
            if str(btn.cget("relief")) != tk.SUNKEN:
                btn.config(bg=data.btn_bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def make_button(self, text, command) -> None:
        btn = tk.Button(
            self.player.btn_frame,
            text=text,
            command=command,
            font=("Roboto", 11, "bold"),
            bg=data.btn_bg,
            fg=data.fg_color,
            activebackground=data.accent_color,
            activeforeground=data.bg_color,
            relief=tk.FLAT,
            highlightbackground=data.btn_border,
            highlightthickness=1,
            cursor="hand2",
            bd=0,
            padx=12,
            pady=4,
        )

        btn.pack(side=tk.LEFT, padx=5)
        self.bind_hover(btn)
        return btn

    def create_topbar(self) -> None:
        self.player.top_frame = tk.Frame(self.player.root, bg=data.bg_color)
        self.player.top_frame.pack(fill=tk.X, pady=10)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.png")

        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.player.root.iconphoto(True, img)
            except Exception as e:
                utils.print(f"Could not load icon: {e}")

        self.player.menu_btn = tk.Label(
            self.player.top_frame,
            text=info.full_name,
            font=data.name_font,
            fg=data.accent_color,
            bg=data.bg_color,
            cursor="hand2",
        )

        self.player.menu_btn.pack(side=tk.LEFT, padx=(20, 5))
        self.player.menu_btn.bind("<Button-1>", self.player.toggle_menu)
        self.player.info_frame = tk.Frame(self.player.top_frame, bg=data.bg_color)
        self.player.info_frame.pack(side=tk.LEFT, padx=(10, 0))

        self.player.name_label = tk.Label(
            self.player.info_frame,
            text=self.player.current_channel_name,
            font=data.name_font,
            bg=data.bg_color,
            fg=data.fg_color,
            cursor="hand2",
        )

        self.player.name_label.pack(anchor=tk.W)
        self.player.name_label.bind("<Button-1>", self.player.cancel_tuning)
        self.player.btn_frame = tk.Frame(self.player.top_frame, bg=data.bg_color)
        self.player.btn_frame.pack(side=tk.RIGHT, padx=(0, 20))

        self.player.country_frame = tk.Frame(
            self.player.btn_frame,
            bg=data.input_bg,
            highlightbackground=data.btn_border,
            highlightcolor=data.accent_color,
            highlightthickness=1,
            bd=0,
        )

        self.player.country_frame.pack(side=tk.LEFT, padx=(0, 10))
        country_val = self.player.country_var.get()

        self.player.country_entry = tk.Entry(
            self.player.country_frame,
            textvariable=self.player.country_var,
            font=data.font_ui,
            bg=data.input_bg,
            fg="gray"
            if country_val == self.player.country_placeholder
            else data.fg_color,
            insertbackground=data.accent_color,
            width=18,
            relief=tk.FLAT,
            highlightthickness=0,
            bd=0,
        )

        self.player.country_entry.pack(side=tk.LEFT, padx=8, pady=4)
        self.player.country_entry.bind("<FocusIn>", self.player.on_country_focus_in)
        self.player.country_entry.bind("<FocusOut>", self.player.on_country_focus_out)
        self.player.country_entry.bind("<Return>", self.player.on_country_return)

        style = ttk.Style()

        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            "TCombobox",
            fieldbackground=data.input_bg,
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
            fieldbackground=[("readonly", data.input_bg)],
            selectbackground=[("readonly", data.input_bg)],
            selectforeground=[("readonly", data.accent_color)],
            background=[("readonly", data.btn_bg), ("active", data.btn_active)],
            bordercolor=[("readonly", data.btn_border)],
        )

        self.player.root.option_add("*TCombobox*Listbox.background", data.btn_bg)
        self.player.root.option_add("*TCombobox*Listbox.foreground", data.fg_color)

        self.player.root.option_add(
            "*TCombobox*Listbox.selectBackground", data.btn_active
        )

        self.player.root.option_add(
            "*TCombobox*Listbox.selectForeground", data.accent_color
        )

        self.player.lang_cb = ttk.Combobox(
            self.player.btn_frame,
            textvariable=self.player.selected_lang,
            values=[data.any_language] + self.player.display_languages,
            state="readonly",
            font=data.font_ui,
            width=16,
        )

        self.player.lang_cb.pack(side=tk.LEFT, padx=(0, 10))

        self.player.lang_cb.bind(
            "<<ComboboxSelected>>", self.player.on_language_selected
        )

        self.player.copy_btn = self.make_button("Copy", self.player.copy_link)
        self.player.paste_btn = self.make_button("Paste", self.player.paste_link)
        self.player.world_btn = self.make_button("World", self.player.toggle_globe)
        self.player.country_btn = self.make_button("Country", self.player.toggle_country)
        self.player.history_btn = self.make_button("History", self.player.toggle_history)
        self.player.play_btn = self.make_button("Roll", self.player.play_random)
