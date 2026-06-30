import os
import json
import requests
import html
import re
import time

CONFIG_FILE = "threads_config.json"

DEFAULT_CONFIG = {
    "threads_cookie": "",
    "x_ig_app_id": "238260118697367",  # Threads App ID
    "x_fb_lsd": "",                  # Token LSD
    "fb_dtsg": "",                   # Token fb_dtsg untuk mutation (Like/Follow)
    "doc_id_comments": "27459511047022916",  # Doc ID komentar (Updated)
    "doc_id_posts": "26868991796135032",     # Doc ID list post
    "doc_id_follow": "26234294899535416",    # Doc ID follow
    "doc_id_like": "24753372994365040",       # Doc ID like
    "doc_id_followers": "27390125367306731",  # Doc ID followers
    "doc_id_following": "26565260693147172",  # Doc ID following
    "doc_id_friendships": "27932967052970549",  # Doc ID follower/following counts
    "admin_threads_cookies": []
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception:
            save_config(config)
            return config
    if not os.path.exists(CONFIG_FILE):
        save_config(config)
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass

def clean_username(input_text):
    text = input_text.strip().lstrip("@")
    if "threads.net/" in text.lower():
        parts = text.split("threads.net/")
        if len(parts) > 1:
            text = parts[1]
    elif "threads.com/" in text.lower():
        parts = text.split("threads.com/")
        if len(parts) > 1:
            text = parts[1]
            
    text = text.split("?")[0].strip("/")
    text = text.split("/")[0]
    return text.lstrip("@")

def shortcode_to_media_id(shortcode):
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    media_id = 0
    for char in shortcode:
        media_id = (media_id * 64) + alphabet.index(char)
    return str(media_id)
def clean_post_id(url_or_id):
    text = url_or_id.strip()
    if "threads.net/" in text or "threads.com/" in text:
        for pattern in ["/post/", "/t/"]:
            if pattern in text:
                parts = text.split(pattern)
                if len(parts) > 1:
                    text = parts[1]
                    break
    text = text.split("?")[0].strip("/")
    text = text.split("/")[0]
    
    if "_" in text:
        parts = text.split("_")
        if parts[0].isdigit():
            text = parts[0]
            
    if not text.isdigit():
        try:
            text = shortcode_to_media_id(text)
        except Exception:
            pass
    return text

# Helper Parser Cerdas
def find_nested_keys(obj, key):
    """Mencari semua value dari key tertentu secara rekursif di JSON yang rumit"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            else:
                yield from find_nested_keys(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from find_nested_keys(item, key)

class ThreadsToolkit:
    def __init__(self, config):
        self.config = config

    @staticmethod
    def _checked_json(response):
        """Parse JSON GraphQL dengan pesan error yang lebih kebaca."""
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200:
            snippet = response.text[:180].replace("\n", " ")
            raise Exception(f"HTTP {response.status_code}: {snippet}")
        if "json" not in content_type and not response.text.lstrip().startswith("{"):
            snippet = response.text[:180].replace("\n", " ")
            raise Exception(f"Respons bukan JSON: {snippet}")
        try:
            return response.json()
        except ValueError as error:
            snippet = response.text[:180].replace("\n", " ")
            raise Exception(f"Gagal parse JSON: {error}; respons={snippet}")

    @staticmethod
    def extract_page_info(raw_data):
        """Cari page_info di response GraphQL Threads yang sering berubah nesting."""
        page_infos = [
            item
            for key in ("page_info", "pageInfo")
            for item in find_nested_keys(raw_data, key)
            if isinstance(item, dict)
        ]
        for info in page_infos:
            cursor = info.get("end_cursor") or info.get("endCursor") or info.get("cursor")
            if cursor:
                has_next = (
                    info.get("has_next_page")
                    if "has_next_page" in info
                    else info.get("hasNextPage")
                    if "hasNextPage" in info
                    else info.get("has_next")
                    if "has_next" in info
                    else True
                )
                return {
                    "has_next_page": bool(has_next),
                    "end_cursor": cursor,
                }
        return {"has_next_page": False, "end_cursor": None}

    @staticmethod
    def extract_users(raw_data):
        seen_usernames = set()
        users_list = []

        for key in ("node", "user"):
            for item in find_nested_keys(raw_data, key):
                if not isinstance(item, dict):
                    continue
                user = item.get("user") if isinstance(item.get("user"), dict) else item
                username = user.get("username")
                if not username or username in seen_usernames:
                    continue
                seen_usernames.add(username)
                users_list.append({
                    "id": str(user.get("pk") or user.get("id") or ""),
                    "username": username,
                    "fullname": user.get("full_name") or user.get("fullname") or "",
                    "is_verified": user.get("is_verified", False),
                })

        return users_list

    def _headers(self, referer="https://www.threads.com/"):
        csrf_match = re.search(r'csrftoken=([^;]+)', self.config.get("threads_cookie", ""))
        csrf_token = csrf_match.group(1) if csrf_match else "2ZUweJkd3BDgyIS3Bhfe7vQcaj3n73J6"
        
        return {
            "Host": "www.threads.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-IG-App-ID": self.config.get("x_ig_app_id", "238260118697367"),
            "X-FB-LSD": self.config.get("x_fb_lsd", ""),
            "X-Csrftoken": csrf_token,
            "X-Asbd-Id": "359341",
            "Cookie": self.config.get("threads_cookie", ""),
            "Origin": "https://www.threads.com",
            "Referer": referer,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }

    def scrape_profile_get(self, username):
        """Mengambil data profil lengkap & User ID menggunakan GET request HTML biasa"""
        cleaned_user = clean_username(username)
        url = f"https://www.threads.com/@{cleaned_user}"
        
        # Header lengkap meniru browser nyata
        headers = {
            "Host": "www.threads.com",
            "Cookie": self.config.get("threads_cookie", ""),
            "Cache-Control": "max-age=0",
            "Dpr": "1",
            "Viewport-Width": "1366",
            "Sec-Ch-Ua": '"Not-A.Brand";v="24", "Chromium";v="146"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Ch-Ua-Platform-Version": '""',
            "Sec-Ch-Ua-Model": '""',
            "Sec-Ch-Ua-Full-Version-List": "",
            "Sec-Ch-Prefers-Color-Scheme": "light",
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://www.threads.com/",
            "Priority": "u=0, i"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Gagal memuat profil target (HTTP {response.status_code})")
            
        html_content = response.text
        
        # 1. Ambil User ID dengan berbagai pola regex
        user_id = None
        patterns = [
            r'threads://user\?id=(\d+)',
            r'"user_id":"(\d+)"',
            r'"user_id"\s*:\s*"(\d+)"',
            r'"pk":"(\d+)"',
            r'"pk"\s*:\s*"(\d+)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                user_id = match.group(1)
                break
                
        # 2. Ambil Statistik dari Meta Description
        followers = "0"
        threads_count = "0"
        bio = ""
        
        desc_match = re.search(r'<meta name="description" content="([^"]+)"', html_content)
        if desc_match:
            desc_text = html.unescape(desc_match.group(1))
            fol_m = re.search(r'([\d\.]+[KMB]?) Followers', desc_text, re.IGNORECASE)
            thr_m = re.search(r'([\d\.]+[KMB]?) Threads', desc_text, re.IGNORECASE)
            
            if fol_m:
                followers = fol_m.group(1)
            if thr_m:
                threads_count = thr_m.group(1)
                
            bio_parts = desc_text.split("•")
            if len(bio_parts) > 2:
                bio = "•".join(bio_parts[2:]).strip()
            else:
                bio = desc_text
                
        # 3. Ambil Nama Lengkap
        fullname = cleaned_user
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        if title_match:
            title_text = html.unescape(title_match.group(1))
            if "(@"+cleaned_user+")" in title_text:
                fullname = title_text.split("(@")[0].strip()
            else:
                fullname = title_text
                
        # 4. Ambil LSD Token
        lsd_token = None
        lsd_match = re.search(r'\"LSD\"\,\s*\[\]\,\s*\{\"token\"\:\"([^\"]+)\"\}', html_content)
        if lsd_match:
            lsd_token = lsd_match.group(1)
        else:
            lsd_match_alt = re.search(r'\"LSD\"[^}]+token\"\:\"([^\"]+)\"', html_content)
            if lsd_match_alt:
                lsd_token = lsd_match_alt.group(1)
                
        # 5. Ambil fb_dtsg Token
        fb_dtsg_token = None
        dtsg_match = re.search(r'\"DTSGInitialData\"\,\s*\[\]\,\s*\{\"token\"\:\"([^\"]+)\"\}', html_content)
        if dtsg_match:
            fb_dtsg_token = dtsg_match.group(1)
        else:
            dtsg_match_alt = re.search(r'\"DTSGInitData\"\,\s*\[\]\,\s*\{\"token\"\:\"([^\"]+)\"\}', html_content)
            if dtsg_match_alt:
                fb_dtsg_token = dtsg_match_alt.group(1)
                
        if not user_id:
            raise Exception("Gagal mengekstrak User ID dari halaman profil. Pastikan cookie Threads terisi.")
            
        # 6. Ambil exact followers & following count jika ada cookie / token
        following = "0"
        if user_id:
            try:
                headers = self._headers()
                if lsd_token:
                    headers["X-FB-LSD"] = lsd_token
                csrf_match = re.search(r'csrftoken=([^;]+)', self.config.get("threads_cookie", ""))
                csrf_token = csrf_match.group(1) if csrf_match else "2ZUweJkd3BDgyIS3Bhfe7vQcaj3n73J6"
                headers["X-Csrftoken"] = csrf_token
                
                payload = {
                    "av": "17841414205490573",
                    "__user": "0",
                    "__a": "1",
                    "__req": "ak",
                    "fb_dtsg": fb_dtsg_token or self.config.get("fb_dtsg", ""),
                    "lsd": lsd_token or self.config.get("x_fb_lsd", ""),
                    "variables": json.dumps({"shouldFetchMutualsCount": False, "userID": str(user_id)}),
                    "doc_id": self.config.get("doc_id_friendships", "27932967052970549")
                }
                res = requests.post(
                    "https://www.threads.com/graphql/query",
                    headers=headers,
                    data=payload,
                    timeout=10
                )
                data_json = res.json()
                counts = data_json.get("data", {}).get("counts", {})
                if counts:
                    total_fol = counts.get('total_followers_count')
                    total_flg = counts.get('total_following_count')
                    if total_fol is not None:
                        followers = f"{total_fol:,}"
                    if total_flg is not None:
                        following = f"{total_flg:,}"
            except Exception:
                pass

        return {
            "username": cleaned_user,
            "user_id": user_id,
            "fullname": fullname,
            "followers": followers,
            "following": following,
            "threads_count": threads_count,
            "bio": bio,
            "lsd_token": lsd_token,
            "fb_dtsg_token": fb_dtsg_token
        }

    def get_profile_posts(self, user_id, limit=10):
        doc_id = self.config.get("doc_id_posts")
        variables = {
          "allow_page_info_for_lox_user": False,
          "first": int(limit),
          "userID": str(user_id),
          "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasProfileSelfReplyContextrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasDearAlgoConsumptionrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasEventBadgerelayprovider": False,
          "__relay_internal__pv__BarcelonaGenAIRepliesEnabledrelayprovider": False,
          "__relay_internal__pv__BarcelonaIsSearchDiscoveryEnabledrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasCommunitiesrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasGameScoreSharerelayprovider": True,
          "__relay_internal__pv__BarcelonaHasPublicViewCountCardrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasCommunityEntityCardrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasScorecardCommunityrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasSportTeamAllegianceCardrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasMusicrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasNewspaperLinkStylerelayprovider": False,
          "__relay_internal__pv__BarcelonaMessagingHasGroupChatsrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasPodcastTextFragmentsrelayprovider": False,
          "__relay_internal__pv__BarcelonaShouldFulfillLightboxQueryrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasMessagingrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasViewerRepliedrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasPrivateRepliesDeprecationrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasGhostPostEmojiActivationrelayprovider": False,
          "__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasDearAlgoWebProductionrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasWebFaviconsrelayprovider": False,
          "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasCommunityTopContributorsrelayprovider": False,
          "__relay_internal__pv__BarcelonaCanSeeSponsoredContentrelayprovider": False,
          "__relay_internal__pv__BarcelonaShouldShowFediverseM075Featuresrelayprovider": True,
          "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider": False
        }
        payload = {
            "av": "17841414205490573",
            "__user": "0",
            "__a": "1",
            "__req": "1",
            "fb_dtsg": self.config.get("fb_dtsg", ""),
            "lsd": self.config.get("x_fb_lsd", ""),
            "variables": json.dumps(variables),
            "doc_id": doc_id
        }
        
        response = requests.post(
            "https://www.threads.com/graphql/query",
            headers=self._headers(),
            data=payload,
            timeout=15
        )
        return self._checked_json(response)

    def get_thread_replies(self, thread_url_or_id, cursor=None):
        doc_id = self.config.get("doc_id_comments")
        post_id = clean_post_id(thread_url_or_id)
        
        variables = {
          "postID": str(post_id),
          "sort_order": "TOP",
          "__relay_internal__pv__BarcelonaHasPermalinkIndentationrelayprovider": False,
          "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasPostAuthorNotifControlsrelayprovider": True,
          "__relay_internal__pv__BarcelonaShouldShowFediverseM1Featuresrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasInlineReplyComposerrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasPermalinkPodcastCardrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasDearAlgoConsumptionrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasEventBadgerelayprovider": False,
          "__relay_internal__pv__BarcelonaGenAIRepliesEnabledrelayprovider": False,
          "__relay_internal__pv__BarcelonaIsSearchDiscoveryEnabledrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasCommunitiesrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasGameScoreSharerelayprovider": True,
          "__relay_internal__pv__BarcelonaHasPublicViewCountCardrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasCommunityEntityCardrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasScorecardCommunityrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasSportTeamAllegianceCardrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasMusicrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasNewspaperLinkStylerelayprovider": False,
          "__relay_internal__pv__BarcelonaMessagingHasGroupChatsrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasPodcastTextFragmentsrelayprovider": False,
          "__relay_internal__pv__BarcelonaShouldFulfillLightboxQueryrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasMessagingrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasViewerRepliedrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasPrivateRepliesDeprecationrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasGhostPostEmojiActivationrelayprovider": False,
          "__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider": True,
          "__relay_internal__pv__BarcelonaHasDearAlgoWebProductionrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasWebFaviconsrelayprovider": False,
          "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider": False,
          "__relay_internal__pv__BarcelonaHasCommunityTopContributorsrelayprovider": False,
          "__relay_internal__pv__BarcelonaCanSeeSponsoredContentrelayprovider": False,
          "__relay_internal__pv__BarcelonaShouldShowFediverseM075Featuresrelayprovider": False,
          "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider": False
        }
        
        if cursor:
            variables["after"] = cursor
        
        payload = {
            "av": "17841414205490573",
            "__user": "0",
            "__a": "1",
            "__req": "1",
            "fb_dtsg": self.config.get("fb_dtsg", ""),
            "lsd": self.config.get("x_fb_lsd", ""),
            "variables": json.dumps(variables),
            "doc_id": doc_id
        }

        response = requests.post(
            "https://www.threads.com/graphql/query",
            headers=self._headers(f"https://www.threads.com/t/{post_id}"),
            data=payload,
            timeout=15
        )
        return self._checked_json(response)

    def get_followers(self, user_id, limit=20, cursor=None):
        doc_id = self.config.get("doc_id_followers")
        variables = {
            "userID": str(user_id),
            "first": min(int(limit), 100),
            "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider": False,
            "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": True,
            "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider": False,
            "__relay_internal__pv__BarcelonaShouldShowFediverseListsrelayprovider": True
        }
        if cursor:
            variables["after"] = cursor
        payload = {
            "av": "17841414205490573",
            "__user": "0",
            "__a": "1",
            "__req": "1",
            "fb_dtsg": self.config.get("fb_dtsg", ""),
            "lsd": self.config.get("x_fb_lsd", ""),
            "variables": json.dumps(variables),
            "doc_id": doc_id
        }
        response = requests.post(
            "https://www.threads.com/graphql/query",
            headers=self._headers(),
            data=payload,
            timeout=15
        )
        return self._checked_json(response)

    def get_following(self, user_id, limit=20, cursor=None):
        doc_id = self.config.get("doc_id_following")
        variables = {
            "userID": str(user_id),
            "first": min(int(limit), 100),
            "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider": False,
            "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": True,
            "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider": False,
            "__relay_internal__pv__BarcelonaShouldShowFediverseListsrelayprovider": True
        }
        if cursor:
            variables["after"] = cursor
        payload = {
            "av": "17841414205490573",
            "__user": "0",
            "__a": "1",
            "__req": "1",
            "fb_dtsg": self.config.get("fb_dtsg", ""),
            "lsd": self.config.get("x_fb_lsd", ""),
            "variables": json.dumps(variables),
            "doc_id": doc_id
        }
        response = requests.post(
            "https://www.threads.com/graphql/query",
            headers=self._headers(),
            data=payload,
            timeout=15
        )
        return self._checked_json(response)

    def scrape_users(self, user_id, relation="followers", limit=20, status=None):
        """Ambil followers/following lintas halaman sampai limit terpenuhi."""
        rows = []
        seen = set()
        cursor = None
        has_next = True

        while len(rows) < int(limit) and has_next:
            remaining = int(limit) - len(rows)
            if relation == "followers":
                raw_data = self.get_followers(user_id, min(remaining, 100), cursor)
            else:
                raw_data = self.get_following(user_id, min(remaining, 100), cursor)

            new_users = 0
            for user in self.extract_users(raw_data):
                username = user["username"]
                if username in seen:
                    continue
                seen.add(username)
                rows.append(user)
                new_users += 1
                if len(rows) >= int(limit):
                    break

            page_info = self.extract_page_info(raw_data)
            cursor = page_info.get("end_cursor")
            has_next = bool(page_info.get("has_next_page") and cursor)

            if status:
                status.update(f"[bold green]Mengambil {relation} Threads... [{len(rows)}][/bold green]")
            if not cursor or new_users == 0:
                break
            time.sleep(1.0)

        return rows

    def follow_user(self, target_user_id):
        doc_id = self.config.get("doc_id_follow")
        fb_dtsg = self.config.get("fb_dtsg", "")
        lsd = self.config.get("x_fb_lsd", "")
        
        variables = {
            "target_user_id": str(target_user_id),
            "container_module": "ig_text_feed_profile"
        }
        payload = {
            "av": "17841414205490573",
            "__user": "0",
            "__a": "1",
            "__req": "2m",
            "fb_dtsg": fb_dtsg,
            "lsd": lsd,
            "fb_api_req_friendly_name": "useTHFollowMutationFollowMutation",
            "variables": json.dumps(variables),
            "doc_id": doc_id
        }
        response = requests.post(
            "https://www.threads.com/graphql/query",
            headers=self._headers(),
            data=payload,
            timeout=15
        )
        return self._checked_json(response)

    def like_post(self, media_id):
        doc_id = self.config.get("doc_id_like")
        fb_dtsg = self.config.get("fb_dtsg", "")
        lsd = self.config.get("x_fb_lsd", "")
        
        variables = {
            "mediaID": str(media_id),
            "requestData": {
                "container_module": "ig_text_feed_timeline"
            }
        }
        payload = {
            "av": "17841414205490573",
            "__user": "0",
            "__a": "1",
            "__req": "1u",
            "fb_dtsg": fb_dtsg,
            "lsd": lsd,
            "fb_api_req_friendly_name": "useTHLikeMutationLikeMutation",
            "variables": json.dumps(variables),
            "doc_id": doc_id
        }
        response = requests.post(
            "https://www.threads.com/graphql/query",
            headers=self._headers(),
            data=payload,
            timeout=15
        )
        return self._checked_json(response)

# Parser Khusus JSON GraphQL ke Output Bersih
def parse_and_print_posts(json_data):
    print("\n--- 📂 DAFTAR POSTINGAN PROFIL TARGET ---")
    threads = list(find_nested_keys(json_data, "thread_items"))
    if not threads:
        posts = list(find_nested_keys(json_data, "post"))
        if not posts:
            print("ℹ️ Tidak ada postingan publik yang terdeteksi.")
            return
        threads = [[{"post": p}] for p in posts]
        
    for idx, thread in enumerate(threads, 1):
        if not thread:
            continue
        post = thread[0].get("post", {})
        post_id = post.get("id") or post.get("pk")
        code = post.get("code")
        
        caption_obj = post.get("caption") or {}
        caption = caption_obj.get("text", "Tidak ada caption")
        
        likes = post.get("like_count") or 0
        replies = post.get("reply_count") or post.get("text_post_app_info", {}).get("direct_reply_count") or 0
        
        link = f"https://www.threads.net/t/{code}" if code else f"Post ID: {post_id}"
        
        print(f"\n📌 Post #{idx}:")
        print(f"🔗 Link: {link}")
        print(f"❤️ Likes: {likes:,} | 💬 Replies: {replies:,}")
        print(f"📝 Caption: {caption[:120]}{'...' if len(caption) > 120 else ''}")
        print("-" * 40)

def parse_and_print_replies(json_data):
    print("\n--- 💬 DAFTAR BALASAN/KOMENTAR THREAD ---")
    posts = list(find_nested_keys(json_data, "post"))
    
    seen_ids = set()
    count = 0
    
    for p in posts:
        pid = p.get("id") or p.get("pk")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        
        user_info = p.get("user") or {}
        username = user_info.get("username")
        
        caption_obj = p.get("caption") or {}
        text = caption_obj.get("text")
        
        if not text:
            text = p.get("text")
            
        if username and text:
            count += 1
            likes = p.get("like_count") or 0
            print(f"{count}. 👤 @{username}: {text}")
            if likes > 0:
                print(f"   └─ ❤️ {likes} likes")
                
    if count == 0:
        print("ℹ️ Tidak ada komentar/balasan publik yang terbaca.")

def parse_and_print_users(json_data, title="Daftar Pengguna"):
    print(f"\n--- 👥 {title.upper()} ---")
    seen_usernames = set()
    count = 0
    
    # Coba cari dari "node" (format followers/following baru)
    nodes = list(find_nested_keys(json_data, "node"))
    for node in nodes:
        if not isinstance(node, dict):
            continue
        username = node.get("username")
        fullname = node.get("full_name") or node.get("fullname") or "Tidak ada nama"
        is_verified = "🛡️ (Verified)" if node.get("is_verified") else ""
        
        if username and username not in seen_usernames:
            seen_usernames.add(username)
            count += 1
            print(f"{count}. 👤 @{username} ({fullname}) {is_verified}")
            
    if count == 0:
        # Fallback cari dari "user"
        users = list(find_nested_keys(json_data, "user"))
        for u in users:
            if not isinstance(u, dict):
                continue
            username = u.get("username")
            fullname = u.get("full_name") or u.get("fullname") or "Tidak ada nama"
            is_verified = "🛡️ (Verified)" if u.get("is_verified") else ""
            
            if username and username not in seen_usernames:
                seen_usernames.add(username)
                count += 1
                print(f"{count}. 👤 @{username} ({fullname}) {is_verified}")
                
    if count == 0:
        print("ℹ️ Tidak ada pengguna yang ditemukan.")

def configure_menu(config):
    while True:
        print("\n=== ⚙️ PENGATURAN CREDENTIALS & DOC IDS ===")
        print(f"1. Set Cookie Threads (Saat ini: {'Set' if config['threads_cookie'] else 'Kosong'})")
        print(f"2. Set LSD Token (Saat ini: {config['x_fb_lsd']})")
        print(f"3. Set fb_dtsg Token (Saat ini: {config['fb_dtsg']})")
        print(f"4. Set Doc ID Profil Posts (Saat ini: {config['doc_id_posts']})")
        print(f"5. Set Doc ID Komentar/Replies (Saat ini: {config['doc_id_comments']})")
        print(f"6. Set Doc ID Followers (Saat ini: {config['doc_id_followers']})")
        print(f"7. Set Doc ID Following (Saat ini: {config['doc_id_following']})")
        print(f"8. Set Doc ID Follow (Saat ini: {config['doc_id_follow']})")
        print(f"9. Set Doc ID Like (Saat ini: {config['doc_id_like']})")
        print("10. ⬅️ Kembali ke Menu Utama")
        
        opt = input("\nPilih opsi (1-10): ").strip()
        if opt == "1":
            config["threads_cookie"] = input("Masukkan Cookie: ").strip()
            save_config(config)
        elif opt == "2":
            config["x_fb_lsd"] = input("Masukkan LSD Token: ").strip()
            save_config(config)
        elif opt == "3":
            config["fb_dtsg"] = input("Masukkan fb_dtsg Token: ").strip()
            save_config(config)
        elif opt == "4":
            config["doc_id_posts"] = input("Masukkan Doc ID Posts: ").strip()
            save_config(config)
        elif opt == "5":
            config["doc_id_comments"] = input("Masukkan Doc ID Komentar: ").strip()
            save_config(config)
        elif opt == "6":
            config["doc_id_followers"] = input("Masukkan Doc ID Followers: ").strip()
            save_config(config)
        elif opt == "7":
            config["doc_id_following"] = input("Masukkan Doc ID Following: ").strip()
            save_config(config)
        elif opt == "8":
            config["doc_id_follow"] = input("Masukkan Doc ID Follow: ").strip()
            save_config(config)
        elif opt == "9":
            config["doc_id_like"] = input("Masukkan Doc ID Like: ").strip()
            save_config(config)
        elif opt == "10":
            break
        else:
            print("❌ Opsi tidak valid.")

def main():
    config = load_config()
    toolkit = ThreadsToolkit(config)
    
    while True:
        print("\n==========================================")
        print("   Threads API Toolkit v3.0 (Perfect) 🧵")
        print("==========================================")
        print("1. ⚙️ Konfigurasi Credentials & Doc IDs")
        print("2. 🔍 Cek Detail Profil Target (GET)")
        print("3. 📂 Ambil Postingan Profil (Thread List)")
        print("4. 💬 Ambil Komentar Postingan (Replies)")
        print("5. 👥 Ambil Followers (Pengikut) Target")
        print("6. 👤 Ambil Following (Diikuti) Target")
        print("7. 👤 Follow Akun Target")
        print("8. ❤️ Like Postingan Target")
        print("9. ❌ Keluar")
        
        choice = input("\nPilih Menu (1-9): ").strip()
        
        if choice == "1":
            configure_menu(config)
        elif choice == "2":
            target = input("Masukkan Username/URL Profil Threads: ").strip()
            print("⏳ Menghubungi profil Threads...")
            try:
                info = toolkit.scrape_profile_get(target)
                print("\n=== ✨ DETAIL PROFIL TARGET ✨ ===")
                print(f"👤 Nama Lengkap : {info['fullname']}")
                print(f"🏷️ Username     : @{info['username']}")
                print(f"🔑 User ID      : {info['user_id']}")
                print(f"📈 Followers    : {info['followers']}")
                print(f"📉 Following    : {info.get('following', '0')}")
                print(f"📝 Post Count   : {info['threads_count']}")
                print(f"📜 Bio          :\n{info['bio']}")
                print("==================================")
                
                # Auto update tokens if extracted
                updated = False
                if info.get("lsd_token") and info["lsd_token"] != config.get("x_fb_lsd"):
                    config["x_fb_lsd"] = info["lsd_token"]
                    updated = True
                    print(f"⚡ Auto-updated LSD Token: {info['lsd_token']}")
                if info.get("fb_dtsg_token") and info["fb_dtsg_token"] != config.get("fb_dtsg"):
                    config["fb_dtsg"] = info["fb_dtsg_token"]
                    updated = True
                    print(f"⚡ Auto-updated fb_dtsg Token: {info['fb_dtsg_token']}")
                if updated:
                    save_config(config)
                    toolkit.config = config
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "3":
            target = input("Masukkan Username/URL/User ID Target: ").strip()
            print("⏳ Menghubungi GraphQL Threads...")
            try:
                if not target.isdigit():
                    print("⏳ Mengonversi username ke ID...")
                    info = toolkit.scrape_profile_get(target)
                    target = info["user_id"]
                raw_data = toolkit.get_profile_posts(target)
                mode = input("Opsi Tampilan: [1] Rapi (Parsed) atau [2] Mentahan (Raw JSON)? [1/2]: ").strip()
                if mode == "2":
                    print(json.dumps(raw_data, indent=4))
                else:
                    parse_and_print_posts(raw_data)
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "4":
            target = input("Masukkan URL/Post ID Threads: ").strip()
            print("⏳ Menghubungi GraphQL Threads...")
            try:
                raw_data = toolkit.get_thread_replies(target)
                mode = input("Opsi Tampilan: [1] Rapi (Parsed) atau [2] Mentahan (Raw JSON)? [1/2]: ").strip()
                if mode == "2":
                    print(json.dumps(raw_data, indent=4))
                else:
                    parse_and_print_replies(raw_data)
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "5":
            target = input("Masukkan Username/URL/User ID Target: ").strip()
            limit = input("Limit Followers (default 20): ").strip()
            if not limit:
                limit = 20
            print("⏳ Menghubungi GraphQL Threads...")
            try:
                if not target.isdigit():
                    print("⏳ Mengonversi username ke ID...")
                    info = toolkit.scrape_profile_get(target)
                    target = info["user_id"]
                raw_data = toolkit.get_followers(target, limit)
                mode = input("Opsi Tampilan: [1] Rapi (Parsed) atau [2] Mentahan (Raw JSON)? [1/2]: ").strip()
                if mode == "2":
                    print(json.dumps(raw_data, indent=4))
                else:
                    parse_and_print_users(raw_data, "Followers")
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "6":
            target = input("Masukkan Username/URL/User ID Target: ").strip()
            limit = input("Limit Following (default 20): ").strip()
            if not limit:
                limit = 20
            print("⏳ Menghubungi GraphQL Threads...")
            try:
                if not target.isdigit():
                    print("⏳ Mengonversi username ke ID...")
                    info = toolkit.scrape_profile_get(target)
                    target = info["user_id"]
                raw_data = toolkit.get_following(target, limit)
                mode = input("Opsi Tampilan: [1] Rapi (Parsed) atau [2] Mentahan (Raw JSON)? [1/2]: ").strip()
                if mode == "2":
                    print(json.dumps(raw_data, indent=4))
                else:
                    parse_and_print_users(raw_data, "Following")
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "7":
            target = input("Masukkan User ID (Numeric) target: ").strip()
            print("⏳ Mengirim permintaan Follow ke GraphQL...")
            try:
                raw_data = toolkit.follow_user(target)
                print(json.dumps(raw_data, indent=4))
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "8":
            target = input("Masukkan Media ID (Numeric) target: ").strip()
            print("⏳ Mengirim permintaan Like ke GraphQL...")
            try:
                raw_data = toolkit.like_post(target)
                print(json.dumps(raw_data, indent=4))
            except Exception as e:
                print(f"❌ Gagal: {e}")
        elif choice == "9":
            print("Keluar. Sampai jumpa!")
            break
        else:
            print("❌ Pilihan tidak valid.")

if __name__ == "__main__":
    main()
