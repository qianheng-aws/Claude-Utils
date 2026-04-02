#!/usr/bin/env python3
"""
Patch Claude Code binary to enable /buddy on non-firstParty providers (Bedrock, Vertex, etc.)

How it works:
  The compiled binary contains isBuddyLive() which gates the buddy feature:

    function isBuddyLive() {
      if (getProvider() !== "firstParty") return false;  // blocks Bedrock/Vertex
      if (isSimpleMode()) return false;
      return date >= April 2026;
    }

  And the /buddy command checks it:

    if (!isBuddyLive()) return onDone("buddy is unavailable on this configuration"), null;

  We apply two same-length byte patches:
    1. "firstParty" -> "xirstParty" in function def (no provider matches, all pass through)
    2. "if(!Qn_())" -> "if(!0&&!1)"  at call site (condition always false, skip the block)

  Then re-sign the Mach-O binary (required on Apple Silicon).

Usage:
  python3 patch-buddy.py [path-to-claude-binary]

  If no path given, auto-detects from ~/.local/share/claude/versions/
"""

import os
import shutil
import subprocess
import sys

# Patch definitions: (description, old_bytes, new_bytes)
# These target Claude Code v2.1.x Bun-compiled binaries.
# Minified names (Qn_, Jq) may change across versions.
PATCHES = [
    (
        'isBuddyLive() provider gate: "firstParty" -> "xirstParty"',
        b'function Qn_(){if(Jq()!=="firstParty")return!1',
        b'function Qn_(){if(Jq()!=="xirstParty")return!1',
    ),
    (
        "call site: if(!Qn_()) -> if(!0&&!1) (always false, never enters block)",
        b"if(!Qn_())",
        b"if(!0&&!1)",
    ),
]


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


def patch(binary_path):
    if not os.path.isfile(binary_path):
        print(f"Error: {binary_path} not found")
        sys.exit(1)

    backup_path = binary_path + ".bak"
    data = open(binary_path, "rb").read()

    # Verify all patches are same length
    for desc, old, new in PATCHES:
        assert len(old) == len(new), f"Length mismatch in patch: {desc}"

    # Check if already patched
    if all(data.count(old) == 0 and data.count(new) > 0 for _, old, new in PATCHES):
        print("Already patched!")
        return True

    # Check if patchable
    for desc, old, new in PATCHES:
        if data.count(old) == 0:
            print(f"Error: pattern not found for: {desc}")
            print(
                "The minified function names may have changed in this version.\n"
                "Run: strings <binary> | grep 'buddy is unavailable'\n"
                "to locate the new names, then update PATCHES in this script."
            )
            return False

    # Backup
    if not os.path.exists(backup_path):
        shutil.copy2(binary_path, backup_path)
        print(f"Backup: {backup_path}")
    else:
        print(f"Backup exists: {backup_path}")

    # Apply patches
    for desc, old, new in PATCHES:
        count = data.count(old)
        data = data.replace(old, new)
        print(f"Patched {count}x: {desc}")

    with open(binary_path, "wb") as f:
        f.write(data)

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
