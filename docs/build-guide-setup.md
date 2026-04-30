> **Historical document** — used to bootstrap code generation in sessions 1–10. Not needed for active development. See CLAUDE.md for current project rules.

# Build Guide Part 1: One-Time Setup

*Full index: see [build-guide.md](build-guide.md)*

---

## PART 1 — ONE-TIME SETUP

### Step 1 — Install WSL2 on Windows

Open **PowerShell as Administrator**:
```
wsl --install
```
Restart your computer. After restart, Ubuntu terminal opens — create Linux username and password.

### Step 2 — Install Node.js inside WSL2

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version  # Should print v20.x.x
```

### Step 3 — Install Python 3.12 inside WSL2

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip
python3.12 --version  # Should print Python 3.12.x
```

### Step 4 — Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### Step 5 — Authenticate Claude Code

Get Anthropic API key from https://console.anthropic.com → API Keys → Create Key. Then run `claude` — it will open a browser to authenticate.

### Step 6 — Create the GitHub repository

Create a new **private** repository called `ai-recruiter` at https://github.com. Do NOT initialise with a README.

```bash
sudo apt install -y git
git config --global user.email "your@email.com"
git config --global user.name "Your Name"
```

### Step 7 — Create the project folder

```bash
cd /mnt/c/Users/YourWindowsUsername/Documents
mkdir ai-recruiter && cd ai-recruiter
git init
git remote add origin https://github.com/yourusername/ai-recruiter.git
```

Copy `SPEC.md` and `guidelines.md` into this folder, then create `.env.example`:

```bash
cat > .env.example << 'EOF'
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_ANON_KEY=your-anon-key
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=sk_test_your-key
STRIPE_WEBHOOK_SECRET=whsec_your-secret
SENDGRID_API_KEY=SG.your-key
ENCRYPTION_KEY=your-fernet-key
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
EOF
```

First commit:
```bash
git add . && git commit -m "Initial: add SPEC.md, guidelines.md, .env.example"
git push -u origin main
```

### Step 8 — Open the project in PyCharm

File → Open → navigate to the project folder. Create a virtual environment (Settings → Python Interpreter → Add → Virtual Environment). Leave PyCharm open — it shows files appearing in real time as Claude Code generates them.

---

## How to start a Claude Code session

```bash
cd /mnt/c/Users/YourName/Documents/ai-recruiter
claude
```

This starts the interactive session. Paste your task prompt. At the end of each session, type `/exit` or press `Ctrl+C`.

**Golden rule: one module per session, commit after each one.**
