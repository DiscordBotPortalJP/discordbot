# discordbot

Discord Bot Portal JP 専属Bot

## ログ記事化エクスポート

スタッフ/コミッター向けに、Discordのチャンネル履歴を記事化レビュー用JSONとして出力するコマンドがあります。

```text
/ログ記事化エクスポート
/ログ記事化一括エクスポート
```

主な挙動:

- `GUILD_ID` / `GUILD_LOGS_ID`、または `LOG_EXPORT_GUILD_IDS` で許可したサーバーだけで実行できます。
- サーバーオーナー、または `LOG_EXPORT_OPERATOR_ROLE_IDS` のロールを持つメンバーだけが実行できます。
- ユーザーIDは出力せず、ギルドIDとユーザーIDから作った短いハッシュだけを含めます。
- Token、メールアドレス、Discord招待リンク、URLは出力時に伏せます。
- 添付ファイルや画像URLは出力せず、添付数/埋め込み数だけを含めます。website側では画像/添付ありのログを保留カテゴリへ分けます。
- 一括エクスポートは、Discord Bot Portal JP ではカテゴリ名に `✅` を含むチャンネル、Discord Bot Portal JP Logs ではテキスト/フォーラムチャンネル全体を対象にします。
- 一括エクスポートも読み取り専用です。カテゴリ作成、チャンネル移動、権限変更、メッセージ削除は実行しません。
- Discord添付サイズを超える場合は、`days`、`limit_per_source`、`max_channels`、`max_forum_threads` を下げて再実行します。
- 対象チャンネルが多い場合は、`channel_offset` を `0`、`80`、`160` のように増やして複数バッチで取得します。
- 出力JSONはそのまま公開せず、website側の `scripts/community-log-to-article-drafts.mjs` でレビュー用ドラフトに変換してから記事化します。

## 記事化チャンネル棚卸し

Discord Bot開発に関する情報交換チャンネルを、記事化対象カテゴリ候補として棚卸しする管理コマンドがあります。

```text
/記事化チャンネル棚卸し
```

主な挙動:

- `ARTICLE_CHANNEL_AUDIT_GUILD_IDS`、または既定の `GUILD_ID` / `GUILD_LOGS_ID` で許可したサーバーだけで実行できます。
- サーバーオーナー、チャンネル管理権限を持つメンバー、または `ARTICLE_CHANNEL_AUDIT_OPERATOR_ROLE_IDS` のロールを持つメンバーだけが実行できます。
- 候補チャンネル、分類先、必要になりそうな変更だけをMarkdownレポートとして返します。
- カテゴリ作成、チャンネル移動、`@everyone` 閲覧権限変更は実行しません。
- 起動時にも同じ棚卸しレポートだけを実行できます。`ARTICLE_CHANNEL_AUDIT_STARTUP_MODE=dry_run` でレポートのみ、`off` で無効化します。
- 起動時レポートは `ARTICLE_CHANNEL_AUDIT_REPORT_CHANNEL_ID`、未指定時は `CHANNEL_LOG_TRACEBACK_ID` へ投稿します。

## チャンネル一覧エクスポート

Bot経由で、許可サーバーのカテゴリ/チャンネル一覧をMarkdownとして出力する読み取り専用コマンドがあります。

```text
/チャンネル一覧エクスポート
```

主な挙動:

- 既定では `ARTICLE_CHANNEL_AUDIT_GUILD_IDS` の全サーバーを対象にします。`all_guilds=false` で実行サーバーだけにできます。
- サーバーオーナー、チャンネル管理権限を持つメンバー、または `ARTICLE_CHANNEL_AUDIT_OPERATOR_ROLE_IDS` のロールを持つメンバーだけが実行できます。
- `guild.by_category()` からカテゴリ名、チャンネル名、種別、ID、`@everyone` の閲覧上書き状態だけを読みます。
- カテゴリ作成、チャンネル移動、権限変更、メッセージ取得は実行しません。
