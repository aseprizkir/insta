
import os, sys, requests, time, random, re, json, uuid, urllib.parse, threading
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markup import escape
from concurrent.futures import ThreadPoolExecutor as executor

from core.config import *
from core.api import Require, sync_params
from core.bruteforce import BruteExecutor
from utils.helper import kalender, _ck, _search, _shortcode_to_id
from utils.instagram_scraper import InstagramScraper
from utils.bot_ai import InstagramAI
from utils.bot_exporter import BotExporter
from utils.config_manager import (
    load_bot_config, save_bot_config,
    load_threads_config, save_threads_config,
)
from threads_tool import ThreadsToolkit, clean_username, clean_post_id, find_nested_keys
import json as _json
from rich.prompt import Prompt as _Prompt, Confirm as _Confirm, IntPrompt as _IntPrompt
from rich.markdown import Markdown as _Markdown
from rich.align import Align as _Align
from rich.rule import Rule as _Rule

# ── Inisialisasi ────────────────────────────────────────────────────────────
hari, tanggal, bulan, tahun, jam = kalender()
hari_save = f"{hari}-{tanggal}-{bulan}-{tahun}.txt"
session = requests.Session()
console = Console()

BLUE   = "#179BFF"
GREEN  = "#32E875"
RED    = "#FF4D5A"
WHITE  = "#EAF4FF"
MUTED  = "#8AA4BD"
YELLOW = "#FFFF00"


