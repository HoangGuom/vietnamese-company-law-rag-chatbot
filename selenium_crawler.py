"""
SELENIUM CRAWLER - GIẢ LẬP NGƯỜI DÙNG TRÊN EDGE
=================================================
Crawl toàn bộ văn bản Luật Doanh nghiệp VN mới nhất từ vbpl.vn:
  - 67/VBHN-VPQH  (VB hợp nhất 2025, MỚI NHẤT - ưu tiên)
  - 76/2025/QH15  (Luật sửa đổi 2025)
  - 59/2020/QH14  (Luật gốc 2020)
  - 03/2022/QH15  (Luật sửa đổi 2022)
  - Nghị định 01/2021/NĐ-CP (đăng ký doanh nghiệp)
  - Nghị định 168/2025/NĐ-CP (đăng ký DN mới nhất)
  - Thông tư 01/2021/TT-BKHĐT (hướng dẫn đăng ký doanh nghiệp)
  - Thông tư 02/2023/TT-BKHĐT (sửa đổi Thông tư 01/2021)
  - VBHN 6568/VBHN-BKHĐT 2024 (văn bản hợp nhất hướng dẫn đăng ký doanh nghiệp)

Cài: pip install selenium webdriver-manager pdfplumber
Chạy: python selenium_crawler.py
"""

import os, re, json, time, random, sys, unicodedata
import pdfplumber
import requests
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urljoin, urlparse
from collections import Counter

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.microsoft import EdgeChromiumDriverManager


# ============================================================
# DANH SÁCH VĂN BẢN CẦN CRAWL (cập nhật đến 30/05/2026)
# ============================================================

