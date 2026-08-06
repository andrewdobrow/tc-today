# v1.13.1.3 review guide

1. Extract the overlay at the repository root and commit all files.
2. Run **Test Editorial Engine**.
3. Confirm the step `Apply generator runtime hotfix` reports either:
   - `html_alias_changed=True` and `registry_batching_changed=True` on its first run, or
   - both values `False` after the patch has already been committed.
4. Run **Update Treasure Coast Today**.
5. Confirm generation no longer ends with `NameError: name 'html' is not defined`.
6. Compare category audit timing. Audit entries should no longer incur a persistent
   registry write for every candidate.

The Ethan Boyd canonical article and its manual image override are not replaced or
removed by this overlay.
