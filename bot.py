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
    # 1. URL（画像リンクなど）を完全に抹消
    clean_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '', text)
    
    # 2. @メンション（@usernameなど）を完全に抹消
    clean_text = re.sub(r'@[\w\.]+', '', clean_text)
    
    # 3. ユマの指定通り「#」の記号だけを消して、後ろの言葉は残す！
    clean_text = clean_text.replace("#", " ")
    
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

    try:
        feeds = client.app.bsky.unspecced.get_popular_feed_generators()
        target_feed = next((f.uri for f in feeds.feeds if "Discover" in f.display_name or "Discovery" in f.display_name), None)
        if not target_feed:
            target_feed = 'at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot'
    except Exception as e:
        print(f"フィード検索失敗: {e}")
        return

    all_raw_posts = []
    cursor = None
    
    # 【修正箇所】100件×10回のおねだりを正しい書き方に直したよ！
    for i in range(10): 
        try:
            response = client.app.bsky.feed.get_feed(feed=target_feed, limit=100, cursor=cursor)
            all_raw_posts.extend(response.feed)
            cursor = response.cursor
            if not cursor: 
                break
        except Exception as e:
            print(f"取得エラー: {e}")
            break

    cleaned_texts = []
    for item in all_raw_posts:
        safe_text = is_safe(item.post.record.text, ng_words)
        # 2文字以上の日本語が含まれていれば、ハッシュタグの残骸でも何でも素材にする！
        if safe_text and len(safe_text) >= 2:
            if re.search(r'[ぁ-んァ-ヶー一-龠]', safe_text):
                cleaned_texts.append(tokenize(safe_text))

    print(f"最終的に集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 3:
        print("素材不足でパズルが組めないよー！")
        return

    # 2. マルコフ連鎖で混ぜる
    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)
    
    # 3. 文章生成（140文字以内）
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("文章が組めなかった")

if __name__ == "__main__":
    main()
