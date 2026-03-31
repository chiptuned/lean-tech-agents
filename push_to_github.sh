#!/bin/bash
# One-time push script for lean-tech-agents
# Run this from the "Lean Tech Agents" folder:
#   bash push_to_github.sh

set -e

echo "Initializing git repo..."
git init -b main

echo "Adding remote..."
git remote add origin https://github.com/chiptuned/lean-tech-agents.git

echo "Staging all files..."
git add -A

echo "Creating commit..."
git commit -m "feat: initial lean tech agents template with MCP server

Three-agent feedback loop (Planner/Builder/Reviewer) with pull-based
work, built-in quality gates, and continuous improvement.
Packaged as MCP server + CLI + Python library.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

echo "Pushing to GitHub (force push to overwrite the .gitignore-only commit)..."
git push --force origin main

echo ""
echo "Done! Your repo is live at: https://github.com/chiptuned/lean-tech-agents"
echo ""
echo "You can now delete this script:"
echo "  rm push_to_github.sh"
