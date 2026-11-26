import os

# Headless Qt for the automated suite; screenshots use a real display separately.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
