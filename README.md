# cctv-id-scraper

Scraper CCTV **publik/resmi** Indonesia → `cctv.json` per wilayah, tersusun
rapi **per pulau → per provinsi → per kota/kabupaten**. Jalan otomatis
tiap 6 jam via GitHub Actions.

## Sumber aktif

| Sumber | Kamera | Keterangan |
|---|---|---|
| CCTV Nusantara (`cctvnusantara.com/api/cameras`) | ~4675 | Jalan, tol, pengadilan, wisata, publik se-Indonesia. API JSON resmi situsnya |
| Bandung Pelindung | ~430 | Kota Bandung, m3u8 langsung via API |

## Sumber gagal / nonaktif (jujur)

- **BPJT** (`bpjt.pu.go.id/cctv`, ~1500 kamera tol) — sejak ~8 Nov 2026
  koneksi ditutup server (`Remote end closed connection`), gagal juga dari CI.
- **Kemenhub** (`mudik.kemenhub.go.id/cctv`, ~290 kamera) — sejak ~8 Nov 2026
  HTTP 404, halaman mudik dicabut usai musim mudik.
- **Lewatmana** — semua kamera offline (endpoint stream kosong).
- **Travoy** — tidak terjangkau dari jaringan scraper; kamera Jasa Marga
  sudah tercover via BPJT.
- **Jakarta Smart City** — HTTPS gagal dari jaringan scraper.
- **Yogyakarta** — tidak terjangkau dari jaringan scraper.
- **Bina Marga** — mirror data BPJT, sengaja tidak diduplikasi.

## Catatan jujur soal stream CCTV Nusantara

Situs sumber **tidak mengekspos URL stream langsung** untuk kamera tipe `hls`
(~3130 kamera): field `url`-nya kosong di API mereka, dan client JS situsnya
pun tidak pernah merujuk `.m3u8`. Yang punya tautan tonton langsung: `iframe`
1415 (halaman play), `youtube` 85, `web` 25, `snapshot` 20.

Karena itu, untuk kamera tanpa stream: `stream` dikosongkan (jujur, bukan
diisi URL karangan), dan `tautan` diisi halaman kamera di situs sumber
(`cctvnusantara.com/embed?cam=<id>`) supaya tetap bisa dibuka.

## Format cctv.json

```json
{
  "updated_at": "2026-11-08T21:52:00+07:00",
  "total_kamera": 5015,
  "sumber_gagal": ["BPJT: ...", "..."],
  "ringkasan": {
    "per_pulau": {"Jawa": 3125, "Sumatera": 1074, "Kalimantan": 319, "...": 0},
    "per_provinsi": {"Jawa Barat": 1221, "Jawa Timur": 718, "...": 0}
  },
  "wilayah": [
    {"nama": "Kabupaten Aceh Tengah", "pulau": "Sumatera",
     "provinsi": "Aceh", "sumber": "CCTV Nusantara",
     "kamera": [{"nama": "Dedalu 1",
                 "lokasi": "Dedalu 1, Takengon, Kabupaten Aceh Tengah, Aceh",
                 "stream": "",
                 "lat": 4.61565176, "lon": 96.85479283,
                 "tipe": "hls", "kategori": "jalan",
                 "sumber": "Diskominfo Kabupaten Aceh Tengah",
                 "tautan": "https://cctvnusantara.com/embed?cam=acehtengah-dedalu-1"}]}
  ]
}
```

- Daftar `wilayah` diurutkan: pulau → provinsi → nama.
- Satu wilayah = satu kota/kabupaten (atau satu ruas tol); wilayah yang
  namanya sama dari dua sumber digabung, kamera ganda dirapikan
  (salinan tanpa stream dibuang bila ada versi ber-stream-nya).
- Kamera tol Nusantara yang kotanya "Lintas Nusantara" dipetakan ke provinsi
  lewat koordinatnya; ruas tol BPJT dipetakan lewat nama ruas, lalu koordinat
  median kameranya.
- Peta kota → provinsi disalin dari data situs Nusantara sendiri (`KOTA_META`
  di JS situs, 132 kota) + tambalan manual 4 kota Sumut (Toba, Mandailing
  Natal, Padang Lawas, Tapanuli Tengah).

Semua feed adalah tayangan publik yang memang disediakan untuk masyarakat.
Bukan hasil peretasan — tidak ada kredensial/bypass apa pun.

## Jalankan lokal

```
python3 scrape.py   # tanpa dependensi (stdlib saja)
```
