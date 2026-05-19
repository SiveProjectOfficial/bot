import os
import re
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
    # 素材不足を防ぐため、URLが含まれていても、その部分を消して使うように改良！
    clean_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '', text)
    clean_text = re.sub(r'@[\w\.]+', '', clean_text)
    
    # NGワードチェック
    for word in ng_words:
        if word in clean_text:
            return False
    return clean_text.strip()

# --- 日本語をバラバラにする関数 ---
def tokenize(text):
    t = Tokenizer()
    return " ".join([token.surface for token in t.tokenize(text)])

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])

    ng_words = load_ng_words()

    # 1. 「Discover」フィードを探す
    try:
        feeds = client.app.bsky.unspecced.get_popular_feed_generators()
        target_feed = None
        for f in feeds.feeds:
            if "Discover" in f.display_name or "Discovery" in f.display_name:
                target_feed = f.uri
                break
        
        if not target_feed:
            target_feed = 'at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot'

        # 件数を200件に倍増！
        response = client.app.bsky.feed.get_feed({'feed': target_feed, 'limit': 200})
        feed = response.feed
    except Exception as e:
        print(f"取得失敗: {e}")
        return

    cleaned_texts = []
    for item in feed:
        raw_text = item.post.record.text
        safe_text = is_safe(raw_text, ng_words)
        
        if safe_text and len(safe_text) > 5:
            # 日本語が含まれているかチェック
            if re.search(r'[ぁ-んァ-ヶー一-龠]', safe_text):
                cleaned_texts.append(tokenize(safe_text))

    print(f"集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 3:
        print("どうしても素材が足りない！")
        return

    # 2. マルコフ連鎖で混ぜる
    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)

    # 3. 文章生成
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("文章が組み立てられなかった")

if __name__ == "__main__":
    main()
