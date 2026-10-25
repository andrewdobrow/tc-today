TCT Austin Hodge one-time repair workflow hotfix

Cause: The original Repair Austin Hodge canonical identity GitHub Action imported scripts/generate.py during focused tests without installing the generator runtime dependencies. GitHub raised ModuleNotFoundError: requests in three tests. The named-death logic was not reached.

Changed: ONLY .github/workflows/tct-hodge-canonical-repair.yml, inserting the same dependency installation used by Test Editorial Engine.

Deployment:
1. Extract this ZIP into the current tc-today repository, replacing the workflow file.
2. Commit and push.
3. Manually re-run Actions > Repair Austin Hodge canonical identity.
4. If green, run Test Editorial Engine, then Update Treasure Coast Today.
5. Verify the duplicate redirects to the original URL, the original image remains, and downstream feeds and protected content are consistent.

This ZIP intentionally does not replace scripts/generate.py, custom_articles.json, or previously installed identity helpers and tests. The previous failed one-time workflow stopped before its commit step; the code integration will be performed on rerun.
