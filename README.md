# Aura_Belle
At AuraBelle, we believe every stitch, brushstrokes and clay curve tells a story. It is an e-commerce website which is born from simple yet powerful idea which is to bridge the gap between traditional artistry and today's world, In a time where everything is fast and factory-made, we choose to slow down and value the human touch.

## Database reliability notes
- SQLite now defaults to `%LOCALAPPDATA%/AuraBelle/database.db` to avoid OneDrive file-lock conflicts.
- To use a custom database path, set `DATABASE_PATH` before running the app.
- On first run, if a legacy `database.db` exists in the project root, it is auto-copied to the new default path.
