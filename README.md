# Roll TV

## System Requirements

This application depends on the `libmpv` C library. You must install it on your system before running the app.

* **Ubuntu/Debian:** `sudo apt install libmpv-dev`
* **Arch Linux:** `sudo pacman -S mpv`
* **Fedora:** `sudo dnf install mpv-libs`
* **macOS:** `brew install mpv`
* **Windows:** Download the latest `mpv-dev` build from the official mpv website and ensure the `mpv-2.dll` is in your system PATH or in the same folder as the script.

Tkinter must be installed as well if not already:

`sudo apt install python3-tk`

Then run this `pipx` command:

`pipx install git+https://github.com/madprops/rolltv --force`

This assumes you have `mpv` installed.

![](screenshot.jpg)