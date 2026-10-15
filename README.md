# Roblox Audio Batch Downloader

A universal Python script to batch download audio assets from the Roblox platform. It uses your session cookie to legitimately fetch audio headers and bypass HTTP 401 Unauthorized errors caused by the Roblox API v2 update.

## Features
* Bypasses Roblox API v2 auth blocks using local browser session cookies.
* Auto-detects true audio formats (`.ogg`, `.wav`, `.mp3`, `.flac`) based on raw file headers.
* Automatically creates and organizes subfolders based on custom headers in your data list.
* Handles duplicate asset IDs locally to optimize download speed and prevent API spam.
* Cleans up corrupted or incomplete `.part` files automatically from previous runs.

## Prerequisites
* Python 3.x installed on your system.
* The `requests` library. Install it via terminal/CMD:
  ```bash
  pip install requests
  ```

## Quick Start

1. Create a file named `cookie.txt` in the same directory and paste your Roblox `.ROBLOSECURITY` cookie inside it.
2. Create a file named `Data.txt` in the same directory and input your asset list. You can organize files into subfolders using headers ending with a colon:
   ```text
   CombatSFX:
   slash: 5704938219
   hit: 5704107374

   BackgroundMusic:
   5711596460 - lobby_theme
   ```
3. Run the script:
   ```bash
   python downloader.py
   ```

## File Outputs
All assets will be downloaded and categorized inside the `ROBLOX_AUDIO/` directory.
