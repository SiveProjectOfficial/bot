import os
import re
from atproto import Client
import markovify
from janome.tokenizer import Tokenizer

REPLIED_HISTORY_FILE = "replied_posts.txt"

def load_replied_uris():
    if os.path.exists(REPLIED_HISTORY_FILE):
        with open(REPLIED_HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_replied_uri(uri):
    with open(REPLIED_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{uri}\n")

# --- NGワードフィルター ---
def load_ng_words():
    if os.path.exists("ng_words.txt"):
        with open("ng_words.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def is_safe(text, ng_words):
    # 1. URLを抹消
    clean_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '', text)
    # 2. @メンションを抹消
    clean_text = re.sub(r'@[\w\.]+', '', clean_text)
    # 3. 「#」の記号だけを消して、後ろの言葉は残す
    clean_text = clean_text.replace("#", " ")
    
    # NGワードチェック
    for word in ng_words:
        if word in clean_text:
            return False
            
    return clean_text.strip()

def tokenize(text):
    t = Tokenizer()
    return " ".join([token.surface for token in t.tokenize(text)])

# --- ハッシュタグ検索＆リポスト機能 ---
def repost_hashtag_posts(client, tag_name, ng_words, limit=10):
    my_handle = os.environ.get('BSKY_HANDLE')
    print(f"#{tag_name} の最新投稿をチェック中...")

    try:
        search_res = client.app.bsky.feed.search_posts({'q': f"#{tag_name}", 'limit': limit})
        for post in search_res.posts:
            if post.author.handle == my_handle:
                continue

            text = post.record.text
            if any(w in text for w in ng_words):
                continue

            try:
                client.like(post.uri, post.cid)
                client.repost(post.uri, post.cid)
                print(f"#{tag_name} をリポスト＆いいねしました！ (@{post.author.handle})")
            except Exception:
                pass
    except Exception as e:
        print(f"ハッシュタグリポストエラー: {e}")

# --- コメント返信機能 ---
def reply_to_comments(client, text_model, ng_words):
    print("コメントをチェック中...")
    replied_uris = load_replied_uris()

    try:
        response = client.app.bsky.notification.list_notifications({'limit': 10})
        for notif in response.notifications:
            if notif.reason in ['reply', 'mention'] and notif.uri not in replied_uris:
                author_handle = notif.author.handle
                comment_text = getattr(notif.record, 'text', '')

                safe_comment = is_safe(comment_text, ng_words)
                if not safe_comment:
                    save_replied_uri(notif.uri)
                    continue

                sentence = text_model.make_short_sentence(100, tries=100)
                if sentence:
                    reply_text = sentence.replace(" ", "")
                    parent_ref = {'cid': notif.cid, 'uri': notif.uri}
                    root_ref = notif.record.reply.root if hasattr(notif.record, 'reply') and notif.record.reply else parent_ref

                    client.send_post(
                        text=f"@{author_handle} {reply_text}",
                        reply_to={'root': root_ref, 'parent': parent_ref}
                    )
                    print(f"@{author_handle} にお返事しました: {reply_text}")
                    save_replied_uri(notif.uri)

        client.app.bsky.notification.update_seen({'seen_at': client.get_current_time_iso()})
    except Exception as e:
        print(f"コメント返信エラー: {e}")

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    ng_words = load_ng_words()

    # 1. ハッシュタグリポスト
    repost_hashtag_posts(client, "おとなみあーと", ng_words)

    # 2. タイムライン（ホーム）から素材を集める（確実）
    all_raw_posts = []
    cursor = None
    
    for i in range(3): 
        try:
            params = {'limit': 100}
            if cursor:
                params['cursor'] = cursor
            response = client.app.bsky.feed.get_timeline(params)
            all_raw_posts.extend(response.feed)
            cursor = response.cursor
            if not cursor: break
        except Exception as e:
            print(f"取得エラー: {e}")
            break

    cleaned_texts = []
    for item in all_raw_posts:
        safe_text = is_safe(item.post.record.text, ng_words)
        if safe_text and len(safe_text) >= 2:
            if re.search(r'[ぁ-んァ-ヶー一-龠]', safe_text):
                cleaned_texts.append(tokenize(safe_text))

    print(f"最終的に集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 3:
        print("素材不足！")
        return

    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)
    
    # 3. 返信チェック
    reply_to_comments(client, text_model, ng_words)

    # 4. 通常ポスト
    sentence = text_model.make_short_sentence(140, tries=100)
    if sentence:
        final_post = sentence.replace(" ", "")
        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("文章が組めなかった")

if __name__ == "__main__":
    main()
