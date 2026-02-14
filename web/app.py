import os

from web import create_app

app = create_app()


if __name__ == "__main__":
    host = app.config.get("BIND_ADDRESS", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    app.run(host=host, port=port)
