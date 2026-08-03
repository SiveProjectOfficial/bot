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

# --- コメント返信機能（無限ループ完全防止版） ---
def reply_to_comments(client, text_model, ng_words):
    print("コメントをチェック中...")
    my_handle = os.environ.get('BSKY_HANDLE')

    try:
        # 1. まずボット自身の直近の投稿（Author Feed）を取得して、「すでに返信した親ポストのURI」を自動で洗い出す
        already_replied_uris = set()
        feed_res = client.app.bsky.feed.get_author_feed({'actor': my_handle, 'limit': 30})
        for item in feed_res.feed:
            record = item.post.record
            # 自分が誰かに返信している場合、その親ポスト（parent）のURIを記録しておく
            if hasattr(record, 'reply') and record.reply and hasattr(record.reply, 'parent'):
                already_replied_uris.add(record.reply.parent.uri)

        # 2. 通知をチェックして、まだ返信していないものだけに返信する
        response = client.app.bsky.notification.list_notifications({'limit': 15})
        for notif in response.notifications:
            if notif.reason == 'reply':
                # すでにこの通知のポストに返信していらスルー
                if notif.uri in already_replied_uris:
                    print(f"すでに返信済みのポストのためスルー: {notif.uri}")
                    continue

                # 自分自身の投稿への通知ならスルー
                if notif.author.handle == my_handle:
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
                    print(f"@{author_handle} にお返事しました: {reply_text}")
                    
                    # 今回返信した分をセットに追加して、同じ実行内で二重返信しないようにする
                    already_replied_uris.add(notif.uri)

        client.app.bsky.notification.update_seen({'seen_at': client.get_current_time_iso()})
    except Exception as e:
        print(f"コメント返信エラー: {e}")

def main():
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    ng_words = load_ng_words()
    my_handle = os.environ.get('BSKY_HANDLE')

    # 1. ハッシュタグリポスト
    repost_hashtag_posts(client, "おとなみあーと", ng_words)

    # 2. ボット自身の過去の投稿（Author Feed）から学習素材を集める
    print(f"@{my_handle} の投稿から学習素材を集めているよ...")
    all_raw_posts = []
    cursor = None
    
    try:
        for i in range(5): 
            params = {'actor': my_handle, 'limit': 50}
            if cursor:
                params['cursor'] = cursor
            response = client.app.bsky.feed.get_author_feed(params)
            all_raw_posts.extend(response.feed)
            cursor = response.cursor
            if not cursor: break
    except Exception as e:
        print(f"投稿取得エラー: {e}")

    cleaned_texts = []
    for item in all_raw_posts:
        if item.post.author.handle == my_handle and hasattr(item.post.record, 'text'):
            safe_text = is_safe(item.post.record.text, ng_words)
            if safe_text and len(safe_text) >= 2:
                if re.search(r'[ぁ-んァ-ヶー一-龠]', safe_text):
                    cleaned_texts.append(tokenize(safe_text))

    print(f"最終的に集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 3:
        print("素材不足！（ボット自身のポストがまだ少ないみたい）")
        return

    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=2)
    
    # 3. 返信チェック（無限ループ防止付き）
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
