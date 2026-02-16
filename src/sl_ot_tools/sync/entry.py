"""Entry point for sl-ot-sync command."""

import os
import subprocess
import sys


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sync_sh = os.path.join(script_dir, "sync.sh")
    result = subprocess.run(["bash", sync_sh] + sys.argv[1:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
