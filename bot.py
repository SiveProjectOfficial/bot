import random
import re
import json
import urllib.request
import os
from datetime import datetime, timezone

# --- 1. Blueskyの認証設定 ---
HANDLE = os.getenv("BSKY_HANDLE")
PASSWORD = os.getenv("BSKY_PASSWORD")

# --- 2. UTAU @wiki から文章を密輸 ---
def get_site_text():
    try:
        url = "https://w.atwiki.jp/utaou/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as res:
            html = res.read()
        soup = BeautifulSoup(html, 'html.parser')
        main_content = soup.find('div', id='wikibody')
        site_text = main_content.get_text() if main_content else soup.get_text()
        return re.sub(r'\s+', ' ', site_text)
    except:
        return "UTAU音源の原音設定は周波数表。連続音と単独音のエイリアス。"

# --- 3. マルコフ連鎖エンジン ---
def generate_markov_text():
    from bs4 import BeautifulSoup
    full_text = get_site_text()
    words = re.findall(r'.', full_text)
    if len(words) < 3: return "UTAUのプロジェクトファイルを読み込みます。"
    markov_dict = {}
    for i in range(len(words) - 2):
        key = (words[i], words[i+1]); value = words[i+2]
        if key not in markov_dict: markov_dict[key] = []
        markov_dict[key].append(value)
    current_key = random.choice(list(markov_dict.keys()))
    result = list(current_key)
    for _ in range(130):
        if current_key in markov_dict:
            next_word = random.choice(markov_dict[current_key])
            result.append(next_word)
            current_key = (current_key[1], next_word)
            if next_word in ["。", "！", "？"] and len(result) > 20: break
        else: break
    return "".join(result).strip()

# --- 4. Blueskyへポスト ---
def send_bsky_post(text):
    try:
        # ログイン
        auth_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
        # HANDLEが空だったりミスしてないか確認用
        if not HANDLE or not PASSWORD:
            print("エラー: BSKY_HANDLE または BSKY_PASSWORD が設定されていません！")
            return

        auth_data = json.dumps({"identifier": HANDLE.strip(), "password": PASSWORD.strip()}).encode("utf-8")
        req = urllib.request.Request(auth_url, data=auth_data, headers={"Content-Type": "application/json"})
        
        with urllib.request.urlopen(req) as res:
            login_info = json.load(res)
            access_token = login_info["accessJwt"]
            did = login_info["did"]

        # 投稿
        post_url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        post_payload = {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": {
                "text": text,
                "createdAt": now,
                "$type": "app.bsky.feed.post"
            }
        }
        
        req_post = urllib.request.Request(post_url, data=json.dumps(post_payload).encode("utf-8"), headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        })
        
        with urllib.request.urlopen(req_post) as res_post:
            if res_post.getcode() == 200:
                print(f"【成功】正弦波くんが青い空で叫んだよ: {text}")
    except Exception as e:
        print(f"エラー発生: {e}")
        # もし400エラーが出るなら、Secretsの設定ミス（空白が入ってる等）の可能性大！

if __name__ == "__main__":
    from bs4 import BeautifulSoup
    generated_text = generate_markov_text()
    send_bsky_post(generated_text)
