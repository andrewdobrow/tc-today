# v1.13.1.2 — Missing-Person Identity Continuity

## Purpose

Prevent the same missing-person alert from publishing under multiple TCT permalinks
when different news outlets omit the person's name, move the age before or after the
name, or describe the same search with different wording.

## Production case

The Aug. 6 Ethan Boyd alert escaped as two articles:

- `2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti`
- `2026-08-06-martin-county-deputies-search-for-missing-autistic-teen-last-seen-in-palm-city`

Both identify the same 14-year-old autistic boy, the same Palm City search, and the
same Grand Oaks/Coquina Cove area. The second URL is now deterministically
consolidated into the first canonical article.

## Core fixes

- Adds `missing_person` as a first-class unified incident family.
- Extracts names from missing-person phrasing such as `14-year-old Ethan Boyd`,
  `Ethan Boyd, a 14-year-old`, `last seen`, and `help finding`.
- Carries source URLs into incident evidence so ages and named landmarks preserved in
  publisher URL slugs can support sparse RSS titles.
- Requires a shared location plus an exact age, named person, or distinctive landmark
  and search profile before two alerts can merge.
- Explicitly rejects same-city alerts with conflicting names or ages.
- Rebuilds legacy `unknown` incident evidence under the current versioned contract.
- Caches story evidence within a repair process so repeated fixed-point validation
  does not repeatedly parse the entire registry.
- Adds `missing-person` to the source-oriented semantic candidate family set.
- Extends final archive cleanup to include source headline and URL evidence.

## Registry repair

The production preflight consolidates the two Ethan Boyd story records and two other
verified Port St. Lucie murder-suicide follow-up fragments exposed by the upgraded
evidence contract. It then verifies that a second repair pass is clean.

## Safety

The contract does not merge alerts merely because they concern a missing teen in the
same city. Conflicting ages or extracted names fail closed, and generic missing-person
language without a concrete shared profile remains separate.

## Canonical article and image retained

The retained canonical is explicitly the article that received the breaking-news image override:

- Canonical: `2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti`
- Image: `https://treasurecoast.today/images/ethan-boyd.png`
- Redirected duplicate: `2026-08-06-martin-county-deputies-search-for-missing-autistic-teen-last-seen-in-palm-city`

The image override is included in this overlay and is applied to the article page, homepage/category data, RSS, archive metadata, and social metadata. The duplicate page is a verified noindex/301 redirect to the retained article.