LAW_LIST = [
    # --- ƯU TIÊN 1: Văn bản hợp nhất (đã tích hợp tất cả sửa đổi) ---
    {
        "ten": "VB hợp nhất Luật Doanh nghiệp 2025",
        "so_hieu": "67/VBHN-VPQH",
        "loai": "hopnhat",
        "hieu_luc": "01/07/2025",
        "tu_khoa_tim": "67/VBHN-VPQH luật doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Van-ban-hop-nhat-67-VBHN-VPQH-2025-Luat-Doanh-nghiep-671127.aspx",
        "uu_tien": 1,
    },
    # --- ƯU TIÊN 2: Luật sửa đổi mới nhất 2025 ---
    {
        "ten": "Luật sửa đổi bổ sung Luật Doanh nghiệp 2025",
        "so_hieu": "76/2025/QH15",
        "loai": "luat",
        "hieu_luc": "01/07/2025",
        "tu_khoa_tim": "76/2025/QH15 luật doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Doanh-nghiep-sua-doi-2025-so-76-2025-QH15-659899.aspx",
        "uu_tien": 2,
    },
    # --- ƯU TIÊN 3: Luật gốc 2020 ---
    {
        "ten": "Luật Doanh nghiệp 2020",
        "so_hieu": "59/2020/QH14",
        "loai": "luat",
        "hieu_luc": "01/01/2021",
        "tu_khoa_tim": "59/2020/QH14 luật doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Doanh-nghiep-so-59-2020-QH14-427301.aspx",
        "uu_tien": 3,
    },
    # --- ƯU TIÊN 4: Luật sửa đổi 2022 ---
    {
        "ten": "Luật sửa đổi bổ sung Luật Doanh nghiệp 2022",
        "so_hieu": "03/2022/QH15",
        "loai": "luat",
        "hieu_luc": "01/03/2022",
        "tu_khoa_tim": "03/2022/QH15 sửa đổi doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/dau-tu/Luat-sua-doi-Luat-Dau-tu-cong-Luat-Dau-tu-theo-phuong-thuc-doi-tac-cong-tu-486653.aspx",
        "uu_tien": 4,
    },
    # --- ƯU TIÊN 5: Nghị định đăng ký DN mới nhất ---
    {
        "ten": "Nghị định 168/2025/NĐ-CP đăng ký doanh nghiệp",
        "so_hieu": "168/2025/NĐ-CP",
        "loai": "nghi_dinh",
        "hieu_luc": "01/07/2025",
        "tu_khoa_tim": "168/2025/NĐ-CP đăng ký doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Nghi-dinh-168-2025-ND-CP-dang-ky-doanh-nghiep-623074.aspx",
        "uu_tien": 5,
    },
    # --- ƯU TIÊN 6: Nghị định nền tảng trước khi thay thế ---
    {
        "ten": "Nghị định 01/2021/NĐ-CP đăng ký doanh nghiệp",
        "so_hieu": "01/2021/NĐ-CP",
        "loai": "nghi_dinh",
        "hieu_luc": "04/01/2021",
        "tu_khoa_tim": "01/2021/NĐ-CP đăng ký doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Nghi-dinh-01-2021-ND-CP-dang-ky-doanh-nghiep-283247.aspx",
        "uu_tien": 6,
        "expected_min_articles": 80,
    },
    # --- ƯU TIÊN 7: Thông tư hướng dẫn đăng ký doanh nghiệp ---
    {
        "ten": "Thông tư 01/2021/TT-BKHĐT hướng dẫn đăng ký doanh nghiệp",
        "so_hieu": "01/2021/TT-BKHĐT",
        "loai": "thong_tu",
        "hieu_luc": "01/05/2021",
        "tu_khoa_tim": "01/2021/TT-BKHĐT hướng dẫn đăng ký doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Thong-tu-01-2021-TT-BKHDT-huong-dan-dang-ky-doanh-nghiep-465911.aspx",
        "uu_tien": 7,
    },
    # --- ƯU TIÊN 8: Thông tư sửa đổi 2023 ---
    {
        "ten": "Thông tư 02/2023/TT-BKHĐT sửa đổi Thông tư 01/2021/TT-BKHĐT",
        "so_hieu": "02/2023/TT-BKHĐT",
        "loai": "thong_tu",
        "hieu_luc": "01/07/2023",
        "tu_khoa_tim": "02/2023/TT-BKHĐT sửa đổi Thông tư 01/2021/TT-BKHĐT",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Thong-tu-02-2023-TT-BKHDT-sua-doi-Thong-tu-01-2021-TT-BKHDT-dang-ky-doanh-nghiep-563848.aspx",
        "uu_tien": 8,
    },
    # --- ƯU TIÊN 9: Văn bản hợp nhất hướng dẫn đăng ký doanh nghiệp ---
    {
        "ten": "VBHN 6568/VBHN-BKHĐT 2024 thông tư hướng dẫn đăng ký doanh nghiệp",
        "so_hieu": "6568/VBHN-BKHĐT",
        "loai": "vb_hop_nhat",
        "hieu_luc": "19/08/2024",
        "tu_khoa_tim": "6568/VBHN-BKHĐT hướng dẫn đăng ký doanh nghiệp",
        "url_truc_tiep": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Van-ban-hop-nhat-6568-VBHN-BKHDT-2024-Thong-tu-huong-dan-dang-ky-doanh-nghiep-622234.aspx",
        "uu_tien": 9,
    },
]

DOWNLOAD_DIR = str(Path("./downloads").absolute())
OUTPUT_JSON  = "legal_chunks.json"
MAX_CHUNK_CHARS = 6000
CHUNK_OVERLAP_CHARS = 500
TRUSTED_DOWNLOAD_DOMAINS = {
    "thuvienphapluat.vn",
    "www.thuvienphapluat.vn",
    "m.thuvienphapluat.vn",
    "files.thuvienphapluat.vn",
    "cdn.thuvienphapluat.vn",
    "vbpl.vn",
    "www.vbpl.vn",
    "datafiles.chinhphu.vn",
    "vanban.chinhphu.vn",
}


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class LegalChunk:
    chunk_id: str
    ten_van_ban: str
    so_hieu: str
    loai: str
    hieu_luc: str
    chuong: Optional[str]
    ten_chuong: Optional[str]
    so_dieu: str
    ten_dieu: str
    noi_dung: str
    nguon: str
    source_url: Optional[str]
    source_file: Optional[str]
    parent_chunk_id: Optional[str] = None
    part_index: int = 1
    part_total: int = 1
    char_count: int = 0


