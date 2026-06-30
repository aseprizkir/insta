import re, requests, json, random, time, urllib, uuid, hashlib, os, threading
from utils.helper import _ck, _search
from core.config import STATIC_PARAMS, IG_UA

# Cache global untuk dynamic params (TTL 10 menit per cookie)
_param_cache: dict = {}   # key: ds_user_id, value: (timestamp, params_dict)
_cache_lock = threading.Lock()
_CACHE_TTL = 600  # detik


def sync_params(cookie: str, force: bool = False) -> dict:
    """
    Ambil dynamic params Instagram dari homepage secara otomatis.
    Hasil di-cache selama 10 menit per akun supaya tidak spam request.

    Returns dict berisi:
        lsd, fb_dtsg, actor_id, __rev, __spin_r, __spin_t,
        jazoest, csrftoken  — semua diambil fresh dari IG.
    """
    uid = re.search(r'ds_user_id=(\d+)', str(cookie))
    cache_key = uid.group(1) if uid else 'anon'

    with _cache_lock:
        cached = _param_cache.get(cache_key)
        if not force and cached:
            ts, params = cached
            if time.time() - ts < _CACHE_TTL:
                return params

    try:
        r = requests.get(
            'https://www.instagram.com/',
            cookies=_ck(cookie),
            headers={
                'user-agent': IG_UA,
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'sec-fetch-site': 'none',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-dest': 'document',
                'upgrade-insecure-requests': '1',
            },
            timeout=15,
            allow_redirects=False,
        )
        html = r.text
        # Ambil csrftoken dari cookie response (lebih reliable dari HTML)
        csrf = r.cookies.get('csrftoken') or _ck(cookie).get('csrftoken', '')

        params = {
            'lsd':       _search(r'"LSD",\[\],{"token":"(.*?)"', html),
            'fb_dtsg':   _search(r'"DTSGInitialData",\[\],{"token":"(.*?)"}', html),
            'actor_id':  _search(r'{"actorID":"(\d+)"', html) or cache_key,
            '__rev':     _search(r'{"consistency":{"rev":(\d+)}', html),
            '__spin_r':  _search(r'"__spin_r":(\d+)', html),
            '__spin_t':  _search(r'"__spin_t":(\d+)', html),
            '__hsi':     _search(r'"hsi":"(\d+)"', html),
            'jazoest':   _search(r'jazoest=(\d+)', html),
            'csrftoken': csrf,
            # Sertakan juga static params supaya caller cukup pakai 1 dict
            **STATIC_PARAMS,
        }
    except Exception:
        # Fallback: kembalikan hanya static params + csrf dari cookie
        params = {
            'lsd': '', 'fb_dtsg': '', 'actor_id': cache_key,
            '__rev': '', '__spin_r': '', '__spin_t': '',
            '__hsi': '', 'jazoest': '',
            'csrftoken': _ck(cookie).get('csrftoken', ''),
            **STATIC_PARAMS,
        }

    with _cache_lock:
        _param_cache[cache_key] = (time.time(), params)
    return params


