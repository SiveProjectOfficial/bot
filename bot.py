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

# --- 2. UTAU ユーザー互助会 @ wiki から文章を密輸 ---
def get_site_text():
    try:
        # ユマが見つけてくれた本命のWikiを指定！
        url = "https://w.atwiki.jp/utaou/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(html, 'html.parser')
        
        # @wikiの本文エリアを抽出
        main_content = soup.find('div', id='wikibody')
        site_text = main_content.get_text() if main_content else soup.get_text()
        
        # 余計な空白を掃除
        site_text = re.sub(r'\s+', ' ', site_text)
        return site_text
    except Exception as e:
        print(f"密輸失敗: {e}")
        return "UTAUは歌声合成ツールです。原音設定や周波数表が重要です。"

# --- 3. マルコフ連鎖エンジン ---
def generate_markov_text(min_len=10, max_len=140):
    full_text = get_site_text()
    words = re.findall(r'.', full_text)
    
    if len(words) < 3:
        return "UTAUの音源を読み込んでいます。"
    
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
            
    return "歌声合成ツールUTAUの最新情報をチェックしましょう。"

# --- 4. ポスト（ツイート）送信 ---
def send_tweet(text):
    twitter = OAuth1Session(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}
    
    response = twitter.post(url, json=payload)
    if response.status_code == 201:
        print(f"投稿成功！: {text}")
    else:
        print(f"エラー: {response.status_code}")

if __name__ == "__main__":
    generated_text = generate_markov_text()
    send_tweet(generated_text)
