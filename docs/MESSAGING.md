# How we talk about the Colorado Open Food Web

**Audience: Claude.** Read this before drafting anything that describes the project to someone
outside it: partner emails, call prep, summaries, introductions. It holds the maintainer's current
best wording, so every partner conversation describes the project the same way.

Each partner conversation runs in its own session. This file is the shared part. Partner-specific
research, contacts and history stay in that partner's session and memory, not here.

Related documents: `docs/CHARTER.md` says what the project is and why. `docs/PARTNERS.md` is the
partner-facing summary to share once a partner wants detail. This file covers how to phrase things.

## Approved wording

These lines were written or approved by the maintainer. Reuse them as they are, or change them as
little as the sentence around them requires.

**What it is** (approved 2026-11-12):

> The Colorado Open Food Web is an open, facts-only record of Colorado producers, the places they
> sell, and the restaurants, stores and farmers markets that carry their products.

**How it stays accurate** (approved 2026-11-12):

> Each fact links back to its source, and the backend automations check producers' own websites on
> a regular basis and flag changes to hours, sales outlets and contact details. A person reviews
> all changes before they go live in the dataset.

**How the apps relate to the dataset** (sent 2026-11-12):

> The Colorado Farm Trail is a statewide, public-facing map I've developed on that dataset, focused
> on connecting people with producers while they travel. It is one example of the kind of
> application I imagine the dataset supporting, and Chaffee Provides is another.

**Why it matters** (sent 2026-11-12):

> Many small organizations are each working on the same challenge of creating and maintaining
> accurate data. By combining those efforts, my hope is that we might all end up with a better,
> more reliable dataset to power our applications.

## The ideas behind the wording

When none of the lines above fits, build the sentence from these points.

- **The dataset is the project.** The Farm Trail and Chaffee Provides are applications built on
  it. Name them as examples, never as the project itself. Other people often introduce the work as
  "the Farm Trail" or "the Chaffee Provides site"; gently reframe to the dataset underneath.
- **Facts only, linked to sources.** The record holds facts and points back to where each came
  from. It does not copy anyone's descriptions or photos.
- **Automation flags, a person decides.** Always pair the two. Do not describe the updates as
  automatic without the human review.
- **Producer-to-outlet connections** are what make it a web: who grows it, where they sell, and
  who carries it.
- **Shared effort.** Many small organizations maintain overlapping lists. The hope is better data
  for all of them by combining that work. It is a hope, not a promise.
- **The partner stays the source of record** for their own listings and their own story.

## First contact with a partner

The maintainer's approach, set on 2026-11-11 while replying to Colorado Open Lands:

1. Thank whoever made the introduction and settle the practical ask (a call, a time).
2. Give short background using the approved wording above.
3. Name the overlap with the partner's work in one or two sentences, and say something specific
   and true about what their project does well.
4. Ask to sit down and talk. The questions to ask are: what are your challenges, what would you
   like to do more of, and how might the open data concept support that?

Do not list proposals, offer deliverables or suggest pilots in a first message. The maintainer's
reason: "I don't want to jump ahead into proposing solutions or promising things I'm not sure if I
want to deliver on." Ideas found during research belong in the session, for the maintainer to
raise on a call if they choose. The "What a partner gets" list in `docs/PARTNERS.md` is for later
in a conversation, not for the opening message.

## Check before you claim

- **What is public.** The repo and the first data release are public (see `CLAUDE.md` and
  `docs/PARTNERS.md`). Confirm the current release and link before citing either; a checkout on
  an old branch can carry an out-of-date `CLAUDE.md`.
- **Counts and coverage.** Take any number of listings, counties or sources from the latest
  release, not from memory or an older document.
- **Licensing and source terms.** Do not state a license to a partner until the maintainer has
  settled it. See the Pending list in `CLAUDE.md`.
- **Features that don't exist.** If something would be new work (a new field, a new filter), say
  "could", and only if the maintainer wants it raised.

## Style

- Plain words, first person, the maintainer's voice. Short paragraphs.
- Write "dataset" as one word.
- Use the full name "Colorado Open Food Web" on first mention, then "the Food Web".
- Avoid jargon in outreach: say "checks producers' own websites", not "scrapes" or "pipeline".

## Keeping this file current

When the maintainer approves, rewrites or rejects wording in any session, update this file in the
same session: replace the line in "Approved wording" or add a new one, with the date. Keep only
the latest version of each line here; git history holds the earlier ones. Do not add wording the
maintainer has not seen, and do not add partner names, contacts or negotiation details.

| Date | Change | From |
|---|---|---|
| 2026-11-12 | File started from the reply sent to Colorado Open Lands. | Conserved Colorado session |
