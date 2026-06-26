from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import time, random, json, os
import urllib.request

DATA_PERKARA_FILE = "data-perkara.json"
DATA_AGENDA_FILE  = "data-agenda.json"

# Kredensial Supabase dari GitHub Secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

TAHAPAN_PUU = {
    1: "Pengajuan Permohonan",
    2: "Registrasi",
    3: "Penyampaian Salinan Permohonan dan Pemberitahuan Sidang Pertama",
    4: "Pemeriksaan Pendahuluan I",
    5: "Penyerahan Perbaikan Permohonan",
    6: "Pemeriksaan Pendahuluan II",
    7: "Pemeriksaan Persidangan",
    8: "Sidang Pengucapan Putusan",
    9: "Penyerahan Salinan Putusan",
}
STEP_FINAL = max(TAHAPAN_PUU.keys())

def frontier_menyala(steps):
    active = next((s for s in steps if s["status"] == "active"), None)
    if active and active["step_no"]:
        return active["step_no"], TAHAPAN_PUU.get(active["step_no"], ""), active["tanggal"]
    complete = [s for s in steps if s["status"] == "complete" and s["step_no"]]
    if not complete:
        return None, "", ""
    last = complete[-1]
    if last["step_no"] >= STEP_FINAL:
        return None, "", ""
    return last["step_no"], TAHAPAN_PUU.get(last["step_no"], ""), last["tanggal"]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def sb_get_submissions():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    url = f"{SUPABASE_URL}/rest/v1/perkara_submissions?select=id,nomor_perkara,link_tracker,is_original"
    req = urllib.request.Request(url, headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[!] Gagal baca Supabase: {e}")
        return []

def sb_update_agenda(row_id, hasil):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    url = f"{SUPABASE_URL}/rest/v1/perkara_submissions?id=eq.{row_id}"
    payload = json.dumps({
        "agenda_terakhir":    hasil["agenda_terakhir"],
        "tgl_terakhir":       hasil["tgl_terakhir"],
        "agenda_selanjutnya": hasil["agenda_selanjutnya"],
        "tgl_selanjutnya":    hasil["tgl_selanjutnya"],
    }).encode()
    req = urllib.request.Request(url, data=payload, headers=sb_headers(), method="PATCH")
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"[!] Gagal update Supabase row {row_id}: {e}")

