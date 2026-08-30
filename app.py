
from flask import Flask, render_template, jsonify
import requests
import pandas as pd
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

app = Flask(__name__)

PAYPAY_CURRENT = "https://www.japannetbank.co.jp/lottery/loto/loto7recent.iframe.html"
PAYPAY_BACK_INDEX = "https://www.japannetbank.co.jp/lottery/loto/loto7recent.iframe.html"
HEADERS = {

    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",

    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",

    "Referer": "https://www.paypay-bank.co.jp/" ,

}

def normalize_text(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def digits_from_cell(x):
    vals = []
    for token in re.findall(r"\d+", str(x)):
        try:
            n = int(token)
            if 1 <= n <= 37:
                vals.append(n)
        except:
            pass
    return vals

def parse_draw_number(x):
    s = normalize_text(x)
    m = re.search(r"第?\s*(\d+)\s*回", s)
    if m:
        return int(m.group(1))
    if re.fullmatch(r"\d+", s):
        n = int(s)
        return n if n > 0 else None
    return None

def parse_date(x):
    s = normalize_text(x)
    m = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""

def extract_rows_from_table(df):
    results = []

    df = df.fillna("")

    rows = []
    for _, row in df.iterrows():
        rows.append([normalize_text(v) for v in row.tolist()])

    draw = None
    date = ""
    main_nums = []
    bonus_nums = []

    for items in rows:
        text = " ".join(items)

        # 回号
        if draw is None:
            for v in items:
                d = parse_draw_number(v)
                if d:
                    draw = d
                    break

        # 抽せん日
        if not date:
            for v in items:
                d = parse_date(v)
                if d:
                    date = d
                    break

        # 本数字
        if "本数字" in text:
            nums = digits_from_cell(text)
            if len(nums) >= 7:
                main_nums = nums[:7]

        # ボーナス数字
        if "ボーナス数字" in text:
            nums = digits_from_cell(text)
            if len(nums) >= 2:
                bonus_nums = nums[:2]

    if draw and len(main_nums) == 7:
        results.append({
            "draw": draw,
            "date": date,
            "main": sorted(main_nums),
            "bonus": bonus_nums[:2]
        })

    return results

def discover_links():
    r = requests.get(PAYPAY_BACK_INDEX, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(PAYPAY_BACK_INDEX, a["href"])
        text = a.get_text(" ", strip=True)
        if "type=loto7" in href.lower():
            links.add(href)
        elif ("ロト7" in text or "LOTO7" in text.upper()) and "backnumber" in href and "detail" in href:
            links.add(href)
    return sorted(links)

def fetch_history():
    urls = []
    try:
        urls += discover_links()
    except:
        pass
    urls.append(PAYPAY_CURRENT)

    found = {}
    for url in dict.fromkeys(urls):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            for t in pd.read_html(r.text):
                for rec in extract_rows_from_table(t):
                    found[rec["draw"]] = rec
        except Exception as e:
            print("FETCH ERROR:", url, repr(e), flush=True)
            continue

    return [found[k] for k in sorted(found)]

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/history")
def history():
    data = fetch_history()
    if not data:
        return jsonify({"ok": False, "error": "公式ページからデータを取得できませんでした。"}), 500
    return jsonify({"ok": True, "history": data})

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
