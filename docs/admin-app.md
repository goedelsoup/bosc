# The admin GitHub App — bootstrap

**Status:** design (Epic #919, as of 2026-07-02) — describes the *planned* admin App;
not yet built. The present-tense below is the target design, not a live system.

The admin App (`watermark-admin-bot`, issue
[#919](https://github.com/watermark-directory/the-watermark-directory/issues/919))
is a separate **GitHub App** identity that allows the Watermark Directory backend to
post PR comments, manage labels, and transition issue states — operations gated to
**admin** and **site-admin** users.

It is intentionally distinct from `bosc-research-bot` so the two identities appear
separately in the audit log (research writes vs. admin writes).

## 1. Register the App

GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**.

- **Name:** `watermark-admin-bot` (or `bosc-admin-bot` if the org name is not yet
  updated).
- **Homepage URL:** the repo URL is fine.
- **Webhook:** **uncheck Active** — the App is called directly from the backend, not via
  webhook delivery.
- **Repository permissions (least privilege):**

  | Permission | Access | Why |
  | --- | --- | --- |
  | Issues | Read & write | comment, label, open/close |
  | Pull requests | Read & write | PR comments and labels |
  | Metadata | Read | mandatory baseline |

  Leave everything else **No access**. The App does **not** need Contents access.

- **Where can this App be installed?** Only on this account.

Create the App, then note its **App ID** and **generate a private key** (downloads a
`.pem`).

## 2. Convert the private key to PKCS#8 (optional)

GitHub generates PKCS#1 keys by default. PyJWT + `cryptography` handles both formats,
so conversion is only needed if your tooling requires PKCS#8:

```sh
openssl pkcs8 -topk8 -nocrypt -in watermark-admin-bot.pem -out watermark-admin-bot.pkcs8.pem
```

The raw PKCS#1 `.pem` from GitHub works as-is — you can skip this step.

## 3. Install the App on the repo

From the App's page → **Install App** → install on
`watermark-directory/the-watermark-directory`, **Only select repositories**.

After installation, find the **Installation ID** in the URL:
`https://github.com/settings/installations/<INSTALLATION_ID>`.

## 4. Set the environment variables

For local / CLI use, add to your `.env` (never commit):

```sh
WATERMARK_GITHUB_APP_ID=<app_id>
WATERMARK_GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----"
WATERMARK_GITHUB_APP_INSTALLATION_ID=<installation_id>
```

For GitHub Actions, store as repository **secrets**:

| Secret | Value |
| --- | --- |
| `ADMIN_APP_ID` | The App ID integer |
| `ADMIN_APP_PRIVATE_KEY` | Full PEM contents |
| `ADMIN_APP_INSTALLATION_ID` | The installation ID integer |

Then pass them to the workflow step:

```yaml
env:
  WATERMARK_GITHUB_APP_ID: ${{ secrets.ADMIN_APP_ID }}
  WATERMARK_GITHUB_APP_PRIVATE_KEY: ${{ secrets.ADMIN_APP_PRIVATE_KEY }}
  WATERMARK_GITHUB_APP_INSTALLATION_ID: ${{ secrets.ADMIN_APP_INSTALLATION_ID }}
```

## 5. Configure admin users

Set the comma-separated allowlist of GitHub logins that may trigger write operations:

```sh
WATERMARK_ADMIN_LOGINS=goedelsoup,alice
```

For per-site admin access (without platform-wide admin), use the site-scoped env var
(slug uppercased):

```sh
WATERMARK_SITE_ADMIN_LOGINS_LIMA=bob
WATERMARK_SITE_ADMIN_LOGINS_FORTWAYNE=carol
```

## 6. GH Actions trust flag

When the backend runs inside a GH Actions workflow and `GITHUB_ACTOR` is not set (or
should not be the gating identity), enable the trust flag:

```sh
WATERMARK_GITHUB_APP_TRUSTED=true
```

This allows a `None` caller identity to pass permission checks — meaning the App
itself is the trusted operator. **Do not set this in local `.env` files.**

## 7. Verify the setup

```sh
# Confirm credentials are loaded
mise run dev -- python -c "
from watermark.config import get_settings
from watermark.github import GitHubAppClient
s = get_settings()
print('Configured:', GitHubAppClient.is_configured(s))
"
```

## Available backend operations

Once configured, the research agent gains four write tools (all gated by App
credentials + caller permissions):

| Tool | Description |
| --- | --- |
| `comment_on_pr` | Post a Markdown comment on a PR or issue |
| `add_label` | Add a label to an issue or PR |
| `remove_label` | Remove a label from an issue or PR |
| `set_issue_state` | Open or close an issue |

These are also directly importable from `watermark.github`:

```python
from watermark.github import comment_on_pr, add_label, remove_label, set_issue_state
from watermark.config import get_settings

result = await comment_on_pr(get_settings(), pr_number=42, body="Reviewed.")
```
