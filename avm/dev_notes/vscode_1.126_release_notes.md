# VS Code 1.126 Release Notes — Practical Summary

**Released:** June 24, 2026
**Scope:** Cost transparency, model tuning simplification, safer browsing of unfamiliar code, expanded Agents window behavior.

---

## 1. Cost Management

Session-level chat cost is now visible for an entire chat session, not just per-message.

**Why it matters:** Copilot/agent sessions can run long, multi-turn, tool-heavy conversations without an obvious running total. Per-message cost display hides cumulative spend, especially in agentic workflows where one user prompt can trigger many tool calls and follow-up turns. Session-level visibility makes runaway-cost sessions detectable *during* the session instead of only after the bill arrives — relevant for long agent-driven refactors or multi-file codebase work.

## 2. Language Model Configuration

Context size and reasoning/thinking effort are now unified in one model customization picker. Model hover text is simplified to concise capability descriptors with deep links into configuration.

**Why it matters:** Tuning a model used to mean hunting across separate settings for context window and reasoning effort. One picker reduces friction for matching model behavior to task type — e.g., dialing down reasoning effort for quick edits, raising it for complex multi-file logic — without leaving the editor. Faster iteration on model choice mid-session.

## 3. Agents Window Preview

Multiple chats can now run inside one agent-host Copilot session. Chats share session/workspace context but keep separate conversations. Chats persist across reloads. Tabs can be renamed.

**Why it matters:** This directly enables parallel agent roles within one workspace context — one chat implementing a change, another reviewing it, another running/testing, another drafting documentation — without losing shared context between them or re-establishing it per chat. Persistence across reloads means a long-running implement/review/test split doesn't get wiped by an editor restart. Renaming tabs makes a multi-chat setup actually navigable instead of a wall of identical "Chat" tabs.

## 4. Agentic Code Feedback

Code comments on generated code are now stored on the agent host. Agents can use tools like `listComments`, `resolveComments`, and `addComment`. `/code-review` can add inline comments directly. PR review comments can be accepted/submitted to the agent, or resolved by the agent with permission.

**Why it matters:** This closes the loop between automated review and the agent that generated the code — instead of a human manually relaying reviewer feedback back into a chat, the agent can read, act on, and resolve comments directly. Shortens the implement → review → fix cycle, particularly relevant for `/code-review` output and PR-based workflows.

## 5. Workspace Trust / Restricted Mode

New folders now open in **Restricted Mode** by default instead of interrupting with a trust dialog. Default for `security.workspace.trust.startupPrompt` changed from `once` to `never`. The **Trust Parent** button was removed to prevent accidentally trusting a broader folder than intended.

**Why it matters:** Opening an unfamiliar repo (a cloned tool, a downloaded script, a third-party project) no longer forces an immediate trust/distrust decision — it opens safely restricted by default, and you can inspect before deciding to trust. Removing "Trust Parent" closes a specific accidental-overtrust path (granting trust to a parent folder broader than the one actually being inspected).

## 6. Website/Docs Updates

VS Code blog now has a landing page and archive. Docs table of contents reorganized: agentic docs now under "Agents," editing/configuration docs under "Editor."

**Why it matters:** Pure navigation/discoverability change — no functional impact, but agentic-feature docs are now easier to find as a distinct category rather than mixed into general editor docs.

## 7. Deprecated Features

None this release.

---

## Impact for digitalscorpyun

- **Claude Code / Copilot agent workflows:** the Agents window's multi-chat-one-session model is the most directly relevant change — supports a real implement/review/test/document split across separate, nameable, persistent chat tabs sharing one workspace context, rather than juggling that manually.
- **Vault vs. Forge safety:** Restricted Mode as the new default for unfamiliar folders is a meaningful safety improvement specifically when inspecting third-party repos or cloned tools before deciding whether they belong in Forge at all — inspection no longer requires an immediate trust decision.
- **Cost visibility:** session-level cost display is directly useful for monitoring long agentic sessions (e.g., large Vault Glyph Audit-style batch operations) before they run away on spend.
- **Workspace trust hygiene:** the removed "Trust Parent" button closes a real accidental-overtrust risk — worth knowing this option is gone if a past habit relied on it.
- **Parallel review/test/documentation chats:** directly enables splitting a single task (e.g., a Forge tooling change) into separate, persistent, shared-context chats for implementation vs. review vs. test vs. doc-writing, without re-explaining context to each one.
