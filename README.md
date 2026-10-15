# Roblox Audio Batch Downloader

A Python script that batch downloads audio assets from Roblox using a list of asset IDs. It authenticates with your own session cookie, since Roblox's asset delivery API (v2) rejects unauthenticated requests.

## Features
* Authenticates with your `.ROBLOSECURITY` cookie, which the v2 asset delivery API requires.
* Detects the real audio format (`.ogg`, `.wav`, `.flac`, `.mp3`) from the file header.
* Names files after the groups in your data list (`Group_Skill_name.ext`), all inside one output folder.
* Skips files you already have and only downloads what's missing, so you can re-run it any time.
* Downloads a duplicate asset ID once, then copies it under every name that uses it.
* Retries on rate limits (429) and network errors; failures are written to `failed.txt`.
* Removes leftover `.part` files from interrupted runs and replaces broken downloads (empty files, HTML/JSON error pages).

## Prerequisites
* Python 3.6+
* The `requests` library:
  ```bash
  pip install requests
  ```

## Quick Start

1. Create `cookie.txt` next to the script and paste your `.ROBLOSECURITY` cookie value into it.
   **Treat this cookie like a password.** Anyone with it can access your account. Never share it or commit it to git.
2. Create `Data.txt` next to the script. Format is one `name: assetId` per line. Anything after the ID is ignored, so you can leave notes there.

   ```text
   Combat:

   Sword:
   slash: 5704938219
   hit: 5704107374

   death: 5711596460
   ______________________________

   Music:

   lobby_theme: 5711596460
   ```

   * The first header at the top of the file, or right after a `____` line, is a **group**.
   * Any other header ending in `:` is a **sub-group** (skill).
   * A blank line ends the current sub-group.

   The example above produces:
   ```text
   Combat_Sword_slash.mp3
   Combat_Sword_hit.mp3
   Combat_death.mp3
   Music_lobby_theme.mp3
   ```
3. Run it:
   ```bash
   python download_roblox_audio.py
   ```

## Options

```bash
python download_roblox_audio.py [data_file] [output_folder]
```

| Setting | How | Default |
|---|---|---|
| Data file | 1st argument | `Data.txt` |
| Output folder | 2nd argument | `ROBLOX_AUDIO/` |
| Cookie | `ROBLOSECURITY` env var, or `cookie.txt` | none (required) |
| Place ID | `PLACE_ID` env var | empty |

**Place ID** is optional. It's the number in a game's URL (`roblox.com/games/<PLACE_ID>/Game-Name`). Only set it if you get many `HTTP 403` or `no download link` errors on audio that belongs to a specific game.

Some top-level headers can't be told apart from sub-groups without a `____` line above them. List such names in `EXTRA_GROUPS` at the top of the script.

## Output
Everything is saved in one flat folder (`ROBLOX_AUDIO/` by default). Files are not split into subfolders; the group and sub-group names are part of each file name.

## Notes
* Only download audio you have the right to use. Respect Roblox's Terms of Use and the rights of the audio's creators.
* Don't commit `cookie.txt`, `failed.txt`, or the downloaded audio. Add them to `.gitignore`:
  ```text
  cookie.txt
  failed.txt
  ROBLOX_AUDIO/
  ```
