# Treasure Coast Today editorial fallback image pool

Release: **v1.11.4.9.3 fallback-subject-and-source-image-protection**

The generator now discovers reusable fallback images from:

```text
/images/editorial/
```

No code change is required when a new valid image is added to an existing folder. The next successful production run discovers it automatically.

## Selection order

A usable explicit or publisher source image always wins. If a live card loses its
image metadata during promotion or rebinding, the generator restores the exact source
image already stored on its permanent archive record before considering a fallback.

When a fallback is still needed, the selector uses the first populated match:

1. A specific subject found in the headline or teaser: schools, road infrastructure/traffic operations, health, or weather/environment
2. Exact city folder detected from the story
3. Strong broad category or detected topic folder, including approved `og-*` graphics
4. County folder, once county-specific photographs are added
5. A round-robin pool made from that county's city folders
6. `general/treasure-coast`
7. The existing root TCT OG graphic

Full article body text is not used for topic-image classification. This prevents an
incidental mention of a road, airport, hospital, or school from overriding the actual
subject of the story. Crash and collision wording alone no longer sends a public-safety
story to the roads pool, and airline/airport route stories are not treated as road stories.

Examples:

- A Fort Pierce arrest story uses `cities/fort-pierce/`.
- A countywide crime story uses `topics/crime-public-safety/`.
- A Martin County story with no clear city or topic rotates through Martin County city folders.
- A statewide hurricane story uses `topics/weather-environment/`.
- A story with no better match uses `general/treasure-coast/`.

## Rotation behavior

Each story receives one persistent assignment. The assignment is saved in:

```text
/data/editorial-image-rotation.json
```

For every new story:

- Images are selected in filename order within the chosen folder.
- The cursor advances after each assignment.
- The last image in a folder is followed by the first image on the next cycle.
- The selector avoids immediately repeating the previous image when another image is available.
- The same story keeps the same assigned image across homepage, category, archive and article surfaces.
- Rotation state is saved only after the production build passes its publication and presentation gates.

## Current library

The supplied image map contains **55 usable editorial images across 20 pools**. The five topic-level `og-*` graphics are included as distinct rotation assets.

| Pool | Images |
|---|---:|
| `cities/fellsmere` | 2 |
| `cities/fort-pierce` | 3 |
| `cities/hobe-sound` | 2 |
| `cities/jensen-beach` | 2 |
| `cities/palm-city` | 2 |
| `cities/port-salerno` | 2 |
| `cities/port-st-lucie` | 3 |
| `cities/sebastian` | 2 |
| `cities/stuart` | 4 |
| `cities/vero-beach` | 2 |
| `general/treasure-coast` | 4 |
| `topics/business-development` | 3 |
| `topics/crime-public-safety` | 3 |
| `topics/health` | 3 |
| `topics/local-government` | 3 |
| `topics/roads-transportation` | 3 |
| `topics/schools` | 3 |
| `topics/sports` | 3 |
| `topics/things-to-do` | 3 |
| `topics/weather-environment` | 3 |

The `counties/` folders are currently empty. The selector is already prepared to use these future folders:

```text
images/editorial/counties/martin/
images/editorial/counties/st-lucie/
images/editorial/counties/indian-river/
```

## Optimization

The supplied originals total approximately **172 MB**. This release uses 55 optimized WebP counterparts totaling approximately **8.8 MB**. The originals remain untouched.

The inventory automatically prefers formats in this order:

```text
WebP → JPG → JPEG → PNG
```

Files with the same folder and filename stem are treated as alternate formats of one image. For example:

```text
fort-pierce-marina.webp
fort-pierce-marina.jpg
fort-pierce-marina.png
```

count as one image, with the WebP version selected.

## Files intentionally excluded

The system ignores:

- `README.md`
- `desktop.ini`
- placeholder files named `place`
- non-image files
- duplicate alternate formats

Topic-level `og-*` graphics are deliberately included in their matching topic pools. Their optimized WebP counterparts are preferred over the larger PNG originals. Root-level OG files still remain the emergency fallback when no editorial pool is available.

## Reports

Each successful run writes:

```text
/data/editorial-image-rotation-report.json
```

It records:

- Discovered image and pool counts
- Excluded files and reasons
- New and reused assignments
- Pool usage during the run
- Persistent assignment count

A full archive migration runs once for each image-selection policy version and writes:

```text
/data/editorial-image-migration.json
```

That report records managed fallback URLs replaced in non-custom archive records and permanent article pages. Normal production runs skip the archive-wide scan after the current policy version has completed.

## Adding images later

Place the new image in the most specific existing folder and give it a descriptive lowercase filename. WebP is preferred.

```text
images/editorial/cities/stuart/stuart-city-hall-exterior-02.webp
images/editorial/topics/schools/school-bus-arrival-02.webp
images/editorial/counties/martin/martin-county-administration-01.webp
```

Do not add article-specific images to this pool. Those should continue to be referenced directly by the article payload.
