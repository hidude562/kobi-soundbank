"""kobi.swipe — a swipe-to-judge app for the bank's sounds; see __main__.py."""
import os

# the app compares against the bank as it was built, so gm_map must not put earlier picks first here
os.environ.setdefault('KOBI_SWIPE_PICKS', '0')
