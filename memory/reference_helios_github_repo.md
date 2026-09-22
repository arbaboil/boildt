---
name: Helios GitHub repo — arbaboil/boildt (DO NOT CONFUSE with other repos on this machine)
description: The one GitHub repo that Helios pushes to and pulls from. Owner has multiple GitHub accounts/repos on this machine; this one is exclusively for the oil / Helios workspace.
type: reference
---

**Repo:** `https://github.com/arbaboil/boildt.git`
**Owner GitHub login for this repo:** `arbaboil`
**Purpose:** deploy + backup for the Helios oil workspace at `C:\Users\farha\OneDrive\Desktop\oil`
**Remote name:** `origin`
**Default branch:** `main` (tracks `origin/main`)

**Token storage.** The PAT is embedded in the `origin` URL in `.git/config` (local file, never committed). Personal Access Token starts with `github_pat_11CPIRYUY0...` (full value in `.git/config`).

**How to use.** For any `git push` / `git pull` / `git fetch` from Helios, `origin` already has the token embedded — plain `git push` works. Do NOT prepend a different token or switch remotes.

**IMPORTANT — never confuse with other repos.** Owner has multiple GitHub accounts and repos on this machine (FAR site, other agents' workspaces). This token is ONLY authorized for `arbaboil/boildt`. If you find yourself pushing to a URL that isn't `github.com/arbaboil/boildt.git`, STOP — you are on the wrong remote.

**Rotation.** If Owner rotates the token, they'll bring a new one. Update `.git/config` via `git remote set-url origin https://<NEW_TOKEN>@github.com/arbaboil/boildt.git`. Do not attempt to fetch tokens from any other source (env vars, keychain, other repos' configs) — Owner brings tokens explicitly per session.

**First push (2026-09-22).** All 16 commits from sessions 1-3 pushed successfully. Branch `main` tracks `origin/main`. `git status` clean apart from `.claude/scheduled_tasks.lock` which is session-transient.
