# Warna UI
Z2 = "[#000000]" # HITAM
M2 = "[#FF0000]" # MERAH
H2 = "[#00FF00]" # HIJAU
K2 = "[#FFFF00]" # KUNING
B2 = "[#00C8FF]" # BIRU
U2 = "[#AF00FF]" # UNGU
N2 = "[#FF00FF]" # PINK
O2 = "[#00FFFF]" # BIRU MUDA
P2 = "[#FFFFFF]" # PUTIH
J2 = "[#FF8F00]" # JINGGA
A2 = "[#AAAAAA]" # ABU-ABU

# ANSI Color Codes
M = '\x1b[1;91m' # MERAH
O = '\x1b[1;96m' # BIRU MUDA
N = '\x1b[0m'    # WARNA MATI
H = '\x1b[1;92m' # HIJAU
K = '\x1b[1;93m' # KUNING

# ===========================================================
# STATIC PARAMS — Update manual di sini tiap bot mulai mati
# Cara update: buka DevTools browser → Network → capture
# request ke www.instagram.com → cari nilai di header/body
# ===========================================================
STATIC_PARAMS = {
    # App ID Instagram Web (jarang berubah)
    'x_ig_app_id': '936619743392459',

    # ASBD ID (jarang berubah)
    'x_asbd_id': '359341',

    # Bloks Version — update tiap IG deploy besar
    # Cari di header: X-Bloks-Version-Id
    'x_bloks_version_id': '879ff742a426fe5ee1b386f4314ce0f9794746e0577a018370f672c73bf9e068',

    # X-Instagram-Ajax (versi build IG) — update tiap deploy
    # Cari di header: X-Instagram-Ajax
    'x_instagram_ajax': '1042285536',

    # doc_id untuk setiap operasi — update tiap IG ubah query
    # Cara cari: filter request di DevTools → cari fb_api_req_friendly_name
    'doc_id_like':     '27182485238052618',   # usePolarisLikeMediaXIGLikeMutation
    'doc_id_comments': '26297736713236852',   # PolarisPostCommentsContainerQuery
    'doc_id_post':     '27128499623469141',   # PolarisPostRootQuery
    'doc_id_login':    '9807605492696448',    # useCDSWebLoginMutation
}

# User-Agent Windows Chrome — update tiap versi Chrome baru
IG_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
