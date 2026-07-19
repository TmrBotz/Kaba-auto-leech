# 🤖 URL Uploader Bot

**Direct download links → Telegram Media** — WZGram MTProto engine ke saath

---

## ✨ Features

| Feature | Detail |
|---|---|
| ⚡ **Engine** | WZGram MTProto (Rust WarpCrypto — sabse fast) |
| 📦 **Max Size** | **2 GB** (Free account, no Premium needed) |
| 🎬 **Upload Format** | Media (Video/Audio/Photo/GIF) — Document NAHI |
| 🔐 **Auth** | Sirf Bot Token — **String Session nahi lagta** |
| 📊 **Progress** | Real-time speed + ETA dikhata hai |
| 🧹 **Auto Cleanup** | Download ke baad file automatic delete |

---

## 🚀 Setup — Step by Step

### 1. Project clone/download karo
```bash
git clone https://github.com/yourrepo/url-uploader-bot
cd url-uploader-bot
```

### 2. Python dependencies install karo
```bash
pip install -r requirements.txt
```

### 3. API credentials lo

**API_ID aur API_HASH:**
1. https://my.telegram.org/apps kholo
2. Login karo apne phone number se
3. "API development tools" pe jao
4. App create karo — `api_id` aur `api_hash` copy karo

**BOT_TOKEN:**
1. Telegram pe `@BotFather` kholo
2. `/newbot` command bhejo
3. Bot ka naam aur username set karo
4. Token copy karo

### 4. Environment variables set karo
```bash
cp .env.example .env
nano .env          # apni values daalo
```

Ya directly export karo:
```bash
export API_ID=12345678
export API_HASH=abcdef1234567890abcdef1234567890
export BOT_TOKEN=123456789:AABBcc...
```

### 5. Bot run karo
```bash
python bot.py
```

---

## 📁 Project Structure

```
url_uploader_bot/
├── bot.py           ← Main bot + all handlers
├── config.py        ← Settings aur constants
├── downloader.py    ← Async download engine
├── uploader.py      ← Telegram media upload engine
├── helpers.py       ← Utility functions
├── requirements.txt ← Python packages
└── .env.example     ← Environment variables template
```

---

## 🎯 Usage

Bot start hone ke baad koi bhi direct link bhejo:

```
https://example.com/video.mp4
https://cdn.example.com/song.mp3
https://files.example.com/image.jpg
```

Bot:
1. File ka size check karega (2GB limit)
2. Download progress dikhayega (speed + ETA)
3. Upload progress dikhayega
4. File ko **Media** format mein bhejega (Document NAHI!)

---

## ⚙️ Supported Formats

| Type | Extensions |
|---|---|
| 🎬 Video | mp4, mkv, avi, mov, wmv, flv, webm, m4v, 3gp, ts |
| 🎵 Audio | mp3, flac, aac, ogg, wav, m4a, opus, wma |
| 🖼️ Photo | jpg, jpeg, png, webp, bmp, tiff |
| 🎞️ GIF | gif (Telegram animation) |
| 📄 Others | Document ke roop mein upload |

---

## ☁️ Deployment (VPS/Server)

**Screen ya tmux se background mein chalao:**
```bash
screen -S urlbot
python bot.py
# Ctrl+A, D se detach karo
```

**Systemd service (recommended):**
```ini
[Unit]
Description=URL Uploader Bot
After=network.target

[Service]
WorkingDirectory=/path/to/url_uploader_bot
ExecStart=/usr/bin/python3 bot.py
EnvironmentFile=/path/to/url_uploader_bot/.env
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## ❓ FAQ

**Q: String Session kyon nahi chahiye?**
A: Bot Token se WZGram MTProto directly kaam karta hai. String Session sirf user accounts ke liye chahiye hoti hai.

**Q: 2GB se bade files?**
A: Nahi ho sakta free account se. Telegram Premium ke saath 4GB tak possible hai.

**Q: YouTube / Drive links kaam kyun nahi karte?**
A: Ye streaming platforms direct file URL nahi dete. Unke liye `yt-dlp` jaisi alag library chahiye.

**Q: Ek saath kai files?**
A: Haan! Har message alag async task mein handle hota hai.
