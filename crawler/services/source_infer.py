# crawler/services/source_infer.py
from urllib.parse import urlparse

DOMAIN_MAP = {
    "www.wipo.int": ("WIPO", "intergovernmental"),
    "wipo.int": ("WIPO", "intergovernmental"),
    "www.copyright.gov": ("US Copyright Office", "government"),
    "copyright.gov": ("US Copyright Office", "government"),
    "www.uspto.gov": ("USPTO", "government"),
    "uspto.gov": ("USPTO", "government"),
    "www.nist.gov": ("NIST", "government"),
    "nist.gov": ("NIST", "government"),
    "www.gov.uk": ("UK Government (GOV.UK)", "government"),
    "gov.uk": ("UK Government (GOV.UK)", "government"),
    "euipo.europa.eu": ("EUIPO", "regulator"),
    "www.epo.org": ("EPO", "regulator"),
    "epo.org": ("EPO", "regulator"),
    "edpb.europa.eu": ("EDPB", "regulator"),
    "www.oecd.org": ("OECD", "intergovernmental"),
    "oecd.org": ("OECD", "intergovernmental"),
    "www.wto.org": ("WTO", "intergovernmental"),
    "wto.org": ("WTO", "intergovernmental"),
    "www.whitehouse.gov": ("The White House", "government"),
    "whitehouse.gov": ("The White House", "government"),
    "www.congress.gov": ("U.S. Congress", "government"),
    "congress.gov": ("U.S. Congress", "government"),
    "www.uschamber.com": ("U.S. Chamber of Commerce", "other"),
    "uschamber.com": ("U.S. Chamber of Commerce", "other"),
    "www.commerce.gov": ("U.S. Department of Commerce", "government"),
    "commerce.gov": ("U.S. Department of Commerce", "government"),
    "patentlyo.com": ("Patently-O", "other"),
    "www.patentlyo.com": ("Patently-O", "other"),
    "www.stateof.ai": ("State of AI Report", "research_center"),
    "stateof.ai": ("State of AI Report", "research_center"),
    "www.jpo.go.jp": ("JPO", "government"),
    "jpo.go.jp": ("JPO", "government"),
    "www.kipo.go.kr": ("KIPO", "government"),
    "kipo.go.kr": ("KIPO", "government"),
    "ipindia.gov.in": ("IPO India", "government"),
    "www.ipindia.gov.in": ("IPO India", "government"),
    "www.ipaustralia.gov.au": ("IP Australia", "government"),
    "ipaustralia.gov.au": ("IP Australia", "government"),
    "ised-isde.canada.ca": ("CIPO (Canada)", "government"),
    "www.ised-isde.canada.ca": ("CIPO (Canada)", "government"),
}


def infer_source(url: str) -> tuple[str, str]:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        host = ""
    if host in DOMAIN_MAP:
        return DOMAIN_MAP[host]
    # fallback: use host as source name
    return host or "Unknown", "other"
