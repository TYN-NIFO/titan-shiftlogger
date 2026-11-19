"""Reset the demo to its starting state (run before every recording take).

  python scripts/reset_demo.py

1. Rebuilds the database: tables, views, read-only role, masters (init_db.py).
2. Loads 4 months of synthetic job cards (generate_synthetic.py --seed 42).
3. Loads 7 photo cards (C01, C03, C05, C06, C07, C09, C10). C02, C04 and C08 are left out:
   they are uploaded live in the video.
4. Clears uploaded images left over from earlier takes.

Takes a few seconds. Restart the backend afterwards only if it was mid-request.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(*args: str) -> None:
    print(f"\n$ {' '.join(args)}")
    subprocess.run([sys.executable, *args], cwd=HERE.parent, check=True)


def main() -> int:
    # Remove images from earlier live uploads; seed_photo_cards copies the 7 seeded ones back.
    sys.path.insert(0, str(HERE.parent))
    from app.services import config  # noqa: E402

    upload = config.upload_dir()
    if upload.exists():
        for f in upload.iterdir():
            if f.is_file():
                f.unlink()
        print(f"cleared {upload}")

    run("scripts/init_db.py")
    run("scripts/generate_synthetic.py", "--seed", "42")
    run("scripts/seed_photo_cards.py")
    print("\nDemo reset: 7 photo cards loaded (4 waiting for review, 3 saved). Upload C02, C04, C08 live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
