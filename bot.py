"""Root launcher allowing 'python bot.py' to run the Telegram bot directly."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
venv_python = root / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    # Relaunch using the project's virtual environment python
    args = [str(venv_python)] + sys.argv
    sys.exit(subprocess.call(args))

if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from cliper.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("bot")
    elif sys.argv[1] not in {"bot", "doctor", "demo", "run", "browser-login", "browser-check", "cleanup"}:
        sys.argv.insert(1, "bot")
    main()
