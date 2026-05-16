from __future__ import annotations

from pathlib import Path

BASE_URL = "https://benhvienathainguyen.com.vn"
DEFAULT_TIMEOUT = 60
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CATALOG_DIR = DATA_DIR / "catalog"
RAW_HTML_DIR = DATA_DIR / "raw" / "html"
RAW_ASSET_DIR = DATA_DIR / "raw" / "assets"
RAW_EMBED_DIR = DATA_DIR / "raw" / "embeds"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
CANONICAL_DOC_DIR = KNOWLEDGE_BASE_DIR / "canonical_docs"

SEED_URLS = [
    f"{BASE_URL}/",
    f"{BASE_URL}/contact",
    f"{BASE_URL}/faqs",
    f"{BASE_URL}/page/2/gioi-thieu-chung",
    f"{BASE_URL}/articles/category/15/dich-vu-bhyt",
    f"{BASE_URL}/vaccines",
    f"{BASE_URL}/tokhaiyte",
    f"{BASE_URL}/his/book_appointment",
]

SMOKE_TARGET_URLS = [
    f"{BASE_URL}/contact",
    f"{BASE_URL}/his/department/34/khoa-kham-benh",
    f"{BASE_URL}/page/15/quy-trinh-kham-benh",
    f"{BASE_URL}/page/11/bang-gia-vien-phi",
    f"{BASE_URL}/faqs/faq/117/",
]

ALLOWED_PATTERNS = (
    "/his/contact/",
    "/contact",
    "/page/",
    "/his/department/",
    "/articles/category/15/",
    "/article/",
    "/faqs",
    "/faqs/index/",
    "/faqs/faq/",
    "/vaccines",
    "/tokhaiyte",
    "/his/book_appointment",
    "/docs/category/3/",
)

EXCLUDED_PATTERNS = (
    "facebook.com",
    "twitter.com",
    "youtube.com",
    "linkedin.com",
    "mailto:",
    "tel:",
    "javascript:",
    "/videos",
    "/news",
    "/articles/category/1/",
    "/articles/category/3/",
    "/articles/category/4/",
    "/articles/category/5/",
    "/articles/category/8/",
    "/articles/category/11/",
    "/articles/category/25/",
    "/articles/category/26/",
    "/docs/category/4/",
)

TOPIC_GROUP_BY_URL = {
    "/his/contact/": "department",
    "/contact": "hospital_profile",
    "/page/2/": "hospital_profile",
    "/his/department/": "department",
    "/faqs": "faq",
    "/articles/category/15/": "bhyt",
    "/page/15/": "process",
    "/page/16/": "process",
    "/page/17/": "process",
    "/page/11/": "pricing",
    "/page/12/": "pricing",
    "/page/13/": "pricing",
    "/page/14/": "service",
    "/docs/category/3/": "bhyt",
    "/vaccines": "service",
    "/tokhaiyte": "form_guide",
    "/his/book_appointment": "form_guide",
}

BOILERPLATE_PATTERNS = (
    "tin bai moi",
    "cau hoi tu van quan tam",
    "cau hoi tu van moi",
    "share:",
    "addthis",
    "gui cau hoi",
    "partner",
    "doi tac",
    "copyright",
    "scrolltotop",
    "search",
)

DIRECT_FILE_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".csv",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
}

STATIC_RESOURCE_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
    ".webp",
}

KATANA_DEPTH_BY_MODE = {
    "smoke": 1,
    "full": 4,
}

KATANA_DURATION_BY_MODE = {
    "smoke": "20s",
    "full": "4m",
}

PROCESS_OCR_PHRASES = (
    "Quy trình khám bệnh",
    "Quy trình khám sức khỏe",
    "Quy trình khám nội trú",
    "A. Bệnh nhân đối tượng viện phí",
    "B. Bệnh nhân đối tượng BHYT",
    "Bệnh nhân",
    "Lấy số thứ tự đăng ký",
    "Đăng ký sổ khám",
    "Phòng khám, nộp tiền",
    "Trình thẻ BHYT, giấy giới thiệu, đăng ký sổ khám",
    "Chờ khám theo số thứ tự",
    "Đóng tiền các dịch vụ cận lâm sàng",
    "Các cận lâm sàng thực hiện",
    "Lấy kết quả quay về phòng khám",
    "Duyệt toa BHYT",
    "Thanh toán, nhận lại thẻ BHYT",
    "Lĩnh thuốc",
    "Đăng ký khám sức khỏe",
    "Thực hiện cận lâm sàng",
    "Các bàn khám chuyên khoa",
    "Kết luận của phòng khám sức khỏe",
    "Bệnh nhân phòng khám",
    "Nhập khoa",
    "Dự trù và hoàn trả hao phí theo khoa phòng",
    "Tạm ứng viện phí",
    "Công nợ nội trú",
    "Dự trù và hoàn trả hao phí theo bệnh nhân",
    "Chỉ định cận lâm sàng, phẫu thuật thủ thuật",
    "Xuất tủ trực",
    "Xuất khoa",
    "Các xử trí khác",
    "Quá trình nội trú",
    "Kết thúc",
)
