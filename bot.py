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

# --- コメント返信機能（ボットの投稿についたコメ欄のみ） ---
def reply_to_comments(client, text_model, ng_words):
    print("コメントをチェック中...")
    my_handle = os.environ.get('BSKY_HANDLE')

    try:
        # 1. すでに自分が返信したポストのURIを洗い出す
        already_replied_uris = set()
        feed_res = client.app.bsky.feed.get_author_feed({'actor': my_handle, 'limit': 30})
        for item in feed_res.feed:
            record = item.post.record
            if hasattr(record, 'reply') and record.reply and hasattr(record.reply, 'parent'):
                already_replied_uris.add(record.reply.parent.uri)

        # 2. 通知を取得
        response = client.app.bsky.notification.list_notifications({'limit': 15})
        for notif in response.notifications:
            # reply（返信）かつ、すでに返信済みのURIでなく、自分自身の投稿への返信でないもの
            if notif.reason == 'reply':
                if notif.uri in already_replied_uris:
                    print(f"すでに返信済みのポストのためスルー: {notif.uri}")
                    continue

                if notif.author.handle == my_handle:
                    continue

                # ここが重要：その返信の「大元の投稿（root）」または「親の投稿（parent）」が、ボット自身の投稿であるかを確認する
                record = notif.record
                if hasattr(record, 'reply') and record.reply:
                    reply_ref = record.reply
                    # ざっくり言うと、リプライツリーのルートや親が自分のもの、あるいは通知元が自分の投稿に紐づいているかチェック
                    # atprotoの通知構造では、ボットの投稿に対するリプライの場合、parentかrootの作者が自分（または自分が関わっているスレッド）になる
                    # 安全のため、返信がついた相手の投稿情報を取得して確認する
                    try:
                        parent_post_uri = reply_ref.parent.uri
                        # 親ポストの情報を取得して、投稿者が自分（my_handle）かどうかをチェック！
                        parent_post_res = client.app.bsky.feed.get_posts({'uris': [parent_post_uri]})
                        if parent_post_res.posts:
                            parent_author = parent_post_res.posts[0].author.handle
                            if parent_author != my_handle:
                                print(f"ボットの投稿に対するコメ欄ではないためスルー (親の作者: @{parent_author})")
                                continue
                    except Exception as e:
                        print(f"親ポストの確認中エラー: {e}")
                        continue

                author_handle = notif.author.handle
                comment_text = getattr(notif.record, 'text', '')

                safe_comment = is_safe(comment_text, ng_words)
                if not safe_comment:
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
                    print(f"@{author_handle} のコメ欄にお返事しました: {reply_text}")
                    already_replied_uris.add(notif.uri)

        client.app.bsky.notification.update_seen({'seen_at': client.get_current_time_iso()})
    except Exception as e:
        print(f"コメント返信エラー: {e}")

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    ng_words = load_ng_words()

    # 1. ハッシュタグリポスト
    repost_hashtag_posts(client, "おとなみあーと", ng_words)

    # 2. 世の中のフィードから素材を集める
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
        if hasattr(item.post.record, 'text'):
            safe_text = is_safe(item.post.record.text, ng_words)
            if safe_text and len(safe_text) >= 1:
                cleaned_texts.append(tokenize(safe_text))


    print(f"最終的に集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 3:
        print("素材不足！")
        return

    # 3. マルコフ連鎖で混ぜる
    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)
    
    # 4. ボットの投稿に対するコメ欄のみ返信チェック
    reply_to_comments(client, text_model, ng_words)

    # 5. 通常ポスト
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("文章が組めなかった")

if __name__ == "__main__":
    main()
