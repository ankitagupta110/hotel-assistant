import argparse

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Hotel Assistant backend server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the FastAPI server.")
    parser.add_argument("--port", type=int, default=8000, help="Port for the FastAPI server.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload during development.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
