# TCT App Store — Step 1A: Privacy policy

## What this overlay does

- Updates the existing **website** `privacy.html` without replacing its current layout or Mediavine disclosure.
- Describes iOS push notification registration, stored preferences, app sign-in, local storage, third-party Apple APNs, and data requests.
- Retains current operator wording **Andrew Dobrow**, because Treasure Coast Today LLC is not yet approved.
- Does **not** add an account-deletion feature, turn on live iOS ads, modify the editorial engine, or change Supabase data.
- Deliberately does not claim the business is already an LLC.

## Installation (one-time)

1. Place `APPLY_IOS_PRIVACY_POLICY.py` at the **root of the tc-today website repository**.
2. Run `python APPLY_IOS_PRIVACY_POLICY.py` from the repo root (or `py` on Windows).
3. Review `git diff -- privacy.html` before committing. Confirm the updated operator and data language describes your operations accurately.
4. Run the normal website test and deployment workflows. Confirm https://treasurecoast.today/privacy.html shows the updated date and iOS sections.

The script is idempotent and fails if it cannot locate the known privacy sections. This is intentional: the website may have changed since the snapshot.

## NOT complete yet — keep these on the submission checklist

- After Florida LLC approval: change operator identity consistently on the policy, ownership page, contact/business records, and App Store Connect seller information as applicable. Do not claim LLC ownership earlier.
- Add a usable **in-app account-deletion initiation** flow and adjust this privacy policy to describe the actual process. A support email alone does not complete that Apple requirement.
- Audit the **final Release app advertising configuration** (AdMob, ATT, consent and Apple's App Privacy answers) *before* making final data disclosures. Test ads in Ad Hoc do not establish what is collected in the App Store Release build.
- Verify any third-party SDK collection/retention claims and account/data retention details, including server logs. This update is a practical drafting step, not a substitute for privacy/legal review.