def scrape_satu(page, no_perkara, custom_url=None):
    if custom_url:
        url = custom_url
    else:
        id_encoded = urllib.parse.quote(str(no_perkara), safe='')
        url = f"https://tracking.mkri.id/index.php?page=web.TrackPerkara&id={id_encoded}"
    hasil = {"agenda_terakhir":"","tgl_terakhir":"","agenda_selanjutnya":"","tgl_selanjutnya":""}
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if "Just a moment" in page.title() or "Cloudflare" in page.title():
            print("    [!] Cloudflare terdeteksi. Mengaktifkan perilaku manusia...")
            page.mouse.move(random.randint(200,600), random.randint(200,600))
            time.sleep(1)
            page.mouse.click(random.randint(200,600), random.randint(200,600))
            time.sleep(10)
        try: page.wait_for_selector(".widget-content table", timeout=15000)
        except: pass
        soup = BeautifulSoup(page.content(), 'html.parser')
        hari_ini = datetime.now().date()
        lewat, depan = [], []
        tabel = soup.select_one(".widget-content table")
        if tabel:
            for baris in tabel.find_all("tr")[1:]:
                kolom = baris.find_all(["td","th"])
                if len(kolom) >= 2:
                    tgl_teks = kolom[1 if len(kolom)>=3 else 0].get_text(separator=" ", strip=True)
                    agenda_teks = kolom[2 if len(kolom)>=3 else 1].get_text(separator=" ", strip=True)
                    try:
                        tgl_obj = datetime.strptime(tgl_teks[:10], "%d-%m-%Y").date()
                        (lewat if tgl_obj <= hari_ini else depan).append({"tgl":tgl_teks,"agenda":agenda_teks})
                    except ValueError: pass
        if lewat:
            hasil["tgl_terakhir"] = lewat[-1]["tgl"]
            hasil["agenda_terakhir"] = lewat[-1]["agenda"]
        if depan:
            hasil["tgl_selanjutnya"] = depan[0]["tgl"]
            hasil["agenda_selanjutnya"] = depan[0]["agenda"]
        if not depan:
            steps = []
            for st in soup.select(".bs-wizard-step"):
                cls = st.get("class",[])
                status = next((c for c in ("complete","active","disabled") if c in cls),"")
                dot = st.select_one(".bs-wizard-dot")
                try: no = int(dot.get("data-step")) if dot and dot.get("data-step") else None
                except: no = None
                h5 = st.find("h5")
                steps.append({"step_no":no,"status":status,"tanggal":h5.text.strip() if h5 else ""})
            _, nama_tahap, tgl_tahap = frontier_menyala(steps)
            if nama_tahap:
                hasil["agenda_selanjutnya"] = nama_tahap
                if tgl_tahap:
                    try:
                        tgl_obj = datetime.strptime(tgl_tahap, "%d-%m-%Y").date()
                        hasil["tgl_selanjutnya"] = tgl_tahap if tgl_obj > hari_ini else "Belum dijadwalkan"
                    except: hasil["tgl_selanjutnya"] = "Belum dijadwalkan"
                else: hasil["tgl_selanjutnya"] = "Belum dijadwalkan"
            else:
                status_el = soup.select_one(".label-info")
                hasil["agenda_selanjutnya"] = status_el.text.strip() if status_el else "Belum Terjadwal"
                hasil["tgl_selanjutnya"] = "Belum dijadwalkan"
    except Exception as e:
        print(f"    [!] Error: {e}")
    return hasil

def jalankan_scraper():
    print(f"Membaca {DATA_PERKARA_FILE}...")
    with open(DATA_PERKARA_FILE, "r", encoding="utf-8") as f:
        data_perkara = json.load(f)
    if os.path.exists(DATA_AGENDA_FILE):
        with open(DATA_AGENDA_FILE, "r", encoding="utf-8") as f:
            data_agenda = json.load(f)
    else:
        data_agenda = {"last_updated":"","agenda":{}}

    daftar_asli = [p["id"] for p in data_perkara["perkara"]]
    submissions = sb_get_submissions()
    print(f"Perkara asli: {len(daftar_asli)} | Perkara komunitas/edit (Supabase): {len(submissions)}\n")

    with sync_playwright() as p:
        # PENTING: headless=False + Xvfb virtual display untuk lolos Cloudflare
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width":1280,"height":720}
        )

        # Scrape perkara asli
        for no_perkara in daftar_asli:
            print(f"[ASLI] Scraping: {no_perkara}")
            page = context.new_page()
            hasil = scrape_satu(page, no_perkara)
            page.close()
            data_agenda["agenda"][no_perkara] = hasil
            print(f"  -> [{hasil['tgl_selanjutnya']}] {hasil['agenda_selanjutnya']}")
            time.sleep(random.uniform(5.5, 9.5))

        # Scrape perkara dari Supabase (komunitas + edited original)
        for sub in submissions:
            nomor = sub.get("nomor_perkara","")
            link = sub.get("link_tracker","") or None
            tag = "[ASLI-EDIT]" if sub.get("is_original") else "[KOMUNITAS]"
            print(f"{tag} Scraping: {nomor}")
            page = context.new_page()
            hasil = scrape_satu(page, nomor, custom_url=link)
            page.close()
            sb_update_agenda(sub["id"], hasil)
            print(f"  -> [{hasil['tgl_selanjutnya']}] {hasil['agenda_selanjutnya']}")
            time.sleep(random.uniform(5.5, 9.5))

        browser.close()

    data_agenda["last_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(DATA_AGENDA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_agenda, f, ensure_ascii=False, indent=2)
    print(f"\nSelesai. data-agenda.json + {len(submissions)} perkara komunitas di Supabase.")

if __name__ == "__main__":
    jalankan_scraper()
