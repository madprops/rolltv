import tkinter as tk
from tkinter import ttk
from typing import Any

from data import data
from info import info


class Sidebar:
    def __init__(self, player: Any) -> None:
        self.player = player
        self.create_menu_sidebar()
        self.create_main_sidebar()

    def create_menu_sidebar(self) -> None:
        self.player.menu_sidebar_frame = tk.Frame(
            self.player.main_content_frame,
            bg=data.btn_bg,
            width=200,
            bd=0,
            highlightthickness=0,
        )

        self.player.menu_sidebar_frame.pack_propagate(False)
        self.main_menu_item("Toggle FX", self.player.toggle_sound_fx)
        self.main_menu_item("Toggle Status", self.player.toggle_status)
        self.main_menu_item("Exit", self.player.exit_app)

        self.player.sidebar_version_label = tk.Label(
            self.player.menu_sidebar_frame,
            text=f"v{info.version}",
            font=data.font_ui,
            bg=data.btn_bg,
            fg=data.info_fg,
            anchor="w",
        )

        self.player.sidebar_version_label.pack(
            side=tk.BOTTOM, fill=tk.X, padx=10, pady=10
        )

    def main_menu_item(self, text: str, command: Any) -> None:
        btn = tk.Button(
            self.player.menu_sidebar_frame,
            text=text,
            command=command,
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

        btn.pack(fill=tk.X, padx=10, pady=5)

    def create_main_sidebar(self) -> None:
        self.player.sidebar_frame = tk.Frame(
            self.player.main_content_frame,
            bg=data.btn_bg,
            width=300,
            bd=0,
            highlightthickness=0,
        )

        self.player.sidebar_frame.pack_propagate(False)
        self.player.sidebar_filter_placeholder = "Filter"

        self.player.history_filter_var = tk.StringVar(
            value=self.player.sidebar_filter_placeholder
        )

        self.player.history_filter_var.trace_add("write", self.player.update_sidebar)

        self.player.country_filter_var = tk.StringVar(
            value=self.player.sidebar_filter_placeholder
        )

        self.player.country_filter_var.trace_add("write", self.player.update_sidebar)

        self.player.sidebar_filter_frame = tk.Frame(
            self.player.sidebar_frame,
            bg=data.btn_bg,
            highlightbackground=data.btn_border,
            highlightcolor=data.btn_border,
            highlightthickness=0,
            bd=0,
        )

        self.player.sidebar_filter_entry = tk.Entry(
            self.player.sidebar_filter_frame,
            textvariable=self.player.history_filter_var,
            font=data.font_ui,
            bg=data.btn_bg,
            fg="gray",
            insertbackground=data.accent_color,
            relief=tk.FLAT,
            highlightthickness=0,
            bd=0,
        )

        self.player.sidebar_filter_entry.pack(fill=tk.X, padx=8, pady=4)

        self.player.sidebar_filter_entry.bind(
            "<FocusIn>", self.player.on_sidebar_filter_focus_in
        )

        self.player.sidebar_filter_entry.bind(
            "<FocusOut>", self.player.on_sidebar_filter_focus_out
        )

        self.player.sidebar_listbox_frame = tk.Frame(
            self.player.sidebar_frame, bg=data.btn_bg
        )

        self.player.sidebar_listbox_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()

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

        self.player.sidebar_listbox = ttk.Treeview(
            self.player.sidebar_listbox_frame,
            style="Sidebar.Treeview",
            show="tree",
            selectmode="browse",
        )

        self.player.scrollbar = tk.Scrollbar(
            self.player.sidebar_listbox_frame,
            command=self.player.sidebar_listbox.yview,
            bg=data.scrollbar_color,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
        )

        self.player.sidebar_listbox.config(yscrollcommand=self.player.scrollbar.set)
        self.player.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.player.sidebar_listbox.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10
        )

        self.player.sidebar_listbox.bind("<Button-1>", self.player.on_sidebar_click)
