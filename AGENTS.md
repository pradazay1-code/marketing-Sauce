# Agent Instructions

> This file is mirrored across CLAUDE.md and AGENTS.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, API tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work.

**Why this works:** If you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-amend when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Website Delivery Format**
When the user asks for a website (for any client), always deliver it as:
- A **single self-contained HTML file** with all CSS, JS, and SVG inline — no external stylesheets, scripts, or image dependencies
- Output the **full HTML code directly in the chat** so the user can copy-paste it into a file and open it in their browser
- Use `<img src="images/...">` tags for portfolio/photo images (the user will add their own), not placeholder divs

**4. Client work lives in `clients/`**
- Each client gets their own folder: `clients/{client-name}/`
- Website files, assets, images all go inside the client folder
- Keep client work organized and separated

**5. Don't guess, ask**
- If a directive is ambiguous, ask the user before executing
- If you're unsure which script to run, ask
- Better to clarify than to waste tokens or break something

## Directory Structure

```
marketing-Sauce/
├── clients/           # Client projects (websites, assets, deliverables)
├── directives/        # SOPs and task instructions (Markdown)
├── execution/         # Deterministic scripts (Python, Shell)
├── scripts/           # Utility scripts
├── tools/             # Reusable tools and helpers
├── .env               # Environment variables (API keys, tokens)
├── .env.example       # Template for .env
├── .gitignore         # Git ignore rules
├── CLAUDE.md          # Agent instructions
├── AGENTS.md          # This file - mirror of CLAUDE.md
└── requirements.txt   # Python dependencies
```

## Current Clients

- **North Atlantic Tattoo** — Custom tattoo studio in New Bedford, MA (`clients/north-atlantic-tattoo/`)
