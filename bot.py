import os
import re
from atproto import Client
import markovify
from janome.tokenizer import Tokenizer

REPLIED_HISTORY_FILE = "replied_posts.txt"

# --- 返信済み投稿IDの記録（同じコメントへの重複返信を100%防ぐ） ---
def load_replied_uris():
    if os.path.exists(REPLIED_HISTORY_FILE):
        with open(REPLIED_HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_replied_uri(uri):
    with open(REPLIED_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{uri}\n")

# --- 鉄壁のNGワードフィルター ---
def load_ng_words():
    if os.path.exists("ng_words.txt"):
        with open("ng_words.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def is_safe(text, ng_words):
    # 1. URL（画像リンクなど）を完全に抹消
    clean_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '', text)
    clean_text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', clean_text)
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

# --- 1. #おとなみあーと のリポスト＆いいね ---
def repost_hashtag_posts(client, tag_name, ng_words, limit=10):
    my_handle = os.environ.get('BSKY_HANDLE')
    print(f"#{tag_name} の最新投稿をチェック中...")

    try:
        search_res = client.app.bsky.feed.search_posts({'q': f"#{tag_name}", 'limit': limit})
        for post in search_res.posts:
            # 自分の投稿は除外
            if post.author.handle == my_handle:
                continue

            # NGワードチェック
            if not is_safe(post.record.text, ng_words):
                print(f"NGワードを含むためリポストをスキップ (@{post.author.handle})")
                continue

            try:
                client.like(post.uri, post.cid)
                client.repost(post.uri, post.cid)
                print(f"#{tag_name} をリポスト＆いいねしました！ (@{post.author.handle})")
            except Exception:
                # すでにいいね/リポスト済みの場合はスルー
                pass
    except Exception as e:
        print(f"ハッシュタグリポストエラー: {e}")

# --- 2. コメ欄（自分宛ての通知）にだけメンション付きでお返事 ---
def reply_to_comments(client, text_model, ng_words):
    print("コメ欄（自分宛ての返信）をチェック中...")
    replied_uris = load_replied_uris()

    try:
        response = client.app.bsky.notification.list_notifications({'limit': 10})
        for notif in response.notifications:
            # 自分へのリプライ・メンションかつ、まだ返信していない「投稿ID」のみ！
            if notif.reason in ['reply', 'mention'] and notif.uri not in replied_uris:
                author_handle = notif.author.handle
                comment_text = getattr(notif.record, 'text', '')

                # 相手のコメントにNGワードがあればスルー
                if not is_safe(comment_text, ng_words):
                    print(f"NGワードを含むコメントのためスルー: @{author_handle}")
                    save_replied_uri(notif.uri)  # 二度とチェックしないように記録
                    continue

                # マルコフでお返事を作成
                sentence = text_model.make_short_sentence(100, tries=100)
                if sentence:
                    reply_text = sentence.replace(" ", "")

                    if is_safe(reply_text, ng_words):
                        parent_ref = {'cid': notif.cid, 'uri': notif.uri}
                        root_ref = notif.record.reply.root if hasattr(notif.record, 'reply') and notif.record.reply else parent_ref

                        # 話しかけてくれた相手のコメ欄だけにメンションでお返事！
                        client.send_post(
                            text=f"@{author_handle} {reply_text}",
                            reply_to={'root': root_ref, 'parent': parent_ref}
                        )
                        print(f"@{author_handle} のコメ欄にお返事しました！: {reply_text}")

                        # 返信した「投稿ID」をメモして保存！
                        save_replied_uri(notif.uri)

        # チェックが終わったら通知を既読化
        client.app.bsky.notification.update_seen({'seen_at': client.get_current_time_iso()})
    except Exception as e:
        print(f"コメ欄返信エラー: {e}")

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    ng_words = load_ng_words()

    # ★ 機能1: #おとなみあーと の自動リポスト＆いいねを実行！
    repost_hashtag_posts(client, "おとなみあーと", ng_words)

    # ★ 機能2: フィードから素材を集める（1000件チェック）
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
    
    for i in range(10): 
        try:
            params = {'feed': target_feed, 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            response = client.app.bsky.feed.get_feed(params)
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

    # マルコフ連鎖でモデル作成
    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)

    # ★ 機能3: コメ欄に届いたコメントへのお返事（重複防止メモ付き）
    reply_to_comments(client, text_model, ng_words)

    # ★ 機能4: 通常のマルコフ連鎖ポスト（140文字以内）
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        
        # 投稿直前にもNGワードのダブルチェック！
        if is_safe(final_post, ng_words):
            print(f"投稿します: {final_post}")
            client.send_post(text=final_post)
        else:
            print(f"生成文にNGワードが含まれたため投稿をスキップ: {final_post}")
    else:
        print("文章が組めなかった")

if __name__ == "__main__":
    main()
