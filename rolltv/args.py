import argparse

from rolltv.info import info
from rolltv.store import store


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
            "--no-status",
            action="store_false",
            dest="show_status",
            default=default_show_status,
            help="Disable the status bar",
        )

        parser.add_argument(
            "--no-sound-fx",
            action="store_false",
            dest="sound_fx",
            default=default_sound_fx,
            help="Disable sound effects",
        )

        parser.add_argument(
            "--captures",
            type=str,
            help="The path for the video captures",
        )

        parsed_args = parser.parse_args()
        self.show_status = parsed_args.show_status
        self.sound_fx = parsed_args.sound_fx
        self.captures = parsed_args.captures


args = Args()
