import uvicorn

from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    # Dev mode entry point
    import os

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=True)
