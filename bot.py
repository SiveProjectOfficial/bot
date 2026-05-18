import random
import re
import json
import urllib.request
from bs4 import BeautifulSoup

# --- 1. Blueskyの認証設定 (GitHubのSecretsに保存する名前だよ) ---
# 後でGitHubのSettingsからこの3つを登録するだけでOK！
# BSKY_HANDLE: 自分のID (例: seigenha.bsky.social)
# BSKY_PASSWORD: アプリパスワード (合鍵)
import os
HANDLE = os.getenv("BSKY_HANDLE")
PASSWORD = os.getenv("BSKY_PASSWORD")

# --- 2. UTAU @wiki から文章を密輸 (ここは最強のまま！) ---
def get_site_text():
    try:
        url = "https://w.atwiki.jp/utaou/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(html, 'html.parser')
        main_content = soup.find('div', id='wikibody')
        site_text = main_content.get_text() if main_content else soup.get_text()
        return re.sub(r'\s+', ' ', site_text)
    except:
        return "UTAU音源の原音設定は周波数表。連続音と単独音のエイリアス。"

# --- 3. マルコフ連鎖エンジン (正弦波くんの脳みそ) ---
def generate_markov_text():
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

# --- 4. Blueskyへポスト (イーロンに1円も払わない魔法) ---
def send_bsky_post(text):
    # ログインしてトークンをもらう
    auth_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    auth_data = json.dumps({"identifier": HANDLE, "password": PASSWORD}).encode("utf-8")
    req = urllib.request.Request(auth_url, data=auth_data, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req) as res:
        login_info = json.load(res)
        access_token = login_info["accessJwt"]
        did = login_info["did"]

    # 投稿する
    post_url = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    post_data = json.dumps({
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": {
            "text": text,
            "createdAt": now,
            "$type": "app.bsky.feed.post"
        }
    }).encode("utf-8")
    
    req_post = urllib.request.Request(post_url, data=post_data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    })
    
    with urllib.request.urlopen(req_post) as res_post:
        if res_post.getcode() == 200:
            print(f"【青い空に到達】正弦波くん: {text}")

if __name__ == "__main__":
    generated_text = generate_markov_text()
    send_bsky_post(generated_text)
