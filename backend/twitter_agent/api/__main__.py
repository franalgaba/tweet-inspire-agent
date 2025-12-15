"""Entry point for running the web server as a module."""

import sys

from twitter_agent.api.main import run_server

if __name__ == "__main__":
    # Default to allowing all origins in development
    import os
    if "ALLOW_ALL_ORIGINS" not in os.environ:
        os.environ["ALLOW_ALL_ORIGINS"] = "true"
    
    # Parse command line arguments if provided
    host = "127.0.0.1"
    port = 8000
    
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg in ["--host", "-h"] and i + 1 < len(sys.argv):
                host = sys.argv[i + 1]
            elif arg in ["--port", "-p"] and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
    
    print(f"Starting Twitter Agent API server at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    run_server(host=host, port=port)

