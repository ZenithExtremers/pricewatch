# PriceWatch（値下げ見張り）

GitHub Actions が約2時間ごとにお店のページを見て、値下がりしたら ntfy でスマホに通知。価格の推移は GitHub Pages のページ（PWA）で見られる。

## 商品を追加・変更する
`items.json` を GitHub 上で編集（スマホのブラウザでもOK）。

- `shops` に「お店の名前」と「商品ページのURL」を並べる
- 対応：ケーズデンキ、価格.com（そのほかのお店も多くは自動で読める）
- `target`（目標価格）以下になると強めの通知が来る

## はじめの設定
1. Settings → Secrets and variables → Actions → `NTFY_TOPIC` に ntfy のトピック名を入れる
2. Settings → Pages → Source を「GitHub Actions」にする
3. Actions → 価格チェック → Run workflow
