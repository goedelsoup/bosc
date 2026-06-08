# Brewfile — Homebrew fallback when not using mise.
#
# Prefer mise (see mise.toml), which pins exact versions per-project. This
# mirrors the same toolchain via Homebrew for environments without mise:
#
#   brew bundle            # install everything below
#
# Then bootstrap the project the same way mise's setup task does:
#   uv sync --extra dev && git lfs install --local
#   npm install -g @anthropic-ai/claude-code

brew "python@3.11"   # mise manages this itself; pinned here for the fallback
brew "uv"            # env + dependency manager
brew "node"          # provides npm for the Claude Code CLI
brew "git-lfs"       # versioning large source scans (see .gitattributes)
brew "tesseract"     # optional OCR for image-only scanned minutes (bosc subdivisions index --ocr)
