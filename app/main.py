from __future__ import annotations

import argparse
import subprocess
import sys

from app.db.session import get_session_factory
from app.services.auth_service import AuthError, AuthService

API_APP = "app.api.main:app"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified project entrypoint.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    web_parser = subparsers.add_parser("web", help="Start the FastAPI web UI and API.")
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="FastAPI server host.",
    )

    admin_parser = subparsers.add_parser("create-admin", help="Create a production administrator account.")
    admin_parser.add_argument("--username", required=True)
    admin_parser.add_argument("--email", required=True)
    admin_parser.add_argument("--password", required=True)
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


def _create_admin(*, username: str, email: str, password: str) -> int:
    session = get_session_factory()()
    try:
        user = AuthService().create_admin(session, username=username, email=email, password=password)
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        session.close()
    print(f"Created admin user {user.username} ({user.email})")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "web":
        return _run_web(
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    if args.command == "create-admin":
        return _create_admin(username=args.username, email=args.email, password=args.password)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
