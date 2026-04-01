"""
Shopify Shop Monitor – wtbtcg.it
Läuft via GitHub Actions alle 30 Minuten.
State wird in einem GitHub Gist gespeichert.
"""

import requests
import json
import os
from datetime import datetime

# ─────────────────────────────────────────────
# KONFIGURATION – via GitHub Secrets
# ─────────────────────────────────────────────

SHOP_URL          = "https://wtbtcg.it"
PRODUCTS_API      = f"{SHOP_URL}/products.json"
LIMIT             = 50

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GIST_ID            = os.environ["GIST_ID"]
GIST_FILENAME      = "wtbtcg_state.json"

# ─────────────────────────────────────────────
# GIST – State laden & speichern
# ─────────────────────────────────────────────

GIST_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def load_state():
    try:
        r = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=GIST_HEADERS, timeout=10)
        r.raise_for_status()
        content = r.json()["files"][GIST_FILENAME]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"State laden fehlgeschlagen: {e}")
        return {"known_ids": []}

def save_state(state):
    try:
        payload = {"files": {GIST_FILENAME: {"content": json.dumps(state, indent=2)}}}
        r = requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=GIST_HEADERS, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"State speichern fehlgeschlagen: {e}")

# ─────────────────────────────────────────────
# SHOP API
# ─────────────────────────────────────────────

def fetch_products():
    try:
        r = requests.get(
            PRODUCTS_API,
            params={"limit": LIMIT, "sort_by": "created-descending"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("products", [])
    except requests.RequestException as e:
        print(f"Fehler beim Laden: {e}")
        return None

# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────

def notify_telegram(new_products):
    for p in new_products:
        title  = p.get("title", "Unbekannt")
        handle = p.get("handle", "")
        url    = f"{SHOP_URL}/products/{handle}"
        image  = (p.get("images") or [{}])[0].get("src", "")
        price  = (p.get("variants") or [{}])[0].get("price", "?")
        msg    = f"🆕 *Neues Produkt!*\n[{title}]({url})\nPreis: €{price}"
        if image:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "photo": image,
                      "caption": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        else:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
    print(f"Telegram: {len(new_products)} Nachricht(en) gesendet.")

# ─────────────────────────────────────────────
# HAUPTLOGIK
# ─────────────────────────────────────────────

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Prüfe {PRODUCTS_API} ...")

    products = fetch_products()
    if products is None:
        return

    state     = load_state()
    known_ids = set(str(i) for i in state.get("known_ids", []))

    new_products = [p for p in products if str(p["id"]) not in known_ids]

    if not known_ids:
        print(f"Erster Lauf – {len(products)} Produkte gespeichert.")
    elif new_products:
        print(f"⚡ {len(new_products)} neues Produkt(e) gefunden!")
        for p in new_products:
            print(f"  → {p['title']} (ID {p['id']})")
        notify_telegram(new_products)
    else:
        print(f"Keine neuen Produkte. ({len(products)} bekannt)")

    all_ids = list(set(known_ids) | {str(p["id"]) for p in products})
    state["known_ids"] = all_ids
    save_state(state)

if __name__ == "__main__":
    main()
