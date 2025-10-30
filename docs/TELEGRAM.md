# Telegram Bot Integration

This service integrates with the Telegram Bot API to support per-workspace bots. Each workspace can register its own bot token, choose a delivery strategy (webhook or polling), and bind specific channels after passing permission checks.

## Creating a bot token

1. Open Telegram and start a conversation with [@BotFather](https://t.me/botfather).
2. Use the `/newbot` command and follow the prompts to choose a name and username for your bot.
3. BotFather will return an API token that looks similar to `12345678:AA...`. Copy this token; it is required when calling the backend registration endpoint.
4. (Optional) Restrict the bot to the channels you control by adding it as an admin in each channel you intend to bind.

## Registering a bot in the backend

Use the `POST /workspaces/{workspace_id}/telegram/bot` endpoint to register the bot token for a workspace. Provide the strategy and optional webhook information in the request body:

```bash
curl -X POST "https://api.example.com/workspaces/acme/telegram/bot" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "12345678:AA...",
    "strategy": "webhook",
    "webhook_url": "https://app.example.com/telegram/hooks/acme",
    "allowed_channel_ids": ["-1001234567890"]
  }'
```

- Set `strategy` to `webhook` when you host a public HTTPS endpoint and supply `webhook_url`.
- Use `strategy` `polling` when you plan to poll Telegram from background workers.
- `allowed_channel_ids` is optional. When provided, only the listed channels can be bound to the workspace.

## Binding a Telegram channel

After registering the bot, bind one of the allowed channels:

```bash
curl -X POST "https://api.example.com/workspaces/acme/telegram/channel" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "-1001234567890"
  }'
```

The backend will verify that the channel is permitted and confirm it via the Telegram Bot API. On success, the workspace configuration records the bound channel.

## Inspecting the current configuration

Use `GET /workspaces/{workspace_id}/telegram/bot` to retrieve the registered strategy, webhook (if any), and the currently bound channel. The token itself is never returned by the API for security reasons.

## Error handling

- **403 Forbidden** – The workspace attempted to bind a channel that is not in the allowed list.
- **404 Not Found** – No bot has been registered for the workspace.
- **400 Bad Request** – The provided configuration is invalid or the Telegram API rejected the channel binding.
- **502 Bad Gateway** – An unexpected error occurred while communicating with the Telegram API.

Refer to the API responses for exact error details during setup.
