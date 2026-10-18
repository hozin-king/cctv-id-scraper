# cctv-id-scraper

Scraper CCTV **publik/resmi** Indonesia → `cctv.json` per wilayah. Jalan otomatis
tiap 6 jam via GitHub Actions.

## Sumber aktif

| Sumber | Kamera | Keterangan |
|---|---|---|
| BPJT (`bpjt.pu.go.id/cctv`) | ~1500 | Jalan tol seluruh Indonesia, stream m3u8 langsung |
| Kemenhub (`mudik.kemenhub.go.id/cctv`) | ~290 | Jalan nasional/pelabuhan per provinsi, m3u8 langsung |
| Bandung Pelindung | ~430 | Kota Bandung, m3u8 langsung via API |

## Sumber gagal (jujur)

- **Lewatmana** — semua kamera offline (endpoint stream kosong).
- **Travoy** — tidak terjangkau dari jaringan scraper; kamera Jasa Marga
  sudah tercover via BPJT.
- **Jakarta Smart City** — HTTPS gagal dari jaringan scraper.
- **Yogyakarta** — tidak terjangkau dari jaringan scraper.
- **Bina Marga** — mirror data BPJT, sengaja tidak diduplikasi.

Semua feed adalah tayangan publik yang memang disediakan untuk masyarakat.
Bukan hasil peretasan — tidak ada kredensial/bypass apa pun.

## Format cctv.json

```json
{
  "updated_at": "2026-10-18T20:30:00+07:00",
  "wilayah": [
    {"nama": "Tol Jakarta-Cikampek", "sumber": "BPJT",
     "kamera": [{"nama": "...", "lokasi": "...",
                 "stream": "https://...m3u8", "lat": -6.28, "lon": 106.87}]}
  ]
}
```

## Jalankan lokal

```
python3 scrape.py   # tanpa dependensi (stdlib saja)
```