class Require:
    """
    Class untuk menangani kebutuhan API, parsing data,
    dan manipulasi request Instagram.
    """
    def __init__(self):
        self.info, self.ex = {}, {}

    @staticmethod
    def sync_params(cookie: str, force: bool = False) -> dict:
        """Shortcut akses sync_params dari instance Require."""
        return sync_params(cookie, force=force)

    def data_graph(self, xxx):
        """Mengekstrak parameter wajib untuk request GraphQL Instagram."""
        data = {
            'av': _search(r'{"actorID":"(\d+)"', xxx),
            '__d': 'www',
            '__user': '0',
            '__a': '1',
            '__req': 'h',
            '__hs': _search('"haste_session":"(.*?)"', xxx),
            'dpr': '1',
            '__ccg': 'GOOD',
            '__rev': _search(r'{"consistency":{"rev":(\d+)}', xxx),
            '__s': '',
            '__hsi': _search(r'"hsi":"(\d+)"', xxx),
            '__dyn': '',
            '__csr': '',
            '__hsdp': '',
            '__hblp': '',
            '__sjsp': '',
            '__comet_req': _search(r'__comet_req=(\d+)', xxx) or '7',
            'fb_dtsg': _search(r'"DTSGInitialData",\[\],{"token":"(.*?)"}', xxx),
            'jazoest': _search(r'jazoest=(\d+)', xxx),
            'lsd': _search(r'"LSD",\[\],{"token":"(.*?)"', xxx),
            '__spin_r': _search(r'"__spin_r":(\d+)', xxx),
            '__spin_b': 'trunk',
            '__spin_t': _search(r'"__spin_t":(\d+)', xxx),
            '__crn': 'comet.igweb.PolarisFeedRoute',
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'PolarisPostCommentsContainerQuery',
            'server_timestamps': 'true',
            # doc_id terbaru untuk comments (update 2026)
            'doc_id': '26297736713236852'
        }
        return data

    def headers_graph(self, xxx):
        """Membentuk header untuk request GraphQL."""
        headers = {
            'x-fb-friendly-name': 'PolarisPostCommentsContainerQuery',
            # App ID resmi Instagram Web (dari request terbaru semua.txt)
            'x-ig-app-id': '936619743392459',
            'x-asbd-id': '359341',
            'x-bloks-version-id': '879ff742a426fe5ee1b386f4314ce0f9794746e0577a018370f672c73bf9e068',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'content-type': 'application/x-www-form-urlencoded',
            'x-fb-lsd': _search(r'"LSD",\[\],{"token":"(.*?)"', xxx),
            'accept': '*/*',
            'origin': 'https://www.instagram.com',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
        }
        return headers

    def ClientId(self, xxx):
        """Mengekstrak Client ID dari HTML response."""
        try:
            Client = _search('{"clientID":"(.*?)"}', xxx)
            return Client
        except AttributeError:
            return ''
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            return self.ClientId(xxx)

    def AccountId(self, xxx):
        """Mengekstrak Account ID (UID) dari HTML response."""
        try:
            Userid = _search(r'{"actorID":"(\d+)"', xxx)
            return Userid
        except AttributeError:
            return ''
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            return self.AccountId(xxx)

    def GetRespon(self, url, cok):
        """Mengambil response HTML dari URL."""
        try:
            req = requests.get(url, cookies=_ck(cok)).text
            return req
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            return self.GetRespon(url, cok)

    def PostLike(self, cookie, media_id):
        """Melakukan aksi Like pada postingan melalui 3 metode fallback.
        
        Auto-sync dynamic params dari IG (cached 10 menit).
        Kalau response mendeteksi stale params / rate-limit → force-refresh otomatis.
        """
        try:
            from rich.console import Console
            console = Console()
            parsed_cookie = _ck(cookie)
            failures = []

            def succeeded(response):
                try:
                    payload = response.json()
                except ValueError:
                    return False
                return response.ok and payload.get('status') == 'ok'

            def record_failure(name, response):
                try:
                    payload = response.json()
                    reason = payload.get('message') or payload.get('error_type') or payload.get('status')
                except ValueError:
                    reason = response.headers.get('location') or response.text[:80] or 'respons bukan JSON'
                failures.append(f'{name}: HTTP {response.status_code}, {reason or "alasan tidak tersedia"}')

            def _needs_resync(resp_text):
                """Deteksi apakah params sudah stale / IG minta refresh."""
                triggers = ('spam', 'feedback_required', 'rate_limit_error',
                            'CSRFTokenInvalid', 'sentry_block', 'challenge_required')
                return any(t in resp_text for t in triggers)

            # Ambil dynamic params (dari cache atau fresh fetch)
            p = sync_params(cookie)

            # ── 1. GraphQL Mutation (RECOMMENDED 2026) ──────────────────
            for attempt in range(2):  # attempt 0: cached, attempt 1: force-refresh
                if attempt == 1:
                    p = sync_params(cookie, force=True)  # refresh kalau attempt 0 gagal

                head_graph = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'user-agent': IG_UA,
                    'x-csrftoken': p['csrftoken'],
                    'x-fb-lsd': p['lsd'],
                    'x-fb-friendly-name': 'usePolarisLikeMediaXIGLikeMutation',
                    'x-ig-app-id': p['x_ig_app_id'],
                    'x-asbd-id': p['x_asbd_id'],
                    'x-ig-max-touch-points': '0',
                    'accept': '*/*',
                    'origin': 'https://www.instagram.com',
                    'referer': 'https://www.instagram.com/',
                    'sec-fetch-site': 'same-origin',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-dest': 'empty',
                }
                data_graph = {
                    'av': p['actor_id'],
                    '__d': 'www', '__user': '0', '__a': '1', '__req': '1c',
                    '__ccg': 'GOOD', '__rev': p['__rev'], '__s': '',
                    '__hsi': p['__hsi'], '__dyn': '', '__csr': '',
                    '__comet_req': '7',
                    'fb_dtsg': p['fb_dtsg'],
                    'jazoest': p['jazoest'],
                    'lsd': p['lsd'],
                    '__spin_r': p['__spin_r'], '__spin_b': 'trunk',
                    '__spin_t': p['__spin_t'],
                    '__crn': 'comet.igweb.PolarisFeedRoute',
                    'fb_api_caller_class': 'RelayModern',
                    'fb_api_req_friendly_name': 'usePolarisLikeMediaXIGLikeMutation',
                    'server_timestamps': 'true',
                    'variables': json.dumps({"input": {
                        "actor_id": p['actor_id'],
                        "client_mutation_id": "1",
                        "container_module": "feed_timeline",
                        "media_id": media_id
                    }}),
                    'doc_id': p['doc_id_like'],
                }
                res_graph = requests.post(
                    'https://www.instagram.com/api/graphql',
                    data=data_graph,
                    headers=head_graph,
                    cookies=parsed_cookie,
                    timeout=15,
                    allow_redirects=False,
                )
                try:
                    if res_graph.ok and res_graph.json().get('data'):
                        return True
                except ValueError:
                    pass

                # Kalau stale params terdeteksi → loop ke attempt 1 (force-refresh)
                if _needs_resync(res_graph.text) and attempt == 0:
                    continue
                break  # tidak perlu retry lagi

            record_failure('graphql', res_graph)

            # ── 2. Fallback: AJAX Web Like ───────────────────────────────
            head_ajax = {
                'accept': '*/*',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://www.instagram.com',
                'referer': 'https://www.instagram.com/',
                'user-agent': IG_UA,
                'x-asbd-id': p['x_asbd_id'],
                'x-csrftoken': p['csrftoken'],
                'x-ig-app-id': p['x_ig_app_id'],
                'x-instagram-ajax': p['x_instagram_ajax'],
                'x-ig-www-claim': '0',
                'x-requested-with': 'XMLHttpRequest',
            }
            res_ajax = requests.post(
                f'https://www.instagram.com/api/v1/web/likes/{media_id}/like/',
                headers=head_ajax,
                cookies=parsed_cookie,
                timeout=15,
                allow_redirects=False,
            )
            if succeeded(res_ajax):
                return True
            record_failure('web', res_ajax)

            # ── 3. Fallback: Mobile API ──────────────────────────────────
            head_v1 = {
                'user-agent': 'Instagram 243.1.0.14.111 (iPhone13,3; iOS 15_5; en_US; en-US; scale=3.00; 1170x2532; 382468104) NW/3',
                'x-csrftoken': p['csrftoken'],
                'x-ig-app-id': '1217981644879628',
            }
            res_v1 = requests.post(
                f'https://i.instagram.com/api/v1/media/{media_id}/like/',
                headers=head_v1,
                cookies=parsed_cookie,
                timeout=15,
                allow_redirects=False,
            )
            if succeeded(res_v1):
                return True
            record_failure('mobile', res_v1)

            console.print(f" [#FF0000]![#FFFFFF] {' | '.join(failures)}")
            return False
        except Exception as e:
            try:
                Console().print(f" [#FF0000]![#FFFFFF] Like error: {type(e).__name__}: {e}")
            except Exception:
                pass
            return False

    def Password(self, fullname, strategy='3'):
        """Menghasilkan kombinasi password berdasarkan strategi yang dipilih."""
        self.one = []
        # Split fullname (biasanya isinya "username nama_lengkap")
        parts = fullname.split(' ')
        username = parts[0].lower()
        real_name = ' '.join(parts[1:]).lower()
        
        # Pola angka/tambahan umum
        patterns = [
            '', '123', '1234', '12345', '321', '123456', '12345678',
            '01', '02', '03', '04', '05', '07', '08', '09', '10',
            '2023', '2024', '2025', '2026'
        ]

        # Strategi 1: Hanya Username + Angka
        if strategy == '1':
            for p in patterns:
                self.one.append(username + p)
                if username + p: self.one.append((username + p).capitalize())

        # Strategi 2: Hanya Password Umum (Kredensial Lemah Global)
        elif strategy == '2':
            global_weak = [
                'sayang', 'sayang123', 'sayang12345', 'bismillah', 'bismillah123',
                'anjing', 'anjing123', 'doraemon', 'doraemon123', 'password', 
                'password123', 'indonesia', 'indonesia123', 'asep1234', 'asep12345'
            ]
            for gw in global_weak:
                self.one.append(gw)
                self.one.append(gw.capitalize())

        # Strategi 3: Sempurna (Nama + Username + Angka + Umum)
        else:
            # Dari Username
            for p in patterns:
                self.one.append(username + p)
                self.one.append((username + p).capitalize())
            
            # Dari Bagian Nama
            for n in real_name.split(' '):
                if len(n) >= 3:
                    for p in patterns:
                        self.one.append(n + p)
                        self.one.append((n + p).capitalize())
            
            # Password Umum
            global_weak = ['sayang123', 'bismillah', 'anjing123', 'password123', 'indonesia123', 'asep1234']
            for gw in global_weak:
                self.one.append(gw)
                self.one.append(gw.capitalize())
            
        return list(set(self.one)) # Hilangkan duplikat

    def Signature(self, data, body='SIGNATURE'):
        """Membuat signature untuk request login."""
        return 'signed_body={}.{}&ig_sig_key_version=4'.format(body, urllib.parse.quote_plus(data))

    def DeviceId(self):
        """Membuat Device ID Android acak."""
        return 'android-%s' % (self.uuid_(True)[:16])

    def uuid_(self, abcd=None, zd=None):
        """Fungsi pembantu pembuatan UUID."""
        if zd is not None:
            m = hashlib.md5()
            m.update(zd.encode('utf-8'))
            i = uuid.UUID(m.hexdigest())
        else:
            i = uuid.uuid4()
            if abcd:
                return str(i.hex)
        return str(i)

    def adid(self, username):
        """Membuat ADID (Advertising ID) berdasarkan username."""
        sha2 = hashlib.sha256()
        sha2.update(username.encode('utf-8'))
        abcd = sha2.hexdigest()
        return self.uuid_(False, abcd)

    def guid(self):
        """Membuat GUID acak."""
        return self.uuid_(False)

    def poid(self):
        """Membuat POID acak."""
        return self.uuid_(False, self.guid())

    def vers(self):
        """Mendapatkan versi aplikasi Instagram acak."""
        igv = ("100.0.0.17.129,100.0.0.17.129,100.0.0.17.129,100.0.0.17.129,100.0.0.17.129,100.0.0.17.129,79.0.0.21.101,78.0.0.11.104,77.0.0.20.113,76.0.0.15.395,75.0.0.23.99,74.0.0.21.99,73.0.0.22.185,72.0.0.21.98,71.0.0.18.102,70.0.0.22.98,69.0.0.30.95,68.0.0.11.99,67.0.0.25.100,66.0.0.11.101,65.0.0.12.86,64.0.0.14.96,63.0.0.17.94,62.0.0.19.93,61.0.0.19.86,60.1.0.17.79,59.0.0.23.76,58.0.0.12.73,57.0.0.9.80,56.0.0.13.78,55.0.0.12.79,54.0.0.14.82,53.0.0.13.84,52.0.0.8.83,51.0.0.20.85,50.1.0.43.119,271.1.0.21.84,131.0.0.23.11,130.0.0.31.12,128.0.0.26.12,126.0.0.25.12,125.0.0.20.12,124.0.0.17.47,123.0.0.21.11,122.0.0.29.23,120.0.0.29.11,119.0.0.33.14,118.0.0.28.12,117.0.0.28.12,115.0.0.26.11,114.0.0.38.12,113.0.0.39.12,112.0.0.29.12,111.1.0.25.15,110.0.0.16.11,109.0.0.18.12,108.0.0.23.11,107.0.0.27.12,106.0.0.24.11,105.0.0.18.11,104.0.0.21.11,103.1.0.15.11,102.0.0.20.11,101.0.0.15.12,100.0.0.17.12,99.0.0.32.182,98.0.0.15.119,97.0.0.32.119")
        igve = igv.split(",")
        versi = random.choice(igve)
        return versi

    def UserAgent(self):
        """Membuat User Agent Instagram Android acak."""
        rr = random.randint
        rc = random.choice
        ig_version = f"{rr(300, 320)}.0.0.{rr(10, 50)}.{rr(10, 100)}"
        
        device_models = [
            ("samsung", "SM-S918B", "2560x1440", "640dpi"),
            ("Xiaomi", "23127PN0CG", "1080x2400", "480dpi"),
            ("google", "Pixel 8 Pro", "1344x2992", "560dpi"),
            ("oppo", "CPH2527", "1080x2412", "480dpi"),
            ("vivo", "V2303", "1080x2400", "440dpi")
        ]
        brand, model, pxl, dpi = rc(device_models)
        basa = rc(['en_US', 'id_ID', 'en_GB', 'pt_BR', 'es_MX'])
        
        return f"Instagram {ig_version} Android ({rc(['30/11', '31/12', '32/13', '33/14'])}; {dpi}; {pxl}; {brand}; {model}; {model}; qcom; {basa}; {rr(400000000, 500000000)})"

    def socks(self, item = []):
        """Mendapatkan daftar proxy SOCKS5."""
        if hasattr(self, 'proxies') and len(self.proxies) != 0:
            return self.proxies
        if os.path.isfile('data/termux/internal/proxies.txt'):
           return open('data/termux/internal/proxies.txt','r').read().splitlines()
        else:
           try:
               resp = requests.get('https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt', timeout=10)
               for i in resp.text.splitlines():
                   if i.strip() and i not in item:
                      item.append(i)
               
               os.makedirs('data/termux/internal', exist_ok=True)
               with open('data/termux/internal/proxies.txt','w') as f:
                   f.write('\n'.join(item))
               return item
           except Exception:
               return []

    def UaGege(self):
        """Alias untuk UserAgent."""
        return self.UserAgent()

    def getUserAgentt(self):
        """Versi lain dari User Agent generator."""
        return self.UserAgent()

    def Convert_cooks(self, item):
        """Konversi format cookie."""
        try:
            sesid = 'sessionid=' + re.findall(r'sessionid=([^;]+)', str(item))[0]
            ds_id = 'ds_user_id=' + re.findall(r'ds_user_id=(\d+)', str(item))[0]
            csrft = 'csrftoken=' + re.findall('csrftoken=(.*?);', str(item))[0]
            donez = '%s; %s; %s; ig_nrcb=1; dpr=2;' % (csrft, ds_id, sesid)
        except Exception:
            donez = 'cookies tidak di temukan, error saat convert'
        return donez
