import os
import re
from atproto import Client
import markovify
from janome.tokenizer import Tokenizer

# --- 鉄壁のNGワードフィルター ---
def load_ng_words():
    # ng_words.txt からNGワードを読み込む
    if os.path.exists("ng_words.txt"):
        with open("ng_words.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def is_safe(text, ng_words):
    # URL、メンション、ハッシュタグが含まれる投稿はゴミが混ざるので除外
    if re.search(r"http|@|#", text):
        return False
    
    # 読み込んだNGワードと照らし合わせる
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

    # NGワードリストを読み込み
    ng_words = load_ng_words()

    # 1. タイムライン（おすすめ含む）から投稿を50件取得
    try:
        response = client.get_timeline(limit=50)
        feed = response.feed
    except Exception as e:
        print(f"取得失敗: {e}")
        return

    cleaned_texts = []
    for item in feed:
        text = item.post.record.text
        if is_safe(text, ng_words):
            # 安全な投稿だけをバラバラにする
            cleaned_texts.append(tokenize(text))

    if len(cleaned_texts) < 5:
        print("安全な素材が足りないから今回はお休み！")
        return

    # 2. マルコフ連鎖モデルを作成
    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)

    # 3. 文章を生成（140文字以内）
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("安全な文章が作れなかったよ")

if __name__ == "__main__":
    main()
