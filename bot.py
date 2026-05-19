import os
import re
import httpx
from atproto import Client
import markovify
from janome.tokenizer import Tokenizer

# --- 鉄壁のNGワードフィルター ---
def load_ng_words():
    if os.path.exists("ng_words.txt"):
        with open("ng_words.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def is_safe(text, ng_words):
    clean_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '', text)
    clean_text = re.sub(r'@[\w\.]+', '', clean_text)
    clean_text = clean_text.replace("#", " ")
    for word in ng_words:
        if word in clean_text:
            return False
    return clean_text.strip()

def tokenize(text):
    t = Tokenizer()
    return " ".join([token.surface for token in t.tokenize(text)])

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    ng_words = load_ng_words()

    # DiscoverフィードのURI（固定）
    target_feed = 'at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot'

    all_raw_texts = []
    cursor = None
    
    # 【禁断の直接アクセス】ライブラリを使わずHTTPリクエストで言葉を奪い取る！
    for i in range(10): 
        try:
            url = f"https://bsky.social/xrpc/app.bsky.feed.getFeed?feed={target_feed}&limit=100"
            if cursor:
                url += f"&cursor={cursor}"
            
            headers = {"Authorization": f"Bearer {client.get_access_token()}"}
            response = httpx.get(url, headers=headers)
            data = response.json()
            
            for item in data.get('feed', []):
                text = item.get('post', {}).get('record', {}).get('text', '')
                if text:
                    all_raw_texts.append(text)
            
            cursor = data.get('cursor')
            if not cursor: 
                break
        except Exception as e:
            print(f"取得エラー: {e}")
            break

    cleaned_texts = []
    for text in all_raw_texts:
        safe_text = is_safe(text, ng_words)
        if safe_text and len(safe_text) >= 2:
            if re.search(r'[ぁ-んァ-ヶー一-龠]', safe_text):
                cleaned_texts.append(tokenize(safe_text))

    print(f"最終的に集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 3:
        print("素材不足でパズルが組めないよー！")
        return

    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("文章が組めなかった")

if __name__ == "__main__":
    main()
