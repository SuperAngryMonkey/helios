"""
helios admin credential setup.
Writes /etc/helios/admin.env with a bcrypt-hashed password + Flask secret key.

Usage:
    sudo /opt/helios/bin/python /opt/helios/passwd.py
"""
import getpass
import grp
import os
import secrets
import sys
from pathlib import Path

import bcrypt

ADMIN_ENV = "/etc/helios/admin.env"
MIN_PASS_LEN = 8


def main():
    if os.geteuid() != 0:
        print("ERROR: must run as root (sudo) — writes /etc/helios/admin.env", file=sys.stderr)
        sys.exit(1)

    username = input("Username: ").strip()
    if not username:
        print("ERROR: username required", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("New password: ")
    confirm  = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: passwords do not match", file=sys.stderr)
        sys.exit(1)
    if len(password) < MIN_PASS_LEN:
        print(f"ERROR: password too short (minimum {MIN_PASS_LEN} chars)", file=sys.stderr)
        sys.exit(1)

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    secret  = secrets.token_hex(32)

    content = (
        f"HELIOS_ADMIN_USER={username}\n"
        f"HELIOS_ADMIN_PASS_HASH={pw_hash}\n"
        f"HELIOS_SECRET_KEY={secret}\n"
    )

    path = Path(ADMIN_ENV)
    path.write_text(content)
    os.chmod(path, 0o640)
    helios_gid = grp.getgrnam("helios").gr_gid
    os.chown(path, 0, helios_gid)  # root:helios

    print(f"Wrote {ADMIN_ENV} (mode 640, root:helios)")
    print("Restart helios-web to load: systemctl restart helios-web")


if __name__ == "__main__":
    main()
