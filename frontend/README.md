# Twitter Agent Web UI

A modern web interface for the Twitter Agent built with TanStack Router, Vite, and Tailwind CSS.

## Development

### Prerequisites

- Node.js 20+ (see `.nvmrc`)
- The backend API running on port 8000

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:3000 and will proxy API requests to the backend at http://localhost:8000.

### Running the Backend

In a separate terminal, start the FastAPI backend:

```bash
# From the project root
python -m twitter_agent.web.server
```

## Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `/api` (uses proxy in dev) |
| `PORT` | Port for production server | 3000 |

## Railway Deployment

This frontend is configured for Railway deployment. The `railway.json` file contains the build and start commands.

### Environment Variables for Railway

Set these in your Railway service:

- `VITE_API_URL`: The URL of your backend API service (e.g., `https://your-backend.railway.app/api`)
- `PORT`: Railway sets this automatically

## Project Structure

```
src/
├── components/       # Shared UI components
├── lib/             # Utilities and API client
├── routes/          # TanStack Router file-based routes
├── app.css          # Global styles
├── main.tsx         # App entry point
└── router.tsx       # Router configuration
```