# ════════════════════════════════════════════════════════════════════════════
# CLASS BRUTE — mewarisi BruteExecutor (semua Exec* method ada di sana)
# ════════════════════════════════════════════════════════════════════════════
class Brute(BruteExecutor):
    """Class utama: menu, sesi, dan orchestrator semua fitur Instagram toolkit."""

    def __init__(self):
        self.tw, self.ok, self.cp, self.id, self.lp = 0, 0, 0, [], 0
        self.head = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 243.1.0.14.111 (iPhone13,3; iOS 15_5; en_US; en-US; scale=3.00; 1170x2532; 382468104) NW/3"}
        self.xyz  = {"user-agent": IG_UA}
        self.param = {'count': '200', 'max_id': '', 'search_surface': 'follow_list_page'}
        self.dire = 'data/termux/internal'
        os.makedirs(self.dire, exist_ok=True)
        self.ipp = self._public_ip()

    # ── Helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _public_ip():
        try:
            r = requests.get("https://api.ipify.org/?format=json", timeout=5)
            return r.json().get("ip", "tidak diketahui")
        except Exception:
            return "offline/tidak tersedia"

    @staticmethod
    def _cookie_validation_error(cookie):
        parsed = _ck(cookie)
        missing = [n for n in ("ds_user_id", "sessionid") if not parsed.get(n)]
        if missing:
            return f"cookie belum terautentikasi; field wajib tidak ada: {', '.join(missing)}"
        return None

    @staticmethod
    def _response_summary(response):
        try:
            payload = response.json()
        except ValueError:
            return f"HTTP {response.status_code}, respons bukan JSON"
        reason = payload.get("message") or payload.get("status") or payload.get("error_type")
        keys = ", ".join(sorted(payload.keys())[:6]) or "kosong"
        return f"HTTP {response.status_code}, alasan={reason or 'tidak tersedia'}, keys={keys}"

    @staticmethod
    def _notice(level, message):
        styles = {"success": (GREEN, "BERHASIL"), "error": (RED, "GAGAL"), "info": (BLUE, "INFO")}
        color, label = styles.get(level, styles["info"])
        console.print(Panel(f"[{WHITE}]{message}[/]", title=f"[bold {color}] {label} [/]", border_style=color))

    @staticmethod
    def _normalize_username(value):
        username = value.strip().lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9._]{1,30}', username):
            return ""
        if username.startswith('.') or username.endswith('.') or '..' in username:
            return ""
        return username

    @staticmethod
    def _normalize_post_url(value):
        url = value.strip()
        try:
            parsed = urllib.parse.urlsplit(url)
        except ValueError:
            return ""
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in ('http', 'https'):
            return ""
        if hostname != 'instagram.com' and not hostname.endswith('.instagram.com'):
            return ""
        if not re.fullmatch(r'/(?:p|reel|reels)/[A-Za-z0-9_-]+/?', parsed.path):
            return ""
        return urllib.parse.urlunsplit(('https', hostname, parsed.path, '', ''))

    @staticmethod
    def _menu_table(items):
        table = Table(show_header=False, box=box.ROUNDED, border_style=BLUE, padding=(0, 2))
        table.add_column(style=WHITE, width=32)
        table.add_column(style=WHITE, width=32)
        for index in range(0, len(items), 2):
            row = items[index:index + 2]
            cells = [f"[bold {GREEN}]{number}[/]  {label}" for number, label in row]
            table.add_row(*cells, *([""] if len(cells) == 1 else []))
        return table

    # ── Session & Auth ───────────────────────────────────────────────────────
    def _web_headers(self, cookie, referer="https://www.instagram.com/"):
        return {
            "user-agent": IG_UA,
            "Accept": "*/*",
            "Referer": referer,
            "X-CSRFToken": _ck(cookie).get("csrftoken", ""),
            "X-IG-App-ID": STATIC_PARAMS['x_ig_app_id'],
            "X-Requested-With": "XMLHttpRequest",
            "X-Asbd-Id": STATIC_PARAMS['x_asbd_id'],
            "X-IG-Max-Touch-Points": "0",
            "X-Ig-Www-Claim": "0",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

    def _validate_web_session(self, cookie, uid):
        headers = self.xyz.copy()
        headers.update({"X-IG-App-ID": STATIC_PARAMS['x_ig_app_id'], "X-CSRFToken": _ck(cookie).get("csrftoken", ""), "Accept": "*/*", "Referer": "https://www.instagram.com/"})
        endpoints = (
            "https://www.instagram.com/api/v1/accounts/current_user/?edit=true",
            f"https://www.instagram.com/api/v1/users/{uid}/info/",
        )
        last_response = None
        for endpoint in endpoints:
            response = requests.get(endpoint, headers=headers, cookies=_ck(cookie), timeout=15, allow_redirects=False)
            last_response = response
            if response.status_code != 200:
                continue
            try:
                user = response.json().get("user")
            except ValueError:
                continue
            response_uid = str((user or {}).get("pk") or (user or {}).get("pk_id") or (user or {}).get("id") or "")
            if user and (not response_uid or response_uid == uid):
                return user, response
        return None, last_response

    def _get_profile(self, cookie, username):
        username = username.lstrip("@")
        referer = f"https://www.instagram.com/{username}/"
        endpoints = (
            ("https://www.instagram.com/api/v1/users/web_profile_info/", {"username": username}),
            ("https://www.instagram.com/api/v1/users/search/", {"q": username, "count": "10"}),
        )
        last_response = None
        for endpoint, params in endpoints:
            attempt = 0
            while attempt < 3:
                response = requests.get(endpoint, params=params, headers=self._web_headers(cookie, referer), cookies=_ck(cookie), timeout=15, allow_redirects=False)
                last_response = response
                if response.status_code == 429:
                    if attempt >= 2: break
                    time.sleep((2 ** attempt) + random.uniform(0, 0.5))
                    attempt += 1
                    continue
                if response.status_code != 200: break
                try:
                    payload = response.json()
                except ValueError:
                    break
                if "web_profile_info" in endpoint:
                    user = (payload.get("data") or {}).get("user")
                else:
                    user = next((item.get("user") for item in payload.get("users", []) if (item.get("user") or {}).get("username", "").lower() == username.lower()), None)
                if user: return user, response
                break
        return None, last_response

    def _resolve_user_id(self, cookie, username):
        user, response = self._get_profile(cookie, username)
        if user:
            return str(user.get("id") or user.get("pk") or user.get("pk_id") or ""), user, response
        profile_response = requests.get(f"https://www.instagram.com/{username.lstrip('@')}/", headers=self._web_headers(cookie), cookies=_ck(cookie), timeout=15, allow_redirects=False)
        user_id = (_search(r'"profile_id":"(\d+)"', profile_response.text) or _search(r'"user_id":"(\d+)"', profile_response.text))
        if user_id: return user_id, user, profile_response
        try:
            search_payload = requests.get("https://www.instagram.com/web/search/topsearch/", params={"query": username.lstrip("@")}, headers=self._web_headers(cookie), cookies=_ck(cookie), timeout=15, allow_redirects=False).json()
            match = next(((item.get("user") or item) for item in (search_payload.get("users", []) or search_payload.get("accounts", [])) if (item.get("user") or item).get("username", "").lower() == username.lstrip("@").lower()), None)
        except ValueError:
            match = None
        if match: return str(match.get("pk") or match.get("id") or ""), match, profile_response
        return "", None, profile_response

    def Path(self):
        if not os.path.isfile(".kukis.log"):
            Console().print(f" {P2}[{M2}!{P2}] Belum login. Silakan set cookie di Settings.")
            return None, None, None, None, None
        try:
            with open(".kukis.log", "r", encoding="utf-8") as f:
                content = f.read()
            if "<=>" not in content: raise ValueError("Format file sesi salah.")
            cokie, nama = content.split("<=>")
            cookie_error = self._cookie_validation_error(cokie)
            if cookie_error:
                Console().print(f" {P2}[{M2}!{P2}] {cookie_error}.")
                return None, None, None, None, None
            uid_match = re.search(r"ds_user_id=(\d+)", str(cokie))
            if not uid_match: return None, None, None, None, None
            uid = uid_match.group(1)
            data, r_info = self._validate_web_session(cokie, uid)
            if data:
                return cokie, data.get("full_name", nama), data.get("follower_count", 0), data.get("following_count", 0), data.get("username", "unknown")
            else:
                reason = self._response_summary(r_info) if r_info else "tidak ada respons"
                try: os.remove(".kukis.log")
                except OSError: pass
                Console().print(f" {P2}[{M2}!{P2}] Cookie tidak valid ({reason}). Silakan update di Settings.")
                return None, None, None, None, None
        except Exception as error:
            Console().print(f" {P2}[{M2}!{P2}] Gagal membaca sesi: {M2}{error}")
            return None, None, None, None, None

    def Clear(self):
        if not sys.stdout.isatty(): return
        try: os.system("clear" if "linux" in sys.platform.lower() or "android" in sys.platform.lower() else "cls")
        except OSError: pass

    def Login(self):
        self.Clear(); self.Logos()
        Console().print(f'\n {P2}[{H2}*{P2}] Masukkan cookie Instagram Anda (gunakan akun khusus testing)')
        cokie = Console().input(f' {P2}[{H2}?{P2}] Cookie Instagram : ')
        cookie_error = self._cookie_validation_error(cokie)
        if not cookie_error:
            try:
                uid_match = re.search(r'ds_user_id=(\d+)', str(cokie))
                if not uid_match:
                    Console().print(f' {P2}[{M2}!{P2}] ds_user_id tidak ditemukan dalam cookie.'); time.sleep(3); self.Login(); return
                uid = uid_match.group(1)
                user, r_user = self._validate_web_session(cokie, uid)
                if user:
                    req = user.get('full_name', f'User_{uid}')
                    req1 = user.get('username', 'unknown')
                else:
                    Console().print(f' {P2}[{M2}!{P2}] Cookie tidak valid atau sudah kedaluwarsa.'); time.sleep(3); self.Login(); return
                parsed_cookie = _ck(cokie)
                clean_cookie = '; '.join([f'{k}={v}' for k, v in parsed_cookie.items()])
                with open('.kukis.log', 'w', encoding='utf-8') as f: f.write(f'{clean_cookie}<=>{req}')
                os.chmod('.kukis.log', 0o600)
                Console().print(f'\n {P2}[{H2}*{P2}] Nama lengkap : {H2}{req}\n {P2}[{H2}*{P2}] Username     : {H2}@{req1}'); time.sleep(3); self.Menu()
            except Exception as e:
                Console().print(f' {P2}[{M2}!{P2}] Error: {M2}{e}'); time.sleep(3); self.Login()
        else:
            Console().print(f' {P2}[{M2}!{P2}] Cookie Error: {cookie_error}'); time.sleep(3); self.Login()

    def Logout(self):
        try: os.remove('.kukis.log')
        except OSError: pass
        Console().print(f'\n {P2}[{H2}*{P2}] Logout berhasil, sampai jumpa lagi!'); sys.exit()

    def Logos(self):
        banner = rf"""[bold {BLUE}]
  ██████╗ ██╗███████╗███████╗██╗  ██╗██╗   ██╗ █████╗ ███████╗
  ██╔══██╗██║██╔════╝╚══███╔╝██║ ██╔╝╚██╗ ██╔╝██╔══██╗██╔════╝
  ██████╔╝██║█████╗    ███╔╝ █████╔╝  ╚████╔╝ ███████║███████╗
  ██╔══██╗██║██╔══╝   ███╔╝  ██╔═██╗   ╚██╔╝  ██╔══██║╚════██║
  ██║  ██║██║███████╗███████╗██║  ██╗   ██║   ██║  ██║███████║
  ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝[/]"""
        console.print(Panel(banner, subtitle=f"[bold {GREEN}]INSTAGRAM TOOLKIT[/] [{MUTED}]• MAS RIZKI GANTENG[/]", border_style=BLUE, box=box.DOUBLE))
        console.print(f" [{BLUE}]●[/] [{MUTED}]NETWORK[/]  [{GREEN}]{self.ipp}[/]    [{GREEN}]●[/] [{MUTED}]STATUS[/]  [{GREEN}]ONLINE[/]\n")

    # ════════════════════════════════════════════════════════════════════════
    # MENU UTAMA
    # ════════════════════════════════════════════════════════════════════════
    def Menu(self):
        self.Clear(); self.Logos()
        cokie = fullname = follower_count = following_count = userx = None
        if os.path.isfile(".kukis.log"):
            cokie, fullname, follower_count, following_count, userx = self.Path()

        if cokie:
            info = (
                f"[{MUTED}]ACCOUNT[/]    [bold {WHITE}]{fullname}[/]  [{GREEN}]@{userx}[/]\n"
                f"[{MUTED}]AUDIENCE[/]   [{BLUE}]{follower_count} followers[/]  [{MUTED}]•[/]  [{BLUE}]{following_count} following[/]"
            )
            console.print(Panel(info, title=f"[bold {GREEN}] ACTIVE SESSION [/]", border_style=GREEN))
        else:
            console.print(Panel(f"[{WHITE}]Cookie Instagram belum aktif. Set di[/] [bold {YELLOW}]04 Settings[/]", title=f"[bold {YELLOW}] SESSION [/]", border_style=YELLOW))

        console.print(self._menu_table([
            ("01", "Bot Instagram"),   ("02", "Bot Threads"),
            ("03", "Brute Force"),     ("04", "Settings"),
        ]))
        console.print(f"\n [{MUTED}]Ketik[/] [bold {RED}]exit[/] [{MUTED}]untuk keluar[/]\n")
        choice = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Pilih menu[/] [{GREEN}]›[/] ').lower()

        if choice in ('1', '01'):
            if not cokie:
                console.print(f"[bold {YELLOW}]Set Cookie Instagram dulu di Settings (04).[/bold {YELLOW}]"); time.sleep(1.2); return self.SettingsMenu()
            self.BotMenu(cokie)
        elif choice in ('2', '02'):
            self.ThreadsMenu(); self.Menu()
        elif choice in ('3', '03'):
            if not cokie:
                console.print(f"[bold {YELLOW}]Set Cookie Instagram dulu di Settings (04).[/bold {YELLOW}]"); time.sleep(1.2); return self.SettingsMenu()
            self.BruteMenu(cokie)
        elif choice in ('4', '04'):
            self.SettingsMenu(); self.Menu()
        elif choice == 'exit':
            sys.exit()
        else:
            self.Menu()

    # ════════════════════════════════════════════════════════════════════════
    # 01 — BOT INSTAGRAM
    # ════════════════════════════════════════════════════════════════════════
    def BotMenu(self, cookie):
        self.Clear(); self.Logos()
        console.print(Panel(f"[{WHITE}]Pilih fitur otomasi Instagram[/]", title=f"[bold {BLUE}] BOT INSTAGRAM [/]", border_style=BLUE))
        console.print(self._menu_table([
            ("01", "Like Post"),                        ("05", "Kumpulkan Komentar + AI"),
            ("02", "Cek Status Post"),                  ("06", "Scrape Profil"),
            ("03", "List Followers / Following"),        ("07", "Cari Kata Kunci Komentar"),
            ("04", "Account Health Check"),             ("00", "Kembali"),
        ]))
        choice = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Pilih fitur[/] [{GREEN}]›[/] ').lower()

        if choice in ('1', '01'):
            link = Console().input(f'\n {P2}[{H2}?{P2}] Input Link Postingan : ')
            self.ExecSingleLike(cookie, link)

        elif choice in ('2', '02'):
            self.PostStatus(cookie)

        elif choice in ('3', '03'):
            self.ListConnections(cookie)

        elif choice in ('4', '04'):
            self.AccountHealth(cookie)

        elif choice in ('5', '05'):
            self.ScrapeKomentar(cookie)

        elif choice in ('6', '06'):
            self.ScrapeProfil(cookie)

        elif choice in ('7', '07'):
            self.SearchCommentKeyword(cookie)

        elif choice in ('0', '00', 'back', 'kembali'):
            self.Menu()
        else:
            self.BotMenu(cookie)

    def ExecSingleLike(self, cookie, link):
        link = self._normalize_post_url(link)
        if not link:
            self._notice("error", "Link harus berupa URL postingan Instagram yang valid."); time.sleep(2); return self.BotMenu(cookie)
        try:
            Console().print(f'\n {P2}[{H2}*{P2}] Mengambil media ID...')
            media = self.get_mediaid(link, cookie)
            if media:
                mid = media[0]
                Console().print(f' {P2}[{H2}*{P2}] Media ID: {H2}{mid}')
                status = Require().PostLike(cookie, mid)
                if status: Console().print(f' {P2}[{H2}✓{P2}] Berhasil menyukai postingan!')
                else: Console().print(f' {P2}[{M2}!{P2}] Gagal. Cek cookie atau koneksi.')
            else:
                Console().print(f' {P2}[{M2}!{P2}] Gagal mengambil Media ID.')
            time.sleep(3); self.BotMenu(cookie)
        except Exception as e:
            Console().print(f'\n {P2}[{M2}!{P2}] Error: {M2}{e}'); time.sleep(3); self.BotMenu(cookie)

    def PostStatus(self, cookie):
        link = self._normalize_post_url(Console().input(f'\n {P2}[{H2}?{P2}] Input Link Postingan : '))
        if not link:
            self._notice("error", "Link tidak valid."); time.sleep(2); return self.BotMenu(cookie)
        media = self.get_mediaid(link, cookie)
        if not media:
            Console().print(f' {P2}[{M2}!{P2}] Media ID tidak ditemukan.'); time.sleep(3); self.BotMenu(cookie); return
        response = requests.get(f'https://www.instagram.com/api/v1/media/{media[0]}/info/', headers=self._web_headers(cookie, link), cookies=_ck(cookie), timeout=15, allow_redirects=False)
        try:
            item = response.json().get('items', [])[0]
            owner = item.get('user') or {}
            caption = (item.get('caption') or {}).get('text', '')
            info = (
                f"[#FFFFFF]Pemilik   : [#00FF00]@{escape(owner.get('username', 'unknown'))}[/]\n"
                f"[#FFFFFF]Like      : [#FFFF00]{item.get('like_count', 0)}[/]\n"
                f"[#FFFFFF]Komentar  : [#FFFF00]{item.get('comment_count', 0)}[/]\n"
                f"[#FFFFFF]Sudah Like: [#00FF00]{'Ya' if item.get('has_liked') else 'Tidak'}[/]\n"
                f"[#FFFFFF]Caption   : {escape(caption[:180])}"
            )
            Console().print(Panel(info, title="[#FF00FF]STATUS POST", border_style="#00C8FF"))
        except (ValueError, IndexError):
            Console().print(f' {P2}[{M2}!{P2}] Gagal membaca post: {self._response_summary(response)}')
        Console().input(f'\n {P2}[{H2}?{P2}] Enter untuk kembali...'); self.BotMenu(cookie)

    def ListConnections(self, cookie):
        username = self._normalize_username(Console().input(f'\n {P2}[{H2}?{P2}] Username target : '))
        if not username:
            self._notice("error", "Username tidak valid."); time.sleep(2); return self.BotMenu(cookie)
        kind = Console().input(f' {P2}[{H2}?{P2}] Followers/Following [1/2] : ').strip().lower()
        relations = {'1': 'followers', 'followers': 'followers', '2': 'following', 'following': 'following'}
        relation = relations.get(kind)
        if not relation:
            self._notice("error", "Pilihan harus 1/followers atau 2/following."); time.sleep(2); return self.BotMenu(cookie)
        Console().print(f' {P2}[{H2}1{P2}]. 100 akun   {P2}[{H2}2{P2}]. 500 akun   {P2}[{H2}3{P2}]. Semua')
        limit_choice = Console().input(f' {P2}[{H2}?{P2}] Batas scraping [1/2/3] : ').strip()
        limits = {'1': 100, '01': 100, '2': 500, '02': 500, '3': None, '03': None}
        if limit_choice not in limits:
            Console().print(f' {P2}[{M2}!{P2}] Pilihan tidak valid.'); time.sleep(2); self.BotMenu(cookie); return
        limit = limits[limit_choice]
        user_id, user, response = self._resolve_user_id(cookie, username)
        if not user_id:
            brute_ids = self.get_id(username, cookie, [])
            user_id = brute_ids[0] if brute_ids else ""
        if not user_id:
            Console().print(f' {P2}[{M2}!{P2}] Profil gagal dibaca: {self._response_summary(response)}'); time.sleep(3); self.BotMenu(cookie); return
        rows, seen, max_id, failure, page = [], set(), '', None, 0
        while True:
            page += 1
            remaining = (limit - len(rows)) if limit else 200
            params = {'count': str(min(200, remaining)), 'search_surface': 'follow_list_page'}
            if max_id: params['max_id'] = max_id
            response = requests.get(f"https://www.instagram.com/api/v1/friendships/{user_id}/{relation}/", params=params, headers=self._web_headers(cookie, f"https://www.instagram.com/{username}/"), cookies=_ck(cookie), timeout=20, allow_redirects=False)
            try: payload = response.json()
            except ValueError: failure = self._response_summary(response); break
            if response.status_code != 200 or payload.get('status') not in (None, 'ok'):
                failure = self._response_summary(response); break
            for acc in payload.get('users', []):
                key = acc.get('pk') or acc.get('username')
                if key not in seen:
                    seen.add(key)
                    rows.append((acc.get('pk'), acc.get('username'), acc.get('full_name')))
                    if limit and len(rows) >= limit: break
            Console().print(f' {P2}[{H2}*{P2}] Halaman {H2}{page}{P2} | Terkumpul {H2}{len(rows)}{P2}', end='\r')
            if limit and len(rows) >= limit: break
            max_id = payload.get('next_max_id')
            if not max_id: break
            time.sleep(1)
        if failure and not rows:
            Console().print(f'\n {P2}[{M2}!{P2}] Gagal: {failure}'); time.sleep(3); self.BotMenu(cookie); return
        table = Table(title=f"{relation.upper()} @{username}", border_style="#00C8FF")
        table.add_column("No", justify="right"); table.add_column("Username", style="#00FF00"); table.add_column("Nama"); table.add_column("User ID", style="#FFFF00")
        for number, (account_id, account_username, full_name) in enumerate(rows, 1):
            table.add_row(str(number), f"@{account_username or 'unknown'}", full_name or "", str(account_id or ""))
        Console().print(f'\n {P2}[{H2}✓{P2}] Berhasil mengambil {H2}{len(rows)}{P2} akun.'); Console().print(table)
        Console().input(f'\n {P2}[{H2}?{P2}] Enter untuk kembali...'); self.BotMenu(cookie)

    def AccountHealth(self, cookie):
        parsed = _ck(cookie)
        uid = parsed.get('ds_user_id', '')
        user, response = self._validate_web_session(cookie, uid)
        checks = [
            ("Session",    bool(user),                self._response_summary(response) if response else "tidak ada respons"),
            ("CSRF Token", bool(parsed.get('csrftoken')), "tersedia" if parsed.get('csrftoken') else "tidak tersedia"),
            ("Session ID", bool(parsed.get('sessionid')), "tersedia" if parsed.get('sessionid') else "tidak tersedia"),
        ]
        table = Table(title="ACCOUNT HEALTH", border_style="#00C8FF")
        table.add_column("Pemeriksaan"); table.add_column("Status"); table.add_column("Detail")
        for name, passed, detail in checks:
            table.add_row(name, "[#00FF00]OK" if passed else "[#FF0000]GAGAL", detail)
        Console().print(table)
        Console().input(f'\n {P2}[{H2}?{P2}] Enter untuk kembali...'); self.BotMenu(cookie)

    def ScrapeKomentar(self, cookie):
        self.Clear(); self.Logos()
        url = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]URL Postingan Instagram[/] [{GREEN}]›[/] ').strip()
        if not url: return self.BotMenu(cookie)
        try: limit = int(console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Limit komentar (default 100)[/] [{GREEN}]›[/] ').strip() or "100")
        except ValueError: limit = 100
        scraper = InstagramScraper()
        console.print(f"[bold {YELLOW}]💡 Tips: Aktifkan mode pesawat 5 detik untuk rotasi IP jika rate limit.[/bold {YELLOW}]")
        comments = scraper.scrape_comments(cookie, url, limit)
        if not comments:
            console.print(f"[{MUTED}]Tidak ada komentar ditemukan. Cookie mungkin perlu diupdate.[/{MUTED}]")
            console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); return self.BotMenu(cookie)
        console.print(f"[dim]✓ {len(comments)} komentar berhasil di-scrape.[/dim]")
        # AI Analysis
        ai_report = ""
        igcfg = load_bot_config()
        openai_key = (igcfg.get("openai_api_key") or "").strip()
        if openai_key:
            ai_opt = console.input(f'\n [bold {GREEN}]🤖 Analisis komentar pakai AI? (y/n)[/] ').strip().lower()
            if ai_opt in ('y', 'ya', 'yes'):
                with console.status("[bold yellow]🤖 Menganalisis sentimen & spammer dengan AI...[/bold yellow]"):
                    ai_analyzer = InstagramAI(api_key=openai_key, base_url=igcfg.get("openai_base_url") or "https://router.bynara.id/v1", model=igcfg.get("openai_model") or "mimo-v2.5-pro-free")
                    ai_report = ai_analyzer.analyze_comments(comments)
                console.print(_Rule(style=BLUE)); console.print(_Markdown(ai_report)); console.print(_Rule(style=BLUE))
        else:
            console.print(f"[bold {YELLOW}]💡 Tips: Set OpenAI API Key di Settings (04) biar bisa analisis AI.[/bold {YELLOW}]")
        if not ai_report:
            lihat = console.input(f' [bold {BLUE}]📋 Lihat tabel komentar? (y/n)[/] ').strip().lower()
            if lihat in ('y', 'ya', 'yes'):
                table = Table(box=box.ROUNDED, border_style=BLUE, title=f"[bold {BLUE}]Komentar (Total: {len(comments)})[/bold {BLUE}]")
                table.add_column("No", justify="center"); table.add_column("Username", style="bold yellow"); table.add_column("Komentar")
                for idx, c in enumerate(comments[:30], 1): table.add_row(str(idx), f"@{c['username']}", c['text'])
                console.print(table)
        export_csv = console.input(f' [bold {GREEN}]📂 Ekspor komentar ke CSV? (y/n)[/] ').strip().lower()
        if export_csv in ('y', 'ya', 'yes'):
            media_id = scraper.get_mediaid(url, cookie) or "post"
            filepath = BotExporter.export_comments_csv(media_id, comments)
            console.print(f"[bold {GREEN}]✓ Disimpan di: {filepath}[/bold {GREEN}]")
        if ai_report:
            export_ai = console.input(f' [bold {GREEN}]📂 Ekspor laporan AI ke TXT? (y/n)[/] ').strip().lower()
            if export_ai in ('y', 'ya', 'yes'):
                media_id = scraper.get_mediaid(url, cookie) or "post"
                filepath = BotExporter.export_report_txt(f"ai_report_{media_id}", ai_report)
                console.print(f"[bold {GREEN}]✓ Laporan AI disimpan di: {filepath}[/bold {GREEN}]")
        console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.BotMenu(cookie)

    def ScrapeProfil(self, cookie):
        target = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Username Instagram Target[/] [{GREEN}]›[/] ').strip()
        if not target: return self.BotMenu(cookie)
        scraper = InstagramScraper()
        with console.status("[bold green]Mengambil profil dari Instagram...[/bold green]"):
            try:
                profile = scraper.scrape_profile(cookie, target)
                profile_table = Table(box=box.ROUNDED, show_header=False, border_style=BLUE, title=f"[bold {BLUE}]Detail Profil: @{profile['username']}[/bold {BLUE}]")
                for label, value in [("Nama Lengkap", profile['name']), ("Username", f"@{profile['username']}"), ("User ID", str(profile['id'])), ("Followers", f"{profile['followers']:,}"), ("Following", f"{profile['following']:,}"), ("Postingan", f"{profile['posts']:,}"), ("Privat?", profile['is_private']), ("Verified?", profile['is_verified']), ("Bio", profile['bio'])]:
                    profile_table.add_row(label, value)
                console.print(profile_table)
            except Exception as e:
                console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
        console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.BotMenu(cookie)

    def SearchCommentKeyword(self, cookie):
        self.Clear(); self.Logos()
        console.print(Panel(f"[{WHITE}]Cari kata kunci spesifik di komentar postingan[/]", title=f"[bold {BLUE}] CARI KATA KUNCI [/]", border_style=BLUE))
        url = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]URL Postingan Instagram[/] [{GREEN}]›[/] ').strip()
        if not url: return self.BotMenu(cookie)
        try: limit = int(console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Limit komentar (default 300)[/] [{GREEN}]›[/] ').strip() or "300")
        except ValueError: limit = 300
        scraper = InstagramScraper()
        console.print(f"[bold {YELLOW}]💡 Tips: Aktifkan mode pesawat 5 detik jika rate limit.[/bold {YELLOW}]")
        comments = scraper.scrape_comments(cookie, url, limit)
        if not comments:
            console.print(f"[{MUTED}]Tidak ada komentar ditemukan.[/{MUTED}]")
            console.input(f'\n [dim]Tekan Enter...[/]'); return self.BotMenu(cookie)
        console.print(f"[dim]✓ {len(comments)} komentar berhasil di-scrape.[/dim]")
        while True:
            keyword = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Kata kunci pencarian[/] [{GREEN}]›[/] ').strip().lower()
            if not keyword: break
            matched = [c for c in comments if keyword in c['text'].lower()]
            if not matched:
                console.print(f"[bold {RED}]❌ Tidak ada komentar dengan kata kunci '{keyword}'.[/bold {RED}]")
            else:
                table = Table(box=box.ROUNDED, border_style=BLUE, title=f"[bold {BLUE}]'{keyword}' ({len(matched)}/{len(comments)})[/bold {BLUE}]")
                table.add_column("No", justify="center"); table.add_column("Username", style="bold yellow"); table.add_column("Komentar")
                for idx, c in enumerate(matched, 1):
                    highlighted = re.sub(f"({re.escape(keyword)})", r"[bold green]\1[/bold green]", escape(c['text']), flags=re.IGNORECASE)
                    table.add_row(str(idx), f"@{c['username']}", highlighted)
                console.print(table)
                export_csv = console.input(f'\n [bold {GREEN}]📂 Ekspor hasil ke CSV? (y/n)[/] ').strip().lower()
                if export_csv in ('y', 'ya', 'yes'):
                    media_id = scraper.get_mediaid(url, cookie) or "post"
                    safe_kw = "".join([ch if ch.isalnum() else "_" for ch in keyword])
                    filepath = BotExporter.export_comments_csv(f"{media_id}_filter_{safe_kw}", matched)
                    console.print(f"[bold {GREEN}]✓ Disimpan di: {filepath}[/bold {GREEN}]")
            if console.input(f'\n [bold {BLUE}]🔍 Cari kata kunci lain? (y/n)[/] [{GREEN}]›[/] ').strip().lower() not in ('y', 'ya', 'yes'): break
        console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.BotMenu(cookie)

    # ════════════════════════════════════════════════════════════════════════
    # 03 — BRUTE FORCE MENU
    # ════════════════════════════════════════════════════════════════════════
    def BruteMenu(self, cookie):
        self.Clear(); self.Logos()
        console.print(Panel(f"[{WHITE}]Scrape target dan jalankan brute force[/]", title=f"[bold {RED}] BRUTE FORCE [/]", border_style=RED))
        console.print(self._menu_table([
            ("01", "Dump Followers"),          ("05", "Checkpoint Akun"),
            ("02", "Dump Following"),          ("06", "Cek Hasil"),
            ("03", "Dump Komentar"),           ("07", "Brute Force (1 Target)"),
            ("04", "Dump Likers"),             ("00", "Kembali"),
        ]))
        self.input_menu(cookie)

    def input_menu(self, kueh):
        x = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Pilih menu[/] [{GREEN}]›[/] ').strip().lower()

        if x in ('1', '01', '2', '02'):
            console.print(Panel(f"[{WHITE}]Pisahkan beberapa username dengan koma.[/]", title=f"[bold {BLUE}] TARGET [/]", border_style=BLUE))
            raw_targets = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Username target[/] [{GREEN}]›[/] ')
            targets = [t.strip().lstrip('@') for t in raw_targets.split(',') if t.strip()]
            if not targets: self._notice("error", "Target belum diisi."); return self.BruteMenu(kueh)
            user_ids = []
            for target in targets: self.get_id(target, kueh, user_ids)
            if not user_ids: self._notice("error", "User ID tidak ditemukan."); return self.BruteMenu(kueh)
            self.dump_acc(kueh, user_ids, x in ('1', '01'), '')
            if self.id:
                console.print(Panel(f"[bold {GREEN}]1[/] Terbaru (Following Baru)\n[bold {GREEN}]2[/] Terlama (Following Lama)", title=f"[bold {BLUE}] URUTAN [/]", border_style=BLUE))
                if console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Pilih [1/2][/] [{GREEN}]›[/] ').strip() == '2': self.id.reverse()
                self.methode()
            else:
                self._notice("error", "Tidak ada akun publik yang berhasil dikumpulkan."); self.BruteMenu(kueh)

        elif x in ('3', '03'):
            try:
                self._notice("info", "Masukkan link postingan publik untuk membaca komentar.")
                link = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Link postingan[/] [{GREEN}]›[/] ')
                medi = self.get_mediaid(link, kueh)
                if not medi: self._notice("error", "Media ID tidak ditemukan."); return self.BruteMenu(kueh)
                for uid in medi: self.GetUserComment(kueh, uid, '')
                self.methode()
            except requests.exceptions.MissingSchema as e:
                self._notice("error", f"Format URL tidak valid: {e}"); self.BruteMenu(kueh)

        elif x in ('4', '04'):
            try:
                self._notice("info", "Masukkan link postingan publik untuk membaca likers.")
                link = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Link postingan[/] [{GREEN}]›[/] ')
                medi = self.get_mediaid(link, kueh)
                if not medi: self._notice("error", "Media ID tidak ditemukan."); return self.BruteMenu(kueh)
                for uid in medi: self.Likes(kueh, uid)
                self.methode()
            except requests.exceptions.MissingSchema as e:
                self._notice("error", f"Format URL tidak valid: {e}"); self.BruteMenu(kueh)

        elif x in ('5', '05'):
            try: file = open(f'data/termux/internal/CP.txt', 'r').read()
            except: Console().print(f'\n {P2}[{M2}!{P2}] Data checkpoint belum tersedia.'); return
            for res in file.splitlines():
                try:
                    user, pswd = res.split('|')[0], res.split('|')[1]
                    fmt = f'{user}<=>{pswd}'
                    if fmt not in self.id: self.id.append(fmt)
                except IndexError: continue
            Console().print(f'\n {P2}[{H2}+{P2}] Ada {K2}{len(self.id)}{P2} akun checkpoint.')
            self.methode()

        elif x in ('6', '06'):
            q = 0
            Console().print(f'\n {P2}[{H2}1{P2}]. Check akun OK    {P2}[{H2}3{P2}]. Check akun A2F')
            Console().print(f' {P2}[{H2}2{P2}]. Check akun CP    {P2}[{H2}4{P2}]. Kembali')
            h = Console().input(f' {P2}[{H2}?{P2}] Input menu : ').strip().lower()
            result_files = {'1': 'OK.txt', '01': 'OK.txt', '2': 'CP.txt', '02': 'CP.txt', '3': '2F.txt', '03': '2F.txt'}
            if h in ('4', '04', 'back', 'kembali'): return self.Menu()
            result_file = result_files.get(h)
            if not result_file: self._notice("error", "Pilihan tidak tersedia."); return self.BruteMenu(kueh)
            try:
                with open(os.path.join(self.dire, result_file), 'r', encoding='utf-8') as f: result_lines = f.read().splitlines()
            except OSError as error:
                self._notice("error", f"File tidak dapat dibaca: {error}"); return self.BruteMenu(kueh)
            Console().print(f'\n {P2}[{H2}+{P2}]. Hasil {result_file}')
            for w in result_lines:
                q += 1
                Console().print(f' {P2}[{H2}{q}{P2}]. {H2 if result_file == "OK.txt" else K2}{w}')

        elif x in ('7', '07'):
            username = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Username target[/] [{GREEN}]›[/] ').strip().lstrip('@')
            if not username: self._notice("error", "Username tidak boleh kosong."); return self.BruteMenu(kueh)
            ikut, mengikut, posting, fullname = self.friends_user(username)
            if fullname == "None": fullname = username
            self.id.append(f"{username}<=>{fullname}")
            self.methode()

        elif x in ('0', '00', 'back', 'kembali'):
            self.Menu()
        elif x.lower() in ('exit', 'EXIT'):
            self.Logout()
        else:
            self._notice("error", "Pilihan tidak tersedia."); self.BruteMenu(kueh)

    # ── Brute Support Methods ────────────────────────────────────────────────
    def get_id(self, ccv, cokie, results=None):
        results = [] if results is None else results
        try:
            response = requests.get(f'https://www.instagram.com/{ccv}/', headers=self._web_headers(cokie, f'https://www.instagram.com/{ccv}/'), cookies=_ck(cokie), timeout=15, allow_redirects=False)
            uid = (_search(r'"profile_id":"(\d+)"', response.text) or _search(r'"user_id":"(\d+)"', response.text) or _search(r'"id":"(\d+)","username":"' + re.escape(ccv) + r'"', response.text))
            if uid and uid not in results: results.append(uid)
            elif not uid: self._notice("error", f"User ID @{ccv} tidak ditemukan.")
        except requests.RequestException as error:
            self._notice("error", f"Gagal membaca @{ccv}: {error}")
        return results

    def get_mediaid(self, url, cokie):
        ahmasa = []
        parsed_cookie = _ck(cokie)
        csrftoken = parsed_cookie.get('csrftoken', '')
        shortcode_match = re.search(r'/(?:p|reels|reel)/([A-Za-z0-9_-]+)', url)
        if shortcode_match:
            shortcode = shortcode_match.group(1)
            try:
                resp = requests.get('https://www.instagram.com/graphql/query', params={'doc_id': STATIC_PARAMS['doc_id_post'], 'variables': json.dumps({'shortcode': shortcode, '__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider': False})}, headers={'user-agent': IG_UA, 'x-ig-app-id': STATIC_PARAMS['x_ig_app_id'], 'x-csrftoken': csrftoken, 'x-root-field-name': 'xdt_api__v1__media__shortcode__web_info', 'x-fb-friendly-name': 'PolarisPostRootQuery', 'x-bloks-version-id': STATIC_PARAMS['x_bloks_version_id'], 'x-asbd-id': STATIC_PARAMS['x_asbd_id'], 'accept': '*/*', 'referer': url}, cookies=parsed_cookie, timeout=10, allow_redirects=False)
                if resp.status_code == 200:
                    web_info = (resp.json().get('data') or {}).get('xdt_api__v1__media__shortcode__web_info') or {}
                    items = web_info.get('items', [])
                    if items:
                        idm = str(items[0].get('id') or items[0].get('pk') or '')
                        if idm and idm.isdigit(): ahmasa.append(idm); return ahmasa
            except Exception: pass
        headers = self.head.copy()
        headers.update({'cookie': cokie})
        try:
            req = requests.get(url, headers=headers, timeout=10).text
            idm = _search(r'\"media_id\":\"(\d+)\"', req)
            if idm: ahmasa.append(idm); return ahmasa
        except Exception: pass
        if shortcode_match:
            idm = _shortcode_to_id(shortcode_match.group(1))
            if idm: ahmasa.append(idm)
        return ahmasa

    def GetUserComment(self, cookie, media_id, max_min):
        try:
            HEADERS = {'user-agent': self.head['user-agent'], 'content-type': 'application/x-www-form-urlencoded', 'x-csrftoken': _search('csrftoken=(.*?)(?:;|$)', cookie), 'cookie': cookie}
            r = requests.get(f'https://i.instagram.com/api/v1/media/{media_id}/comments/?can_support_threading=true&permalink_enabled=false', headers=HEADERS, timeout=15)
            x = r.json().get('comments', [])
            for data in x:
                username_comment = data.get('user', {}).get('username', '')
                pk = data.get('user', {}).get('pk', '')
                formatusr = f'{username_comment}<=>{pk}'
                if formatusr not in self.id: self.id.append(formatusr)
        except Exception: pass

    def Likes(self, cokie, mediaid):
        try:
            head = {'user-agent': self.head['user-agent'], 'content-type': 'application/x-www-form-urlencoded', 'x-csrftoken': _search('csrftoken=(.*?)(?:;|$)', cokie), 'cookie': cokie}
            x = requests.get(f'https://i.instagram.com/api/v1/media/{mediaid}/likers/', headers=head, timeout=15).json().get('users', [])
            for data in x:
                username = data.get('username', '')
                pk = data.get('pk', '')
                fmt = f'{username}<=>{pk}'
                if fmt not in self.id: self.id.append(fmt)
        except Exception: pass

    def dump_acc(self, cokie, users, type, max_id):
        relation = 'followers' if type else 'following'
        head = {'user-agent': self.head['user-agent'], 'x-csrftoken': _search('csrftoken=(.*?)(?:;|$)', cokie), 'x-ig-app-id': STATIC_PARAMS['x_ig_app_id'], 'x-asbd-id': STATIC_PARAMS['x_asbd_id'], 'x-ig-www-claim': '0', 'cookie': cokie}
        for uid in users:
            max_id_local = ''
            while True:
                params = {'count': '200', 'search_surface': 'follow_list_page'}
                if max_id_local: params['max_id'] = max_id_local
                try:
                    resp = requests.get(f'https://www.instagram.com/api/v1/friendships/{uid}/{relation}/', params=params, headers=head, timeout=15)
                    data = resp.json()
                    for user in data.get('users', []):
                        username = user.get('username', '')
                        pk = user.get('pk', '') or user.get('pk_id', '')
                        fmt = f'{username}<=>{pk}'
                        if fmt not in self.id: self.id.append(fmt)
                    next_max = data.get('next_max_id')
                    if not next_max: break
                    max_id_local = next_max
                    Console().print(f' {P2}[{H2}*{P2}] Dump {relation}: {H2}{len(self.id)}{P2} akun terkumpul...', end='\r')
                    time.sleep(0.8)
                except Exception: break

    def friends_user(self, name):
        try:
            headers = {'user-agent': IG_UA, 'x-ig-app-id': STATIC_PARAMS['x_ig_app_id'], 'x-asbd-id': STATIC_PARAMS['x_asbd_id'], 'accept': '*/*', 'x-requested-with': 'XMLHttpRequest'}
            resp = requests.get(f'https://www.instagram.com/api/v1/users/web_profile_info/?username={name}', headers=headers, timeout=15, allow_redirects=False)
            req = resp.json()['data']['user']
            ikut     = req.get('follower_count') or req.get('edge_followed_by', {}).get('count', 0)
            mengikut = req.get('following_count') or req.get('edge_follow', {}).get('count', 0)
            posting  = req.get('media_count') or req.get('edge_owner_to_timeline_media', {}).get('count', 0)
            fulmmnn  = req.get('full_name', '')
            return (ikut, mengikut, posting, fulmmnn)
        except Exception: return ('None', 'None', 'None', 'None')

    def all_dateee(self, name):
        try:
            headers = {'user-agent': IG_UA, 'x-ig-app-id': STATIC_PARAMS['x_ig_app_id'], 'x-asbd-id': STATIC_PARAMS['x_asbd_id'], 'accept': '*/*', 'x-requested-with': 'XMLHttpRequest'}
            req = requests.get(f'https://www.instagram.com/api/v1/users/web_profile_info/?username={name}', headers=headers, timeout=15, allow_redirects=False).json()['data']['user']
            return (
                req.get('follower_count') or req.get('edge_followed_by', {}).get('count', 0),
                req.get('following_count') or req.get('edge_follow', {}).get('count', 0),
                req.get('media_count') or req.get('edge_owner_to_timeline_media', {}).get('count', 0),
                req.get('full_name', ''), req.get('id') or req.get('pk', ''), req.get('biography', ''),
                req.get('profile_pic_url_hd', req.get('profile_pic_url', '')),
                req.get('edge_mutual_followed_by', {}).get('count', 0),
                req.get('is_private', False), req.get('is_verified', False),
                req.get('fbid', ''), req.get('highlight_reel_count', 0), req.get('business_contact_method', '')
            )
        except Exception: return ('None',) * 13

    # ════════════════════════════════════════════════════════════════════════
    # 02 — BOT THREADS
    # ════════════════════════════════════════════════════════════════════════
    def ThreadsMenu(self):
        try: threads_config = load_threads_config()
        except Exception: threads_config = {}
        threads_cookie = threads_config.get("threads_cookie", "")
        toolkit = ThreadsToolkit(threads_config)

        self.Clear(); self.Logos()
        console.print(Panel(f"[{WHITE}]Pilih fitur otomasi Threads[/]", title=f"[bold {BLUE}] BOT THREADS [/]", border_style=BLUE))
        if not threads_cookie:
            console.print(f"[bold {RED}]⚠️  Cookie Threads kosong! Set di Settings (04).[/bold {RED}]\n")

        console.print(self._menu_table([
            ("01", "Cek Detail Profil"),         ("05", "Ambil Following"),
            ("02", "Ambil Postingan"),            ("06", "Follow Akun"),
            ("03", "Ambil Replies"),              ("07", "Like Postingan"),
            ("04", "Ambil Followers"),            ("08", "Replies + Analisis AI"),
            ("09", "Cari Kata Kunci Replies"),    ("00", "Kembali"),
        ]))
        choice = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Pilih fitur[/] [{GREEN}]›[/] ').lower()

        if choice in ('1', '01'):
            target = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Username/URL Profil Threads[/] [{GREEN}]›[/] ').strip()
            if not target: return self.ThreadsMenu()
            with console.status("[bold green]Menghubungi profil Threads...[/bold green]"):
                try:
                    info = toolkit.scrape_profile_get(target)
                    profile_table = Table(box=box.ROUNDED, show_header=False, border_style=BLUE, title=f"[bold {BLUE}]Detail Profil Threads: @{info['username']}[/bold {BLUE}]")
                    for label, value in [("Nama Lengkap", info['fullname']), ("Username", f"@{info['username']}"), ("User ID", str(info['user_id'])), ("Followers", str(info['followers'])), ("Posts", str(info['threads_count'])), ("Bio", info['bio'])]:
                        profile_table.add_row(label, value)
                    console.print(profile_table)
                    updated = False
                    if info.get("lsd_token") and info["lsd_token"] != threads_config.get("x_fb_lsd"):
                        threads_config["x_fb_lsd"] = info["lsd_token"]; updated = True; console.print(f"[dim]⚡ Auto-updated LSD Token[/dim]")
                    if info.get("fb_dtsg_token") and info["fb_dtsg_token"] != threads_config.get("fb_dtsg"):
                        threads_config["fb_dtsg"] = info["fb_dtsg_token"]; updated = True; console.print(f"[dim]⚡ Auto-updated fb_dtsg Token[/dim]")
                    if updated: save_threads_config(threads_config); toolkit.config = threads_config
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
            console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.ThreadsMenu()

        elif choice in ('2', '02'):
            target = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Username/URL/User ID Target[/] [{GREEN}]›[/] ').strip()
            if not target: return self.ThreadsMenu()
            with console.status("[bold green]Mengambil postingan Threads...[/bold green]"):
                try:
                    if not target.isdigit(): info = toolkit.scrape_profile_get(target); target = info["user_id"]
                    raw_data = toolkit.get_profile_posts(target)
                    threads = list(find_nested_keys(raw_data, "thread_items"))
                    if not threads:
                        posts = list(find_nested_keys(raw_data, "post"))
                        if posts: threads = [[{"post": p}] for p in posts]
                    if not threads:
                        console.print(f"[{MUTED}]Tidak ada postingan publik terdeteksi.[/{MUTED}]")
                    else:
                        console.print(f"[bold {GREEN}]Daftar Postingan Threads (Total: {len(threads)})[/bold {GREEN}]\n")
                        for idx, thread in enumerate(threads, 1):
                            if not thread: continue
                            post = thread[0].get("post", {})
                            post_id = post.get("id") or post.get("pk")
                            code = post.get("code")
                            caption = (post.get("caption") or {}).get("text", "Tidak ada caption")
                            likes = post.get("like_count") or 0
                            replies = post.get("reply_count") or post.get("text_post_app_info", {}).get("direct_reply_count") or 0
                            link = f"https://www.threads.net/t/{code}" if code else f"Post ID: {post_id}"
                            console.print(Panel(f"🔗 [bold yellow]Link:[/bold yellow] {link}\n❤️ [bold {RED}]Likes:[/bold {RED}] {likes:,} | 💬 [bold {BLUE}]Balasan:[/bold {BLUE}] {replies:,}\n📝 [bold]Caption:[/bold]\n{caption}", border_style=BLUE, title=f"Post #{idx} (ID: {post_id})", box=box.ROUNDED))
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
            console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.ThreadsMenu()

        elif choice in ('3', '03'):
            url_or_id = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]URL/Post ID Threads[/] [{GREEN}]›[/] ').strip()
            if not url_or_id: return self.ThreadsMenu()
            try: limit = int(console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Limit replies (default 100)[/] [{GREEN}]›[/] ').strip() or "100")
            except ValueError: limit = 100
            comments, seen_ids, cursor, has_next = [], set(), None, True
            with console.status("[bold green]Mengambil balasan Threads...[/bold green]") as status:
                try:
                    while len(comments) < limit and has_next:
                        raw_data = toolkit.get_thread_replies(url_or_id, cursor)
                        new_found = False
                        for p in find_nested_keys(raw_data, "post"):
                            pid = p.get("id") or p.get("pk")
                            if not pid or pid in seen_ids: continue
                            seen_ids.add(pid)
                            user_info = p.get("user") or {}
                            username = user_info.get("username")
                            text = (p.get("caption") or {}).get("text") or p.get("text")
                            if username and text:
                                comments.append({"comment_id": str(pid), "username": username, "fullname": user_info.get("full_name") or "", "text": text, "likes": p.get("like_count") or 0})
                                new_found = True
                                if len(comments) >= limit: break
                        page_info = toolkit.extract_page_info(raw_data)
                        has_next = page_info.get("has_next_page", False)
                        cursor = page_info.get("end_cursor")
                        status.update(f"[bold green]Mengambil balasan Threads... [{len(comments)}][/bold green]")
                        if not cursor or not new_found: break
                        time.sleep(1.0)
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
            if not comments:
                console.print(f"[{MUTED}]Tidak ada balasan. Cookie mungkin perlu diupdate.[/{MUTED}]")
            else:
                table = Table(box=box.ROUNDED, border_style=BLUE, title=f"[bold {BLUE}]Balasan Threads (Total: {len(comments)})[/bold {BLUE}]")
                table.add_column("No", justify="center"); table.add_column("Username", style="bold yellow"); table.add_column("Balasan"); table.add_column("Likes", justify="right")
                for idx, c in enumerate(comments[:30], 1): table.add_row(str(idx), f"@{c['username']}", c['text'], f"❤️ {c['likes']}")
                console.print(table)
                if _Confirm.ask("\nEkspor balasan ke CSV?"):
                    filepath = BotExporter.export_comments_csv(clean_post_id(url_or_id), comments)
                    console.print(f"[bold {GREEN}]✓ Disimpan di: {filepath}[/bold {GREEN}]")
            console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.ThreadsMenu()

        elif choice in ('4', '04', '5', '05'):
            relation = "followers" if choice in ('4', '04') else "following"
            target = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Username/User ID Target ({relation})[/] [{GREEN}]›[/] ').strip()
            if not target: return self.ThreadsMenu()
            try: limit = int(console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Limit jumlah data[/] [{GREEN}]›[/] ').strip() or "20")
            except ValueError: limit = 20
            with console.status(f"[bold green]Mengambil {relation} Threads...[/bold green]") as status:
                try:
                    if not target.isdigit(): info = toolkit.scrape_profile_get(target); target = info["user_id"]
                    users_list = toolkit.scrape_users(target, relation, limit, status)
                    if not users_list:
                        console.print(f"[{MUTED}]Tidak ada pengguna ditemukan.[/{MUTED}]")
                    else:
                        table = Table(box=box.ROUNDED, border_style=BLUE, title=f"[bold {BLUE}]{relation.capitalize()} Threads @{target}[/bold {BLUE}]")
                        table.add_column("No", justify="center"); table.add_column("User ID", style="dim"); table.add_column("Username", style="bold yellow"); table.add_column("Nama Lengkap"); table.add_column("Verified", justify="center")
                        for idx, u in enumerate(users_list, 1): table.add_row(str(idx), u["id"], f"@{u['username']}", u["fullname"], "🛡️" if u["is_verified"] else "")
                        console.print(table)
                        if _Confirm.ask("\nEkspor ke CSV?"):
                            filepath = BotExporter.export_connections_csv(target, f"threads_{relation}", users_list)
                            console.print(f"[bold {GREEN}]✓ Berhasil: {filepath}[/bold {GREEN}]")
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
            console.input(f'\n [dim]Tekan Enter untuk melanjutkan...[/]'); self.ThreadsMenu()

        elif choice in ('6', '06'):
            target = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]User ID Target (Numeric)[/] [{GREEN}]›[/] ').strip()
            if not target: return self.ThreadsMenu()
            with console.status("[bold green]Follow...[/bold green]"):
                try: toolkit.follow_user(target); console.print(f"[bold {GREEN}]✓ Berhasil follow user ID: {target}[/bold {GREEN}]")
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
            console.input(f'\n [dim]Tekan Enter...[/]'); self.ThreadsMenu()

        elif choice in ('7', '07'):
            target = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]URL/Post ID Threads[/] [{GREEN}]›[/] ').strip()
            if not target: return self.ThreadsMenu()
            with console.status("[bold green]Like Threads...[/bold green]"):
                try: toolkit.like_post(clean_post_id(target)); console.print(f"[bold {GREEN}]✓ Berhasil like postingan Threads![/bold {GREEN}]")
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
            console.input(f'\n [dim]Tekan Enter...[/]'); self.ThreadsMenu()

        elif choice in ('8', '08'):
            self._threads_replies_ai(toolkit, threads_config)

        elif choice in ('9', '09'):
            self._threads_keyword_search(toolkit)

        elif choice in ('0', '00', 'back', 'kembali'):
            self.Menu()
        else:
            self.ThreadsMenu()

    def _threads_replies_ai(self, toolkit, threads_config):
        """Scrape replies Threads + analisis AI."""
        url_or_id = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]URL/Post ID Threads[/] [{GREEN}]›[/] ').strip()
        if not url_or_id: return self.ThreadsMenu()
        try: limit = int(console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Limit (default 100)[/] [{GREEN}]›[/] ').strip() or "100")
        except ValueError: limit = 100
        comments, seen_ids, cursor, has_next = [], set(), None, True
        with console.status("[bold green]Mengambil balasan...[/bold green]") as status:
            try:
                while len(comments) < limit and has_next:
                    raw_data = toolkit.get_thread_replies(url_or_id, cursor)
                    new_found = False
                    for p in find_nested_keys(raw_data, "post"):
                        pid = p.get("id") or p.get("pk")
                        if not pid or pid in seen_ids: continue
                        seen_ids.add(pid)
                        user_info = p.get("user") or {}
                        username = user_info.get("username")
                        text = (p.get("caption") or {}).get("text") or p.get("text")
                        if username and text:
                            comments.append({"comment_id": str(pid), "username": username, "fullname": user_info.get("full_name") or "", "text": text})
                            new_found = True
                            if len(comments) >= limit: break
                    page_info = toolkit.extract_page_info(raw_data)
                    has_next = page_info.get("has_next_page", False)
                    cursor = page_info.get("end_cursor")
                    status.update(f"[bold green]Mengambil... [{len(comments)}][/bold green]")
                    if not cursor or not new_found: break
                    time.sleep(1.0)
            except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]"); comments = []
        if not comments:
            console.print(f"[{MUTED}]Tidak ada balasan.[/{MUTED}]")
        else:
            console.print(f"[dim]✓ {len(comments)} balasan.[/dim]")
            ai_report = ""
            igcfg = load_bot_config()
            openai_key = (igcfg.get("openai_api_key") or "").strip()
            if openai_key and console.input(f'\n [bold {GREEN}]🤖 Analisis AI? (y/n)[/] ').strip().lower() in ('y', 'ya', 'yes'):
                with console.status("[bold yellow]🤖 Menganalisis AI...[/bold yellow]"):
                    ai_analyzer = InstagramAI(api_key=openai_key, base_url=igcfg.get("openai_base_url") or "https://router.bynara.id/v1", model=igcfg.get("openai_model") or "mimo-v2.5-pro-free")
                    ai_report = ai_analyzer.analyze_comments(comments)
                console.print(_Rule(style=BLUE)); console.print(_Markdown(ai_report)); console.print(_Rule(style=BLUE))
            if console.input(f' [bold {GREEN}]📂 Ekspor ke CSV? (y/n)[/] ').strip().lower() in ('y', 'ya', 'yes'):
                filepath = BotExporter.export_comments_csv(f"threads_{clean_post_id(url_or_id)}", comments)
                console.print(f"[bold {GREEN}]✓ Disimpan: {filepath}[/bold {GREEN}]")
        console.input(f'\n [dim]Tekan Enter...[/]'); self.ThreadsMenu()

    def _threads_keyword_search(self, toolkit):
        """Cari kata kunci di replies Threads."""
        url_or_id = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]URL/Post ID Threads[/] [{GREEN}]›[/] ').strip()
        if not url_or_id: return self.ThreadsMenu()
        try: limit = int(console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Limit (default 300)[/] [{GREEN}]›[/] ').strip() or "300")
        except ValueError: limit = 300
        comments, seen_ids, cursor, has_next = [], set(), None, True
        with console.status("[bold green]Mengambil balasan...[/bold green]") as status:
            try:
                while len(comments) < limit and has_next:
                    raw_data = toolkit.get_thread_replies(url_or_id, cursor)
                    new_found = False
                    for p in find_nested_keys(raw_data, "post"):
                        pid = p.get("id") or p.get("pk")
                        if not pid or pid in seen_ids: continue
                        seen_ids.add(pid)
                        user_info = p.get("user") or {}
                        username = user_info.get("username")
                        text = (p.get("caption") or {}).get("text") or p.get("text")
                        if username and text:
                            comments.append({"comment_id": str(pid), "username": username, "fullname": user_info.get("full_name") or "", "text": text})
                            new_found = True
                            if len(comments) >= limit: break
                    page_info = toolkit.extract_page_info(raw_data)
                    has_next = page_info.get("has_next_page", False); cursor = page_info.get("end_cursor")
                    status.update(f"[bold green]Mengambil... [{len(comments)}][/bold green]")
                    if not cursor or not new_found: break
                    time.sleep(1.0)
            except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]"); comments = []
        if not comments:
            console.print(f"[{MUTED}]Tidak ada balasan.[/{MUTED}]")
        else:
            console.print(f"[dim]✓ {len(comments)} balasan.[/dim]")
            while True:
                keyword = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Kata kunci pencarian[/] [{GREEN}]›[/] ').strip().lower()
                if not keyword: break
                matched = [c for c in comments if keyword in c['text'].lower()]
                if not matched:
                    console.print(f"[bold {RED}]❌ Tidak ada yang mengandung '{keyword}'.[/bold {RED}]")
                else:
                    table = Table(box=box.ROUNDED, border_style=BLUE, title=f"[bold {BLUE}]'{keyword}' ({len(matched)}/{len(comments)})[/bold {BLUE}]")
                    table.add_column("No", justify="center"); table.add_column("Username", style="bold yellow"); table.add_column("Balasan")
                    for idx, c in enumerate(matched, 1):
                        highlighted = re.sub(f"({re.escape(keyword)})", r"[bold green]\1[/bold green]", escape(c['text']), flags=re.IGNORECASE)
                        table.add_row(str(idx), f"@{c['username']}", highlighted)
                    console.print(table)
                    if console.input(f'\n [bold {GREEN}]📂 Ekspor? (y/n)[/] ').strip().lower() in ('y', 'ya', 'yes'):
                        safe_kw = "".join([ch if ch.isalnum() else "_" for ch in keyword])
                        filepath = BotExporter.export_comments_csv(f"threads_{clean_post_id(url_or_id)}_filter_{safe_kw}", matched)
                        console.print(f"[bold {GREEN}]✓ Disimpan: {filepath}[/bold {GREEN}]")
                if console.input(f'\n [bold {BLUE}]🔍 Cari lagi? (y/n)[/] [{GREEN}]›[/] ').strip().lower() not in ('y', 'ya', 'yes'): break
        console.input(f'\n [dim]Tekan Enter...[/]'); self.ThreadsMenu()

    # ════════════════════════════════════════════════════════════════════════
    # 04 — SETTINGS
    # ════════════════════════════════════════════════════════════════════════
    def SettingsMenu(self):
        self.Clear(); self.Logos()
        ig_cookie_status = f"[bold {GREEN}]● AKTIF[/bold {GREEN}]" if os.path.isfile(".kukis.log") else f"[bold {RED}]● KOSONG[/bold {RED}]"
        try:
            threads_config = load_threads_config()
            threads_status = f"[bold {GREEN}]● AKTIF[/bold {GREEN}]" if threads_config.get("threads_cookie") else f"[bold {RED}]● KOSONG[/bold {RED}]"
        except Exception:
            threads_status = f"[bold {RED}]● ERROR[/bold {RED}]"

        status_table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {BLUE}", title=f"[bold {BLUE}]🔐 CREDENTIAL STATUS[/bold {BLUE}]", padding=(0, 1))
        status_table.add_column("Platform", style=WHITE, width=15); status_table.add_column("Status", justify="center", width=12); status_table.add_column("Keterangan")
        status_table.add_row("🍊 Instagram", ig_cookie_status, ".kukis.log" if os.path.isfile(".kukis.log") else f"[{RED}]Belum diset[/{RED}]")
        status_table.add_row("🧵 Threads", threads_status, "threads_config.json")
        console.print(Panel(status_table, title=f"[bold {BLUE}] SETTINGS [/]", border_style=BLUE))

        console.print(self._menu_table([
            ("01", "Set Cookie Instagram"),     ("05", "Set OpenAI API Key"),
            ("02", "Set Cookie Threads"),       ("06", "Set LSD Token"),
            ("03", "Set fb_dtsg Token"),        ("07", "Panduan Rate Limit"),
            ("04", "Update Static Params"),     ("00", "Kembali"),
        ]))
        opt = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Pilih[/] [{GREEN}]›[/] ').lower()

        if opt in ('1', '01'):
            val = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Cookie Instagram[/] [{GREEN}]›[/] ').strip()
            if val:
                try:
                    parsed = _ck(val)
                    clean_cookie = '; '.join([f'{k}={v}' for k, v in parsed.items()])
                    uid_match = re.search(r'ds_user_id=(\d+)', str(val))
                    full_name = f'User_{uid_match.group(1)}' if uid_match else 'User_Unknown'
                    with open('.kukis.log', 'w', encoding='utf-8') as f: f.write(f'{clean_cookie}<=>{full_name}')
                    os.chmod('.kukis.log', 0o600)
                    console.print(f"[bold {GREEN}]✓ Cookie Instagram berhasil diupdate![/bold {GREEN}]")
                except Exception as e: console.print(f"[bold {RED}]❌ Gagal: {e}[/bold {RED}]")
                time.sleep(1.5)
            self.SettingsMenu()

        elif opt in ('2', '02'):
            val = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]Cookie Threads[/] [{GREEN}]›[/] ').strip()
            if val:
                try: tcfg = load_threads_config()
                except Exception: tcfg = {}
                tcfg["threads_cookie"] = val
                uid_match = re.search(r"ds_user_id=(\d+)", val)
                if uid_match:
                    uid = uid_match.group(1)
                    admin_threads = tcfg.get("admin_threads_cookies", [])
                    exists = False
                    for c in admin_threads:
                        if c.get("uid") == uid: c["cookie"] = val; exists = True; break
                    if not exists: admin_threads.append({"cookie": val, "uid": uid, "lsd": "", "fb_dtsg": ""})
                    tcfg["admin_threads_cookies"] = admin_threads
                save_threads_config(tcfg)
                console.print(f"[bold {GREEN}]✓ Cookie Threads berhasil diupdate.[/bold {GREEN}]")
                time.sleep(1.2)
            self.SettingsMenu()

        elif opt in ('3', '03'):
            console.print(f'\n [bold {YELLOW}]⚠️  fb_dtsg auto keisi dari menu Cek Profil Threads.[/bold {YELLOW}]')
            val = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]fb_dtsg Token (Enter skip)[/] [{GREEN}]›[/] ').strip()
            if val:
                try: tcfg = load_threads_config()
                except Exception: tcfg = {}
                tcfg["fb_dtsg"] = val
                save_threads_config(tcfg)
                console.print(f"[bold {GREEN}]✓ fb_dtsg berhasil diupdate.[/bold {GREEN}]")
                time.sleep(1.2)
            self.SettingsMenu()

        elif opt in ('4', '04'):
            console.print(Panel(
                f"[{WHITE}]Update nilai static params Instagram.\n"
                f"Cari dari DevTools browser → Network → request ke instagram.com\n\n"
                f"[bold {YELLOW}]Field yang bisa diupdate:[/bold {YELLOW}]\n"
                f"• x_bloks_version_id  (header: X-Bloks-Version-Id)\n"
                f"• x_instagram_ajax    (header: X-Instagram-Ajax)\n"
                f"• doc_id_like         (body: doc_id saat request like)\n"
                f"• doc_id_comments     (body: doc_id saat request comments)\n"
                f"• doc_id_post         (body: doc_id saat request post info)\n"
                f"• doc_id_login        (body: doc_id saat request login)[/]",
                title=f"[bold {BLUE}] UPDATE STATIC PARAMS [/]", border_style=BLUE
            ))
            console.print(f"[dim]Edit langsung di: [bold]core/config.py[/bold] bagian STATIC_PARAMS[/dim]")
            console.input(f'\n [dim]Tekan Enter untuk kembali...[/]')
            self.SettingsMenu()

        elif opt in ('5', '05'):
            base_url = console.input(f'\n [bold {BLUE}]❯[/] [{WHITE}]OpenAI Base URL (Enter default)[/] [{GREEN}]›[/] ').strip()
            api_key = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]OpenAI API Key[/] [{GREEN}]›[/] ').strip()
            model = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]Model (Enter default: mimo-v2.5-pro-free)[/] [{GREEN}]›[/] ').strip()
            if base_url or api_key or model:
                try: igcfg = load_bot_config()
                except Exception: igcfg = {}
                if base_url: igcfg["openai_base_url"] = base_url
                if api_key: igcfg["openai_api_key"] = api_key
                if model: igcfg["openai_model"] = model
                save_bot_config(igcfg)
                parts = []
                if base_url: parts.append(f"Base URL: {base_url}")
                if model: parts.append(f"Model: {model}")
                if api_key: parts.append(f"API Key: {'*' * 12}{api_key[-4:]}")
                console.print(f"[bold {GREEN}]✓ OpenAI diupdate: {', '.join(parts)}[/bold {GREEN}]")
                time.sleep(1.2)
            self.SettingsMenu()

        elif opt in ('6', '06'):
            console.print(f'\n [bold {YELLOW}]⚠️  LSD Token auto keisi dari menu Cek Profil Threads.[/bold {YELLOW}]')
            val = console.input(f' [bold {BLUE}]❯[/] [{WHITE}]LSD Token (Enter skip)[/] [{GREEN}]›[/] ').strip()
            if val:
                try: tcfg = load_threads_config()
                except Exception: tcfg = {}
                tcfg["x_fb_lsd"] = val
                save_threads_config(tcfg)
                console.print(f"[bold {GREEN}]✓ LSD Token diupdate.[/bold {GREEN}]")
                time.sleep(1.2)
            self.SettingsMenu()

        elif opt in ('7', '07'):
            self.GuideMenu()
        elif opt in ('0', '00', 'back', 'kembali'):
            self.Menu()
        else:
            self.SettingsMenu()

    def GuideMenu(self):
        self.Clear(); self.Logos()
        guide_text = (
            f"[bold {YELLOW}]💡 PANDUAN MENGATASI RATE LIMIT (PEMBATASAN META)[/bold {YELLOW}]\n\n"
            f"Jika saat scraping Anda menjumpai kegagalan, data tidak muncul, atau program mandek, "
            f"itu tandanya Anda terkena rate limit oleh Instagram atau Threads.\n\n"
            f"[bold {GREEN}]Langkah-Langkah Mengatasi:[/bold {GREEN}]\n"
            f"1. [bold]Nyalakan Mode Pesawat[/bold] selama [bold]5–10 detik[/bold] — rotasi IP seluler.\n"
            f"2. [bold]Siapkan Akun Tumbal[/bold] — hindari blokir akun utama.\n"
            f"3. [bold]Perbarui Cookie di Settings[/bold] dengan cookie akun tumbal baru.\n"
            f"4. Jalankan kembali — IG akan menganggap request berasal dari user baru.\n\n"
            f"[bold {BLUE}]Pro Tips:[/bold {BLUE}]\n"
            f"• Jangan scrape lebih dari 100-300 data per sesi.\n"
            f"• Jika doc_id berubah, update di [bold]core/config.py[/bold] bagian STATIC_PARAMS.\n"
            f"• Selalu pakai akun tumbal, jangan akun utama."
        )
        console.print(Panel(guide_text, title=f"[bold {BLUE}] 📖 PANDUAN PENGGUNA [/]", border_style=BLUE))
        console.input(f'\n [dim]Tekan Enter untuk kembali ke Settings...[/]')
        self.SettingsMenu()


# ════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    try:
        Brute().Menu()
    except (EOFError, KeyboardInterrupt):
        Console().print(f"\n {P2}[{H2}*{P2}] Program dihentikan.")
