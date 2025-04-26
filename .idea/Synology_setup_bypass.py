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
# The fallback password is the "no-RTC" default Synology uses when real-time clock isn't set
FALLBACK_PASSWORD = "101-0101"
BUFFER_SIZE = 4096
READ_TIMEOUT = 10
VERIFY_TIMEOUT = 2
LOOP_COMMAND = (
    "while true; do touch /tmp/installable_check_pass; sleep 1; done"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def pass_of_the_day() -> str:
    # Generate the Synology "password-of-the-day":
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
            logger.info("Telnet enabled on NAS %s", nas_ip)
            return True
        logger.error("Unexpected API response: %s", json.dumps(data))
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.error("Failed to enable Telnet: %s", e)
    return False


def recv_until(sock: socket.socket, marker: bytes, timeout: int = READ_TIMEOUT) -> bytes:
    # Read from `sock` until `marker` is found or timeout expires.
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


def exec_cmd_via_socket(nas_ip: str, port: int, command: str) -> bool:
    # Connect to the NAS via raw TCP on `port`, perform Telnet login, check the NAS RTC, verify it started.
    try:
        with socket.create_connection((nas_ip, port), timeout=5) as sock:
            # Login sequence
            recv_until(sock, b"login: ")
            sock.sendall(b"root\n")
            recv_until(sock, b"Password: ")
            primary_pw = pass_of_the_day()
            sock.sendall(primary_pw.encode() + b"\n")
            login_resp = recv_until(sock, b"# ", timeout=5)
            if b"Login incorrect" in login_resp:
                logger.warning("Rotating password failed, retrying fallback")
                sock.sendall(b"root\n")
                recv_until(sock, b"Password: ")
                sock.sendall(FALLBACK_PASSWORD.encode() + b"\n")
                login_resp = recv_until(sock, b"# ", timeout=5)
                if b"Login incorrect" in login_resp:
                    logger.error("Both passwords failed, aborting")
                    return False
            logger.info("Telnet login successful")
            recv_until(sock, b"# ", timeout=5)

            # Check and log NAS RTC time
            rtc_cmd = 'date +"%F %T %Z"'
            sock.sendall(rtc_cmd.encode() + b"\n")
            time.sleep(1)
            rtc_bytes = b""
            sock.settimeout(VERIFY_TIMEOUT)
            while True:
                try:
                    part = sock.recv(BUFFER_SIZE)
                    if not part:
                        break
                    rtc_bytes += part
                except socket.timeout:
                    break
            rtc_lines = rtc_bytes.decode(errors="ignore").splitlines()
            rtc_lines = [ln for ln in rtc_lines if not ln.startswith('date') and ln]
            if rtc_lines:
                logger.info("NAS RTC time: %s", rtc_lines[0])
            else:
                logger.warning("No RTC response received")

            # Verification
            verify_cmd = (
                f"{command} & echo __LOOP_STARTED__ && ls -l /tmp/installable_check_pass"
            )
            sock.sendall(verify_cmd.encode() + b"\n")
            time.sleep(1)
            out = b""
            sock.settimeout(VERIFY_TIMEOUT)
            while True:
                try:
                    chunk = sock.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    out += chunk
                except socket.timeout:
                    break
            lines = out.decode(errors="ignore").splitlines()
            # Remove echoed verify_cmd
            filtered = [ln for ln in lines if not ln.startswith(command)]
            logger.info("Command output:\n%s", "\n".join(filtered))
            return True
    except Exception:
        logger.exception("Error during Telnet session")
    return False


def main():
    parser = ArgumentParser(
        description="Enable Telnet on a Synology NAS, report its RTC, and start a persistent loop.",
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument("nas_ip", help="IP address of your Synology NAS")
    args = parser.parse_args()

    if not enable_telnet(args.nas_ip):
        sys.exit(1)
    if not exec_cmd_via_socket(args.nas_ip, TELNET_PORT, LOOP_COMMAND):
        sys.exit(1)


if __name__ == "__main__":
    main()
