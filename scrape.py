#!/usr/bin/env python3
"""Scraper CCTV publik Indonesia -> cctv.json (per wilayah, per pulau, per provinsi).

Sumber AKTIF (terverifikasi 8 Nov 2026):
  - CCTV Nusantara (cctvnusantara.com/api/cameras): ~4675 kamera (jalan, tol,
    pengadilan, wisata, publik, ...), API JSON resmi situsnya sendiri.
    Jujur soal stream: situs ini TIDAK mengekspos URL stream langsung untuk
    kamera tipe hls (~3130 kamera) — field `url`-nya kosong di API. Yang punya
    tautan tonton langsung: iframe 1415 (play.html), youtube 85, web 25,
    snapshot 20. Untuk kamera tanpa stream, `stream` dikosongkan dan `tautan`
    diisi halaman kamera di situs sumber (cctvnusantara.com/embed?cam=<id>).
  - Bandung Pelindung (pelindung.bandung.go.id:8443/api/cek): ~430 kamera m3u8.

Sumber GAGAL / NONAKTIF (dicatat jujur, dicek tiap run):
  - BPJT (bpjt.pu.go.id/cctv): sejak ~8 Nov 2026 koneksi ditutup server
    ("Remote end closed connection without response") — juga gagal dari CI.
  - Kemenhub (mudik.kemenhub.go.id/cctv): HTTP 404 sejak ~8 Nov 2026
    (halaman mudik dicabut usai musim mudik).
  - Lewatmana (lewatmana.com/cam): semua endpoint /camvidurl/<id>/ kosong
    (kamera offline).
  - Travoy (travoy.jasamarga.com): tidak bisa dijangkau dari jaringan ini;
    kamera Jasa Marga sudah tercover via BPJT (host jmlive.jasamarga.com).
  - Jakarta Smart City: HTTPS gagal dari jaringan ini.
  - Yogyakarta (cctv.jogjakarta.go.id): tidak bisa dijangkau.
  - Bina Marga: mirror data BPJT (sengaja tidak diduplikasi).

Output: cctv.json
  {"updated_at": "...", "total_kamera": N,
   "sumber_gagal": ["BPJT: ...", ...],
   "ringkasan": {"per_pulau": {"Jawa": N, ...},
                 "per_provinsi": {"Jawa Barat": N, ...}},
   "wilayah": [{"nama": "...", "pulau": "Jawa", "provinsi": "Jawa Barat",
                "sumber": "CCTV Nusantara",
                "kamera": [{"nama": "...", "lokasi": "...",
                            "stream": "https://... (bisa kosong)",
                            "lat": ..., "lon": ...,
                            "tipe": "iframe", "kategori": "jalan",
                            "sumber": "Ditjen Badilag ...",
                            "tautan": "https://cctvnusantara.com/embed?cam=..."}]}]}
  Daftar wilayah diurutkan: pulau -> provinsi -> nama.
  Hanya stdlib (urllib) — tanpa dependensi.
"""
import json
import re
import ssl
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
WIB = timezone(timedelta(hours=7))

# SSL: coba verifikasi normal dulu, fallback unverified (untuk API Bandung).
CTX_UNVERIFIED = ssl.create_default_context()
CTX_UNVERIFIED.check_hostname = False
CTX_UNVERIFIED.verify_mode = ssl.CERT_NONE