def configure_console_encoding() -> None:
    """Keep Vietnamese output readable on Windows terminals."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


# ============================================================
# KHỞI TẠO EDGE DRIVER
# ============================================================

def create_driver(headless: bool = False) -> webdriver.Edge:
    """Tạo Edge driver giả lập người dùng thật"""
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1366,768")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    )

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }
    opts.add_experimental_option("prefs", prefs)

    driver = webdriver.Edge(
        service=Service(EdgeChromiumDriverManager().install()),
        options=opts,
    )

    # Ẩn dấu hiệu Selenium
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ============================================================
# HELPER: HÀNH ĐỘNG GIẢ LẬP NGƯỜI THẬT
# ============================================================

def delay(min_s=0.8, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))

def scroll(driver, px=400):
    driver.execute_script(f"window.scrollBy(0, {px});")
    delay(0.3, 0.6)

def click(driver, by, selector, timeout=12):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )
    ActionChains(driver).move_to_element(el).perform()
    delay(0.3, 0.5)
    el.click()
    return el

def find(driver, by, selector, timeout=12):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, selector))
    )


def _trusted_url(url: str) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return host in TRUSTED_DOWNLOAD_DOMAINS or any(host.endswith(f".{d}") for d in TRUSTED_DOWNLOAD_DOMAINS)


def _resolve_url(href: str, base_url: str) -> str:
    if not href:
        return ""
    return urljoin(base_url, href)


# ============================================================
# BƯỚC A: TÌM KIẾM VĂN BẢN TRÊN VBPL.VN
# ============================================================

def tim_kiem_van_ban(driver: webdriver.Edge, law: dict) -> Optional[str]:
    """
    Trả về URL nguồn chính thức đã kiểm chứng.
    Script hiện không phụ thuộc vào trang tìm kiếm vbpl.vn vì trang đó bị chặn với automation.
    """
    direct_url = law.get("url_truc_tiep")
    if direct_url:
        print(f"  → Dùng URL trực tiếp: {direct_url}")
        return direct_url

    return None


# ============================================================
# BƯỚC B: BẤM NÚT TẢI VỀ → DOWNLOAD PDF
# ============================================================

def bam_tai_ve(driver: webdriver.Edge, law: dict) -> Optional[str]:
    """
    Giả lập bấm nút Tải về trên trang toàn văn.
    Ưu tiên: tìm link PDF → download trực tiếp.
    Fallback: extract text từ trang.
    """
    scroll(driver, 200)
    delay(0.5, 1.0)

    # FIX #7: dùng _ascii_slug() thay cho re.sub(r"[^\w]", "_", ...) để
    # tên file luôn thuần ASCII, nhất quán trên mọi OS và locale Windows.
    so_hieu_slug = _ascii_slug(law["so_hieu"])

    # --- Thử tìm link PDF ---
    pdf_url = None
    for sel in [
        "a[href$='.pdf']", "a[href*='.pdf']",
        "a[title*='Tải']", "a[title*='tải']",
        "//a[contains(text(),'Tải về')]",
        "//a[contains(text(),'Bản PDF')]",
        "//input[@value='Tải về']",
        ".download", "a[href*='download']",
    ]:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel)))
            href = _resolve_url(el.get_attribute("href") or "", driver.current_url)
            if href:
                if not _trusted_url(href):
                    print(f"  ⚠️  Bỏ qua link tải ngoài nguồn tin cậy: {href}")
                    continue
                pdf_url = href
                print(f"  → Nút tải: '{el.text or sel[:40]}'")
                break
        except: continue

    # --- Download PDF trực tiếp ---
    direct_download_failed = False
    if pdf_url:
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent"),
            "Referer": driver.current_url,
        }
        try:
            resp = requests.get(pdf_url, cookies=cookies, headers=headers,
                                stream=True, timeout=60)
            if not _trusted_url(resp.url):
                print(f"  ⚠️  Link tải chuyển hướng ra ngoài nguồn tin cậy: {resp.url}")
                direct_download_failed = True
                resp.close()
                return _extract_text_page(driver, so_hieu_slug)
            if resp.status_code == 200 and len(resp.content) > 1000:
                fname = f"{so_hieu_slug}.pdf"
                fpath = Path(DOWNLOAD_DIR) / fname
                with open(fpath, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                content_type = (resp.headers.get("content-type") or "").lower()
                with open(fpath, "rb") as f:
                    header = f.read(4)

                if header == b"%PDF" or "pdf" in content_type:
                    size = fpath.stat().st_size / 1024
                    print(f"  ✅ PDF saved: {fname} ({size:.0f} KB)")
                    return str(fpath)

                print("  ⚠️  Link tải trả về nội dung không phải PDF thật, chuyển sang trích xuất từ trang...")
                direct_download_failed = True
                try:
                    fpath.unlink()
                except OSError:
                    pass
        except Exception as e:
            print(f"  ⚠️  Download lỗi: {e}")

    if direct_download_failed:
        return _extract_text_page(driver, so_hieu_slug)

    # --- Fallback: bấm nút và chờ download ---
    for sel in ["//a[contains(text(),'Tải về')]", "a.btn-download",
                "//input[@value='Tải về']"]:
        try:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel)))
            href = _resolve_url(el.get_attribute("href") or "", driver.current_url)
            if href and not _trusted_url(href):
                print(f"  ⚠️  Bỏ qua nút tải ngoài nguồn tin cậy: {href}")
                continue
            ActionChains(driver).move_to_element(el).perform()
            delay(0.5, 1.0)
            el.click()
            path = _cho_download(so_hieu_slug)
            if path:
                return path
        except: continue

    # --- Fallback cuối: extract text từ trang HTML ---
    print("  ⚠️  Không tìm thấy PDF, extract text từ trang...")
    return _extract_text_page(driver, so_hieu_slug)


def _cho_download(slug: str, timeout=45) -> Optional[str]:
    """Chờ file PDF download hoàn tất"""
    dl_dir = Path(DOWNLOAD_DIR)
    start = time.time()
    while time.time() - start < timeout:
        pdfs = [p for p in dl_dir.glob("*.pdf")
                if not p.name.endswith(".crdownload")]
        if pdfs:
            latest = max(pdfs, key=lambda p: p.stat().st_mtime)
            # Đợi file không còn thay đổi kích thước
            size1 = latest.stat().st_size
            time.sleep(1)
            size2 = latest.stat().st_size
            if size1 == size2 and size2 > 5000:
                print(f"  ✅ Download xong: {latest.name} ({size2/1024:.0f} KB)")
                return str(latest)
        time.sleep(1)
    return None


def _extract_text_page(driver: webdriver.Edge, slug: str) -> Optional[str]:
    """Lưu text từ trang web ra file .txt"""
    try:
        content = None
        for sel in [
            "div#divNoiDung",
            "div#divContentDoc",
            "div#divNDVB",
            "div#toanVanBan",
            "div.toanvan",
            "div.content-law",
            "div.vanban-content",
            "article",
            "main",
        ]:
            try:
                content = driver.find_element(By.CSS_SELECTOR, sel)
                break
            except: continue

        text = content.text if content else driver.find_element(By.TAG_NAME, "body").text
        fpath = Path(DOWNLOAD_DIR) / f"{slug}.txt"
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  ✅ Text saved: {fpath.name} ({len(text)} ký tự)")
        return str(fpath)
    except Exception as e:
        print(f"  ❌ Lỗi extract: {e}")
        return None


# ============================================================
# BƯỚC C: EXTRACT TEXT TỪ FILE
# ============================================================

def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        return _read_pdf(file_path)
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

def _read_pdf(path: str) -> str:
    print(f"  Đọc PDF: {Path(path).name}")
    parts = []
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        print(f"  Tổng trang: {total}")
        for i, page in enumerate(pdf.pages):
            t = page.extract_text(x_tolerance=2, y_tolerance=2)
            if t:
                parts.append(t)
            if (i+1) % 30 == 0:
                print(f"  Trang {i+1}/{total}...")
    result = "\n".join(parts)
    print(f"  ✅ Extracted {len(result):,} ký tự")
    return result


# ============================================================
# BƯỚC D: PARSE THÀNH CHUNKS
# ============================================================

def _strip_accents(text: str) -> str:
    # Đ/đ (U+0110/U+0111) không phân rã được trong NFD nên cần xử lý riêng
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _line_key(text: str) -> str:
    key = _strip_accents(text).lower()
    key = re.sub(r"\s+", " ", key).strip()
    return key


def _ascii_slug(text: str) -> str:
    """
    FIX #7: Tạo slug ASCII thuần túy, không phụ thuộc locale của \\w.
    Bỏ dấu tiếng Việt → lowercase → thay mọi ký tự không phải [a-z0-9] bằng '_'.
    Ví dụ: '168/2025/NĐ-CP' → '168_2025_nd_cp'
    """
    no_accent = _strip_accents(text).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", no_accent)
    return slug.strip("_")


def _is_article_heading(line: str) -> Optional[re.Match]:
    return re.match(
        r"^\s*(?:Điều|Đ\s*i\s*u|D\s*i\s*u)\s*(\d+[a-zA-Z]?)\s*[\.:\s]+(.+?)\s*$",
        line,
        re.IGNORECASE,
    )


def _is_chapter_heading(line: str) -> Optional[re.Match]:
    return re.match(
        r"^\s*(?:Chương|Ch\s*ương|Ch\s*ng)\s+([IVXLCDM\d]+)\s*[\.:\s]*(.*?)\s*$",
        line,
        re.IGNORECASE,
    )


def _looks_like_chapter_title(line: str) -> bool:
    """
    FIX #6: Mở rộng nhận diện tên chương — chấp nhận cả Title Case lẫn ALL CAPS.
    Logic cũ chỉ nhận ALL CAPS (>= 65% ký tự hoa) nên bỏ sót tên chương dạng
    title case trong văn bản hợp nhất 67/VBHN-VPQH.

    Tiêu chí bổ sung: dòng bắt đầu bằng chữ hoa, <= 12 từ, không phải heading
    Điều/Chương, không nằm trong blacklist.
    """
    text = line.strip()
    if len(text) < 4:
        return False
    if _is_article_heading(text) or _is_chapter_heading(text):
        return False
    if _line_key(text) in {
        "noi dung",
        "tai ve",
        "tieng anh english",
        "lien quan hieu luc",
        "lien quan noi dung",
    }:
        return False
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False

    # ALL CAPS: >= 65% chữ hoa (giữ nguyên logic cũ, tốt cho file PDF scan)
    upper_letters = [ch for ch in letters if ch.upper() == ch]
    if len(upper_letters) / len(letters) >= 0.65:
        return True

    # Title Case: ký tự alpha đầu tiên là hoa + dòng ngắn (<= 12 từ)
    # Câu văn thường dài và có nhiều từ thường ở giữa; tên chương ngắn.
    first_alpha = next((ch for ch in text if ch.isalpha()), "")
    if (
        first_alpha
        and first_alpha == first_alpha.upper()
        and first_alpha != first_alpha.lower()
        and len(text.split()) <= 12
    ):
        return True

    return False


def _clean_chapter_title(title: str) -> Optional[str]:
    title = re.sub(r"\s+", " ", title).strip(" .:-")
    if not title:
        return None
    if _line_key(title) in {"u o", "u", "o"}:
        return None
    return title


def _next_chapter_title(lines: list[str], start_idx: int) -> Optional[str]:
    for offset in range(1, 5):
        idx = start_idx + offset
        if idx >= len(lines):
            break
        candidate = lines[idx].strip()
        if _looks_like_chapter_title(candidate):
            return _clean_chapter_title(candidate)
    return None


def _law_slug(so_hieu: str) -> str:
    """Slug dùng trong chunk_id — gọi _ascii_slug để đảm bảo ASCII thuần túy."""
    return _ascii_slug(so_hieu)


def _split_long_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n{1,}", text) if p.strip()]
    parts: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            parts.append(current.strip())
            current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            flush()
            start = 0
            while start < len(paragraph):
                end = min(start + max_chars, len(paragraph))
                if end < len(paragraph):
                    boundary = max(
                        paragraph.rfind(". ", start, end),
                        paragraph.rfind("; ", start, end),
                        paragraph.rfind(", ", start, end),
                    )
                    if boundary > start + max_chars // 2:
                        end = boundary + 1
                parts.append(paragraph[start:end].strip())
                start = end
            continue

        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) > max_chars:
            flush()
            current = paragraph
        else:
            current = candidate

    flush()
    return [part for part in parts if part]


def parse_chunks(raw: str, law: dict, source: str, source_url: str, source_file: str) -> list[LegalChunk]:
    chunks: list[LegalChunk] = []
    cur_chuong = None
    cur_ten_chuong = None

    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    # Tìm tất cả Điều
    positions = []
    for idx, line in enumerate(lines):
        m = _is_chapter_heading(line)
        if m:
            cur_chuong = f"Chương {m.group(1).strip()}"
            cur_ten_chuong = _clean_chapter_title(m.group(2)) or _next_chapter_title(lines, idx)
            continue

        m = _is_article_heading(line)
        if m:
            positions.append({
                "idx": idx,
                "so_dieu": f"Điều {m.group(1).strip()}",
                "ten_dieu": m.group(2).strip(),
                "chuong": cur_chuong,
                "ten_chuong": cur_ten_chuong,
            })

    print(f"  → Parse được {len(positions)} Điều luật")

    # Đếm trước tổng số lần mỗi base_id xuất hiện trong văn bản này.
    # FIX: Đã chuyển sang dùng _ascii_slug để tạo base_id sạch không lỗi font chữ Việt.
    law_slug = _law_slug(law["so_hieu"])
    base_id_totals: Counter = Counter(
        f"{law_slug}_{_ascii_slug(pos['so_dieu'])}"
        for pos in positions
    )
    seen_ids: dict[str, int] = {}

    for i, pos in enumerate(positions):
        start = pos["idx"] + 1
        end   = positions[i + 1]["idx"] if i + 1 < len(positions) else len(lines)
        content_lines = [l for l in lines[start:end] if len(l) > 3]
        noi_dung = "\n".join(content_lines)
        if len(noi_dung) < 20:
            continue

        # FIX: Sửa đổi tạo id thuần ASCII ở đây giúp đồng bộ hệ thống RAG
        dieu_slug = _ascii_slug(pos["so_dieu"])
        base_id  = f"{law_slug}_{dieu_slug}"
        seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
        occurrence = seen_ids[base_id]

        if base_id_totals[base_id] > 1:
            # Điều trùng số: thêm _lan_N ngay từ lần đầu
            parent_id = f"{base_id}_lan_{occurrence}"
        else:
            parent_id = base_id

        header = f"{pos['so_dieu']}. {pos['ten_dieu']}"
        # FIX #4: Đảm bảo max_body_chars luôn dương và đủ lớn để split hoạt động.
        max_body_chars = max(MAX_CHUNK_CHARS - len(header) - 40, 500)
        body_parts = _split_long_text(noi_dung, max_body_chars)
        total_parts = len(body_parts)

        for part_index, body in enumerate(body_parts, 1):
            if total_parts == 1:
                chunk_id   = parent_id
                part_label = ""
            else:
                chunk_id   = f"{parent_id}_part_{part_index:02d}"
                part_label = f"\n[Phần {part_index}/{total_parts}]"

            full_text = f"{header}{part_label}\n{body}"
            # FIX #2: Gán đủ tất cả 4 field bổ sung của LegalChunk dataclass
            chunks.append(LegalChunk(
                chunk_id=chunk_id,
                ten_van_ban=law["ten"],
                so_hieu=law["so_hieu"],
                loai=law["loai"],
                hieu_luc=law["hieu_luc"],
                chuong=pos["chuong"],
                ten_chuong=pos["ten_chuong"],
                so_dieu=pos["so_dieu"],
                ten_dieu=pos["ten_dieu"],
                noi_dung=full_text,
                nguon=source,
                source_url=source_url,
                source_file=source_file,
                parent_chunk_id=parent_id,
                part_index=part_index,
                part_total=total_parts,
                char_count=len(full_text),
            ))

    return chunks


def validate_law_chunks(chunks: list[LegalChunk], law: dict) -> bool:
    ok = True
    article_count = len({chunk.so_dieu for chunk in chunks})
    expected_min_articles = law.get("expected_min_articles")
    if expected_min_articles and article_count < expected_min_articles:
        ok = False
        print(
            f"  ⚠️  {law['so_hieu']} chỉ parse được "
            f"{article_count}/{expected_min_articles} Điều. "
            "Nguồn tải có thể bị cắt hoặc không phải toàn văn."
        )

    empty_chapters = sum(1 for chunk in chunks if not chunk.ten_chuong)
    if chunks and empty_chapters == len(chunks):
        print(f"  ⚠️  {law['so_hieu']} chưa nhận được tên chương nào.")

    max_len = max((len(chunk.noi_dung) for chunk in chunks), default=0)
    if max_len > MAX_CHUNK_CHARS + 200:
        ok = False
        print(f"  ⚠️  {law['so_hieu']} còn chunk quá dài: {max_len:,} ký tự.")

    return ok


def validate_all_chunks(chunks: list[LegalChunk]) -> bool:
    ok = True
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    duplicate_ids = [chunk_id for chunk_id, count in Counter(chunk_ids).items() if count > 1]
    if duplicate_ids:
        ok = False
        preview = ", ".join(duplicate_ids[:10])
        print(f"⚠️  Còn {len(duplicate_ids)} chunk_id trùng: {preview}")

    too_large = [chunk for chunk in chunks if len(chunk.noi_dung) > MAX_CHUNK_CHARS + 200]
    if too_large:
        ok = False
        print(f"⚠️  Còn {len(too_large)} chunks quá lớn; max={max(len(c.noi_dung) for c in too_large):,}")

    empty_ten_chuong = sum(1 for chunk in chunks if not chunk.ten_chuong)
    if chunks:
        print(
            f"Kiểm tra chunks: {len(chunks)} chunks, "
            f"{len(duplicate_ids)} ID trùng, "
            f"{empty_ten_chuong} thiếu ten_chuong, "
            f"max={max(len(c.noi_dung) for c in chunks):,} ký tự."
        )

    return ok


# ============================================================
# LƯU KẾT QUẢ
# ============================================================

def save_chunks(chunks: list[LegalChunk]):
    validate_all_chunks(chunks)
    data = [asdict(c) for c in chunks]
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size_kb = Path(OUTPUT_JSON).stat().st_size / 1024
    print(f"\n{'='*55}")
    print(f"✅ Đã lưu {len(chunks)} chunks → {OUTPUT_JSON} ({size_kb:.1f} KB)")

    count = Counter(c.ten_van_ban for c in chunks)
    print(f"\n📊 Thống kê:")
    for name, n in count.items():
        print(f"   {n:>4} Điều  ←  {name}")

    avg = sum(len(c.noi_dung) for c in chunks) / max(len(chunks), 1)
    print(f"\n   Trung bình: {avg:.0f} ký tự/chunk")
    print(f"\n→ Bước tiếp: python step2_build_vectorstore.py")


# ============================================================
# MAIN
# ============================================================

def main():
    configure_console_encoding()
    print("=" * 55)
    print("CRAWL LUẬT DOANH NGHIỆP VN — EDGE SELENIUM")
    print("Phạm vi: tất cả văn bản đến 30/05/2026")
    print("=" * 55)

    laws = sorted(LAW_LIST, key=lambda x: x["uu_tien"])

    print(f"\nDanh sách {len(laws)} văn bản cần crawl:")
    for law in laws:
        print(f"  [{law['uu_tien']}] {law['so_hieu']:25s} — {law['ten'][:45]}")

    print("\nMở Edge... (headless=False → thấy trình duyệt thao tác)")
    driver = create_driver(headless=False)
    all_chunks: list[LegalChunk] = []

    try:
        for i, law in enumerate(laws):
            print(f"\n{'─'*55}")
            print(f"[{i+1}/{len(laws)}] {law['so_hieu']} — {law['ten']}")
            print(f"{'─'*55}")

            url = tim_kiem_van_ban(driver, law)
            if not url:
                print(f"  ❌ Không tìm được URL, bỏ qua")
                continue

            if driver.current_url != url:
                driver.get(url)
                delay(2, 3)

            file_path = bam_tai_ve(driver, law)
            if not file_path:
                print(f"  ❌ Không lấy được file, bỏ qua")
                continue

            raw_text = extract_text(file_path)
            if not raw_text or len(raw_text) < 500:
                print(f"  ❌ Text quá ngắn ({len(raw_text)} ký tự), bỏ qua")
                continue

            source      = "pdf" if file_path.endswith(".pdf") else "html"
            source_url  = url
            source_file = str(Path(file_path).resolve())
            chunks      = parse_chunks(raw_text, law, source, source_url, source_file)
            validate_law_chunks(chunks, law)
            all_chunks.extend(chunks)
            print(f"  ✅ {law['so_hieu']}: {len(chunks)} chunks")

            if i < len(laws) - 1:
                wait = random.uniform(3, 6)
                print(f"  ⏳ Đợi {wait:.1f}s trước văn bản tiếp theo...")
                time.sleep(wait)

    except KeyboardInterrupt:
        print("\n⚠️  Bị dừng bởi người dùng")
    finally:
        print("\nĐóng Edge...")
        driver.quit()

    if all_chunks:
        save_chunks(all_chunks)
    else:
        print("\n❌ Không có dữ liệu nào được crawl.")
        print("   Kiểm tra kết nối mạng và thử lại.")


if __name__ == "__main__":
    main()