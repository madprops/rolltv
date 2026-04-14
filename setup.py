import shutil
import platform
import sys
from pathlib import Path
from setuptools import setup
from rolltv.info import info

requirements = []


def _copy_icon_file():
    source = Path("rolltv/icon.png").expanduser().resolve()
    destination = Path(f"~/.local/share/icons/{info.name}.png").expanduser().resolve()

    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source, destination)


def _create_desktop_file():
    content = f"""[Desktop Entry]
Version=1.0
Name={info.full_name}
Exec={Path(f"~/.local/bin/{info.name}").expanduser().resolve()}
Icon={Path(f"~/.local/share/icons/{info.name}.png").expanduser().resolve()}
Terminal=false
Type=Application
Categories=Utility;
"""

    file_path = (
        Path(f"~/.local/share/applications/{info.name}.desktop").expanduser().resolve()
    )

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        f.write(content)


def _post_install():
    system = platform.system()

    if system == "Linux":
        try:
            _copy_icon_file()
            _create_desktop_file()
        except Exception as e:
            print(f"Error during post install: {e}", file=sys.stderr)


with open("requirements.txt") as f:
    for line in f:
        clean_line = line.strip()

        if clean_line and not clean_line.startswith("#"):
            requirements.append(clean_line)

setup(
    name=info.name,
    version=info.version,
    # We remove package_dir and tell setuptools to find the 'rolltv' package
    packages=["rolltv"],
    package_data={"rolltv": ["*.toml", "*.txt", "*.png"]},
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            # Point to rolltv.main
            f"{info.name} = rolltv.main:main",
        ],
    },
)

_post_install()
