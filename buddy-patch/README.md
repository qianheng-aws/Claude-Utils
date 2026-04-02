# buddy-patch

Enable the `/buddy` companion pet feature on Claude Code with non-firstParty providers (Bedrock, Vertex, etc.).

## Background

Claude Code v2.1.x includes a built-in companion pet system (`/buddy`) that lets you hatch an ASCII-art coding companion. The companion sits beside your input, animates, and reacts to your conversation with speech bubbles.

However, the feature is gated by a provider check — only `firstParty` (direct Anthropic API) users can access it. Users on AWS Bedrock, Google Vertex, or other providers see:

```
buddy is unavailable on this configuration
```

This script patches the compiled binary to bypass the provider check while preserving all other guards (date check, simple-mode check).

## How it works

The Claude Code binary (Bun-compiled Mach-O) contains two guards:

```js
// Guard 1: isBuddyLive() function definition
function isBuddyLive() {
  if (getProvider() !== "firstParty") return false;  // ← patched out
  if (isSimpleMode()) return false;
  return date >= April 2026;
}

// Guard 2: /buddy command handler
if (!isBuddyLive()) {
  return "buddy is unavailable on this configuration";  // ← patched out
}
```

The script applies two same-length byte replacements:

| Location | Before | After | Effect |
|----------|--------|-------|--------|
| Function def | `"firstParty"` | `"xirstParty"` | No provider matches → all pass through to date check |
| Call site | `if(!Qn_())` | `if(!0&&!1)` | Condition is always `false` → block never entered |

On macOS ARM64, the binary is re-signed with an ad-hoc signature (required by the kernel).

## Usage

```bash
# Auto-detect latest Claude binary
python3 patch-buddy.py

# Or specify path explicitly
python3 patch-buddy.py ~/.local/share/claude/versions/2.1.90
```

After patching, restart Claude Code and run `/buddy` to hatch your companion.

## /buddy commands

| Command | Description |
|---------|-------------|
| `/buddy` | Hatch (first time) or view your companion's stats card |
| `/buddy pet` | Pet your companion (triggers heart animation) |
| `/buddy off` | Mute the companion |
| `/buddy on` | Unmute the companion |

Your companion also:
- Animates with idle/fidget/blink cycles beside the input box
- Reacts to errors, large diffs, and test failures via speech bubbles
- Responds when you mention its name in conversation

## After Claude Code updates

Updates overwrite the binary — re-run the script after each update. You can automate this with a session hook:

```json
// ~/.claude/settings.json
{
  "hooks": {
    "onSessionStart": [{
      "command": "python3 /path/to/patch-buddy.py 2>/dev/null || true"
    }]
  }
}
```

The script is idempotent — it exits immediately if already patched.

## Compatibility

- **Tested on**: Claude Code v2.1.90, macOS ARM64 (Apple Silicon)
- **Requires**: Python 3.6+, `codesign` (macOS only, for re-signing)
- **Risk**: Minified function names (`Qn_`, `Jq`) may change across versions. If the script reports "pattern not found", the names need updating. See the script comments for how to locate them.

## Restoring

```bash
# Restore from backup
cp ~/.local/share/claude/versions/2.1.90.bak ~/.local/share/claude/versions/2.1.90
```
