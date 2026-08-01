# TCT v1.12.2.9 — RSS Image Authority Ledger and Sitewide Newsletter Modal

## RSS image contract correction

The v1.12.2.8 run still stopped with four image-policy violations after persisting source-image metadata. The remaining split was caused by the validator independently recomputing category fallback images from archive metadata while the RSS renderer could use richer current-run category context. Both decisions were individually reasonable, but they were not guaranteed to resolve the same category for archive-recovery placements.

The RSS renderer now writes an explicit per-item authority ledger to:

`data/rss-social-image-authority.json`

Each RSS item records its exact selected image, image kind (`source` or `category_og`), canonical category key, and selection origin. The same authority is persisted on the archive row and synchronized into article Open Graph and Twitter metadata before validation.

The validator now checks the emitted feed against that persisted authority decision rather than attempting to recreate a second decision from different inputs. It still independently enforces that source images are valid publisher images and category fallbacks are the correct green category OG cards. Editorial placeholders remain prohibited from RSS and social metadata.

Social metadata synchronization now handles `<meta>` attributes in any order and inserts missing OG or Twitter image tags when necessary.

## Newsletter presentation change

The desktop sticky newsletter bar has been retired. Kit modal `be625cadfe` is now loaded once on desktop and mobile. The former sticky UID `4edef44197` is no longer loaded, and all sticky-layer masthead offset JavaScript has been removed.

On mobile, the modal is constrained to leave 24 pixels of visible backdrop on each side and 32 pixels above and below, making the close control and outside-dismiss area easier to reach.
