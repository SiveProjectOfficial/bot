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

# --- 2. VOCALOIDや音声シンセ系のページから文章を密輸する関数 ---
def get_site_text():
    try:
        # VOCALOID（音声合成ソフト）の解説ページから、ボカロ用語をたっぷり吸い上げるよ！
        url = "https://ja.wikipedia.org/wiki/VOCALOID"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(html, 'html.parser')
        
        # 本文の文字だけを抽出
        paragraphs = soup.find_all('p')
        site_text = "".join([p.text for p in paragraphs])
        
        # 引用番号とかのゴミ掃除
        site_text = re.sub(r'\[\d+\]', '', site_text) 
        return site_text
    except Exception as e:
        print(f"テキスト密輸に失敗したから予備のボカロ文使うね: {e}")
        return "VOCALOIDは、メロディと歌詞を入力することでサンプリングされた人の声を元に歌声を合成する技術である。"

# --- 3. マルコフ連鎖エンジン（ボカロ文 ＋ 正弦波くんの設定） ---
def generate_markov_text(min_len=10, max_len=140):
    scraped_text = get_site_text()
    
    # 正弦波くんの魂（電波成分）を強制注入！
    seigenha_elements = """
    僕は正弦波くん。ストロベリーアイスが大好き。にんじんとツリーハウスは苦手。
    ライオンが来たら怖いから高いところに登るけど高いところも苦手。
    1992年のノートに鉛筆で正弦波の波形を描く。赤いバックパック。
    ジャックはぼくで僕は僕。
    """
    
    full_text = scraped_text + " " + seigenha_elements
    words = re.findall(r'.', full_text.replace('\n', ' '))
    
    if len(words) < 3:
        return "僕は正弦波くん。ボカロの音声を生成するシステムです。"
    
    # マルコフ辞書の作成
    markov_dict = {}
    for i in range(len(words) - 2):
        key = (words[i], words[i+1])
        value = words[i+2]
        if key not in markov_dict:
            markov_dict[key] = []
        markov_dict[key].append(value)
        
    # 文章生成
    for _ in range(30): # ボカロっぽさを厳選するためにリトライ回数を増やしたよ！
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
        # ユマのこだわりを反映させるためのワードチェック！
        if min_len <= len(tweet) <= max_len:
            return tweet
            
    return "歌声合成ソフトウェアは、僕のストロベリーアイスを1992年の正弦波に変換する。"

# --- 4. ポスト（ツイート）送信 ---
def send_tweet(text):
    twitter = OAuth1Session(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}
    
    response = twitter.post(url, json=payload)
    if response.status_code == 201:
        print(f"投稿成功！: {text}")
    else:
        print(f"エラーだよ: {response.status_code}, {response.text}")

if __name__ == "__main__":
    generated_text = generate_markov_text()
    send_tweet(generated_text)
