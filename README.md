# Synology HDD Compatibility Bypass

## Overview
This utility script temporarily disables the HDD compatibility check on Synology 25‑series NAS models, allowing you to complete the initial DSM installation with third‑party or unsupported drives.

> **Note:** This is a one‑time, in‑memory bypass that only applies during the initial setup. After DSM is installed, the NAS will revert to its standard compatibility policy until you add your drives to the database.

---

## Disclaimer
- **Temporary bypass only.** Use this script to finish setup _once_, then configure permanent compatibility via DSM or the community database.
- **Use at your own risk.** Bypassing compatibility checks may result in data loss or void your warranty.

---

## Requirements
- **Windows PC** with **Python 3.8+** installed and on your `PATH`.
- **Python packages:**
  ```sh
  pip install requests
  ```
- **Network access** to the unconfigured Synology NAS (no DSM login required).

---

## Installation

Grab the latest packaged release from our GitHub releases page:
1. Visit the [Releases](https://github.com/your-repo/synology-hdd-bypass/releases) section.
2. Download the standalone `skip_syno_hdds.py` script from the latest version.

**Install required Python package:**
```sh
pip install requests
```

---

## Usage
```sh
python Synology_setup_bypass.py <NAS_IP>
```
OR
```sh
python Synology_setup_bypass.py <NAS_IP> --show-output
```
- `<NAS_IP>`: IP address of your Synology NAS (fresh/uninitialized).
- `--show-output` (optional): display the verification output for debugging.

**Example:**
```sh
python Synology_setup_bypass.py 192.168.1.199 --show-output
```

---

## Next Steps
After you successfully install DSM using this bypass, run the HDD database script below to add your drives permanently:
- **Synology_HDD_db by 007revad:** https://github.com/007revad/Synology_HDD_db

---

## Support
Feel free to open Issues or Pull Requests on the [GitHub repository](https://github.com/your-repo/synology-hdd-bypass). Contributions and feedback are welcome!

