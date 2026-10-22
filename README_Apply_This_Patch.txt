TCT CUSTOM ARTICLE IMAGE-ONLY UPDATE FIX
====================================

Problem:
The custom-article loader only compared body and product-guide content
when deciding if a published custom article should be skipped. An editor
could add/change image_url without triggering a fresh HTML render.

Change:
- Image-only edits now trigger an in-place update of the existing custom
  permalink, including the article image and Open Graph/Twitter image tags.
- An unchanged existing image remains a no-op; recognized source vs mirrored
  hosted URLs are treated as the same image.
- Updates three tests in existing test modules, including correcting an
  incomplete historical fixture that omitted the image already in the queue.
- Does not modify custom_articles.json, published article pages, archive.json,
  expiration behavior, subscriber access, or paid membership code.
- Does NOT force republishing every custom article on every run.

How to apply (from your LOCAL main TCT repo root, in Git Bash or PowerShell):
1. Extract the PATCH file in this ZIP to your repo root.
2. Verify it applies cleanly:
     git apply --check TCT_Custom_Article_Image_Only_Update_Fix.patch
3. Apply it:
     git apply TCT_Custom_Article_Image_Only_Update_Fix.patch
4. Review:
     git diff -- scripts/generate.py tests/test_custom_authority_contract.py tests/test_custom_archive_recovery_write_through.py
5. Commit and push, then run the normal Update workflow.

Your existing custom_articles.json entry already has the correct field:
  "image_url": "https://treasurecoast.today/images/hobgoblins-stuart.jpg"
Keep exactly one October 24-25 event guide entry in the custom queue.

This is a surgical patch, NOT a full replacement generate.py. Using git apply
prevents an old copy of the 2MB generator from overwriting unrelated recent
newsroom fixes. If --check fails, do not force it; use your newer live repo to
reconcile and produce a revised patch.

Workaround when not applying the patch:
Add "republish": true to the current custom article entry, run Update once,
then remove it. This forces the existing article to render even without a
body change; it should not be left enabled permanently.

Validation:
- 52 relevant tests passed using the available Oct 19 repo snapshot and a
  newer current custom-weekend regression suite.
- git apply --check verified against the Oct 19 source and byte-for-byte
  matched the tested patched files.
- Live website/image network fetches were not available in the sandbox.
