"""Run the demo server so Ctrl+C actually stops it.

On Windows, ``uv run uvicorn app.main:app`` can hang at "Shutting down" after
Ctrl+C: uvicorn's graceful shutdown waits (by default forever) for lingering
connections to close, and an open browser tab -- or a paused ``<video>`` still
holding a keep-alive/range-request connection -- never closes on its own, so the
prompt never returns and the shell has to be killed.

``timeout_graceful_shutdown`` bounds that wait, after which uvicorn force-closes
the stragglers and exits. Run with ``uv run python -m app`` (host/port via the
HOST/PORT env vars). The ``ConnectionResetError [WinError 10054]`` line the
browser sometimes triggers on video seek is a separate, harmless ProactorEventLoop
message, not the hang.
"""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    main()
