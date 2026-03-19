import argparse

from info import info


class Args:
    def __init__(self) -> None:
        parser = argparse.ArgumentParser(
            prog=info.name,
            description=f"{info.full_name} v{info.version}",
        )

        parser.add_argument(
            "--no-status", action="store_false", dest="show_status", default=True
        )

        parser.add_argument(
            "--no-sound-fx", action="store_false", dest="sound_fx", default=True
        )

        parsed_args = parser.parse_args()
        self.show_status = parsed_args.show_status
        self.sound_fx = parsed_args.sound_fx


args = Args()
