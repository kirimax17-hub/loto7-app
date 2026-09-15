from flask import Flask, render_template, jsonify
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)

BASE_URL = "https://www.ohtashp.com/topics/takarakuji/loto7/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.6 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}


def year_url(year):
    return f"{BASE_URL}index_{year}.html"


def parse_year(year):
    url = year_url(year)

    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    # 日本語ページの文字コードを自動判定
    r.encoding = r.apparent_encoding

    soup = BeautifulSoup(r.text, "html.parser")

    results = []

    # 各 tr を直接読む
    for tr in soup.find_all("tr"):

        cells = [
            re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
            for td in tr.find_all(["td", "th"])
        ]

        if not cells:
            continue

        row_text = " ".join(cells)

        # 第123回 のような回号を探す
        draw_match = re.search(r"第\s*(\d+)\s*回", row_text)

        if not draw_match:
            continue

        draw = int(draw_match.group(1))

        # 日付を探す
        date_match = re.search(
            r"(20\d{2})/(\d{1,2})/(\d{1,2})",
            row_text
        )

        if not date_match:
            continue

        y, m, d = map(int, date_match.groups())
        date = f"{y:04d}-{m:02d}-{d:02d}"

        # セルから1～37の数字を取得
        numbers = []

        for cell in cells:

            # 回号や日付のセルは除外
            if "第" in cell and "回" in cell:
                continue

            if re.search(r"20\d{2}/\d{1,2}/\d{1,2}", cell):
                continue

            # セルが数字だけの場合
            if re.fullmatch(r"\d{1,2}", cell):
                n = int(cell)

                if 1 <= n <= 37:
                    numbers.append(n)

        # 最初の7個＝本数字
        # 次の2個＝ボーナス数字
        if len(numbers) >= 9:

            main = numbers[:7]
            bonus = numbers[7:9]

            results.append({
                "draw": draw,
                "date": date,
                "main": main,
                "bonus": bonus
            })

    return results


def fetch_history():

    all_results = {}

    # 2013～2023は年別ページ
    for year in range(2013, 2024):
        try:
            rows = parse_year(year)

            print(f"YEAR {year}: {len(rows)} records", flush=True)

            for row in rows:
                all_results[row["draw"]] = row

        except Exception as e:
            print(f"YEAR ERROR {year}: {repr(e)}", flush=True)

    # 2024年以降は現在のメインページから取得
    try:
        url = BASE_URL

        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding

        soup = BeautifulSoup(r.text, "html.parser")

        current_results = []

        for tr in soup.find_all("tr"):

            cells = [
                re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
                for td in tr.find_all(["td", "th"])
            ]

            if not cells:
                continue

            row_text = " ".join(cells)

            draw_match = re.search(r"第\s*(\d+)\s*回", row_text)

            if not draw_match:
                continue

            draw = int(draw_match.group(1))

            # 556回以降だけ取得
            if draw < 556:
                continue

            date_match = re.search(
                r"(20\d{2})/(\d{1,2})/(\d{1,2})",
                row_text
            )

            if not date_match:
                continue

            y, m, d = map(int, date_match.groups())
            date = f"{y:04d}-{m:02d}-{d:02d}"

            numbers = []

            for cell in cells:

                if "第" in cell and "回" in cell:
                    continue

                if re.search(r"20\d{2}/\d{1,2}/\d{1,2}", cell):
                    continue

                if re.fullmatch(r"\d{1,2}", cell):
                    n = int(cell)

                    if 1 <= n <= 37:
                        numbers.append(n)

            if len(numbers) >= 9:

                current_results.append({
                    "draw": draw,
                    "date": date,
                    "main": numbers[:7],
                    "bonus": numbers[7:9]
                })

        print(
            f"CURRENT PAGE: {len(current_results)} records",
            flush=True
        )

        for row in current_results:
            all_results[row["draw"]] = row

    except Exception as e:
        print("CURRENT PAGE ERROR:", repr(e), flush=True)

    results = list(all_results.values())
    results.sort(key=lambda x: x["draw"])

    print(f"TOTAL HISTORY: {len(results)} records", flush=True)

    if results:
        print(
            f"FIRST DRAW: {results[0]['draw']} / "
            f"LATEST DRAW: {results[-1]['draw']}",
            flush=True
        )

    return results


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/history")
def history():

    data = fetch_history()

    if not data:
        return jsonify({
            "ok": False,
            "error": "過去のロト7データを取得できませんでした。"
        }), 500

    return jsonify({
        "ok": True,
        "count": len(data),
        "first_draw": data[0]["draw"],
        "latest_draw": data[-1]["draw"],
        "history": data
    })


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
