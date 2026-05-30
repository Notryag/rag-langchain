from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from app.retrieval.ingest import ingest_documents

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STREAMLIT_ENTRY = PROJECT_ROOT / "streamlit_app.py"
API_APP = "app.api.main:app"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified project entrypoint.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("cli", help="Start the interactive CLI chat.")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest local documents into the vector store.")
    ingest_parser.add_argument(
        "--data-dir",
        default="./data/raw",
        help="Directory containing raw documents to ingest.",
    )
    ingest_parser.add_argument(
        "--mode",
        default="skip_existing",
        choices=["skip_existing", "rebuild"],
        help="Ingest mode: skip_existing keeps existing chunks, rebuild clears and recreates the collection.",
    )

    streamlit_parser = subparsers.add_parser("streamlit", help="Start the Streamlit UI.")
    streamlit_parser.add_argument(
        "--server-port",
        default=None,
        help="Optional Streamlit server port override.",
    )
    streamlit_parser.add_argument(
        "--server-address",
        default=None,
        help="Optional Streamlit server address override.",
    )

    web_parser = subparsers.add_parser("web", help="Start the FastAPI web UI and API.")
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="FastAPI server host.",
    )
    web_parser.add_argument(
        "--port",
        default="8000",
        help="FastAPI server port.",
    )
    web_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload for local development.",
    )

    return parser


def _run_cli() -> int:
    from app.cli.main import main as cli_main

    cli_main()
    return 0


def _run_ingest(data_dir: str, *, mode: str) -> int:
    inserted = ingest_documents(data_dir, mode=mode)
    print(f"ingested_chunks={inserted}")
    return 0


def _run_streamlit(*, server_port: str | None, server_address: str | None) -> int:
    command = [sys.executable, "-m", "streamlit", "run", str(STREAMLIT_ENTRY)]
    if server_port:
        command.extend(["--server.port", server_port])
    if server_address:
        command.extend(["--server.address", server_address])
    completed = subprocess.run(command, check=False)
    return completed.returncode


def _run_web(*, host: str, port: str, reload: bool) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        API_APP,
        "--host",
        host,
        "--port",
        port,
    ]
    if reload:
        command.append("--reload")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "cli":
        return _run_cli()
    if args.command == "ingest":
        return _run_ingest(args.data_dir, mode=args.mode)
    if args.command == "streamlit":
        return _run_streamlit(
            server_port=args.server_port,
            server_address=args.server_address,
        )
    if args.command == "web":
        return _run_web(
            host=args.host,
            port=args.port,
            reload=args.reload,
        )

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
