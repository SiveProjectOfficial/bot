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
    if re.search(r"http|@|#", text):
        return False
    for word in ng_words:
        if word in text:
            return False
    return True

# --- 日本語をバラバラにする関数 ---
def tokenize(text):
    t = Tokenizer()
    return " ".join([token.surface for token in t.tokenize(text)])

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])

    ng_words = load_ng_words()

    # 1. 【最強版】「Discover（おすすめ）」フィードを探して取得
    try:
        # まず「Discover」という名前のフィードを探す
        feeds = client.app.bsky.unspecced.get_popular_feed_generators()
        target_feed = None
        for f in feeds.feeds:
            if "Discover" in f.display_name:
                target_feed = f.uri
                break
        
        # 見つからなかったら「Whats-hot」を予備にする
        if not target_feed:
            target_feed = 'at://did:plc:z7w6ecvfs5sgwga6i6clgqzz/app.bsky.feed.generator/whats-hot'

        print(f"ターゲットフィード: {target_feed}")
        response = client.app.bsky.feed.get_feed({'feed': target_feed, 'limit': 100})
        feed = response.feed
    except Exception as e:
        print(f"取得失敗: {e}")
        return

    cleaned_texts = []
    for item in feed:
        text = item.post.record.text
        if is_safe(text, ng_words):
            if re.search(r'[ぁ-んァ-ヶー一-龠]', text):
                cleaned_texts.append(tokenize(text))

    if len(cleaned_texts) < 5:
        print("素材不足！")
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
        print("文章が作れなかった")

if __name__ == "__main__":
    main()
