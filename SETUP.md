# Setup Guide

## 1. Push to GitHub (from your machine)

```bash
cd "path/to/Lean Tech Agents"

# Init and push
git init -b main
git add -A
git commit -m "feat: initial lean tech agents template with MCP server"

gh repo create lean-tech-agents --public --source . --push
```

## 2. Install on Another Computer

### Option A: As an MCP server (recommended for Claude Code / Cowork)

```bash
# Install globally with uv
uv tool install git+https://github.com/YOUR_USER/lean-tech-agents

# Or from local clone
git clone https://github.com/YOUR_USER/lean-tech-agents
cd lean-tech-agents
uv sync
```

Then add to your Claude Code / Claude Desktop config (`~/.claude/settings.json` or Claude Desktop settings):

```json
{
  "mcpServers": {
    "lean-tech": {
      "command": "uv",
      "args": ["run", "--from", "lean-tech-agents", "lean-agents", "serve"]
    }
  }
}
```

After connecting, Claude will have access to all lean tools: kanban management, quality gates, SQDCE scoring, PISCAR problem-solving, and kaizen tracking.

### Option B: As a project template

```bash
# Clone and use as starting point for a new project
gh repo create my-new-project --template YOUR_USER/lean-tech-agents --clone

cd my-new-project
uv sync
```

### Option C: As a Python package (SDK usage)

```bash
uv add git+https://github.com/YOUR_USER/lean-tech-agents

# Then in your code:
from lean_agents.orchestrator import Orchestrator

orchestrator = Orchestrator()
result = await orchestrator.run("Build feature X")
```

## 3. Test It

```bash
# Run the CLI
lean-agents version
lean-agents run "Add a health check endpoint" --budget 2.0

# Or start the MCP server
lean-agents serve
```

## 4. Give Feedback

After testing, create GitHub issues with:
- What worked well
- What felt redundant or over-engineered
- Where the agents got stuck
- Missing lean concepts that should be tools
- Quality gate improvements

Use the PISCAR format for bug reports:
- **Problem**: What happened
- **Impact**: What was affected (SQDCE)
- **Standard**: What should have happened
- **Causes**: Why you think it happened
- **Action**: Suggested fix
- **Result**: How to verify the fix
