<div align="center">
  <img src="https://raw.githubusercontent.com/nbmsystemas/Bass-Music/main/image/logo.png" alt="Bass Music Logo" width="200"/>
  <h1>Bass Music</h1>
  <h1>Bass Music</h1>
  <p><strong>A Professional Terminal Music Player (TUI)</strong></p>
  
  <p>
    <a href="https://github.com/nbmsystemas/Bass-Music/commits/main"><img src="https://img.shields.io/github/last-commit/nbmsystemas/Bass-Music?style=flat-square" alt="Last Commit"></a>
    <a href="https://github.com/nbmsystemas/Bass-Music/issues"><img src="https://img.shields.io/github/issues/nbmsystemas/Bass-Music?style=flat-square" alt="Issues"></a>
    <a href="https://github.com/nbmsystemas/Bass-Music/network/members"><img src="https://img.shields.io/github/forks/nbmsystemas/Bass-Music?style=flat-square" alt="Forks"></a>
    <a href="https://github.com/nbmsystemas/Bass-Music/stargazers"><img src="https://img.shields.io/github/stars/nbmsystemas/Bass-Music?style=flat-square" alt="Stars"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License"></a>
  </p>
</div>

---

## 🎵 Overview

**Bass Music** is a 100% terminal-based (no GUI required) professional music player built with Python and `curses`. Powered by the robust `mpv` engine and `yt-dlp`, it offers a rich, interactive experience directly from your command line. 

Whether you want to play local high-fidelity FLAC files, stream a live online radio, or directly load music from YouTube and SoundCloud, Bass Music handles it seamlessly.

### ✨ Key Features

- **TUI & Mouse Support:** Fully interactive curses-based interface with both keyboard and mouse controls.
- **Universal Playback:** Plays local files (`.mp3`, `.flac`, `.wav`, etc.) and URLs (YouTube, SoundCloud, direct streams).
- **10-Band Equalizer:** Live EQ with 6 built-in presets (Flat, Bass, Rock, Pop, Vocal, Electro).
- **Live Spectrum Analyzer:** Visualizes the actual audio playing on your system in real-time (using PulseAudio/PipeWire monitor).
- **Smart Playlist:** Search/filter your playlist on the fly, auto-saves between sessions.
- **Zero-Friction Startup:** Includes a beautiful ASCII startup animation and an easy launch script.

---

## 🚀 Installation & Updates

**One-Step Install / Update:**
Copy and paste this single command into your terminal. It will install all dependencies, download Bass, and create a global command so you can launch it from anywhere.

```bash
curl -sL https://raw.githubusercontent.com/nbmsystemas/Bass-Music/main/install.sh | bash
```

*Note: The script automatically detects `apt` (Ubuntu/Debian) or `pacman` (Arch) to install `mpv`.*

### Maintenance Commands

Bass includes built-in commands to manage itself directly from the terminal:

- **Update to latest version:** `bass --update` (Automatically fetches new features and updates yt-dlp)
- **Uninstall completely:** `bass --uninstall`

---

## 🎮 Usage

Launch Bass Music from anywhere by simply typing:

```bash
# 1. Start the player (loads your saved playlist and local library)
bass

# 2. Play a specific YouTube video or stream URL directly
bass "https://www.youtube.com/watch?v=p0OH206z9Wg"

# 3. Play a local folder or file directly
bass ~/Music/MyAlbum
```

### Controls

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `n` / `p` | Next / Previous Track |
| `h` / `l` | Seek Backward / Forward 5 seconds |
| `k` / `j` | Volume Up / Down |
| `m` | Mute Toggle |
| `s` | Shuffle Toggle |
| `r` | Repeat Mode (Off → One → All) |
| `a` | Add Local File or Folder |
| `u` | Add URL (YouTube, SoundCloud, Radio, etc.) |
| `d` | Scan and Add Entire Directory |
| `x` | Remove Selected Track from Playlist |
| `/` | Search / Filter Playlist |
| `Tab` | Switch Focus (Playlist ↔ Equalizer) |
| `e` | Show / Hide Equalizer Panel |
| `↑` `↓` | Navigate List or Adjust EQ Band (depending on focus) |
| `←` `→` | Change EQ Band (when EQ is focused) |
| `1`-`6` | Apply EQ Preset (Flat, Bass, Rock, Pop, Vocal, Electro) |
| `?` | Show Help Overlay |
| `q` | Quit Application |

**Mouse Controls:**
- **Left Click** on a track to play it.
- **Left Click** on the progress bar to seek.
- **Scroll Wheel** to navigate the playlist.

---

## 🧠 Architecture & Tech Stack

Bass Music is built with a strong focus on separation of concerns:

- `bass.py`: Entry point, terminal initialization, and ASCII splash screen.
- `player.py`: Core audio engine wrapping `mpv` via IPC (Inter-Process Communication). Thread-safe state management and playlist persistence.
- `spectrum.py`: Real-time audio capture and Fast Fourier Transform (FFT) logic for the visualizer.
- `ui.py`: The `curses` event loop, rendering engine, and input handling.
- `config.py`: Centralized configuration for keybindings, colors, and EQ bands.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/nbmsystemas/Bass-Music/issues).

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

<div align="center">
  <p>Made with ❤️ for the terminal enthusiasts.</p>
</div>
