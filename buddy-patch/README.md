# buddy-patch

<p align="center">
  <img src="https://img.shields.io/badge/status-working-brightgreen.svg" alt="Status: Working">
  <img src="https://img.shields.io/badge/python-3.6+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.6+">
  <img src="https://img.shields.io/badge/macOS-ARM64-000000.svg?logo=apple&logoColor=white" alt="macOS ARM64">
  <img src="https://img.shields.io/badge/Linux-x86__64-FCC624.svg?logo=linux&logoColor=black" alt="Linux x86_64">
</p>

> Fix `/buddy` broken in Claude Code **v2.1.90** — the companion pet is unavailable for all users, not just specific providers.
>
> 修复 Claude Code **v2.1.90** 中 `/buddy` 功能失效的问题 —— 该版本下所有用户均无法使用伴生宠物，而非仅限特定 Provider。

---

<p align="center">
  <img src="./resources/buddy-idle.png" width="200" alt="Wild CAPYBARA appeared!">
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="./resources/buddy-stats.png" width="280" alt="Gotcha! CAPYBARA was caught!">
</p>

<p align="center">
  <i>Wild CAPYBARA appeared! &nbsp;···&nbsp; Gotcha! CAPYBARA was caught!</i><br/>
  <i>野生的卡皮巴拉出现了！ &nbsp;···&nbsp; 抓到了！卡皮巴拉被收服了！</i>
</p>

---

## What is `/buddy`? / 什么是 `/buddy`？

<table>
<tr><td><b>English</b></td><td><b>中文</b></td></tr>
<tr>
<td>

Claude Code v2.1.x ships with a hidden companion pet system. Run `/buddy` and you'll hatch an ASCII-art creature that lives beside your input box:

- Idle animations — fidgets, blinks, breathes
- Reacts to events — errors, large diffs, test failures pop speech bubbles
- Responds when you mention its name in conversation

In v2.1.90, the `isBuddyLive()` function is broken — it returns `false` for **all** users, so everyone sees:

```
buddy is unavailable on this configuration
```

This script fixes that.

</td>
<td>

Claude Code v2.1.x 内置了一个隐藏的伴生宠物系统。运行 `/buddy` 即可孵化一个住在输入框旁的 ASCII 小生物：

- 待机动画 —— 扭动、眨眼、呼吸
- 事件反应 —— 报错、大段 diff、测试失败时弹出对话气泡
- 在对话中提到它的名字时会回应

在 v2.1.90 中，`isBuddyLive()` 函数存在问题 —— 对**所有**用户都返回 `false`，因此所有人都会看到：

```
buddy is unavailable on this configuration
```

本脚本解决这个问题。

</td>
</tr>
</table>

## How it works / 工作原理

The compiled binary contains `isBuddyLive()`, which gates the feature. In v2.1.90 this function returns `false` for all users:

编译后的二进制文件中包含 `isBuddyLive()` 函数，用于控制功能开关。在 v2.1.90 中该函数对所有用户均返回 `false`：

```js
function isBuddyLive() {
  if (getProvider() !== "firstParty") return false;
  if (isSimpleMode()) return false;
  return date >= April 2026;  // <-- broken in v2.1.90 / 在 v2.1.90 中失效
}
```

The script applies two same-length byte patches / 脚本应用两个等长字节替换：

| Patch / 补丁 | Before / 替换前 | After / 替换后 | Effect / 效果 |
|-------|--------|-------|--------|
| Function def / 函数定义 | `"firstParty"` | `"xirstParty"` | Neutralize provider gate / 消除 Provider 门控 |
| Call site / 调用处 | `if(!FN())` | `if(!0&&!1)` | Condition always false, guard skipped / 条件恒为 false，跳过守卫 |

> [!NOTE]
> **Auto-detection / 自动检测**: The script locates the minified function name by matching the unique structure of `isBuddyLive` (its `getFullYear()>2026` date check distinguishes it from other `firstParty` gates). No hardcoded names to update when the minifier shuffles identifiers.
>
> 脚本通过匹配 `isBuddyLive` 的独特结构（`getFullYear()>2026` 日期检查）自动定位混淆后的函数名，与其他 `firstParty` 守卫区分开来。混淆器重新分配标识符时无需手动更新。

On macOS ARM64, the binary is re-signed with an ad-hoc signature (required by the kernel).

在 macOS ARM64 上，补丁后会重新进行 ad-hoc 签名（内核要求）。

## Usage / 使用方法

```bash
# Auto-detect latest Claude binary / 自动检测最新的 Claude 二进制文件
python3 patch-buddy.py

# Or specify path explicitly / 或手动指定路径
python3 patch-buddy.py ~/.local/share/claude/versions/2.1.90
```

After patching, restart Claude Code and run `/buddy` to hatch your companion.

补丁完成后，重启 Claude Code 并运行 `/buddy` 来孵化你的宠物。

## `/buddy` commands / `/buddy` 命令

| Command / 命令 | Description / 说明 |
|---------|-------------|
| `/buddy` | Hatch (first time) or view stats card / 孵化（首次）或查看状态卡 |
| `/buddy pet` | Pet your companion / 抚摸你的宠物 |
| `/buddy off` | Mute the companion / 静音宠物 |
| `/buddy on` | Unmute the companion / 取消静音 |

## After Claude Code updates / Claude Code 更新后

Updates overwrite the binary — re-run the script. Automate with a session hook:

更新会覆盖二进制文件 —— 需重新运行脚本。可通过 hook 自动化：

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

The script is idempotent — exits immediately if already patched.

脚本是幂等的 —— 已补丁时会立即退出。

## Compatibility / 兼容性

| | |
|---|---|
| **Tested on / 已测试** | Claude Code v2.1.90 — macOS ARM64 & Linux x86-64 |
| **Requires / 依赖** | Python 3.6+, `codesign` (macOS only) |
| **Version resilience / 版本适应性** | Minified names auto-detected via regex. Fails cleanly if function *structure* changes. / 混淆名称通过正则自动检测。仅在函数*结构*变化时才会失败。 |

## Restoring / 还原

The script creates a `.bak` before patching / 脚本在补丁前会创建 `.bak` 备份：

```bash
cp ~/.local/share/claude/versions/2.1.90.bak ~/.local/share/claude/versions/2.1.90
```
