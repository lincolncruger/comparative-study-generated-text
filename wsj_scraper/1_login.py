"""
Step A: bootstrap a persistent, authenticated WSJ browser session.

Opens a real (visible) Chromium window using a persistent profile
directory. You log into WSJ manually, once, in that window. The profile
directory then holds your session cookies on disk, so later scripts can
reuse it without logging in again.

This does not touch your real Chrome profile or any saved passwords —
it's a brand new, isolated browser profile just for this.

Run:
    venv/bin/python 1_login.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).parent / "browser_profile"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
    )
    page = context.new_page()
    page.goto("https://www.wsj.com/")

    print("\nA Chromium window has opened.")
    print("1. Click 'Sign In' and log into your WSJ account (including any 2FA).")
    print("2. Confirm you can see your account icon / are logged in.")
    print("3. Come back to this terminal and press Enter.\n")
    input("Press Enter once you're logged in... ")

    context.close()

print(f"Session saved to {PROFILE_DIR}")
print("You can now run 2_test_article.py <wsj article url> to verify it works.")
