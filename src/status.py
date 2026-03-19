import tkinter as tk
from typing import Any

from data import data
from args import args


class Status:
    def __init__(self, player: Any) -> None:
        self.player = player
        self.frame = tk.Frame(player.root, bg=data.btn_bg)
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.label = tk.Label(
            self.frame,
            text="",
            font=data.status_font,
            bg=data.btn_bg,
            fg=data.info_fg,
        )

        self.label.pack(anchor=tk.W, padx=20, pady=4)
        self.update_loop()

    def set_text(self, text: str) -> None:
        if not args.show_status:
            return

        self.label.config(text=text)

    def update_loop(self) -> None:
        self.update()
        self.player.root.after(1000, self.update_loop)

    def update(self) -> None:
        if not args.show_status:
            return

        if self.player.tuning:
            self.player.show_name_message("Tuning...")
            return

        if not hasattr(self.player, "players") or not hasattr(
            self.player, "active_idx"
        ):
            return

        player_mpv = self.player.players[self.player.active_idx]

        if player_mpv and getattr(player_mpv, "playback_time", None) is not None:
            w = getattr(player_mpv, "width", None)
            h = getattr(player_mpv, "height", None)
            res = f"{w}x{h}" if w and h else "Unknown Res"

            fps = getattr(
                player_mpv,
                "container_fps",
                getattr(player_mpv, "estimated_vf_fps", None),
            )

            fps_str = f"{fps:.0f} fps" if fps else "Unknown fps"
            v_br = getattr(player_mpv, "video_bitrate", None) or 0
            a_br = getattr(player_mpv, "audio_bitrate", None) or 0
            tb = v_br + a_br

            def fmt_br(b: float) -> str:
                if b >= 1000000:
                    return f"{b / 1000000:.1f}M"
                elif b > 0:
                    return f"{b / 1000:.0f}K"

                return "0"

            br_str = (
                f"{fmt_br(tb)}bps (V:{fmt_br(v_br)} A:{fmt_br(a_br)})"
                if tb > 0
                else "Unknown bitrate"
            )

            vc = (
                getattr(
                    player_mpv, "video_format", getattr(player_mpv, "video_codec", None)
                )

                or "No Video"
            )

            ac = (
                getattr(
                    player_mpv,
                    "audio_codec_name",
                    getattr(player_mpv, "audio_codec", None),
                )

                or "No Audio"
            )

            vc = vc.upper() if isinstance(vc, str) else vc
            ac = ac.upper() if isinstance(ac, str) else ac
            audio_params = getattr(player_mpv, "audio_params", None)

            if isinstance(audio_params, dict) and "samplerate" in audio_params:
                ac += f" ({audio_params['samplerate'] / 1000:.1f}kHz)"

            cache = getattr(player_mpv, "demuxer_cache_duration", None)

            drops = (getattr(player_mpv, "drop_frame_count", None) or 0) + (
                getattr(player_mpv, "vo_drop_frame_count", None) or 0
            )

            hwdec = getattr(player_mpv, "hwdec_current", None)
            status_text = f"{self.player.current_country} | {res} | {fps_str} | {br_str} | {vc} / {ac} | {'HW: ' + hwdec.upper() if hwdec and hwdec != 'no' else 'SW'} | Buf: {cache:.1f}s | Drops: {drops}"
            self.set_text(status_text)
        else:
            self.set_text("")
