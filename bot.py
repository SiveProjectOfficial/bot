import random
import re
import urllib.request
from bs4 import BeautifulSoup
from requests_oauthlib import OAuth1Session

# --- 1. X (Twitter) API の認証設定 ---
CONSUMER_KEY = "7YIXOVWGd3N9iulB4et39h56c"
CONSUMER_SECRET = "y2Qj2iq6PeGJ4cHkqta6nLEGSR8ONwFDpReYQqL0wbpMY3O2bB"
ACCESS_TOKEN = "2056405722490105856-LUwWbx5BVxtbjzvB5lialvQQD7l28V"
ACCESS_TOKEN_SECRET = "M2RE8Lfhwi5ABCfdYiN7D9L0GgeOv0myfO6Wbb3u7rqdz"

# --- 2. UTAU @wiki から文章を密輸 ---
def get_site_text():
    try:
        url = "https://w.atwiki.jp/utaou/"
        # ガードを突破するために「普通のブラウザ（Chrome）」のふりをする設定を強化！
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
        }
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(html, 'html.parser')
        
        main_content = soup.find('div', id='wikibody')
        site_text = main_content.get_text() if main_content else soup.get_text()
        
        site_text = re.sub(r'\s+', ' ', site_text)
        return site_text
    except Exception as e:
        # 万が一また失敗しても、何かが投稿されるように予備の文を豪華にしたよ！
        print(f"密輸失敗（再挑戦）: {e}")
        return "UTAU音源の原音設定は周波数表。連続音と単独音のエイリアス設定。ツールオプションからエンジンを選択。"

# --- 3. マルコフ連鎖エンジン ---
def generate_markov_text(min_len=10, max_len=140):
    full_text = get_site_text()
    words = re.findall(r'.', full_text)
    
    if len(words) < 3:
        return "UTAUのプロジェクトファイルを読み込みます。"
    
    markov_dict = {}
    for i in range(len(words) - 2):
        key = (words[i], words[i+1])
        value = words[i+2]
        if key not in markov_dict:
            markov_dict[key] = []
        markov_dict[key].append(value)
        
    for _ in range(50):
        current_key = random.choice(list(markov_dict.keys()))
        result = list(current_key)
        
        for _ in range(max_len):
            if current_key in markov_dict:
                next_word = random.choice(markov_dict[current_key])
                result.append(next_word)
                current_key = (current_key[1], next_word)
                if next_word in ["。", "！", "？"] and len(result) >= min_len:
                    break
            else:
                break
                
        tweet = "".join(result).strip()
        if min_len <= len(tweet) <= max_len:
            return tweet
            
    return "歌声合成ソフトウェアUTAUでの調声作業を開始します。"

# --- 4. ポスト（ツイート）送信 ---
def send_tweet(text):
    twitter = OAuth1Session(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}
    
    response = twitter.post(url, json=payload)
    if response.status_code == 201:
        print(f"投稿成功！: {text}")
    else:
        print(f"エラー（X側）: {response.status_code}, {response.text}")

if __name__ == "__main__":
    generated_text = generate_markov_text()
    send_tweet(generated_text)
