"""TuxToys: power-user utilities for Linux Mint Cinnamon."""

# The application id, in reverse-DNS form from where the project lives on GitHub. The
# daemon's bus name, the desktop file and the icon are all named after it, and renaming it
# would break scripts and settings, so it stays.
APP_ID = "io.github.konabe_studio.TuxToys"
BUS_NAME = APP_ID
OBJECT_PATH = "/io/github/konabe_studio/TuxToys"
# Where the project lives, for the links in the settings window and the panel icon's menu.
PROJECT_URL = "https://github.com/konabe-studio/tuxtoys"

# The version, as pyproject.toml has it; debian/changelog says the same in Debian's way
# (0.5.0~dev for 0.5.0.dev0). tests/test_version.py keeps the three in step.
VERSION = "0.5.0"
