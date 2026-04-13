import math
import wave
import struct
import tempfile
import platform


class Sound:
    def create(self) -> None:
        self.tuning_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        self.tuning_wav.close()
        self.generate_tuning_sound(self.tuning_wav.name)

        if platform.system() == "Linux":
            try:
                import mpv  # type: ignore

                self.player = mpv.MPV(vid="no", vo="null")
            except Exception:
                self.player = None

    def generate_tuning_sound(self, filename: str) -> None:
        duration = 0.2
        sample_rate = 44100
        num_samples = int(sample_rate * duration)
        volume_reduction = 0.3

        with wave.open(filename, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            for i in range(num_samples):
                t = i / sample_rate
                freq = 220 + 220 * t / duration
                value = math.sin(2 * math.pi * freq * t)
                envelope = 1.0

                if t < 0.05:
                    envelope = t / 0.05

                if t > 0.15:
                    envelope = (0.2 - t) / 0.05

                sample = int(value * envelope * 32767 * volume_reduction)
                wav_file.writeframesraw(struct.pack("<h", sample))

    def play_tuning_sound(self) -> None:
        system = platform.system()

        if system == "Windows":
            import winsound

            winsound.PlaySound(  # type: ignore
                self.tuning_wav.name,
                winsound.SND_FILENAME | winsound.SND_ASYNC,  # type: ignore
            )

        if system == "Darwin":
            import subprocess

            subprocess.Popen(["afplay", self.tuning_wav.name])

        if system == "Linux":
            if getattr(self, "player", None) is not None:
                self.player.play(self.tuning_wav.name)
                return

            import subprocess
            import shutil

            if shutil.which("paplay"):
                subprocess.Popen(
                    ["paplay", self.tuning_wav.name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["aplay", "-q", self.tuning_wav.name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


sound = Sound()
