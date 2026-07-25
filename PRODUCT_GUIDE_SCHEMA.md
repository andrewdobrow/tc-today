# TCT Product Guide Publishing

Product guides live in `custom_articles.json` beside normal custom articles but use:

```json
"article_type": "product_guide"
```

## Required article fields

- `headline`: Permanent article identity. Reusing the exact same headline updates the existing page. Any character change creates a new article.
- `category`: Existing TCT category key.
- `intro`: Opening editorial copy.
- `products`: Non-empty array of structured product objects.

## Required product fields

- `name`
- `image_url`: Full `http://` or `https://` URL.
- `affiliate_url`: Full `http://` or `https://` affiliate destination.

## Optional product fields

- `label`: For example, `Best Overall` or `Best for Power Outages`.
- `summary`
- `why_we_chose_it`: Array of bullet points.
- `best_for`
- `key_feature`
- `price_note`
- `button_text` (defaults to `View on Amazon`)
- `image_alt`

## Rendering and safety contract

- Affiliate links are preserved exactly and rendered with `rel="sponsored nofollow noopener noreferrer"`.
- Every product name, image URL and affiliate URL must appear in the rendered page or publication fails.
- An affiliate disclosure appears before product content.
- Product cards and Quick Picks stack into a single column on mobile.
- Product guides use `Article` plus `ItemList`/`Product` structured data.
- Product guides never use fuzzy custom matching or recurring-series matching.
- Only an exact headline match can update an existing custom page.
