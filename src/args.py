import argparse

from info import info
from store import store


class Args:
    def __init__(self) -> None:
        parser = argparse.ArgumentParser(
            prog=info.name,
            description=f"{info.full_name} v{info.version}",
        )

        saved_data = store.load_data()
        default_show_status = saved_data.get("show_status", True)
        default_sound_fx = saved_data.get("sound_fx", True)

        parser.add_argument(
            "--no-status", action="store_false", dest="show_status", default=default_show_status
        )

        parser.add_argument(
            "--no-sound-fx", action="store_false", dest="sound_fx", default=default_sound_fx
        )

        parsed_args = parser.parse_args()
        self.show_status = parsed_args.show_status
        self.sound_fx = parsed_args.sound_fx


args = Args()
