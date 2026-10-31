# KoverIQ Install Showcase — Director Skill

Pipeline: `pipeline_defs/koveriq-install-showcase.yaml` (`idea → script → scene_plan → assets → edit → compose`).

A short video of one finished install: the window before, the reveal, a few
details, the town, and the call to action. You run headless inside the KoverIQ
video worker. Code owns everything except three jobs: **write the script**,
**plan the scenes** (kinds, slots, photos) and **review snapshot frames** once.
The step instructions give the exact artifact format; this file is the
install-specific direction. Every rule under "Rules that always apply" in
`koveriq/product-promo` holds here too.

## The customer stays private

- The brief names the **town only** (`source.job.town`). Never write a customer
  name, a street, a house number, a postcode or a phone number, in the
  narration or on screen. Nothing else about the customer is in the brief, and
  nothing may be read off a photo (a door number, a street sign, a car).
- The town goes on the `town_card` exactly as the brief spells it, and may be
  spoken once ("fitted in Guildford").
- Products are named only as `source.job.productsFitted` names them, or
  generically ("shutters"). No figures unless they are in the brief facts: no
  sizes, prices, dates or durations.

## Photos

`get_brief().photos` lists every photo with its `role`: `before` (the window as
it was) or `after` (the finished install). Look at each with `view_asset`
before you use it.

| Scene | Photo |
|---|---|
| before | a `before` photo (`photo_pan`), or a `before_after` |
| reveal | a `before_after` (a before and an after photo of the same window), or an `after` photo (`photo_reveal`) |
| details | `after` photos (`photo_pan`), or a `text_card` |
| town card | optional: an `after` photo, never one showing a house number |
| CTA | optional: an `after` photo |

Use each photo at most twice. Set `focus` on the window or the shutters, away
from faces, house numbers, number plates and street signs.

## Scene grammar

`koveriq/scene_grammar.yaml` (install_showcase) is binding:

**before → reveal → details → town card → CTA**

| Role | Count | Kinds |
|---|---|---|
| before | 1 | `photo_pan`, `before_after` |
| reveal | 1 | `photo_reveal`, `before_after` |
| details | 0–2 | `photo_pan`, `text_card` |
| town_card | 1 | `town_card` |
| cta | 1, last | `cta_endcard` |

15 s: 4–5 scenes, 35–40 words. 30 s: 4–7 scenes, 69–81 words. 60 s: 5–9 scenes
(the role counts allow 6 at most), 138–162 words.

## Script

- Open on what the before photo shows (glare, no privacy, a bare window) in one
  short line. Say nothing else about the customer or their home.
- The reveal line names what was fitted, from `productsFitted`.
- Details: what the products do (light, privacy, panels folding back), only as
  far as the photos and the brief support it.
- The town-card line may say the town. The last line is `brief.cta` word for word.

## Scene plan

- `before_after`: `beforeAssetId` is a `before` photo and `afterAssetId` an
  `after` photo of the same window. Keep the labels "Before" / "After".
- `town_card`: `town` is the brief's town exactly; an `overline` such as
  "Recently fitted in"; a `subline` naming the products in a few words.
- `visual` says in plain words what the viewer sees. It follows the narration
  rules (no figures, no address).

## Review

Report anything that could identify the customer as `pii_possible`: a house
number, a street sign, a number plate, a face or reflection, post on a doormat.
Prefer a `crop_focus` that moves it out of frame, and report it anyway if it
stays visible.
