# Twitter Voice Agent

A monorepo containing both a CLI tool and web API for analyzing Twitter users' voice and persona, then generating authentic content proposals (tweets, threads, replies) based on their style. Uses Ollama (local or cloud) for voice analysis and content generation.

## Components

- **Backend**: FastAPI REST API with CLI support (`backend/`)
- **Frontend**: Modern web UI built with TanStack Router and React (`frontend/`)

## Features

- **Voice Analysis**: Analyze a Twitter user's writing style, tone, topics, and engagement patterns
- **Content Generation**: Generate tweets, threads, and replies that match the analyzed voice
- **Content Context**: Use text files from a directory to provide context for content generation
- **Engagement Analytics**: Analyze engagement patterns to optimize content proposals
- **Calendar Integration**: Schedule content proposals based on calendar events

## Prerequisites

### Backend
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Ollama Cloud API key OR local Ollama instance
- TwitterAPI.io API key ([Get one here](https://twitterapi.io/))
- Perplexity API key ([Get one here](https://www.perplexity.ai/))

### Frontend
- Node.js 20+ or Bun
- Backend API running (for development)

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd twitter-agent
```

2. **Install backend dependencies**:
```bash
cd backend
uv sync
```

3. **Install frontend dependencies**:
```bash
cd ../frontend
bun install  # or npm install
```

4. **Set up environment variables**:

For backend (create `.env` in `backend/` or export):
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

For frontend (create `.env` in `frontend/`):
```bash
VITE_API_URL=http://localhost:8000  # Backend URL
```

## Usage

### CLI Usage

The backend includes a CLI tool for command-line usage. See [backend/README.md](backend/README.md) for detailed CLI documentation.

**Quick start**:
```bash
cd backend

# Check configuration
uv run twitter-agent check

# Analyze a user's voice
uv run twitter-agent analyze <username>

# Generate content
uv run twitter-agent generate <username> --type tweet
```

### Web API Usage

**Start the API server**:
```bash
cd backend
uv run python -m twitter_agent.api

# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

**Start the frontend**:
```bash
cd frontend
bun run dev  # or npm run dev

# Frontend runs at http://localhost:3000
```

See [backend/README.md](backend/README.md) for API documentation and [frontend/README.md](frontend/README.md) for frontend details.

## Content Directory

Place text files (`.txt`, `.md`, `.markdown`, `.rst`) in the `content/` directory. These files are used as context for content generation.

## Calendar Format

Create a calendar file (JSON or YAML) to schedule content proposals. See [backend/README.md](backend/README.md) for detailed format specifications.

## Project Structure

```
twitter-agent/
├── backend/                # Python FastAPI backend
│   ├── twitter_agent/
│   │   ├── api/           # FastAPI application
│   │   │   ├── routers/   # API route handlers
│   │   │   ├── services.py # Business logic
│   │   │   └── main.py    # FastAPI app factory
│   │   ├── clients/       # External API clients
│   │   │   └── twitter.py # TwitterAPI.io client
│   │   ├── llm/           # LLM clients
│   │   │   ├── ollama_client.py
│   │   │   └── perplexity_client.py
│   │   ├── analysis/       # Analysis modules
│   │   ├── utils/         # Utility modules
│   │   └── cli.py         # CLI entry point
│   ├── pyproject.toml     # Python dependencies
│   └── README.md          # Backend documentation
│
├── frontend/              # React/TypeScript frontend
│   ├── src/
│   │   ├── routes/       # TanStack Router routes
│   │   ├── components/   # React components
│   │   └── lib/          # Utilities and API client
│   ├── package.json      # Node dependencies
│   └── README.md         # Frontend documentation
│
└── content/              # User-provided content directory
```

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for detailed documentation.

## Environment Variables

### Backend

See [backend/README.md](backend/README.md#configuration) for complete configuration details.

**Required**:
- `TWITTER_API_KEY`: TwitterAPI.io API key
- `PERPLEXITY_API_KEY`: Perplexity API key
- `OLLAMA_API_KEY`: Ollama Cloud API key (or use local Ollama)

**Optional**:
- `OLLAMA_BASE_URL`: Ollama API URL (default: `http://localhost:11434` or `https://ollama.com` for cloud)
- `OLLAMA_MODEL`: Model name (default: `llama3.2` or `gpt-oss:120b` for cloud)
- `FRONTEND_URL`: Frontend URL for CORS (production)
- `ALLOW_ALL_ORIGINS`: Allow all CORS origins (default: `false`)

### Frontend

- `VITE_API_URL`: Backend API URL (default: `/api` in dev, must be set in production)

## Deployment

### Railway Deployment

The project is configured for Railway deployment as a monorepo with separate services:

1. **Backend Service**:
   - Root directory: `backend/`
   - Start command: `uv run python -m twitter_agent.api`
   - See [backend/railway.json](backend/railway.json)

2. **Frontend Service**:
   - Root directory: `frontend/`
   - Build command: `bun install && bun run build`
   - Start command: `bun run start`
   - See [frontend/railway.json](frontend/railway.json)

See [backend/README.md](backend/README.md#deployment) for detailed deployment instructions.

## Examples

### CLI Example

```bash
cd backend

# Analyze a user's voice
uv run twitter-agent analyze techinfluencer --output tech_profile.json

# Generate content based on the profile
uv run twitter-agent generate techinfluencer \
  --profile tech_profile.json \
  --type thread \
  --content-dir ../content \
  --count 3
```

### API Example

```bash
# Start the API server
cd backend
uv run python -m twitter_agent.api

# In another terminal, make API requests
curl -X POST http://localhost:8000/api/inspire \
  -H "Content-Type: application/json" \
  -d '{
    "username": "techinfluencer",
    "tweet_url": "https://twitter.com/user/status/1234567890",
    "content_type": "all"
  }'
```

Visit http://localhost:8000/docs for interactive API documentation.

## Troubleshooting

### Backend Issues

**Server won't start**:
- Check Python version: `python --version` (requires 3.12+)
- Verify dependencies: `cd backend && uv sync`
- Check environment variables are set correctly

**API errors**:
- Verify API keys are valid and have credits
- Check Ollama is accessible (local or cloud)
- See [backend/README.md](backend/README.md#troubleshooting) for more details

### Frontend Issues

**Can't connect to backend**:
- Ensure backend is running on port 8000
- Check `VITE_API_URL` is set correctly
- Verify CORS is configured properly

**Build errors**:
- Check Node.js version: `node --version` (requires 20+)
- Clear node_modules and reinstall: `rm -rf node_modules && bun install`

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for component-specific troubleshooting.

## Documentation

- **[Backend README](backend/README.md)**: Backend API documentation, CLI usage, and deployment
- **[Frontend README](frontend/README.md)**: Frontend development and deployment guide

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]