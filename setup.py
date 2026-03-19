import shutil
import platform
import sys
from pathlib import Path
from setuptools import setup
from src.info import info

requirements = []

def _copy_icon_file():
    # Adjusted this path to what is likely correct.
    # If info.name is actually the root folder name, change it back.
    source = Path("src/icon.png").expanduser().resolve()
    destination = Path(f"~/.local/share/icons/{info.name}.png").expanduser().resolve()

    # Ensure the icons folder exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source, destination)

def _create_desktop_file():
    content = f"""[Desktop Entry]
Version=1.0
Name={info.full_name}
Exec={Path(f"~/.local/bin/{info.name}").expanduser().resolve()} --gui
Icon={Path(f"~/.local/share/icons/{info.name}.png").expanduser().resolve()}
Terminal=false
Type=Application
Categories=Utility;
"""

    file_path = Path(f"~/.local/share/applications/{info.name}.desktop").expanduser().resolve()

    # Ensure the applications folder exists
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
            # Writing to stderr forces the error to show up in the console
            print(f"Error during post install: {e}", file=sys.stderr)

with open("requirements.txt") as f:
    for line in f:
        clean_line = line.strip()

        if clean_line and not clean_line.startswith("#"):
            requirements.append(clean_line)

setup(
    name=info.name,
    version=info.version,
    package_dir={"": "src"},
    packages=[""],
    package_data={"": ["*.toml", "*.txt", "*.png"]},
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            f"{info.name} = main:main",
        ],
    },
)

_post_install()