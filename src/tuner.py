import sys
import random
import threading
import urllib.request
import concurrent.futures
from typing import Any

from data import data
from store import store
from sound import sound
from args import args


class Tuner:
    def __init__(self, player: Any) -> None:
        self.player = player

    def play_random(self) -> None:
        if len(self.player.channels) == 0:
            return

        if args.sound_fx:
            sound.play_tuning_sound()

        self.player.animate_roll_button()

        if self.player.tuning:
            self.cancel_tuning()

        self.player.stall_retries = 0
        self.player.tuning = True
        self.player.is_roll = True
        self.player.search_id += 1
        self.player.show_message("Tuning...", auto_restore=False)

        # Grab Tkinter variables safely in the main UI thread
        sel_lang = self.player.selected_lang.get()
        target_country = self.player.country_var.get().strip().lower()

        thread = threading.Thread(
            target=self.find_live_stream,
            args=(self.player.search_id, sel_lang, target_country),
            daemon=True,
        )

        thread.start()

    def play_specific(self, channel: dict[str, Any], manual: bool = False) -> None:
        if manual and args.sound_fx:
            sound.play_tuning_sound()

        if self.player.tuning:
            self.cancel_tuning()

        if channel["url"] == self.player.current_url:
            return

        for db_ch in self.player.channels:
            if db_ch["url"] == channel["url"]:
                for key, value in db_ch.items():
                    if key not in channel or not channel[key]:
                        channel[key] = value
                break

        self.player.stall_retries = 0
        self.player.tuning = True
        self.player.is_roll = False
        self.player.search_id += 1
        self.player.show_message("Tuning...", auto_restore=False)
        self.prepare_switch(channel, self.player.search_id)

    def cancel_tuning(self, event: Any = None) -> None:
        if not self.player.tuning:
            return

        self.player.tuning = False

        if self.player.tuning_timeout is not None:
            self.player.root.after_cancel(self.player.tuning_timeout)
            self.player.tuning_timeout = None

        next_idx = 1 if self.player.active_idx == 0 else 0
        self.player.player_search_ids[next_idx] = -1
        self.player.players[next_idx].stop()
        self.player.restore_channel_name()

    def find_live_stream(
        self, my_search_id: int, sel_lang: str, target_country: str
    ) -> None:
        working_channel = None
        valid_channels = self.player.channels

        if sel_lang != data.any_language:
            target_code = self.player.lang_map_rev.get(sel_lang, sel_lang)

            valid_channels = [
                ch
                for ch in valid_channels
                if target_code in (ch.get("languages") or [])
            ]

        if (
            target_country != ""
            and target_country != self.player.country_placeholder.lower()
        ):
            valid_channels = [
                ch
                for ch in valid_channels
                if target_country == (ch.get("country_code") or "").lower()
                or (
                    len(target_country) > 2
                    and target_country in (ch.get("country_name") or "").lower()
                )
            ]

        recent_urls = {ch["url"] for ch in self.player.history[-data.recent_urls :]}
        fresh_channels = [ch for ch in valid_channels if ch["url"] not in recent_urls]

        if len(fresh_channels) > 0:
            valid_channels = fresh_channels

        if len(valid_channels) == 0:
            self.player.root.after(0, self.reset_button)

            self.player.root.after(
                0, lambda: self.player.show_message("No channels for this filter")
            )

            return

        candidates = random.sample(valid_channels, min(30, len(valid_channels)))
        found_event = threading.Event()

        def check_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
            if (
                found_event.is_set()
                or not self.player.tuning
                or my_search_id != self.player.search_id
            ):
                return None

            if (
                self.player.is_roll
                and self.player.pending_channel
                and candidate["url"] == self.player.pending_channel["url"]
                and len(valid_channels) > 1
            ):
                return None

            try:
                req = urllib.request.Request(
                    candidate["url"],
                    method="GET",
                    headers={"User-Agent": "mpv/0.34.0"},
                )

                with urllib.request.urlopen(req, timeout=data.url_timeout) as response:
                    if (
                        found_event.is_set()
                        or not self.player.tuning
                        or my_search_id != self.player.search_id
                    ):
                        return None

                    if response.status in [200, 206, 301, 302]:
                        chunk = response.read(2048)

                        if len(chunk) > 0:
                            text_chunk = chunk.decode("utf-8", errors="ignore")

                            if "#EXTM3U" in text_chunk:
                                if (
                                    "#EXTINF" not in text_chunk
                                    and "#EXT-X" not in text_chunk
                                ):
                                    return None

                            return candidate
            except Exception:
                pass

            return None

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        futures = [executor.submit(check_candidate, c) for c in candidates]

        for future in concurrent.futures.as_completed(futures):
            if not self.player.tuning or my_search_id != self.player.search_id:
                break

            result = future.result()
            if result is not None:
                working_channel = result
                found_event.set()
                break

        if sys.version_info >= (3, 9):
            executor.shutdown(wait=False, cancel_futures=True)
        else:
            executor.shutdown(wait=False)

        if not self.player.tuning or my_search_id != self.player.search_id:
            return

        if working_channel is not None:
            self.player.root.after(
                0, self.prepare_switch, working_channel, my_search_id
            )
        else:
            if self.player.is_roll and self.player.stall_retries < data.max_retries:

                def retry_find() -> None:
                    if not self.player.tuning or my_search_id != self.player.search_id:
                        return

                    self.player.stall_retries += 1
                    self.player.search_id += 1
                    new_search_id = self.player.search_id

                    threading.Thread(
                        target=self.find_live_stream,
                        args=(new_search_id, sel_lang, target_country),
                        daemon=True,
                    ).start()

                self.player.root.after(0, retry_find)
            else:
                self.player.root.after(0, self.reset_button)

                self.player.root.after(
                    0,
                    lambda: self.player.show_message(
                        "Could not find a working stream."
                    ),
                )

    def prepare_switch(self, channel: dict[str, Any], search_id: int) -> None:
        if not self.player.tuning or search_id != self.player.search_id:
            return

        self.player.pending_channel = channel
        next_idx = 1 if self.player.active_idx == 0 else 0

        if self.player.tuning_timeout is not None:
            self.player.root.after_cancel(self.player.tuning_timeout)

        self.player.tuning_timeout = self.player.root.after(
            data.tuning_timeout, lambda: self.handle_timeout(search_id)
        )

        self.player.player_search_ids[next_idx] = search_id
        self.player.players[next_idx].mute = True
        self.player.players[next_idx].play(channel["url"])

    def handle_timeout(self, search_id: int) -> None:
        if not self.player.tuning or (search_id != self.player.search_id):
            return

        if self.player.is_roll or self.player.stall_retries < data.max_retries:
            self.player.stall_retries = (
                0 if self.player.is_roll else self.player.stall_retries + 1
            )

            next_idx = 1 if self.player.active_idx == 0 else 0
            self.player.player_search_ids[next_idx] = -1
            self.player.players[next_idx].stop()
            self.player.search_id += 1
            new_search_id = self.player.search_id

            if self.player.is_roll:
                # This runs via root.after(), so it is in the main thread and safe to call .get()
                sel_lang = self.player.selected_lang.get()
                target_country = self.player.country_var.get().strip().lower()

                threading.Thread(
                    target=self.find_live_stream,
                    args=(new_search_id, sel_lang, target_country),
                    daemon=True,
                ).start()
            elif self.player.pending_channel:
                self.prepare_switch(self.player.pending_channel, new_search_id)
        else:
            self.player.tuning = False
            next_idx = 1 if self.player.active_idx == 0 else 0
            self.player.player_search_ids[next_idx] = -1
            self.player.players[next_idx].stop()

            self.player.show_message(
                f"Stream stalled {data.max_retries} times. Roll again."
            )

    def commit_switch_if_valid(self, ready_idx: int, search_id: int) -> None:
        if (
            self.player.tuning
            and search_id == self.player.search_id
            and self.player.active_idx != ready_idx
        ):
            self.commit_switch(ready_idx)

    def commit_switch(self, ready_idx: int) -> None:
        self.player.tuning = False
        self.player.stall_retries = 0

        if self.player.tuning_timeout is not None:
            self.player.root.after_cancel(self.player.tuning_timeout)
            self.player.tuning_timeout = None

        self.player.active_idx = ready_idx
        self.player.frames[ready_idx].tkraise()
        self.player.players[ready_idx].mute = False
        old_idx = 1 if ready_idx == 0 else 0
        self.player.player_search_ids[old_idx] = -1
        self.player.players[old_idx].stop()

        if self.player.pending_channel is None:
            return

        self.player.current_url = self.player.pending_channel["url"]
        c_name = self.player.pending_channel.get("country_name", "")
        self.player.current_country = c_name.title() if c_name else "Unknown"

        self.player.current_channel_name = self.player.pending_channel.get(
            "name", "Unknown"
        )

        c_code = self.player.pending_channel.get("country_code", "")

        self.player.current_country_code = (
            c_code.lower() if isinstance(c_code, str) else ""
        )

        self.player.schedule_update_country_count()
        globe_code = self.player.current_country_code

        if globe_code == "uk":
            globe_code = "gb"

        self.player.update_globe_country(globe_code)

        if isinstance(c_code, str) and len(c_code) == 2:
            c_code = "gb" if c_code.lower() == "uk" else c_code.lower()

            threading.Thread(
                target=self.player.flags.load_or_fetch,
                args=(c_code, self.player.current_channel_name),
                daemon=True,
            ).start()
        else:
            self.player.flags.clear()

        self.player.restore_channel_name()

        self.player.history = [
            ch
            for ch in self.player.history
            if ch["url"] != self.player.pending_channel["url"]
        ]

        self.player.history.append(self.player.pending_channel)

        if len(self.player.history) > data.max_history_items:
            self.player.history.pop(0)

        store.save_history(self.player.history)

        if self.player.active_sidebar:
            self.player.update_sidebar()

    def reset_button(self) -> None:
        self.player.tuning = False
