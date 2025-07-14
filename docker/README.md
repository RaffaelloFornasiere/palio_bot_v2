# Docker Setup for Palio Bot

This folder contains Docker configuration for running the Palio Bot system with both the Telegram bot and API server.

## Services

- **telegram-bot**: Runs the Telegram bot for interactive chat
- **api-server**: Runs the FastAPI server that serves palio.json data

## Quick Start

1. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Build and run**:
   ```bash
   cd docker
   docker-compose up -d
   ```

3. **Check logs**:
   ```bash
   docker-compose logs -f telegram-bot
   docker-compose logs -f api-server
   ```

## Environment Variables

### Required
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather
- `ALLOWED_USER_ID`: Telegram user ID allowed to use the bot

### Optional
- `LLAMACPP_URL`: URL to LlamaCPP server (default: http://mac-studio.local:11454)
- `ANTHROPIC_API_KEY`: Anthropic API key for Claude integration

## Volumes

- `telegram_data`: Persistent storage for Telegram bot data
- `api_data`: Persistent storage for API server data
- `../logs`: Log files mounted from host

## Network

Both services run on the `palio-network` Docker network for internal communication.

## Ports

- API Server: `8000` (exposed to host)
- Telegram Bot: `8001` (internal only, for health checks)

## Data Persistence

Both services store their data in Docker volumes:
- Telegram bot: session files, backups
- API server: palio.json data

## Useful Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service-name]

# Rebuild and restart
docker-compose down && docker-compose up -d --build

# Access API
curl http://localhost:8000/palio

# Clean up volumes (WARNING: deletes all data)
docker-compose down -v
```

## Development

For development, you can override the compose file:

```bash
# Create docker-compose.override.yml for development settings
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```