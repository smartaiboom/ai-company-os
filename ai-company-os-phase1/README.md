# AI Company OS — Phase 1

A small, dependency-free starter for project management and saved state.

## What is included
- Create and list projects
- Open a project and update its status
- Save project state to JSON
- Store artifacts in a project-specific folder
- Resume by reopening saved project state

## Run
From this folder:

```bash
python app.py
```

Then open the URL printed in the terminal (default: http://127.0.0.1:8000).

## Data safety
All new data is written only under this folder's `data/` directory.
This starter does not access, move, or modify files from the existing AI Company OS project.
No API calls are made in Phase 1.

## Phase 1 acceptance checks
1. Create a project.
2. Refresh the page; the project remains listed.
3. Open the project and change its status.
4. Restart the app and confirm the status remains saved.
5. Confirm the project has its own artifacts directory.
