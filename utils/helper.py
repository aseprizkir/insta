import time

def kalender():
    """Mengembalikan informasi waktu saat ini."""
    struct_time = time.localtime(time.time())
    hari_indonesia = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    hari = hari_indonesia[struct_time.tm_wday]
    tanggal = time.strftime("%d", struct_time)
    bulan = time.strftime("%B", struct_time)
    tahun = time.strftime("%Y", struct_time)
    jam = time.strftime("%H:%M:%S", struct_time)
    return hari, tanggal, bulan, tahun, jam

def _search(pattern, string, group=1, default=""):
    """Search pattern in string and return group safely."""
    import re
    match = re.search(pattern, str(string))
    if match:
        try:
            return match.group(group)
        except IndexError:
            return default
    return default

def _shortcode_to_id(shortcode):
    """Convert Instagram shortcode to Media ID."""
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    mediaid = 0
    for char in shortcode:
        mediaid = mediaid * 64 + alphabet.index(char)
    return str(mediaid)

def _ck(cookie_str):
    """Parse string cookie jadi dict buat requests."""
    from http.cookies import SimpleCookie
    import re
    
    # Jika input adalah full HTTP request/header, ambil bagian Cookie-nya saja
    if "Cookie: " in cookie_str:
        match = re.search(r"Cookie: (.*?)(?:\r?\n|$)", cookie_str, re.IGNORECASE)
        if match:
            cookie_str = match.group(1)
    
    try:
        c = SimpleCookie()
        c.load(cookie_str)
        # Filter out keys that might be misinterpreted headers if parsing failed slightly
        res = {k: v.value for k, v in c.items() if not k.startswith(("GET ", "POST ", "Host:", "User-Agent:"))}
        if not res and cookie_str:
             return {"cookie": cookie_str}
        return res
    except:
        return {"cookie": cookie_str}
