#!/usr/bin/env python3
"""
Patch Claude Code binary to fix /buddy broken in v2.1.90.

How it works:
  The compiled binary contains isBuddyLive() which gates the buddy feature.
  In v2.1.90 this function returns false for ALL users — not just non-firstParty
  providers — so everyone sees "buddy is unavailable on this configuration":

    function isBuddyLive() {
      if (getProvider() !== "firstParty") return false;
      if (isSimpleMode()) return false;
      return date >= April 2026;  // <-- broken in v2.1.90
    }

  And the /buddy command checks it:

    if (!isBuddyLive()) return onDone("buddy is unavailable on this configuration"), null;

  We auto-detect the minified function name via regex, then apply two same-length patches:
    1. "firstParty" -> "xirstParty" in function def (neutralize provider gate)
    2. "if(!FN())"  -> "if(!0&&!1)"  at call site (condition always false, guard skipped)

  Then re-sign the Mach-O binary (required on Apple Silicon).

Usage:
  python3 patch-buddy.py [path-to-claude-binary]

  If no path given, auto-detects from ~/.local/share/claude/versions/
"""

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile


def find_claude_binary():
    """Auto-detect the latest Claude Code binary."""
    versions_dir = os.path.expanduser("~/.local/share/claude/versions")
    if not os.path.isdir(versions_dir):
        return None
    candidates = []
    for f in os.listdir(versions_dir):
        path = os.path.join(versions_dir, f)
        if os.path.isfile(path) and not f.endswith(".bak"):
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def discover_patches(data):
    """Auto-detect minified isBuddyLive function name and build patches.

    Multiple functions gate on "firstParty", so we disambiguate isBuddyLive by
    its unique date check: getFullYear()>2026 (the feature gate that is broken
    in v2.1.90).
    """
    ID = rb'[a-zA-Z_$][a-zA-Z0-9_$]{0,5}'
    # Match the full isBuddyLive body up through the date check to uniquely identify it
    full_pattern = (
        rb'function (' + ID + rb')\(\)\{if\(' + ID + rb'\(\)!=="firstParty"\)return!1;'
        rb'if\(' + ID + rb'\(\)\)return!1;'
        rb'let \w=new Date;return \w\.getFullYear\(\)>2026'
    )
    m = re.search(full_pattern, data)
    if not m:
        return None

    fn_name = m.group(1)  # e.g. b"di$"
    fn_name_str = fn_name.decode()
    print(f"Auto-detected isBuddyLive: {fn_name_str}()")

    # Build patch 1: just the provider gate portion (same length swap)
    gate_pattern = (
        rb'function ' + re.escape(fn_name) +
        rb'\(\)\{if\((' + ID + rb')\(\)!=="firstParty"\)return!1'
    )
    gate_m = re.search(gate_pattern, data)
    gate_old = gate_m.group(0)
    gate_new = gate_old.replace(b'"firstParty"', b'"xirstParty"')

    # Build patch 2: call site if(!FN()) -> if(!0&&!1)
    call_old = b"if(!" + fn_name + b"())"
    call_new = b"if(!0&&!1)"

    # Adjust length: "if(!0&&!1)" is 10 bytes, "if(!FN())" is 7 + len(FN)
    diff = len(call_old) - len(call_new)
    if diff > 0:
        call_new = b"if(" + b" " * diff + b"!0&&!1)"
    elif diff < 0:
        # FN is too short for a same-length replacement; skip call-site patch
        return [
            (
                f'isBuddyLive() provider gate: neutralize "firstParty" check [auto: {fn_name_str}]',
                gate_old,
                gate_new,
            )
        ]

    assert len(gate_old) == len(gate_new), "Patch 1 length mismatch"
    assert len(call_old) == len(call_new), "Patch 2 length mismatch"

    return [
        (
            f'isBuddyLive() provider gate: neutralize "firstParty" check [auto: {fn_name_str}]',
            gate_old,
            gate_new,
        ),
        (
            f"call site: if(!{fn_name_str}()) -> if(!0&&!1) — condition always false, guard skipped [auto]",
            call_old,
            call_new,
        ),
    ]


def patch(binary_path):
    if not os.path.isfile(binary_path):
        print(f"Error: {binary_path} not found")
        sys.exit(1)

    backup_path = binary_path + ".bak"
    data = open(binary_path, "rb").read()

    # Check if already patched (xirstParty with date check = isBuddyLive already patched)
    ID = rb'[a-zA-Z_$][a-zA-Z0-9_$]{0,5}'
    buddy_patched = (
        rb'function ' + ID + rb'\(\)\{if\(' + ID + rb'\(\)!=="xirstParty"\)return!1;'
        rb'if\(' + ID + rb'\(\)\)return!1;'
        rb'let \w=new Date;return \w\.getFullYear\(\)>2026'
    )
    if re.search(buddy_patched, data):
        print("Already patched!")
        return True

    # Auto-discover patches
    patches = discover_patches(data)
    if patches is None:
        print("Error: could not find isBuddyLive() pattern in binary.")
        print(
            "Expected pattern: function <NAME>(){if(<PROVIDER>()!==\"firstParty\")return!1\n"
            "The function structure may have changed in this version."
        )
        return False

    # Verify all patterns exist
    for desc, old, new in patches:
        if data.count(old) == 0:
            print(f"Error: pattern not found for: {desc}")
            return False

    # Backup
    if not os.path.exists(backup_path):
        shutil.copy2(binary_path, backup_path)
        print(f"Backup: {backup_path}")
    else:
        print(f"Backup exists: {backup_path}")

    # Apply patches
    for desc, old, new in patches:
        count = data.count(old)
        data = data.replace(old, new)
        print(f"Patched {count}x: {desc}")

    # Write to temp file + rename to handle ETXTBSY (binary in use on Linux)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(binary_path))
    try:
        os.write(tmp_fd, data)
        os.close(tmp_fd)
        st = os.stat(binary_path)
        os.chmod(tmp_path, stat.S_IMODE(st.st_mode))
        os.rename(tmp_path, binary_path)
    except BaseException:
        os.unlink(tmp_path)
        raise

    # Re-sign on macOS (required for Apple Silicon)
    if sys.platform == "darwin":
        result = subprocess.run(
            ["codesign", "--force", "--sign", "-", binary_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Re-signed binary (ad-hoc)")
        else:
            print(f"Warning: codesign failed: {result.stderr}")

    print("Done! Restart Claude Code and run /buddy")
    return True


def main():
    if len(sys.argv) > 1:
        binary_path = sys.argv[1]
    else:
        binary_path = find_claude_binary()
        if not binary_path:
            print("Could not auto-detect Claude binary.")
            print("Usage: python3 patch-buddy.py <path-to-claude-binary>")
            sys.exit(1)
        print(f"Detected: {binary_path}")

    if not patch(binary_path):
        sys.exit(1)


if __name__ == "__main__":
    main()
