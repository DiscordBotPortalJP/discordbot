# discordbot

Discord Bot Portal JP 専属Bot

## ログ記事化エクスポート

スタッフ/コミッター向けに、Discordのチャンネル履歴を記事化レビュー用JSONとして出力するコマンドがあります。

```text
/ログ記事化エクスポート
```

主な挙動:

- `GUILD_ID` / `GUILD_LOGS_ID`、または `LOG_EXPORT_GUILD_IDS` で許可したサーバーだけで実行できます。
- サーバーオーナー、または `LOG_EXPORT_OPERATOR_ROLE_IDS` のロールを持つメンバーだけが実行できます。
- ユーザーIDは出力せず、ギルドIDとユーザーIDから作った短いハッシュだけを含めます。
- Token、メールアドレス、Discord招待リンク、URLは出力時に伏せます。
- 出力JSONはそのまま公開せず、website側の `scripts/community-log-to-article-drafts.mjs` でレビュー用ドラフトに変換してから記事化します。
