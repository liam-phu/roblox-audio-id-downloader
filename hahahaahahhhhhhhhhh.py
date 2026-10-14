import os
import re
import sys
import time
import shutil
import requests

# ================== Cấu hình ==================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_FOLDER = os.path.join(SCRIPT_DIR, "HOVERS_SFX")
DATA_FILE = os.path.join(SCRIPT_DIR, "Data.txt")
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie.txt")
FAILED_FILE = os.path.join(SCRIPT_DIR, "failed.txt")
PLACE_ID = os.environ.get("PLACE_ID", "").strip()
DELAY = 1.0          # giây nghỉ giữa các lần tải
KNOWN_EXTS = (".mp3", ".ogg", ".wav", ".flac")

HOSTS = {
    "Hot Gash", "Hot Slash", "Hot Flash", "Hot Kalash",
    "Invader", "Prophet", "Witness", "Artisan",
    "Vestige", "Visitor", "Subject",
}

# ================== Cookie ==================
cookie = os.environ.get("ROBLOSECURITY", "").strip().strip('"')
if not cookie and os.path.exists(COOKIE_FILE):
    with open(COOKIE_FILE, encoding="utf-8") as f:
        cookie = f.read().strip().strip('"')
if not cookie:
    sys.exit(f"❌ Không tìm thấy cookie. Hãy tạo file: {COOKIE_FILE}")

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})
session.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")

os.makedirs(BASE_FOLDER, exist_ok=True)


# ================== Tiện ích ==================
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
    """File hợp lệ: không rỗng và không phải trang lỗi HTML/JSON."""
    try:
        if os.path.getsize(path) == 0:
            return False
        with open(path, "rb") as f:
            head = f.read(16).lstrip()
        return not head.startswith((b"<", b"{"))
    except OSError:
        return False


def find_existing(base, asset_id):
    """Tìm file đã tải (tên mới hoặc tên cũ sfx_<id>). Trả về đường dẫn hợp lệ hoặc None."""
    candidates = [base + e for e in KNOWN_EXTS] + [f"sfx_{asset_id}{e}" for e in KNOWN_EXTS]
    for name in candidates:
        path = os.path.join(BASE_FOLDER, name)
        if os.path.exists(path):
            if is_valid_file(path):
                return path
            print(f"🗑️  File hỏng, sẽ tải lại: {name}")
            try:
                os.remove(path)
            except OSError:
                pass
    return None


def check_login():
    r = session.get("https://users.roblox.com/v1/users/authenticated", timeout=20)
    if r.status_code != 200:
        sys.exit(f"❌ Cookie không hợp lệ/hết hạn (HTTP {r.status_code}). Copy lại cookie mới.")
    print(f"🔑 Đăng nhập OK: {r.json().get('name')}")


def download(asset_id, retries=4):
    url = f"https://assetdelivery.roblox.com/v2/assetId/{asset_id}"
    headers = {"Roblox-Place-Id": PLACE_ID} if PLACE_ID else {}
    last_err = "không rõ"

    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=30)

            if r.status_code == 429:
                last_err = "bị rate limit (429)"
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}: {r.text[:120]}"

            info = r.json()
            locations = info.get("locations") or []
            if not locations:
                return None, f"không có link tải: {str(info.get('errors'))[:150]}"

            # CDN: request sạch, KHÔNG kèm cookie
            f = requests.get(locations[0]["location"],
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            if f.status_code == 200 and f.content:
                return f.content, None
            last_err = f"CDN HTTP {f.status_code}"

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = f"lỗi mạng: {type(e).__name__}"

        time.sleep(2 * (attempt + 1))

    return None, last_err


def save_atomic(path, data):
    """Ghi ra .part rồi đổi tên, để lỡ bị ngắt giữa chừng không tạo file dở."""
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


# ================== Đọc danh sách ==================
def parse_entries():
    if not os.path.exists(DATA_FILE):
        sys.exit(f"❌ Không tìm thấy {DATA_FILE}")

    entries = []
    host, skill = "General", ""
    with open(DATA_FILE, encoding="utf-8") as fh:
        for raw in fh.read().splitlines():
            line = raw.strip()
            if not line or line.startswith("____"):
                skill = ""
                continue
            if line.endswith(":"):
                name = line[:-1].strip()
                if name in HOSTS:
                    host, skill = name, ""
                else:
                    skill = name
                continue
            m = re.match(r"^(\w+):\s*(\d+)", line)
            if not m:
                continue
            audio_name, asset_id = m.groups()
            parts = [safe(host)] + ([safe(skill)] if skill else []) + [audio_name]
            entries.append({"base": "_".join(parts), "id": asset_id})
    return entries


# ================== Chạy ==================
def main():
    for leftover in os.listdir(BASE_FOLDER):          # dọn file .part dở từ lần chạy trước
        if leftover.endswith(".part"):
            os.remove(os.path.join(BASE_FOLDER, leftover))

    entries = parse_entries()
    total = len(entries)

    # Bước 1: quét xem file nào đã có, file nào thiếu
    have, missing = [], []
    for e in entries:
        path = find_existing(e["base"], e["id"])
        (have if path else missing).append(e)

    print(f"📋 Tổng: {total} | Đã có: {len(have)} | Cần tải: {len(missing)}")
    if not missing:
        print("🎉 Đã đủ tất cả file, không cần tải thêm.")
        return

    check_login()

    # Bước 2: chỉ tải file thiếu
    ok = copied = 0
    failed = []
    done_by_id = {}   # id -> đường dẫn file đã có/đã tải, để ID trùng chỉ tải 1 lần
    for e in have:
        p = find_existing(e["base"], e["id"])
        if p:
            done_by_id.setdefault(e["id"], p)

    try:
        for i, e in enumerate(missing, 1):
            base, asset_id = e["base"], e["id"]
            tag = f"[{i}/{len(missing)}]"

            # Cùng ID đã có file khác -> chép lại, không gọi API
            if asset_id in done_by_id:
                src = done_by_id[asset_id]
                ext = os.path.splitext(src)[1]
                shutil.copyfile(src, os.path.join(BASE_FOLDER, base + ext))
                print(f"{tag} 📄 {base}{ext} (trùng ID {asset_id}, chép từ file có sẵn)")
                copied += 1
                continue

            data, err = download(asset_id)
            if data is None:
                print(f"{tag} ❌ {base} (ID {asset_id}) -> {err}")
                failed.append(f"{base}: {asset_id} -> {err}")
            else:
                path = os.path.join(BASE_FOLDER, base + detect_ext(data))
                save_atomic(path, data)
                done_by_id[asset_id] = path
                print(f"{tag} ✅ {os.path.basename(path)}")
                ok += 1
            time.sleep(DELAY)

    except KeyboardInterrupt:
        print("\n⏹️  Đã dừng. Chạy lại script để tải tiếp phần còn thiếu.")

    print(f"\nXong: {ok} tải mới, {copied} chép từ ID trùng, {len(failed)} lỗi, "
          f"{len(have)} đã có từ trước.")

    if failed:
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(failed))
        print(f"Danh sách lỗi đã lưu vào {FAILED_FILE}")
        print("Chạy lại script để thử tải lại riêng các file lỗi này.")
    elif os.path.exists(FAILED_FILE):
        os.remove(FAILED_FILE)


if __name__ == "__main__":
    main()