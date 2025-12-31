"""
A simple web scraper used to retrieve game documentation from figgie.com.

Usage:
> pip install trafilatura requests beautifulsoup4
> python scrape.py
"""

import os, re, time, json, hashlib
from collections import deque
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup
import trafilatura

START = "https://www.figgie.com/"
ALLOWED_NETLOCS = {"www.figgie.com", "figgie.com"}

OUTDIR = "docs"
DELAY_S = 1.0
MAX_PAGES = 500  # safety cap; raise if needed

os.makedirs(OUTDIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; doc-scraper; +you@example.com)"
})

def same_site(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc in ALLOWED_NETLOCS

def normalize(url: str) -> str:
    url = urldefrag(url).url
    # drop common tracking params (keep it simple)
    p = urlparse(url)
    if p.query:
        # keep query only if you *know* it's meaningful; otherwise remove
        url = p._replace(query="").geturl()
    return url

def slug_for(url: str) -> str:
    p = urlparse(url)
    path = p.path.strip("/") or "index"
    # filesystem-safe
    path = re.sub(r"[^a-zA-Z0-9/_\-.]", "_", path)
    # avoid collisions
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{path}__{h}"

seen = set()
q = deque([START])
manifest = []

while q and len(seen) < MAX_PAGES:
    url = normalize(q.popleft())
    if url in seen or not same_site(url):
        continue
    seen.add(url)
    print("GET", url)

    try:
        r = session.get(url, timeout=20)
        ct = r.headers.get("Content-Type", "")
        if "text/html" not in ct:
            continue

        html = r.text

        # Extract main text
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            output_format="txt",
            favor_recall=True,
        )

        if not text or len(text.strip()) < 80:
            # fallback: basic visible-text extraction
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n")
            text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        slug = slug_for(url)
        outpath = os.path.join(OUTDIR, slug + ".txt")
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")

        manifest.append({"url": url, "file": outpath, "chars": len(text)})

        # Discover more URLs
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            nxt = normalize(urljoin(url, href))
            if same_site(nxt) and nxt not in seen:
                q.append(nxt)

        time.sleep(DELAY_S)

    except requests.RequestException as e:
        print("  error:", e)

# Save an index so you can browse what you captured
with open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"\nSaved {len(manifest)} pages to {OUTDIR}/ (cap={MAX_PAGES})")

