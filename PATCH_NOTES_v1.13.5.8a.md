# TCT v1.13.5.8a — Ethan Boyd image regression test correction

This is a test-only follow-up to v1.13.5.8. It does not change production rendering,
article content, membership behavior, image selection, ranking, or story identity.

## Why the Test Editorial Engine workflow failed

`tests/test_article_image_overrides.py::test_current_surfaces_use_selected_image`
searched the homepage for the first link to the Ethan Boyd canonical article and then
required that exact `<a>` element to contain the selected article image.

That assumption is no longer valid. A story can legitimately appear in a text-only
homepage surface such as the **Older News** rail. In the failing workflow state, the
first matching link was an `older-link`, which intentionally contains only the
headline and date. The image override itself remained correct on the archive row,
article OG/Twitter metadata, article hero, and feed.

## Fix

The regression now:

- requires at least one homepage link to the canonical article;
- distinguishes text-only links from image-bearing placements;
- ignores text-only placements for image assertions; and
- requires every image-bearing homepage placement for the article to use
  `https://treasurecoast.today/images/ethan-boyd.png`.

The archive, article hero/social metadata, and RSS image assertions remain unchanged.

## Validation

- The previously failing test passes locally after the assertion correction.
- The uploaded GitHub Actions run reached 859 collected tests with 858 passing and
  only this assertion failing, so no production-code regression was indicated by the
  workflow failure.

Run **Test Editorial Engine** again. If it is green, proceed with the normal
**Update Treasure Coast Today** production workflow for v1.13.5.8.
