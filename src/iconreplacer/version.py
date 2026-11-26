"""Single source of truth for the IconReplacer version.

Format: MAJOR.MINOR.PATCH.BUILD. BUILD increases by one for every change merged
into ``main`` and never resets. Edit only through ``tools/bump_version.py``.
"""

VERSION: tuple[int, int, int, int] = (0, 6, 0, 8)

__version__ = "0.6.0.8"

MAJOR, MINOR, PATCH, BUILD = VERSION
SHORT_VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
FULL_VERSION = __version__
PRODUCT_NAME = "IconReplacer"
