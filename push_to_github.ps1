# One-time push script for lean-tech-agents
# Right-click this file > "Run with PowerShell"
# Or from terminal: powershell -ExecutionPolicy Bypass -File push_to_github.ps1

Set-Location $PSScriptRoot

git init -b main
git remote add origin https://github.com/chiptuned/lean-tech-agents.git
git add -A
git commit -m "feat: initial lean tech agents template with MCP server"
git push --force origin main

Write-Host "`nDone! https://github.com/chiptuned/lean-tech-agents" -ForegroundColor Green
Read-Host "Press Enter to close"
