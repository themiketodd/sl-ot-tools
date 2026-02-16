"""Entry point for sl-ot-read-emails command."""

import os
import subprocess
import sys


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    read_email_sh = os.path.join(script_dir, "read_email.sh")
    result = subprocess.run(["bash", read_email_sh] + sys.argv[1:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
