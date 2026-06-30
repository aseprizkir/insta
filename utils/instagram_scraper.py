import os
import re
import time
import random
import json
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor as executor
from core.api import Require
from utils.helper import _ck, _search, _shortcode_to_id

class InstagramScraper:
    def __init__(self):
        # User-Agent Windows Chrome 146 sesuai request terbaru (semua.txt)
        self.xyz = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        }
        self.head = {
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 243.1.0.14.111 (iPhone13,3; iOS 15_5; en_US; en-US; scale=3.00; 1170x2532; 382468104) NW/3"
        }
        self.param = {'count': '200', 'search_surface': 'follow_list_page'}

    def _cookie_validation_error(self, cookie):
        parsed = _ck(cookie)
        missing = [name for name in ("ds_user_id", "sessionid") if not parsed.get(name)]
        if missing:
            return f"Cookie belum terautentikasi; field wajib tidak ada: {', '.join(missing)}"
        return None

    def _web_headers(self, cookie, referer="https://www.instagram.com/"):
        headers = self.xyz.copy()
        parsed = _ck(cookie)
        headers.update({
            "Accept": "*/*",
            "Referer": referer,
            "X-CSRFToken": parsed.get("csrftoken", ""),
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "X-Asbd-Id": "359341",
            "X-IG-Max-Touch-Points": "0",
            # X-Ig-Www-Claim dibutuhkan untuk endpoints followers/following (dari semua.txt)
            "X-Ig-Www-Claim": "0",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        })
        return headers

    def _response_summary(self, response):
        try:
            payload = response.json()
        except ValueError:
            return f"HTTP {response.status_code}, respons bukan JSON"
        reason = payload.get("message") or payload.get("status") or payload.get("error_type")
        keys = ", ".join(sorted(payload.keys())[:6]) or "kosong"
        return f"HTTP {response.status_code}, alasan={reason or 'tidak tersedia'}, keys={keys}"

    def _validate_web_session(self, cookie, uid):
        headers = self.xyz.copy()
        headers.update({
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": _ck(cookie).get("csrftoken", ""),
            "Accept": "*/*",
            "Referer": "https://www.instagram.com/",
        })
        endpoints = (
            "https://www.instagram.com/api/v1/accounts/current_user/?edit=true",
            f"https://www.instagram.com/api/v1/users/{uid}/info/",
        )
        last_response = None
        for endpoint in endpoints:
            try:
                response = requests.get(
                    endpoint,
                    headers=headers,
                    cookies=_ck(cookie),
                    timeout=15,
                    allow_redirects=False,
                )
                last_response = response
                if response.status_code != 200:
                    continue
                user = response.json().get("user")
                response_uid = str((user or {}).get("pk") or (user or {}).get("pk_id") or (user or {}).get("id") or "")
                if user and (not response_uid or response_uid == uid):
                    return user, response
            except Exception:
                continue
        return None, last_response

    def validate_cookie(self, cookie):
        """Memvalidasi cookie Instagram dan mengembalikan info user."""
        err = self._cookie_validation_error(cookie)
        if err:
            raise Exception(err)
        uid_match = re.search(r"ds_user_id=(\d+)", str(cookie))
        if not uid_match:
            raise Exception("ds_user_id tidak ditemukan dalam cookie.")
        uid = uid_match.group(1)
        user_data, resp = self._validate_web_session(cookie, uid)
        if not user_data:
            summary = self._response_summary(resp) if resp is not None else "Tidak ada respon dari Instagram"
            raise Exception(f"Cookie tidak valid atau kedaluwarsa ({summary}).")
        return {
            "fullname": user_data.get("full_name", "Unknown"),
            "username": user_data.get("username", "unknown"),
            "followers": user_data.get("follower_count", 0),
            "following": user_data.get("following_count", 0),
            "uid": uid
        }

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
                try:
                    response = requests.get(
                        endpoint,
                        params=params,
                        headers=self._web_headers(cookie, referer),
                        cookies=_ck(cookie),
                        timeout=15,
                        allow_redirects=False,
                    )
                    last_response = response
                    if response.status_code == 429:
                        delay = (2 ** attempt) + random.uniform(0, 0.5)
                        time.sleep(delay)
                        attempt += 1
                        continue
                    if response.status_code != 200:
                        break
                    payload = response.json()
                    if "web_profile_info" in endpoint:
                        user = (payload.get("data") or {}).get("user")
                    else:
                        user = next(
                            (item.get("user") for item in payload.get("users", [])
                             if (item.get("user") or {}).get("username", "").lower() == username.lower()),
                            None,
                        )
                    if user:
                        return user, response
                    break
                except Exception:
                    break
        return None, last_response

    def _resolve_user_id(self, cookie, username):
        user, response = self._get_profile(cookie, username)
        if user:
            return str(user.get("id") or user.get("pk") or user.get("pk_id") or ""), user, response
        try:
            profile_response = requests.get(
                f"https://www.instagram.com/{username.lstrip('@')}/",
                headers=self._web_headers(cookie),
                cookies=_ck(cookie),
                timeout=15,
                allow_redirects=False,
            )
            user_id = (
                _search(r'"profile_id":"(\d+)"', profile_response.text)
                or _search(r'"user_id":"(\d+)"', profile_response.text)
                or _search(r'"id":"(\d+)","username":"' + re.escape(username.lstrip("@")) + r'"', profile_response.text)
            )
            if user_id:
                return user_id, user, profile_response
        except Exception:
            pass

        try:
            search_response = requests.get(
                "https://www.instagram.com/web/search/topsearch/",
                params={"query": username.lstrip("@")},
                headers=self._web_headers(cookie),
                cookies=_ck(cookie),
                timeout=15,
                allow_redirects=False,
            )
            search_payload = search_response.json()
            search_users = search_payload.get("users", []) or search_payload.get("accounts", [])
            match = next(
                ((item.get("user") or item) for item in search_users
                 if (item.get("user") or item).get("username", "").lower() == username.lstrip("@").lower()),
                None,
            )
            if match:
                return str(match.get("pk") or match.get("id") or ""), match, search_response
        except Exception:
            pass

        return "", None, None

    def scrape_profile(self, cookie, username):
        """Scrape profile info target."""
        username = username.strip().lstrip("@")
        user_id, user, response = self._resolve_user_id(cookie, username)
        
        if user_id:
            # Panggil endpoint info detail tambahan
            try:
                for domain in ("www.instagram.com", "i.instagram.com"):
                    info_response = requests.get(
                        f"https://{domain}/api/v1/users/{user_id}/info/",
                        headers=self._web_headers(cookie, f"https://www.instagram.com/{username}/"),
                        cookies=_ck(cookie),
                        timeout=15,
                        allow_redirects=False,
                    )
                    if info_response.status_code == 200:
                        detailed_user = info_response.json().get("user")
                        if detailed_user:
                            if user:
                                user.update(detailed_user)
                            else:
                                user = detailed_user
                            break
            except Exception:
                pass
        
        if not user:
            if response is not None:
                if response.status_code == 429:
                    raise Exception("Instagram membatasi request (429). Tunggu beberapa menit.")
                raise Exception(f"Profil gagal dibaca/privat: {self._response_summary(response)}")
            raise Exception("Profil tidak ditemukan atau gagal diakses.")
            
        followers = user.get('follower_count', user.get('edge_followed_by', {}).get('count', 0))
        following = user.get('following_count', user.get('edge_follow', {}).get('count', 0))
        posts = user.get('media_count', user.get('edge_owner_to_timeline_media', {}).get('count', 0))
        
        return {
            "name": user.get('full_name', ''),
            "username": user.get('username', username),
            "id": user.get('id') or user.get('pk') or user_id,
            "followers": followers,
            "following": following,
            "posts": posts,
            "is_private": "Ya" if user.get('is_private') else "Tidak",
            "is_verified": "Ya" if user.get('is_verified') else "Tidak",
            "bio": user.get('biography', '')
        }

    def scrape_connections(self, cookie, username, relation="followers", limit=200):
        """Scrape list followers atau following."""
        username = username.strip().lstrip("@")
        user_id, user, response = self._resolve_user_id(cookie, username)
        if not user_id:
            raise Exception("Target tidak ditemukan atau privat.")
            
        rows, seen, max_id, failure = [], set(), '', None
        page = 0
        
        while True:
            page += 1
            remaining = (limit - len(rows)) if limit else 200
            if remaining <= 0:
                break
                
            params = {'count': str(min(200, remaining)), 'search_surface': 'follow_list_page'}
            if max_id:
                params['max_id'] = max_id
                
            try:
                response = requests.get(
                    f"https://www.instagram.com/api/v1/friendships/{user_id}/{relation}/",
                    params=params,
                    headers=self._web_headers(cookie, f"https://www.instagram.com/{username}/"),
                    cookies=_ck(cookie),
                    timeout=20,
                    allow_redirects=False,
                )
                if response.status_code != 200:
                    failure = self._response_summary(response)
                    break
                payload = response.json()
                accounts = payload.get('users', [])
                if not accounts:
                    break
                    
                for acc in accounts:
                    uid = acc.get('pk') or acc.get('pk_id') or acc.get('id')
                    uname = acc.get('username')
                    fullname = acc.get('full_name')
                    if uid not in seen:
                        seen.add(uid)
                        rows.append({"id": str(uid), "username": uname, "fullname": fullname})
                        if limit and len(rows) >= limit:
                            break
                            
                max_id = payload.get('next_max_id')
                if not max_id:
                    break
                time.sleep(1.5)
            except Exception as e:
                failure = str(e)
                break
                
        if not rows and failure:
            raise Exception(f"Gagal mengambil daftar: {failure}")
        return rows

    def get_mediaid(self, url, cookie):
        url = self._normalize_post_url(url)
        if not url:
            return None

        parsed_cookie = _ck(cookie)
        csrftoken = parsed_cookie.get('csrftoken', '')

        # Cara 1: Coba GraphQL query PolarisPostRootQuery (request terbaru semua.txt)
        shortcode_match = re.search(r'/(?:p|reels|reel)/([A-Za-z0-9_-]+)', url)
        if shortcode_match:
            shortcode = shortcode_match.group(1)
            try:
                resp = requests.get(
                    'https://www.instagram.com/graphql/query',
                    params={
                        'doc_id': '27128499623469141',
                        'variables': json.dumps({
                            'shortcode': shortcode,
                            '__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider': False
                        })
                    },
                    headers={
                        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                        'x-ig-app-id': '936619743392459',
                        'x-csrftoken': csrftoken,
                        'x-root-field-name': 'xdt_api__v1__media__shortcode__web_info',
                        'x-fb-friendly-name': 'PolarisPostRootQuery',
                        'x-bloks-version-id': '879ff742a426fe5ee1b386f4314ce0f9794746e0577a018370f672c73bf9e068',
                        'x-asbd-id': '359341',
                        'accept': '*/*',
                        'referer': url,
                    },
                    cookies=parsed_cookie,
                    timeout=10,
                    allow_redirects=False,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    # Cari media_id di nested response
                    media = (
                        ((payload.get('data') or {}).get('xdt_api__v1__media__shortcode__web_info') or {})
                        .get('items', [{}])[0] if (payload.get('data') or {}).get('xdt_api__v1__media__shortcode__web_info') else {}
                    )
                    idm = str(media.get('id') or media.get('pk') or '')
                    if idm and idm.isdigit():
                        return idm
            except Exception:
                pass

        # Cara 2: Coba ambil dari HTML (fallback)
        headers = self.head.copy()
        headers.update({'cookie': cookie})
        try:
            req = requests.get(url, headers=headers, timeout=10).text
            idm = _search(r'\"media_id\":\"(\d+)\"', req)
            if idm:
                return idm
        except Exception:
            pass

        # Cara 3: Konversi shortcode (offline fallback)
        if shortcode_match:
            return _shortcode_to_id(shortcode_match.group(1))

        return None

    def scrape_comments(self, cookie, post_url, limit=100):
        """Scrape komentar dari link postingan."""
        media_id = self.get_mediaid(post_url, cookie)
        if not media_id:
            raise Exception("Media ID tidak ditemukan. Link postingan salah atau privat.")
            
        comments = []
        max_min = ''
        seen_ids = set()
        
        headers = self._web_headers(cookie, referer=post_url)
        
        while len(comments) < limit:
            print(f" \r[*] Sedang scraping comment mohon ditunggu [{len(comments)}]", end="", flush=True)
            try:
                response = requests.get(
                    f'https://www.instagram.com/api/v1/media/{media_id}/comments/?can_support_threading=true&permalink_enabled=false&min_id={max_min}',
                    headers=headers,
                    cookies=_ck(cookie),
                    timeout=15,
                    allow_redirects=False
                )
                if response.status_code != 200:
                    # Menambahkan debug sementara jika bukan 200, agar error lebih jelas
                    # print(f" Error: {response.status_code} - {response.text}")
                    break
                payload = response.json()
                raw_comments = payload.get('comments', [])
                if not raw_comments:
                    break
                    
                for c in raw_comments:
                    cid = c.get('pk') or c.get('id')
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        comments.append({
                            "comment_id": str(cid),
                            "username": c['user']['username'],
                            "fullname": c['user']['full_name'],
                            "text": c['text'],
                            "created_at": c.get('created_at_utc', '')
                        })
                        if len(comments) >= limit:
                            break
                max_min = payload.get('next_min_id')
                if not max_min:
                    break
                time.sleep(1.0)
            except Exception:
                break
                
        print(f" \r[✓] Scraping selesai! Total: {len(comments)} komentar.             ")
                
        return comments

    def scrape_post_status(self, cookie, post_url):
        media_id = self.get_mediaid(post_url, cookie)
        if not media_id:
            raise Exception("Media ID tidak ditemukan.")
            
        response = requests.get(
            f'https://www.instagram.com/api/v1/media/{media_id}/info/',
            headers=self._web_headers(cookie, post_url),
            cookies=_ck(cookie),
            timeout=15,
            allow_redirects=False,
        )
        try:
            item = response.json().get('items', [])[0]
            owner = item.get('user') or {}
            caption = (item.get('caption') or {}).get('text', '')
            shares = item.get('reshare_count') or item.get('share_count') or "Tidak tersedia"
            views = item.get('view_count') or item.get('play_count') or "Tidak tersedia"
            return {
                "owner": owner.get('username', 'unknown'),
                "likes": item.get('like_count', 0),
                "comments": item.get('comment_count', 0),
                "shares": shares,
                "views": views,
                "has_liked": "Ya" if item.get('has_liked') else "Tidak",
                "caption": caption
            }
        except Exception:
            raise Exception(f"Gagal membaca status postingan: {self._response_summary(response)}")

    def scrape_likers(self, cookie, post_url):
        media_id = self.get_mediaid(post_url, cookie)
        if not media_id:
            raise Exception("Media ID tidak ditemukan.")
            
        try:
            headers = self.head.copy()
            headers.update({
                'cookie': cookie,
                'x-csrftoken': _search('csrftoken=(.*?)(?:;|$)', cookie)
            })
            response = requests.get(
                f'https://www.instagram.com/api/v1/media/{media_id}/likers/',
                cookies=_ck(cookie),
                headers=headers,
                timeout=15
            )
            payload = response.json()
            users = payload.get('users', [])
            return [{"username": u['username'], "fullname": u['full_name'], "id": str(u.get('pk') or u.get('pk_id'))} for u in users]
        except Exception as e:
            raise Exception(f"Gagal mengambil likers: {str(e)}")

    def like_post(self, cookie, post_url):
        media_id = self.get_mediaid(post_url, cookie)
        if not media_id:
            raise Exception("Media ID tidak ditemukan.")
        return Require().PostLike(cookie, media_id)

    def _normalize_post_url(self, value):
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
