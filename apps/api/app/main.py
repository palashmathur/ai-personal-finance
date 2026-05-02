# This is the entry point of the entire FastAPI application.
# When uvicorn starts (e.g. `uvicorn app.main:app`), it imports this file
# and looks for the `app` object to serve.

from fastapi import FastAPI

# The FastAPI app instance — this is what ties everything together.
# Every router, middleware, and endpoint gets registered on this object.
# Think of it like your Spring Boot `@SpringBootApplication` class.
app = FastAPI(title="AI Personal Finance API", version="0.1.0")


# A simple root endpoint just to confirm the server is alive.
# Will be replaced by a proper /health check in PF-5.
@app.get("/")
def home_page():
    return "Power up your finance and investments with the AI 🚀"
