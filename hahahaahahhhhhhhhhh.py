import os
import re
import sys
import time
import shutil
import requests

# ================== Config ==================
# usage: python download_roblox_audio.py [data_file] [output_folder]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "Data.txt")
BASE_FOLDER = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(SCRIPT_DIR, "ROBLOX_AUDIO")
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie.txt")
FAILED_FILE = os.path.join(SCRIPT_DIR, "failed.txt")
PLACE_ID = os.environ.get("PLACE_ID", "").strip()   # game's place ID, needed for audio the game owns
DELAY = 1.0          # seconds between downloads
KNOWN_EXTS = (".mp3", ".ogg", ".wav", ".flac")

# Data.txt layout:
#   Group:            <- first header after a "____" line (or at the top) = top-level group
#   Skill:            <- any other header = sub-group
#   name: 123456789   <- audio line (anything after the ID is ignored)
# A header that should ALWAYS count as a top-level group, even without a "____" above it,
# goes here. Leave empty if you don't need it.
EXTRA_GROUPS = set()

# ================== Cookie ==================
cookie = os.environ.get("ROBLOSECURITY", "").strip().strip('"')
if not cookie and os.path.exists(COOKIE_FILE):
    with open(COOKIE_FILE, encoding="utf-8") as f:
        cookie = f.read().strip().strip('"')
if not cookie:
    sys.exit(f"No cookie. Put it in: {COOKIE_FILE}")

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})
session.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")

os.makedirs(BASE_FOLDER, exist_ok=True)


# ================== Helpers ==================
def safe(s):
    return re.sub(r"[^\w\-]+", "_", s).strip("_")


def detect_ext(data):
    if data.startswith(b"OggS"):
        return ".ogg"
    if data.startswith(b"RIFF"):
        return ".wav"
    if data.startswith(b"fLaC"):
        return ".flac"
    return ".mp3"


def is_valid_file(path):
    """Valid = not empty, not an HTML/JSON error page."""
    try:
        if os.path.getsize(path) == 0:
            return False
        with open(path, "rb") as f:
            head = f.read(16).lstrip()
        return not head.startswith((b"<", b"{"))
    except OSError:
        return False


def find_existing(base, asset_id):
    """Look for a file we already have (new name or old sfx_<id> name). Valid path or None."""
    candidates = [base + e for e in KNOWN_EXTS] + [f"sfx_{asset_id}{e}" for e in KNOWN_EXTS]
    for name in candidates:
        path = os.path.join(BASE_FOLDER, name)
        if os.path.exists(path):
            if is_valid_file(path):
                return path
            print(f"Broken file, redownloading: {name}")
            try:
                os.remove(path)
            except OSError:
                pass
    return None


def check_login():
    r = session.get("https://users.roblox.com/v1/users/authenticated", timeout=20)
    if r.status_code != 200:
        sys.exit(f"Cookie's dead (HTTP {r.status_code}). Grab a fresh one.")
    print(f"Logged in as {r.json().get('name')}")


def download(asset_id, retries=4):
    url = f"https://assetdelivery.roblox.com/v2/assetId/{asset_id}"
    headers = {"Roblox-Place-Id": PLACE_ID} if PLACE_ID else {}
    last_err = "unknown"

    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=30)

            if r.status_code == 429:
                last_err = "rate limited (429)"
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}: {r.text[:120]}"

            info = r.json()
            locations = info.get("locations") or []
            if not locations:
                return None, f"no download link: {str(info.get('errors'))[:150]}"

            # CDN: clean request, NO cookie
            f = requests.get(locations[0]["location"],
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            if f.status_code == 200 and f.content:
                return f.content, None
            last_err = f"CDN HTTP {f.status_code}"

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = f"network error: {type(e).__name__}"

        time.sleep(2 * (attempt + 1))

    return None, last_err


def save_atomic(path, data):
    """Write to .part, then rename. A crash won't leave a half-written file."""
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


# ================== Parse the list ==================
def parse_entries():
    if not os.path.exists(DATA_FILE):
        sys.exit(f"Can't find {DATA_FILE}")

    entries = []
    group, skill = "General", ""
    after_sep = True      # top of file or right after "____" -> next header is a group
    with open(DATA_FILE, encoding="utf-8-sig") as fh:
        for raw in fh.read().splitlines():
            line = raw.strip()
            if not line:
                skill = ""
                continue
            if line.startswith("____"):
                skill, after_sep = "", True
                continue
            if line.endswith(":"):
                name = line[:-1].strip()
                if after_sep or name in EXTRA_GROUPS:
                    group, skill = name, ""
                else:
                    skill = name
                after_sep = False
                continue
            after_sep = False
            m = re.match(r"^([\w\-]+):\s*(\d+)", line)
            if not m:
                continue
            audio_name, asset_id = m.groups()
            parts = [safe(group)] + ([safe(skill)] if skill else []) + [audio_name]
            entries.append({"base": "_".join(parts), "id": asset_id})
    return entries


# ================== Run ==================
def main():
    for leftover in os.listdir(BASE_FOLDER):          # wipe .part leftovers from last run
        if leftover.endswith(".part"):
            os.remove(os.path.join(BASE_FOLDER, leftover))

    entries = parse_entries()
    total = len(entries)

    # step 1: what do we have, what's missing
    have, missing = [], []
    for e in entries:
        path = find_existing(e["base"], e["id"])
        (have if path else missing).append(e)

    print(f"Total: {total} | Have: {len(have)} | Missing: {len(missing)}")
    if not missing:
        print("Everything's already here. Nothing to do.")
        return

    check_login()

    # step 2: download only what's missing
    ok = copied = 0
    failed = []
    done_by_id = {}   # id -> path, so a duplicate ID only gets downloaded once
    for e in have:
        p = find_existing(e["base"], e["id"])
        if p:
            done_by_id.setdefault(e["id"], p)

    try:
        for i, e in enumerate(missing, 1):
            base, asset_id = e["base"], e["id"]
            tag = f"[{i}/{len(missing)}]"

            # same ID already on disk -> copy it, skip the API
            if asset_id in done_by_id:
                src = done_by_id[asset_id]
                ext = os.path.splitext(src)[1]
                shutil.copyfile(src, os.path.join(BASE_FOLDER, base + ext))
                print(f"{tag} copied {base}{ext} (same ID {asset_id}, reused existing file)")
                copied += 1
                continue

            data, err = download(asset_id)
            if data is None:
                print(f"{tag} FAIL {base} (ID {asset_id}) -> {err}")
                failed.append(f"{base}: {asset_id} -> {err}")
            else:
                path = os.path.join(BASE_FOLDER, base + detect_ext(data))
                save_atomic(path, data)
                done_by_id[asset_id] = path
                print(f"{tag} ok {os.path.basename(path)}")
                ok += 1
            time.sleep(DELAY)

    except KeyboardInterrupt:
        print("\nStopped. Run it again to pick up the rest.")

    print(f"\nDone: {ok} new, {copied} copied from duplicate IDs, {len(failed)} failed, "
          f"{len(have)} already had.")

    if failed:
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(failed))
        print(f"Failures saved to {FAILED_FILE}")
        print("Run it again to retry just those.")
    elif os.path.exists(FAILED_FILE):
        os.remove(FAILED_FILE)


if __name__ == "__main__":
    main()
