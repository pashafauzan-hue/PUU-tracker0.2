# Pemantau Perkara MK

Dashboard pemantauan perkara uji materiil Mahkamah Konstitusi.

## Struktur file

```
index.html          ← Dashboard (buka di browser, atau deploy ke GitHub Pages)
data-perkara.json   ← Data perkara & objek pengujian (dikurasi manual)
data-agenda.json    ← Data agenda sidang (diperbarui otomatis oleh scraper)
scraper.py          ← Script Python untuk scrape jadwal dari mkri.id
requirements.txt    ← Dependensi Python
.github/workflows/
  scrape.yml        ← GitHub Actions: jalankan scraper tiap Minggu 03.00 WIB
```

## Cara menambah perkara baru

1. Buka `data-perkara.json` di GitHub (klik nama file → klik ikon pensil)
2. Tambahkan entry baru di dalam array `"perkara"` mengikuti format yang ada:
   ```json
   {
     "id": "NomorPerkara/PUU-XXIV/2026",
     "kluster": "Polkam",
     "uu": "UU No. X Tahun YYYY tentang ...",
     "jenis": "Materiil",
     "batu_uji": "Pasal ...",
     "agendaLast": "",
     "tglLast": "",
     "agendaNext": "",
     "tglNext": "",
     "pemohon": "Nama pemohon",
     "ringkasan": "",
     "objek_petitum": [
       {
         "pasal": "Pasal X ayat (Y)",
         "objek_verbatim": "Teks pasal asli...",
         "petitum_verbatim": "Permintaan pemohon..."
       }
     ]
   }
   ```
3. Klik **Commit changes**
4. Scraper otomatis akan mengambil jadwal sidang perkara baru di jadwal berikutnya
   (atau trigger manual via tab Actions)

## Cara update manual data perkara

Edit `data-perkara.json` langsung di GitHub. Perubahan langsung terlihat di dashboard
setelah GitHub Pages rebuild (±1 menit).

## Cara trigger scraper manual

Tab **Actions** → klik **Update Agenda Perkara MK** → **Run workflow** → **Run workflow**
