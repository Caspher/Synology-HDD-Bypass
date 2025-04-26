#!/usr/bin/env python3
"""
To bypass HDD compatibility check for 25 series Synology products.
"""

import sys
import socket
import requests
import json
import time
import warnings
import logging
from datetime import date
from argparse import ArgumentParser, RawTextHelpFormatter

warnings.filterwarnings("ignore", category=DeprecationWarning)

TELNET_PORT = 23
# no-RTC default
FALLBACK_PASSWORD = "101-0101"
BUFFER_SIZE = 4096
READ_TIMEOUT = 10
VERIFY_TIMEOUT = 2
LOOP_COMMAND = "while true; do touch /tmp/installable_check_pass; sleep 1; done"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def default_pass() -> str:
    # Compute the daily rotating Synology Telnet password based on current date.
    def gcd(a: int, b: int) -> int:
        return a if not b else gcd(b, a % b)

    today = date.today()
    m, d = today.month, today.day
    return f"{m:x}{m:02}-{d:02x}{gcd(m, d):02}"


def enable_telnet(nas_ip: str) -> bool:
    # Enable Telnet on the NAS via its HTTP API(default port).
    url = f"http://{nas_ip}:5000/webman/start_telnet.cgi"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            logger.info("Telnet enabled on %s", nas_ip)
            return True
        logger.error("API did not return success: %s", data)
    except Exception as e:
        logger.error("Failed to enable Telnet: %s", e)
    return False


def recv_until(sock: socket.socket, marker: bytes, timeout: int) -> bytes:
    # Read from `sock` until `marker` is found or timeout expires.
    # TODO: Needs further debug
    buf = b""
    sock.settimeout(timeout)
    while marker not in buf:
        try:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                break
            buf += chunk
        except socket.timeout:
            break
    return buf


def exec_cmd_via_socket(nas_ip: str, port: int, command: str, show_output: bool = False) -> bool:
    # Connect to the NAS via Telnet login, RTC check, optional verify output.
    try:
        with socket.create_connection((nas_ip, port), timeout=5) as sock:
            # Login
            recv_until(sock, b"login: ", READ_TIMEOUT)
            sock.sendall(b"root\n")

            recv_until(sock, b"Password: ", READ_TIMEOUT)
            primary_pw = default_pass()
            sock.sendall(primary_pw.encode() + b"\n")

            login_resp = recv_until(sock, b"# ", READ_TIMEOUT)
            if b"Login incorrect" in login_resp:
                logger.warning("Rotating password failed, trying fallback")
                sock.sendall(b"root\n")
                recv_until(sock, b"Password: ", READ_TIMEOUT)
                sock.sendall(FALLBACK_PASSWORD.encode() + b"\n")
                login_resp = recv_until(sock, b"# ", READ_TIMEOUT)
                if b"Login incorrect" in login_resp:
                    logger.error("Both passwords failed -- aborting")
                    return False
            logger.info("Telnet login successful")

            # Clear prompt
            recv_until(sock, b"# ", READ_TIMEOUT)

            # RTC check
            sock.sendall(b'date +"%F %T %Z"\n')

            time.sleep(1)
            rtc_data = recv_until(sock, b"# ", VERIFY_TIMEOUT)
            rtc_lines = [ln for ln in rtc_data.decode(errors="ignore").splitlines()
                         if ln and not ln.startswith('date')]
            rtc_ok = False
            if rtc_lines:
                rtc_val = rtc_lines[0].strip()
                try:
                    year = int(rtc_val.split('-', 1)[0])
                except ValueError:
                    logger.warning("Unexpected RTC format: %s", rtc_val)
                    rtc_ok = True
                else:
                    if year < 2005:
                        # Default/unset RTC on fresh NAS; fallback password expected
                        rtc_ok = True
                        logger.info("RTC appears default/unset (%s); proceeding with fallback", rtc_val)
                    else:
                        rtc_ok = True
                        logger.info("RTC is set correctly: %s", rtc_val)
            else:
                # No RTC data: assume fresh server
                rtc_ok = True
                logger.info("No RTC response; assuming default/unset state")

            # Loop + optional verification(debug only)
            verify_cmd = f"{command} & echo __LOOP_STARTED__ && ls -l /tmp/installable_check_pass"
            sock.sendall(verify_cmd.encode() + b"\n")
            time.sleep(1)
            if show_output:
                out = recv_until(sock, b"# ", VERIFY_TIMEOUT)
                lines = [ln for ln in out.decode(errors="ignore").splitlines()
                         if not ln.startswith(command)]
                logger.info("Command output:\n%s", "\n".join(lines))

            return rtc_ok
    except Exception as e:
        logger.exception("Telnet session error")
    return False


def main():
    parser = ArgumentParser(
        description="Enable Telnet, check RTC, and optionally show output on Synology NAS(debug purposes only)",
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("nas_ip", help="IP address of your Synology NAS")
    args = parser.parse_args()

    if not enable_telnet(args.nas_ip):
        sys.exit(1)

    # Login, RTC check, loop start
    success = exec_cmd_via_socket(
        args.nas_ip, TELNET_PORT, LOOP_COMMAND, args.show_output
    )
    if not success:
        logger.error("One or more steps failed (RTC or loop)")
        sys.exit(1)
    logger.info("All steps completed successfully. Refresh your web assistant!")


if __name__ == "__main__":
    main()
