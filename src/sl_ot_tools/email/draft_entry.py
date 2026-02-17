"""Entry point for sl-ot-draft-email command."""

import os
import subprocess
import sys


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    draft_email_sh = os.path.join(script_dir, "draft_email.sh")
    result = subprocess.run(["bash", draft_email_sh] + sys.argv[1:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
