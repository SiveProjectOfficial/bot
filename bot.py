import os
import re
from atproto import Client
import markovify
from janome.tokenizer import Tokenizer

# NGワードフィルター
def load_ng_words():
    if os.path.exists("ng_words.txt"):
        with open("ng_words.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def is_safe(text, ng_words):
    # URL消し
    clean_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', '', text)
    # メンション消し
    clean_text = re.sub(r'@[\w\.]+', '', clean_text)
    
    # 1. 「部」で終わる言葉や、文脈としての部活系ワードを弾く
    if re.search(r'部$', text) or '部活' in text:
        return False

    # 2. 災害・地震・警報系ワードを弾く
    disaster_pattern = r'(原爆|空襲|地震|震度|津波|警報|注意報|避難|災害|冠水|停電|余震)'
    if re.search(disaster_pattern, text):
        return False

    # 3. 代表的な都道府県名や「〜市・〜町・〜村」などの地名を弾く
    place_pattern = r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄|ヒロシマ|ナガサキ|広島|長崎|沖縄県|[都道府県]|.+[市区町村])'
    if re.search(place_pattern, text):
        return False

    # NGワードチェック
    for word in ng_words:
        if word in clean_text:
            return False
            
    # ハッシュタグがくっついて単語が崩壊しないように、#や＃の直前にスペースを挿入する
    clean_text = re.sub(r'([#＃])', r' \1', clean_text)
    
    return clean_text.strip()

def tokenize(text):
    t = Tokenizer()
    return " ".join([token.surface for token in t.tokenize(text)])

# 検索＆リポスト
def repost_hashtag_posts(client, tag_name, ng_words, limit=10):
    my_handle = os.environ.get('BSKY_HANDLE')
    print(f"#{tag_name} の最新投稿をチェック中...")

    try:
        already_reposted_uris = set()
        feed_res = client.app.bsky.feed.get_author_feed({'actor': my_handle, 'limit': 50})
        for item in feed_res.feed:
            if item.post.uri:
                already_reposted_uris.add(item.post.uri)

        search_res = client.app.bsky.feed.search_posts({'q': f"#{tag_name}", 'limit': limit})
        for post in search_res.posts:
            if post.author.handle == my_handle:
                continue

            if post.uri in already_reposted_uris:
                print(f"すでに処理済みの投稿のためスルー: {post.uri}")
                continue

            if post.viewer and getattr(post.viewer, 'like', None):
                print(f"すでにいいね済みの投稿のためスルー: {post.uri}")
                continue

            text = post.record.text
            if not is_safe(text, ng_words):
                continue

            try:
                client.like(post.uri, post.cid)
                client.repost(post.uri, post.cid)
                print(f"#{tag_name} をリポスト＆いいねしました！ (@{post.author.handle})")
                already_reposted_uris.add(post.uri)
            except Exception as e:
                print(f"リポスト/いいねエラー: {e}")
                pass
    except Exception as e:
        print(f"ハッシュタグリポストエラー: {e}")

# ボットの投稿についたコメ欄の返信機能
def reply_to_comments(client, text_model, ng_words):
    print("コメントをチェック中...")
    my_handle = os.environ.get('BSKY_HANDLE')

    try:
        already_replied_uris = set()
        feed_res = client.app.bsky.feed.get_author_feed({'actor': my_handle, 'limit': 30})
        for item in feed_res.feed:
            record = item.post.record
            if hasattr(record, 'reply') and record.reply and hasattr(record.reply, 'parent'):
                already_replied_uris.add(record.reply.parent.uri)

        response = client.app.bsky.notification.list_notifications({'limit': 15})
        for notif in response.notifications:
            if notif.reason == 'reply':
                if notif.uri in already_replied_uris:
                    print(f"すでに返信済みのポストのためスルー: {notif.uri}")
                    continue

                if notif.author.handle == my_handle:
                    continue

                record = notif.record
                if hasattr(record, 'reply') and record.reply:
                    reply_ref = record.reply
                    try:
                        parent_post_uri = reply_ref.parent.uri
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

    # ハッシュタグリポスト
    repost_hashtag_posts(client, "おとなみあーと", ng_words)

    # フィードから素材集め
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
    
    # 414エラー対策：リクエストのサイズと回数を安全に制限
    for i in range(5): 
        try:
            params = {'feed': target_feed, 'limit': 50}
            if cursor:
                params['cursor'] = cursor
            response = client.app.bsky.feed.get_feed(params)
            if not response or not response.feed:
                break
            all_raw_posts.extend(response.feed)
            cursor = getattr(response, 'cursor', None)
            if not cursor: 
                break
        except Exception as e:
            print(f"取得エラー: {e}")
            break

    cleaned_texts = []
    for item in all_raw_posts:
        if hasattr(item.post.record, 'text'):
            safe_text = is_safe(item.post.record.text, ng_words)
            if safe_text and len(safe_text) >= 2:
                if re.search(r'[ぁ-んァ-ヶー一-龠]', safe_text):
                    cleaned_texts.append(tokenize(safe_text))

    print(f"最終的に集まった素材数: {len(cleaned_texts)}件")

    if len(cleaned_texts) < 2:
        print("素材不足！")
        return

    # マルコフ連鎖
    source_data = "\n".join(cleaned_texts)
    text_model = markovify.NewlineText(source_data, state_size=1)
    
    # 投稿に対するコメ欄の返信チェック
    reply_to_comments(client, text_model, ng_words)

    # 通常ポスト
    sentence = text_model.make_short_sentence(140, tries=100)

    if sentence:
        final_post = sentence.replace(" ", "")
        
        # ハッシュタグの混入チェック（念のため）
        if "#" in final_post or "＃" in final_post:
            print("ハッシュタグが含まれているためスキップします")
            return

        print(f"投稿します: {final_post}")
        client.send_post(text=final_post)
    else:
        print("文章が組めなかった")

if __name__ == "__main__":
    main()
