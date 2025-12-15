# Twitter Agent Backend

FastAPI backend service for analyzing Twitter users' voice and generating authentic content proposals (tweets, threads, replies) based on their writing style.

## Features

- **REST API**: FastAPI-based RESTful API with automatic OpenAPI documentation
- **Voice Analysis**: Analyze Twitter users' writing style, tone, topics, and engagement patterns
- **Content Generation**: Generate tweets, threads, and replies that match analyzed voice
- **Streaming Progress**: Server-Sent Events (SSE) for real-time progress updates
- **Research Caching**: Cache research results to avoid redundant API calls
- **History Tracking**: Track and retrieve generation history

## Architecture

The backend follows FastAPI best practices with a clean, modular structure:

```
backend/
├── twitter_agent/
│   ├── api/                    # FastAPI application
│   │   ├── routers/            # API route handlers
│   │   │   ├── inspire.py      # Main inspire flow endpoints
│   │   │   ├── generate.py     # Content generation endpoints
│   │   │   ├── cache.py        # Cache management
│   │   │   └── history.py      # History management
│   │   ├── services.py          # Business logic
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── config.py           # Application settings
│   │   ├── dependencies.py     # Dependency injection
│   │   └── main.py             # FastAPI app factory
│   ├── clients/                # External API clients
│   │   └── twitter.py          # TwitterAPI.io client
│   ├── llm/                    # LLM clients
│   │   ├── ollama_client.py    # Ollama client (local/cloud)
│   │   └── perplexity_client.py # Perplexity research client
│   ├── analysis/               # Analysis modules
│   │   ├── voice_analyzer.py   # Voice analysis logic
│   │   └── content_generator.py # Content generation logic
│   ├── utils/                  # Utility modules
│   │   ├── cache.py            # Caching utilities
│   │   ├── analytics.py         # Engagement analytics
│   │   └── calendar.py         # Calendar processing
│   └── models/                 # Data models
│       └── schemas.py          # Pydantic schemas
├── pyproject.toml              # Project configuration
└── railway.json                # Railway deployment config
```

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Ollama Cloud API key OR local Ollama instance
- TwitterAPI.io API key ([Get one here](https://twitterapi.io/))
- Perplexity API key ([Get one here](https://www.perplexity.ai/))

## Installation

1. **Install dependencies**:
```bash
cd backend
uv sync
```

2. **Set up environment variables**:
```bash
export TWITTER_API_KEY="your-twitter-api-key"
export PERPLEXITY_API_KEY="your-perplexity-api-key"
export OLLAMA_API_KEY="your-ollama-cloud-api-key"  # For Ollama Cloud
export OLLAMA_BASE_URL="https://ollama.com"         # For Ollama Cloud
export OLLAMA_MODEL="gpt-oss:120b"                  # Cloud model
# OR for local Ollama:
# export OLLAMA_BASE_URL="http://localhost:11434"
# export OLLAMA_MODEL="llama3.2"
```

## Running the Server

### Development

Run the API server locally:

```bash
# From backend directory
uv run python -m twitter_agent.api

# With custom host/port
uv run python -m twitter_agent.api --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Production

The server is configured for Railway deployment. See `railway.json` for deployment settings.

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Health Check

```
GET /health
```

Returns server health status.

### Inspire Endpoints

Generate content from a tweet URL:

```
POST /api/inspire
```

**Request Body**:
```json
{
  "username": "elonmusk",
  "tweet_url": "https://twitter.com/user/status/1234567890",
  "content_type": "all",
  "thread_count": 5,
  "vibe": "excited",
  "deep_research": false,
  "context": "Optional context text"
}
```

**Response**: Returns original tweet, generated proposals, and research ID.

**Streaming Version**:
```
POST /api/inspire/stream
```

Returns Server-Sent Events (SSE) with real-time progress updates.

**Regenerate**:
```
POST /api/inspire/regenerate
```

Regenerate content using cached research (no need to research again).

### Generate Endpoints

**Analyze Voice**:
```
POST /api/analyze
```

Analyze a Twitter user's voice and persona.

**Generate Content**:
```
POST /api/generate
```

Generate content proposals based on analyzed voice.

**Propose Content**:
```
POST /api/propose
```

Propose content based on analytics, calendar, or content files.

**Check Configuration**:
```
GET /api/check
```

Check configuration and dependencies.

### Cache Endpoints

**Get Cache Info**:
```
GET /api/cache/info?username=optional
```

Get cache information for a user (or all users).

**Clear Cache**:
```
DELETE /api/cache/clear?username=optional
```

Clear cache for a user (or all users).

### History Endpoints

**Get History**:
```
GET /api/history?limit=optional
```

Get generation history.

**Get History Entry**:
```
GET /api/history/{entry_id}
```

Get a specific history entry.

**Clear History**:
```
DELETE /api/history
```

Clear all history.

## Configuration

Configuration is managed via environment variables and `twitter_agent/api/config.py`:

| Variable | Description | Default |
|----------|-------------|---------|
| `TWITTER_API_KEY` | TwitterAPI.io API key | Required |
| `PERPLEXITY_API_KEY` | Perplexity API key | Required |
| `OLLAMA_API_KEY` | Ollama Cloud API key | Required for cloud |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model name | `llama3.2` |
| `FRONTEND_URL` | Frontend URL for CORS | None |
| `ALLOW_ALL_ORIGINS` | Allow all CORS origins | `false` |
| `CONTENT_DIR` | Content directory path | `content` |

## Development

### Project Structure

- **`api/`**: FastAPI application with routers, services, and schemas
- **`clients/`**: External API clients (Twitter, etc.)
- **`llm/`**: LLM clients (Ollama, Perplexity)
- **`analysis/`**: Core analysis and generation logic
- **`utils/`**: Utility functions (cache, analytics, calendar)
- **`models/`**: Data models and schemas

### Adding New Endpoints

1. Create or update router in `api/routers/`
2. Add request/response schemas in `api/schemas.py`
3. Implement business logic in `api/services.py`
4. Register router in `api/main.py`

### Testing

```bash
# Run tests (when implemented)
uv run pytest

# Run with coverage
uv run pytest --cov=twitter_agent
```

## Deployment

### Railway

The backend is configured for Railway deployment:

1. **Set root directory** to `backend/` in Railway dashboard
2. **Set environment variables** (see Configuration section)
3. **Deploy** - Railway will automatically build and deploy

The `railway.json` config uses:
- **Builder**: NIXPACKS (auto-detects Python)
- **Start Command**: `uv run python -m twitter_agent.api`

### Environment Variables for Railway

Set these in your Railway service:

- `TWITTER_API_KEY`
- `PERPLEXITY_API_KEY`
- `OLLAMA_API_KEY`
- `OLLAMA_BASE_URL` (set to `https://ollama.com` for cloud)
- `OLLAMA_MODEL` (e.g., `gpt-oss:120b`)
- `FRONTEND_URL` (your frontend domain)
- `ALLOW_ALL_ORIGINS` (set to `false` for production)

## CORS Configuration

CORS is configured in `api/main.py`. By default:
- Localhost origins are allowed for development
- `FRONTEND_URL` environment variable adds the frontend domain
- `ALLOW_ALL_ORIGINS=true` allows all origins (development only)

For production, set `ALLOW_ALL_ORIGINS=false` and configure `FRONTEND_URL`.

## Troubleshooting

### Server won't start

- Check Python version: `python --version` (requires 3.12+)
- Verify dependencies: `uv sync`
- Check environment variables are set

### API errors

- Check API keys are valid and have credits
- Verify Ollama is accessible (local or cloud)
- Check logs for detailed error messages

### CORS errors

- Verify `FRONTEND_URL` matches your frontend domain exactly
- Check `ALLOW_ALL_ORIGINS` setting
- Ensure frontend is making requests to correct backend URL

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

