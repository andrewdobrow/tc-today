# TCT Editorial Photo Library Framework

This framework is for reusable, real Treasure Coast photography that can eventually sit between article-specific source images and the branded `og-*.png` fallback graphics.

## Intended image priority

1. Explicit image supplied with a custom article
2. Valid image from the source article (`media:content`, enclosure, `og:image`, `twitter:image`, JSON-LD, or article body)
3. Matching real photograph from this TCT editorial library
4. Matching branded TCT `og-*.png` graphic
5. Generic `og-image.png`

The current release activates steps 4 and 5. The real-photo pool can be enabled after enough images and metadata have been added.

## Storage structure

Store reusable photos under `images/editorial/`:

```text
images/editorial/
  counties/
    martin/
    st-lucie/
    indian-river/
  cities/
    hobe-sound/
    stuart/
    jensen-beach/
    palm-city/
    port-salerno/
    port-st-lucie/
    fort-pierce/
    vero-beach/
    sebastian/
    fellsmere/
  topics/
    local-government/
    crime-public-safety/
    business-development/
    schools/
    sports/
    things-to-do/
    roads-transportation/
    weather-environment/
    health/
  regional/
    treasure-coast/
```

Put a photo in the most specific location folder that describes it. Use topic folders for genuinely location-neutral images, such as an empty baseball field, school bus, road traffic, storm clouds, or a government meeting room.

## File naming

Use lowercase ASCII, hyphens, and a two-digit sequence:

```text
{location}-{subject}-{view-or-condition}-{sequence}.jpg
```

Examples:

```text
stuart-city-hall-exterior-day-01.jpg
martin-county-administration-center-wide-01.jpg
hobe-sound-bridge-waterfront-sunset-01.jpg
port-st-lucie-city-hall-exterior-01.jpg
fort-pierce-downtown-street-scene-01.jpg
vero-beach-oceanfront-wide-01.jpg
indian-river-county-school-district-exterior-01.jpg
treasure-coast-road-traffic-generic-01.jpg
treasure-coast-storm-clouds-coastal-01.jpg
```

Do not include `fallback`, `final`, spaces, parentheses, camera filenames, or an article date in a reusable filename. Include a date only when the image depicts a specific dated event and should not be reused generically.

## Photo specifications

- Preferred: landscape 16:9
- Target size: 1600×900 or larger
- Minimum useful size: 1200×675
- Formats: `.jpg` for photographs; `.webp` is also acceptable
- Keep the original uncropped photo outside the web repository
- Avoid text overlays, decorative borders, watermarks, and embedded logos
- Leave room around the main subject so the image survives card and hero crops
- Capture horizontal and vertical versions when practical, but treat the horizontal version as primary

## Initial shot list

### Each county

Collect at least five reusable images:

1. County administration or commission building
2. Courthouse or another recognizable civic building
3. Major road or traffic corridor
4. Waterfront, park, or environmental scene
5. General business or downtown corridor

### Each major city

Collect at least three:

1. City hall or municipal building
2. Recognizable downtown, main road, or commercial district
3. Park, waterfront, beach, marina, or community landmark

### Topic coverage

**Local government:** city halls, county administration buildings, chambers, courthouse exteriors, public meeting rooms.

**Crime and public safety:** police and sheriff headquarters, fire stations, emergency vehicles parked in neutral settings, courthouse exteriors. Do not use an unrelated active crime scene as a reusable image.

**Business and development:** downtown corridors, construction sites viewed from public property, industrial parks, shopping districts, cranes, new commercial buildings.

**Schools:** district offices, school exteriors, empty athletic fields, school buses. Avoid identifiable children unless the image is from a public event and publication is appropriate.

**Sports:** Clover Park, high-school stadium exteriors, empty fields and courts, scoreboards, neutral equipment details.

**Things to do:** parks, beaches, marinas, museums, theaters, downtown event areas, farmers-market spaces, trails.

**Roads and transportation:** major intersections, bridges, traffic, construction signs, transit facilities. Never photograph while driving.

**Weather and environment:** storm clouds, heavy rain from a safe location, rough surf, flooded public roads from a safe distance, beaches, rivers, wetlands, canals.

## Metadata manifest

Record every approved image in `data/editorial-image-library.json` using the example file included with this release. Important fields are:

- `path`
- `locations`
- `topics`
- `subjects`
- `credit`
- `copyright_owner`
- `license`
- `date_taken`
- `hero_eligible`
- `safe_for_reuse`
- `sensitive`

An image should not enter automated selection unless `safe_for_reuse` is `true` and its ownership or permission is documented.

## Editorial safeguards

Do not use the reusable pool to imply that a pictured person, house, vehicle, business, school, or emergency scene is connected to an unrelated story. Generic images should be plainly contextual. Avoid:

- Victims or grieving families
- Private homes
- License plates and personally identifying details
- Children as generic school imagery
- Active arrests, crashes, fires, or medical emergencies
- Photos whose reuse rights are unclear

The branded OG graphic is preferable whenever a real photo would be misleading.
