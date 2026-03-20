import os
import json
from typing import Any, cast

from data import data
from utils import utils


class Store:
    def load_data(self) -> dict[str, Any]:
        config_dir = os.path.dirname(data.data_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        if os.path.exists(data.data_file):
            try:
                with open(data.data_file, "r", encoding="utf-8") as f:
                    return cast(dict[str, Any], json.load(f))
            except Exception as e:
                utils.print(f"Failed to load data: {e}")

        return {}

    def save_data(self, payload: dict[str, Any]) -> None:
        config_dir = os.path.dirname(data.data_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        try:
            with open(data.data_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
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

    def save_history(self, history: list[dict[str, Any]]) -> None:
        config_dir = os.path.dirname(data.history_file)

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        try:
            with open(data.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            utils.print(f"Failed to save history: {e}")


store = Store()