def fetch(url, timeout=30, unverified=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = CTX_UNVERIFIED if unverified else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        if not unverified:
            # coba sekali lagi tanpa verifikasi SSL
            try:
                with urllib.request.urlopen(req, timeout=timeout,
                                            context=CTX_UNVERIFIED) as r:
                    return r.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
        print(f"  ! gagal fetch {url}: {e}", file=sys.stderr)
        return ""


# ---------------------------------------------------------------------------
# Pulau / provinsi
# ---------------------------------------------------------------------------
# Urutan tampil pulau (Nasional paling akhir = yang tak terpetakan).
PULAU_ORDER = ["Sumatera", "Jawa", "Bali", "Nusa Tenggara", "Kalimantan",
               "Sulawesi", "Maluku", "Papua", "Nasional"]

PROVINSI_KE_PULAU = {
    # Sumatera
    "Aceh": "Sumatera", "Sumatera Utara": "Sumatera",
    "Sumatera Barat": "Sumatera", "Riau": "Sumatera",
    "Kepulauan Riau": "Sumatera", "Jambi": "Sumatera",
    "Sumatera Selatan": "Sumatera",
    "Kepulauan Bangka Belitung": "Sumatera", "Bengkulu": "Sumatera",
    "Lampung": "Sumatera",
    # Jawa
    "DKI Jakarta": "Jawa", "Jawa Barat": "Jawa", "Jawa Tengah": "Jawa",
    "DI Yogyakarta": "Jawa", "D.I. Yogyakarta": "Jawa",
    "Jawa Timur": "Jawa", "Banten": "Jawa",
    # Bali + Nusa Tenggara
    "Bali": "Bali",
    "Nusa Tenggara Barat": "Nusa Tenggara",
    "Nusa Tenggara Timur": "Nusa Tenggara",
    # Kalimantan
    "Kalimantan Barat": "Kalimantan", "Kalimantan Tengah": "Kalimantan",
    "Kalimantan Selatan": "Kalimantan", "Kalimantan Timur": "Kalimantan",
    "Kalimantan Utara": "Kalimantan", "Kalimantan": "Kalimantan",
    # Sulawesi
    "Sulawesi Utara": "Sulawesi", "Sulawesi Tengah": "Sulawesi",
    "Sulawesi Selatan": "Sulawesi", "Sulawesi Tenggara": "Sulawesi",
    "Gorontalo": "Sulawesi", "Sulawesi Barat": "Sulawesi",
    # Maluku
    "Maluku": "Maluku", "Maluku Utara": "Maluku",
    # Papua
    "Papua": "Papua", "Papua Barat": "Papua", "Papua Selatan": "Papua",
    "Papua Tengah": "Papua", "Papua Pegunungan": "Papua",
    "Papua Barat Daya": "Papua",
    # Tangkapan situs (bukan provinsi resmi)
    "Lintas Nusantara": "Nasional", "Indonesia": "Nasional",
}

# Kota (slug) -> provinsi, disalin dari data situs CCTV Nusantara sendiri
# (KOTA_META di JS situs, diekstrak 8 Nov 2026). 132 entri.
KOTA_KE_PROVINSI = {
    "aceh": "Aceh", "babel": "Kepulauan Bangka Belitung", "bali": "Bali", "balikpapan": "Kalimantan Timur",
    "bandung": "Jawa Barat", "banjar": "Jawa Barat", "banjarbaru": "Kalimantan Selatan", "banjarmasin": "Kalimantan Selatan",
    "banjarnegara": "Jawa Tengah", "banten": "Banten", "banyumas": "Jawa Tengah", "banyuwangi": "Jawa Timur",
    "batam": "Kepulauan Riau", "bekasi": "Jawa Barat", "bengkulu": "Bengkulu", "blora": "Jawa Tengah",
    "bogor": "Jawa Barat", "bojonegoro": "Jawa Timur", "bondowoso": "Jawa Timur", "boyolali": "Jawa Tengah",
    "brebes": "Jawa Tengah", "ciamis": "Jawa Barat", "cianjur": "Jawa Barat", "cikampek": "Jawa Barat",
    "cikarang": "Jawa Barat", "cilacap": "Jawa Tengah", "cilegon": "Banten", "cimahi": "Jawa Barat",
    "cipali": "Jawa Barat", "cirebon": "Jawa Barat", "demak": "Jawa Tengah", "depok": "Jawa Barat",
    "garut": "Jawa Barat", "gorontalo": "Gorontalo", "gresik": "Jawa Timur", "grobogan": "Jawa Tengah",
    "halmahera-barat": "Maluku Utara", "indramayu": "Jawa Barat", "jakarta": "DKI Jakarta", "jambi": "Jambi",
    "jawatengah": "Jawa Tengah", "jawatimur": "Jawa Timur", "jember": "Jawa Timur", "jepara": "Jawa Tengah",
    "jombang": "Jawa Timur", "kabbandung": "Jawa Barat", "kabbogor": "Jawa Barat", "kabtegal": "Jawa Tengah",
    "kabupaten-bandung-barat": "Jawa Barat", "kalbar": "Kalimantan Barat", "kalimantan": "Kalimantan", "kalsel": "Kalimantan Selatan",
    "kaltara": "Kalimantan Utara", "kalteng": "Kalimantan Tengah", "kaltim": "Kalimantan Timur", "karanganyar": "Jawa Tengah",
    "karawang": "Jawa Barat", "karo": "Sumatera Utara", "kebumen": "Jawa Tengah", "kediri": "Jawa Timur",
    "kendal": "Jawa Tengah", "kepri": "Kepulauan Riau", "kerinci": "Jambi", "klaten": "Jawa Tengah",
    "kota-metro": "Lampung", "kudus": "Jawa Tengah", "kuningan": "Jawa Barat", "lainnya": "Indonesia",
    "lamongan": "Jawa Timur", "lampung": "Lampung", "lampung-selatan": "Lampung", "lumajang": "Jawa Timur",
    "madiun": "Jawa Timur", "magelangkab": "Jawa Tengah", "magetan": "Jawa Timur", "makassar": "Sulawesi Selatan",
    "malang": "Jawa Timur", "maluku": "Maluku", "medan": "Sumatera Utara", "merak": "Banten",
    "mojokerto": "Jawa Timur", "nganjuk": "Jawa Timur", "ntb": "Nusa Tenggara Barat", "ntt": "Nusa Tenggara Timur",
    "pagar-alam": "Sumatera Selatan", "palembang": "Sumatera Selatan", "pangandaran": "Jawa Barat", "papua": "Papua",
    "pati": "Jawa Tengah", "pekalongan": "Jawa Tengah", "pemalang": "Jawa Tengah", "pematangsiantar": "Sumatera Utara",
    "pontianak": "Kalimantan Barat", "pringsewu": "Lampung", "probolinggo": "Jawa Timur", "puncak": "Jawa Barat",
    "purbalingga": "Jawa Tengah", "purwakarta": "Jawa Barat", "purwokerto": "Jawa Tengah", "purworejo": "Jawa Tengah",
    "rembang": "Jawa Tengah", "riau": "Riau", "salatiga": "Jawa Tengah", "samarinda": "Kalimantan Timur",
    "semarang": "Jawa Tengah", "serang": "Banten", "singkawang": "Kalimantan Barat", "situbondo": "Jawa Timur",
    "sleman": "DI Yogyakarta", "solok": "Sumatera Barat", "subang": "Jawa Barat", "sukabumi": "Jawa Barat",
    "sulbar": "Sulawesi Barat", "sulsel": "Sulawesi Selatan", "sulteng": "Sulawesi Tengah", "sultra": "Sulawesi Tenggara",
    "sulut": "Sulawesi Utara", "sumbar": "Sumatera Barat", "sumedang": "Jawa Barat", "sumenep": "Jawa Timur",
    "surabaya": "Jawa Timur", "surakarta": "Jawa Tengah", "tangerang": "Banten", "tangsel": "Banten",
    "tanjungpati": "Sumatera Barat", "tasikmalaya": "Jawa Barat", "tegal": "Jawa Tengah", "temanggung": "Jawa Tengah",
    "tol": "Lintas Nusantara", "wonogiri": "Jawa Tengah", "wonosobo": "Jawa Tengah", "yogyakarta": "DI Yogyakarta",
}

# Kota yang belum ada di KOTA_META situs (12 kamera, 8 Nov 2026) — semua
# di Sumatera Utara (Toba, Mandailing Natal, Padang Lawas, Tapanuli Tengah).
KOTA_TAMBAHAN = {
    "toba": "Sumatera Utara",
    "mandailingnatal": "Sumatera Utara",
    "padanglawas": "Sumatera Utara",
    "tapanulitengah": "Sumatera Utara",
}


def provinsi_ke_pulau(prov):
    return PROVINSI_KE_PULAU.get((prov or "").strip(), "Nasional")


def provinsi_dari_lokasi(lokasi):
    """Tebak provinsi dari segmen terakhir field lokasi
    (format situs: 'nama, kota, kabupaten, PROVINSI')."""
    if not lokasi:
        return None
    segmen = [s.strip() for s in lokasi.split(",") if s.strip()]
    for seg in reversed(segmen):
        norm = seg.replace("D.I.", "DI").replace("D. I.", "DI")
        for prov in PROVINSI_KE_PULAU:
            if norm.lower() == prov.lower().replace("d.i.", "di"):
                return prov
            if norm.lower() == prov.lower():
                return prov
    return None


def provinsi_dari_kota(kota_slug, kota_nama="", lokasi=""):
    """Rantai penentuan provinsi untuk satu kamera Nusantara."""
    slug = (kota_slug or "").strip().lower()
    if slug in KOTA_KE_PROVINSI:
        return KOTA_KE_PROVINSI[slug]
    if slug in KOTA_TAMBAHAN:
        return KOTA_TAMBAHAN[slug]
    prov = provinsi_dari_lokasi(lokasi)
    if prov:
        return prov
    prov = provinsi_dari_lokasi(kota_nama or "")
    if prov:
        return prov
    return "Lainnya"


# Perkiraan kotak provinsi (lat_min, lat_max, lon_min, lon_max) — dipakai
# HANYA sebagai fallback pemetaan ruas tol BPJT dari koordinat median
# kameranya. Provinsi kecil/enclave dicek dulu supaya tidak tertelan
# tetangga besarnya. Angka kasar, bukan batas resmi.
PROVINSI_BBOX = [
    ("DKI Jakarta", -6.40, -6.00, 106.65, 107.05),
    ("DI Yogyakarta", -8.20, -7.50, 110.00, 110.90),
    ("Banten", -6.90, -5.90, 105.90, 106.90),
    ("Bali", -8.90, -8.05, 114.35, 115.75),
    ("Kepulauan Riau", -1.10, 4.10, 103.50, 109.10),
    ("Kepulauan Bangka Belitung", -3.20, -1.00, 105.00, 107.00),
    ("Gorontalo", 0.30, 1.10, 121.30, 123.60),
    ("Sulawesi Barat", -3.10, -0.90, 118.70, 119.70),
    ("Maluku Utara", -3.20, 2.90, 125.90, 129.70),
    ("Papua Barat Daya", -1.90, 0.90, 129.40, 132.60),
    ("Aceh", 2.30, 6.10, 95.00, 98.30),
    ("Sumatera Utara", 0.90, 4.10, 97.80, 100.10),
    ("Sumatera Barat", -3.10, 0.90, 99.30, 101.90),
    ("Riau", -1.10, 2.90, 100.10, 103.50),
    ("Jambi", -2.90, 0.30, 101.20, 104.50),
    ("Sumatera Selatan", -4.20, -1.30, 102.20, 106.20),
    ("Bengkulu", -5.10, -2.30, 101.20, 103.90),
    ("Lampung", -6.20, -3.70, 103.50, 106.10),
    ("Jawa Barat", -7.90, -5.90, 106.90, 108.90),
    ("Jawa Tengah", -8.20, -6.40, 108.90, 111.50),
    ("Jawa Timur", -8.80, -6.80, 111.50, 114.60),
    ("Nusa Tenggara Barat", -9.10, -8.10, 115.70, 119.30),
    ("Nusa Tenggara Timur", -11.10, -7.70, 118.80, 125.20),
    ("Kalimantan Barat", -3.50, 4.20, 108.80, 114.30),
    ("Kalimantan Tengah", -3.60, 0.90, 111.30, 115.90),
    ("Kalimantan Selatan", -4.30, -1.20, 114.30, 116.30),
    ("Kalimantan Timur", -2.30, 2.30, 115.90, 118.60),
    ("Kalimantan Utara", 1.20, 4.50, 116.10, 118.10),
    ("Sulawesi Utara", 0.40, 2.10, 123.30, 125.60),
    ("Sulawesi Tengah", -3.00, 1.20, 119.60, 123.60),
    ("Sulawesi Selatan", -6.30, -2.30, 118.90, 121.10),
    ("Sulawesi Tenggara", -6.10, -2.80, 120.50, 123.90),
    ("Maluku", -8.40, -2.40, 125.90, 131.10),
    ("Papua", -9.10, -0.90, 130.80, 141.00),
    ("Papua Barat", -4.30, -0.40, 130.20, 133.10),
    ("Papua Selatan", -8.50, -4.50, 134.50, 141.00),
    ("Papua Tengah", -4.90, -1.80, 134.90, 137.90),
    ("Papua Pegunungan", -4.90, -2.80, 137.90, 141.00),
]


def provinsi_dari_koordinat(lat, lon):
    """Provinsi dari satu titik (dipakai untuk median koordinat ruas tol)."""
    if lat is None or lon is None:
        return None
    for prov, la_min, la_max, lo_min, lo_max in PROVINSI_BBOX:
        if la_min <= lat <= la_max and lo_min <= lon <= lo_max:
            return prov
    return None


# Nama ruas tol -> provinsi (best-effort; ruas lintas provinsi dipetakan ke
# provinsi awalnya). Dipakai sebelum fallback koordinat.
RUAS_KE_PROVINSI = {
    "jakarta-cikampek": "Jawa Barat", "cikampek": "Jawa Barat",
    "cipali": "Jawa Barat", "jagorawi": "Jawa Barat",
    "purbaleunyi": "Jawa Barat", "palikanci": "Jawa Barat",
    "kanci-pejagan": "Jawa Barat", "pejagan-pemalang": "Jawa Tengah",
    "pemalang-batang": "Jawa Tengah", "batang-semarang": "Jawa Tengah",
    "semarang-solo": "Jawa Tengah", "solo-ngawi": "Jawa Timur",
    "ngawi-kertosono": "Jawa Timur", "kertosono-mojokerto": "Jawa Timur",
    "mojokerto-surabaya": "Jawa Timur", "surabaya-gempol": "Jawa Timur",
    "gempol-pasuruan": "Jawa Timur", "pasuruan-probolinggo": "Jawa Timur",
    "probolinggo-banyuwangi": "Jawa Timur",
    "jakarta outer ring road": "DKI Jakarta", "jorr": "DKI Jakarta",
    "dalam kota": "DKI Jakarta", "jakarta-tangerang": "Banten",
    "tangerang-merak": "Banten", "serpong-cinere": "Banten",
    "cinere-jagorawi": "Jawa Barat", "depok-antasari": "Jawa Barat",
    "cimanggis-cibitung": "Jawa Barat", "cibitung-cilincing": "DKI Jakarta",
    "bekasi-cawang-kampung melayu": "DKI Jakarta",
    "trans sumatera": "Lampung", "bakauheni-terbanggi besar": "Lampung",
    "terbanggi besar-pematang panggang": "Lampung",
    "pematang panggang-kayu agung": "Sumatera Selatan",
    "kayu agung-palembang": "Sumatera Selatan",
    "palembang-indralaya": "Sumatera Selatan",
    "indralaya-prabumulih": "Sumatera Selatan",
    "prabumulih-muara enim": "Sumatera Selatan",
    "pekanbaru-dumai": "Riau", "pekanbaru-bangkinang": "Riau",
    "bangkinang-pangkalan": "Riau", "dumai": "Riau",
    "medan-kualanamu-tebing tinggi": "Sumatera Utara",
    "medan-binjai": "Sumatera Utara", "binjai-langkat": "Sumatera Utara",
    "tebing tinggi-indrapura": "Sumatera Utara",
    "kuala tanjung-tebing tinggi-parapat": "Sumatera Utara",
    "sigli-banda aceh": "Aceh", "banda aceh-sigli": "Aceh",
    "balikpapan-samarinda": "Kalimantan Timur",
    "manado-bitung": "Sulawesi Utara",
    "makassar": "Sulawesi Selatan",
    "bali mandara": "Bali", "denpasar": "Bali",
}


def provinsi_dari_ruas(ruas, kameras):
    """Provinsi untuk satu ruas tol: keyword nama dulu, lalu koordinat
    median kameranya, terakhir 'Lintas Provinsi'."""
    nama = (ruas or "").lower()
    for kunci, prov in RUAS_KE_PROVINSI.items():
        if kunci in nama:
            return prov
    lats = sorted(k["lat"] for k in kameras if k.get("lat") is not None)
    lons = sorted(k["lon"] for k in kameras if k.get("lon") is not None)
    if lats and lons:
        prov = provinsi_dari_koordinat(lats[len(lats) // 2],
                                       lons[len(lons) // 2])
        if prov:
            return prov
    return "Lintas Provinsi"


# ---------------------------------------------------------------------------
# Sumber: BPJT / Kemenhub / Bandung (sudah ada, dipertahankan)
# ---------------------------------------------------------------------------

def parse_bpjt():
    """BPJT: objek JSON {..,"stream":"..",..} di HTML."""
    print("BPJT ...")
    html = fetch("https://bpjt.pu.go.id/cctv", timeout=60)
    if not html:
        return [], "BPJT: tidak bisa dijangkau (koneksi ditutup server)"
    pats = re.findall(r'\{[^{}]*"stream"\s*:\s*"[^"]*"[^{}]*\}', html)
    objs = []
    for p in pats:
        try:
            objs.append(json.loads(p.replace("\\/", "/")))
        except Exception:
            continue
    print(f"  objek: {len(objs)}")
    grouped = defaultdict(list)
    for o in objs:
        if o.get("status") not in ("1", "online"):
            continue
        stream = (o.get("streamhls") or "").strip()
        if not stream or "m3u8" not in stream:
            continue
        ruas = (o.get("nama_ruas") or "Lainnya").strip()
        nama = (o.get("nama_km") or o.get("nama_segment") or "Kamera").strip()
        lokasi = (o.get("nama_segment") or "").strip()
        try:
            lat = float(o["lat"]) if o.get("lat") else None
            lon = float(o["lon"]) if o.get("lon") else None
        except (ValueError, TypeError):
            lat, lon = None, None
        grouped[ruas].append({"nama": nama, "lokasi": lokasi,
                              "stream": stream, "lat": lat, "lon": lon,
                              "tipe": "m3u8", "kategori": "tol"})
    out = []
    for ruas in sorted(grouped):
        kams = sorted(grouped[ruas], key=lambda k: k["nama"])
        prov = provinsi_dari_ruas(ruas, kams)
        out.append({"nama": f"Tol {ruas}", "pulau": provinsi_ke_pulau(prov),
                    "provinsi": prov, "sumber": "BPJT", "kamera": kams})
    if not out:
        return [], "BPJT: halaman termuat tapi tidak ada kamera m3u8"
    return out, None


def _extract_js_array(html, varname):
    m = re.search(varname + r"\s*=\s*\[", html)
    if not m:
        return []
    start = html.find("[", m.start())
    depth, instr, esc, q, end = 0, False, False, "", start
    for j in range(start, len(html)):
        c = html[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == q:
                instr = False
        else:
            if c in "\"'":
                instr, q = True, c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
    try:
        return json.loads(html[start:end])
    except Exception as e:
        print(f"  ! parse array {varname} gagal: {e}", file=sys.stderr)
        return []


def parse_kemenhub():
    """Kemenhub: const cctv = [...] di HTML; ambil protocol m3u8."""
    print("Kemenhub ...")
    html = fetch("https://mudik.kemenhub.go.id/cctv", timeout=60)
    if not html:
        return [], "Kemenhub: tidak bisa dijangkau"
    if "404" in html[:200] and "Not Found" in html[:500]:
        return [], "Kemenhub: HTTP 404 (halaman mudik dicabut)"
    objs = _extract_js_array(html, r"cctv")
    print(f"  objek: {len(objs)}")
    grouped = defaultdict(list)
    for o in objs:
        if o.get("protocol") != "m3u8":
            continue
        stream = (o.get("stream_url") or "").strip()
        if not stream:
            continue
        prov = (o.get("nama_provinsi") or "Lainnya").strip().title()
        nama = (o.get("nama_cctv") or o.get("nama_lokasi") or "Kamera").strip()
        lokasi = (o.get("nama_lokasi") or "").strip()
        kab = (o.get("nama_kabupaten_kota") or "").strip()
        if kab and kab.lower() not in lokasi.lower():
            lokasi = f"{lokasi} ({kab})".strip()
        grouped[prov].append({"nama": nama, "lokasi": lokasi,
                              "stream": stream, "lat": None, "lon": None,
                              "tipe": "m3u8"})
    out = []
    for prov in sorted(grouped):
        out.append({"nama": prov, "pulau": provinsi_ke_pulau(prov),
                    "provinsi": prov, "sumber": "Kemenhub",
                    "kamera": sorted(grouped[prov], key=lambda k: k["nama"])})
    if not out:
        return [], "Kemenhub: halaman termuat tapi tidak ada kamera m3u8"
    return out, None


def parse_bandung():
    """Bandung Pelindung: JSON API langsung."""
    print("Bandung ...")
    raw = fetch("https://pelindung.bandung.go.id:8443/api/cek",
                timeout=90, unverified=True)
    if not raw:
        return [], "Bandung: API tidak bisa dijangkau"
    try:
        cams = json.loads(raw)
    except Exception as e:
        print(f"  ! parse JSON Bandung gagal: {e}", file=sys.stderr)
        return [], "Bandung: respons API bukan JSON"
    print(f"  objek: {len(cams)}")
    kams = []
    for c in cams:
        stream = (c.get("stream_cctv") or "").strip()
        if not stream:
            continue
        nama = (c.get("cctv_name") or "Kamera").strip()
        try:
            lat = float(c["lat"]) if c.get("lat") else None
            lon = float(c["lng"]) if c.get("lng") else None
        except (ValueError, TypeError):
            lat, lon = None, None
        kams.append({"nama": nama, "lokasi": "Kota Bandung",
                     "stream": stream, "lat": lat, "lon": lon,
                     "tipe": "m3u8"})
    if not kams:
        return [], "Bandung: API termuat tapi tidak ada kamera"
    return [{"nama": "Kota Bandung", "pulau": "Jawa",
             "provinsi": "Jawa Barat", "sumber": "Pelindung Bandung",
             "kamera": sorted(kams, key=lambda k: k["nama"])}], None


# ---------------------------------------------------------------------------
# Sumber: CCTV Nusantara (cctvnusantara.com)
# ---------------------------------------------------------------------------

def _kamera_nusantara(o):
    """Satu objek kamera API -> entri cctv.json (None bila tak layak)."""
    nama = (o.get("nama") or "Kamera").strip()
    lokasi = (o.get("lokasi") or "").strip()
    try:
        lat = float(o["lat"]) if o.get("lat") not in (None, "") else None
        lon = float(o["lng"]) if o.get("lng") not in (None, "") else None
    except (ValueError, TypeError):
        lat, lon = None, None
    stream = (o.get("url") or "").strip()
    cam_id = (o.get("id") or "").strip()
    return {
        "nama": nama,
        "lokasi": lokasi,
        "stream": stream,
        "lat": lat,
        "lon": lon,
        "tipe": o.get("tipe") or None,
        "kategori": (o.get("kategori") or "").strip() or None,
        "sumber": (o.get("sumber") or "").strip() or None,
        "tautan": f"https://cctvnusantara.com/embed?cam={cam_id}" if cam_id else None,
        "_id": cam_id,
    }


def _extract_nusantara_dari_html(html):
    """Fallback: ambil array kamera dari payload RSC halaman utama
    (dipakai bila /api/cameras gagal)."""
    # Cari '"cameras":[' lalu parse array dengan pencocokan kurung.
    m = re.search(r'"cameras"\s*:\s*\[', html)
    if not m:
        return []
    start = html.find("[", m.start())
    depth, instr, esc, q, end = 0, False, False, "", start
    for j in range(start, len(html)):
        c = html[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == q:
                instr = False
        else:
            if c in "\"'":
                instr, q = True, c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
    try:
        return json.loads(html[start:end])
    except Exception:
        # HTML RSC memakai \" — coba unescape dulu
        try:
            return json.loads(html[start:end].replace('\\"', '"'))
        except Exception as e:
            print(f"  ! parse array nusantara gagal: {e}", file=sys.stderr)
            return []


def parse_nusantara():
    """CCTV Nusantara: GET /api/cameras (JSON resmi situsnya)."""
    print("CCTV Nusantara ...")
    raw = fetch("https://cctvnusantara.com/api/cameras", timeout=60)
    objs = []
    via = "api"
    if raw:
        try:
            objs = json.loads(raw).get("cameras", [])
        except Exception:
            objs = []
    if not objs:
        print("  api gagal/kosong, coba HTML ...")
        html = fetch("https://cctvnusantara.com/", timeout=60)
        if html:
            objs = _extract_nusantara_dari_html(html)
            via = "html"
    print(f"  objek: {len(objs)} (via {via})")
    if not objs:
        return [], "CCTV Nusantara: API + HTML gagal dimuat"
    grouped = defaultdict(list)
    seen_id = set()
    for o in objs:
        cam_id = (o.get("id") or "").strip()
        if cam_id:
            if cam_id in seen_id:
                continue
            seen_id.add(cam_id)
        slug = (o.get("kota") or "").strip().lower()
        prov = provinsi_dari_kota(slug, o.get("kotaNama", ""),
                                 o.get("lokasi", ""))
        if prov in ("Lintas Nusantara", "Lainnya"):
            # Kamera tol/nasional: petakan per kamera lewat koordinatnya.
            try:
                lat = float(o["lat"]) if o.get("lat") not in (None, "") else None
                lon = float(o["lng"]) if o.get("lng") not in (None, "") else None
            except (ValueError, TypeError):
                lat, lon = None, None
            prov2 = provinsi_dari_koordinat(lat, lon)
            if prov2:
                prov = prov2
        grouped[(prov, slug)].append(_kamera_nusantara(o))
    out = []
    for (prov, slug), kams in sorted(grouped.items()):
        # Nama wilayah = kotaNama yang paling sering muncul di grup ini.
        hitung = defaultdict(int)
        for o in objs:
            if (o.get("kota") or "").strip().lower() == slug:
                hitung[(o.get("kotaNama") or "").strip()] += 1
        nama_wil = ""
        if hitung:
            nama_wil = max(hitung.items(), key=lambda kv: kv[1])[0]
        nama_wil = nama_wil or slug
        kams = sorted(kams, key=lambda k: k["nama"])
        for k in kams:
            k.pop("_id", None)
        out.append({"nama": nama_wil, "pulau": provinsi_ke_pulau(prov),
                    "provinsi": prov, "sumber": "CCTV Nusantara",
                    "kamera": kams})
    if not out:
        return [], "CCTV Nusantara: data termuat tapi 0 kamera"
    return out, None


# ---------------------------------------------------------------------------

def _norm_nama(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _dedupe_kamera(kams):
    """Rapikan kamera senama dalam satu wilayah:
    - Bila ada yang ber-stream, buang salinan tanpa stream (cermin sumber
      yang sama, mis. Nusantara vs Pelindung Bandung).
    - Di antara yang ber-stream, buang duplikat eksak (lokasi+stream sama);
      stream beda dipertahankan (bisa feed/court berbeda, mis. dua PA. Negara).
    - Bila semuanya tanpa stream, buang duplikat lokasi saja."""
    by_name = defaultdict(list)
    for k in kams:
        by_name[_norm_nama(k.get("nama"))].append(k)
    out = []
    for nk, grp in by_name.items():
        streamed = [k for k in grp if k.get("stream")]
        if streamed:
            seen = set()
            for k in streamed:
                key = (_norm_nama(k.get("lokasi")), k["stream"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(k)
        else:
            seen = set()
            for k in grp:
                key = _norm_nama(k.get("lokasi"))
                if key in seen:
                    continue
                seen.add(key)
                out.append(k)
    return sorted(out, key=lambda k: k["nama"])


def gabung_wilayah_ganda(wilayah):
    """Gabung wilayah yang (pulau, provinsi, nama)-nya sama (mis. Kota Bandung
    dari Nusantara + Pelindung; dua slug Banyumas)."""
    gabung = {}
    urutan = []
    for w in wilayah:
        kunci = (w.get("pulau"), w.get("provinsi"), w.get("nama"))
        if kunci not in gabung:
            gabung[kunci] = dict(w)
            gabung[kunci]["kamera"] = list(w["kamera"])
            urutan.append(kunci)
            continue
        g = gabung[kunci]
        if w.get("sumber") and w["sumber"] not in g.get("sumber", ""):
            g["sumber"] = g.get("sumber", "") + " + " + w["sumber"]
        g["kamera"].extend(w["kamera"])
    out = []
    for kunci in urutan:
        g = gabung[kunci]
        g["kamera"] = _dedupe_kamera(g["kamera"])
        out.append(g)
    return out


def urut_wilayah(wilayah):
    """Urutkan daftar wilayah: pulau -> provinsi -> nama."""
    def kunci(w):
        try:
            p = PULAU_ORDER.index(w.get("pulau", "Nasional"))
        except ValueError:
            p = len(PULAU_ORDER)
        return (p, w.get("provinsi", ""), w.get("nama", ""))
    return sorted(wilayah, key=kunci)


def main():
    wilayah = []
    gagal = []
    for fn in (parse_nusantara, parse_bpjt, parse_kemenhub, parse_bandung):
        try:
            out, err = fn()
        except Exception as e:
            out, err = [], f"{fn.__name__}: {e}"
        wilayah += out
        if err:
            gagal.append(err)
    wilayah = gabung_wilayah_ganda(wilayah)
    wilayah = urut_wilayah(wilayah)
    total = sum(len(w["kamera"]) for w in wilayah)
    per_pulau = defaultdict(int)
    per_prov = defaultdict(int)
    for w in wilayah:
        per_pulau[w.get("pulau", "Nasional")] += len(w["kamera"])
        per_prov[w.get("provinsi", "Lainnya")] += len(w["kamera"])
    data = {
        "updated_at": datetime.now(WIB).isoformat(timespec="seconds"),
        "total_kamera": total,
        "sumber_gagal": gagal + [
            "Lewatmana: kamera offline (endpoint /camvidurl kosong)",
            "Travoy: tidak terjangkau; kamera Jasa Marga tercover via BPJT",
            "Jakarta Smart City: HTTPS gagal dari jaringan scraper",
            "Yogyakarta: tidak terjangkau dari jaringan scraper",
            "Bina Marga: mirror data BPJT (sengaja tidak diduplikasi)",
        ],
        "ringkasan": {
            "per_pulau": dict(sorted(per_pulau.items(),
                                     key=lambda kv: -kv[1])),
            "per_provinsi": dict(sorted(per_prov.items(),
                                        key=lambda kv: -kv[1])),
        },
        "wilayah": wilayah,
    }
    with open("cctv.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"SELESAI: {len(wilayah)} wilayah, {total} kamera -> cctv.json")
    if gagal:
        print("Gagal run ini:")
        for g in gagal:
            print(f"  - {g}")


if __name__ == "__main__":
    main()
