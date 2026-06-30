# 🍊 Instagram & Threads CLI Toolkit 🧵

Toolkit baris perintah (CLI) untuk mengambil data publik dari Instagram dan Threads: profil, followers/following, komentar postingan, balasan Threads, ekspor CSV/TXT, dan analisis komentar berbasis AI.

Cocok dijalankan secara lokal di **Termux (Android)**, **Linux**, maupun **macOS**.

---

## 🛠️ Cara Install & Setup

### 1. Kloning Repositori & Masuk Folder
Pastikan Anda sudah menginstal Git dan Python 3 (khusus pengguna Termux, jalankan `pkg install git python` terlebih dahulu).
```bash
git clone <URL_GITHUB_ANDA>
cd insta
```

### 2. Instalasi Dependensi
Jalankan perintah berikut untuk menginstal modul Python yang dibutuhkan:
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Awal
Jalankan program lalu buka menu **Settings (04)** untuk mengisi cookie Instagram, cookie Threads, dan API key jika ingin memakai fitur AI.

File template tersedia di:
- `bot_config.example.json`
- `threads_config.example.json`

---

## 🚀 Cara Menjalankan Aplikasi

Jalankan perintah berikut di terminal/Termux Anda:
```bash
python run.py
```

### 📋 Fitur yang Tersedia:
* **01. Instagram Bot Menu:**
  - Auto-like postingan target.
  - Cek detail status postingan.
  - Ekstraksi daftar followers & following target.
  - Scrape komentar postingan + analisis sentimen & buzzer dengan AI.
  - Filter pencarian kata kunci komentar (dengan fitur pencarian berulang).
* **02. Threads Bot Menu:**
  - Scrape detail profil Threads target.
  - Ambil daftar postingan Threads.
  - Ekstraksi balasan/komentar postingan Threads dengan pagination penuh.
  - Ekstraksi balasan + analisis sentimen AI.
  - Filter kata kunci balasan secara instan.
* **03. Instagram Brute Force Menu:**
  - Mengumpulkan database target (dari followers, following, likers, atau komentar postingan).
  - Melakukan bruteforce akun pengujian dengan 5 pilihan metode login (API, Ajax, Threads, Graph, GraphQL).
* **04. Settings Menu:**
  - Set Cookie Instagram & Threads.
  - Set OpenAI API Key, Base URL, dan Model.
