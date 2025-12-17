const API_URL = process.env.API_URL || "http://localhost:8000";
const PORT = process.env.PORT || 3000;

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);

    // Health check endpoint
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ status: "healthy" }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Proxy /api requests to backend
    if (url.pathname.startsWith("/api")) {
      const backendUrl = `${API_URL}${url.pathname}${url.search}`;

      const headers = new Headers(req.headers);
      headers.delete("host");

      try {
        const response = await fetch(backendUrl, {
          method: req.method,
          headers,
          body: req.body,
          // @ts-ignore - Bun supports duplex
          duplex: "half",
        });

        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });
      } catch (error) {
        console.error("Proxy error:", error);
        return new Response(
          JSON.stringify({ error: "Failed to connect to backend" }),
          {
            status: 502,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
    }

    // Serve static files from dist/
    const filePath = url.pathname === "/" ? "/index.html" : url.pathname;
    const file = Bun.file(`./dist${filePath}`);

    if (await file.exists()) {
      return new Response(file);
    }

    // SPA fallback - serve index.html for client-side routing
    return new Response(Bun.file("./dist/index.html"));
  },
});

console.log(`Frontend server running on port ${server.port}`);
console.log(`Proxying /api to ${API_URL}`);
