# Treasure Coast Today v1.13.7.1l
## Sitewide Mediavine loader placement

This overlay is cumulative with v1.13.7.1k. If 1k has not yet been applied, 1l can be applied directly over the latest 1j production repo.

### Change

Treasure Coast Today now normalizes the required Mediavine loader across every rendered HTML page at the end of Generate News:

```html
<script type="text/javascript" async="async" data-noptimize="1" data-cfasync="false" src="//scripts.mediavine.com/tags/31bba1e2-0cf0-4381-8d83-ea54f9aa3bbf.js"></script>
```

The loader is placed exactly once and immediately before the page's closing `</head>` tag.

The normalization is recursive across the output tree, so it covers:
- homepage and category pages;
- all retained article pages, including legacy articles;
- author and static policy/about/advertising pages;
- any future HTML page generated into the site tree.

If an existing copy of the same Mediavine tag is present elsewhere in the head, it is removed and reinserted in the required position rather than duplicated.

### Production contract

At the end of Generate News the pipeline now verifies every `*.html` file under the output root. The build fails if any page:
- lacks the Mediavine loader;
- contains more than one copy of this loader; or
- does not have the loader immediately before `</head>`.

Expected log line:

`Mediavine loader contract PASSED: <N> HTML page(s) verified; <N> normalized this run`

On the first production run, most existing HTML files will be normalized. Subsequent runs should generally show only newly written/changed pages being normalized.

### 1k included

The v1.13.7.1k category-hero → Top Stories candidate fix is included in `scripts/generate.py` and its regression test is included in this overlay.

### Validation

- focused Mediavine tests: 3 passed
- exact Test Editorial Engine pytest command: 1,093 passed, 0 failed
- existing warnings: 44 deprecation warnings
- package validation: 38 modules imported / 122 public exports verified
