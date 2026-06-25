# Doc rewrite prompt

This is the reusable prompt for rewriting or editing a Crawfish docs page to house style. Paste
it to an agent (or follow it yourself), fill in the page list at the bottom, and go. It is the
prompt the doc-rewrite swarm ran. It assumes the repo at `/Users/nealkotval/crawfish` and the two
authoring references in `dev_docs/`.

---

You are rewriting Crawfish documentation pages to the house style. Crawfish is a Python framework
documented with mkdocs in `/Users/nealkotval/crawfish`.

## Step 1: learn the style

Read these two files completely before writing anything:

- `/Users/nealkotval/crawfish/dev_docs/WRITING_STYLE.md`
- `/Users/nealkotval/crawfish/dev_docs/HOW_TO_WRITE_DOCS.md`

Then calibrate the rhythm by navigating at least two subroutes of the reference doc sites. Follow
links into the subpages, do not just read the landing page. Use the fetch tool, and if a page
returns only a shell, render it with the browser tools or move on. Suggested pages:

- React, for teaching voice: <https://react.dev/learn/describing-the-ui>,
  <https://react.dev/learn/adding-interactivity>
- Stripe, for task-first pages: <https://docs.stripe.com/payments/accept-a-payment>,
  <https://docs.stripe.com/payments/quickstart>
- Next.js, for information architecture: <https://nextjs.org/docs/app/getting-started/installation>,
  <https://nextjs.org/docs/app/getting-started/project-structure>

The goal is to match how a real page is paced (where the first code block lands, how short the
paragraphs are, how a page hands off to the next), which the rules list alone will not give you.

## Step 2: rewrite each page in place

Read the page, then rewrite it with Write or Edit. Apply these rules:

- Voice: second person, present tense, active. Lead with the task or the fact, not the philosophy.
- One vision: **Crawfish is a programming language for agents.** Do not introduce a competing
  framing. Never use "the X half," "PyTorch half," "the thesis," "revolutionary," "load-bearing,"
  "by construction" (unless you immediately explain how), "leverage," "utilize," "simply," "just,"
  "seamless," or "first-class."
- No em dashes in prose. Replace them with a period, comma, colon, or parentheses. No stacked
  parentheticals. Leave em dashes that appear inside code blocks or literal CLI output untouched.
- Headings: sentence case, naming a task or a thing. No clever or metaphor headings.
- Preserve every technical fact, API name, signature, command, flag, and code block exactly. Do
  not invent API. If unsure of a fact, keep the original meaning and just de-jargon it. Every code
  fence declares a language.
- Bold and callouts are rare. At most one callout per concept, for a real footgun.
- Define each term the first time you use it, in plain words, then use the term.
- End the page with a short "Next steps" list of two to four links.
- Keep pages tight. Cut filler and repetition. Elaborate where a step is unclear, trim where it
  rambles.

Match the page type (see HOW_TO_WRITE_DOCS.md). Guide pages teach one idea with a runnable example.
Reference pages stay terse and complete: the reader is confirming a type or a signature, so do not
pad them into tutorials, just de-jargon the prose and fix the voice.

## Step 3: fix links

These paths moved out of the published site into `dev_docs/` and must not be linked from any
public page: anything under `roadmap/`, `product/`, `architecture/decisions/` (the ADRs),
`_changelog/`, and the files `CRAW-LANGUAGE-VISION.md`, `AGENT-LANGUAGE-AUDIT.md`,
`SECURITY-REVIEW-DOD.md`, `experiment-design.md`, and `emission-taxonomy.md`.

If a page links to one of these (often an ADR cited for rationale), either fold the one-sentence
takeaway into the prose and drop the link, or remove the citation. Never link into `dev_docs`. Keep
valid links to other `guide/`, `reference/`, and `architecture/{ARCHITECTURE,SECURITY,API-STABILITY}`
pages. The `concepts.md` page was rewritten, so its old anchors are stale: link the page without a
fragment, or use a current anchor.

## Constraints

- Only edit the `.md` files assigned to you.
- Do not edit any `.py` file, `mkdocs.yml`, or `gen_api_reference.py`. (`api-reference.md` is
  auto-generated from source docstrings: only touch its hand-written intro, never the generated
  table.)
- Do not run mkdocs.

## Report back

Give a one-line summary per page of what you changed, and list any links you removed.

## Verify (run once after a batch)

```bash
cd /Users/nealkotval/crawfish
# em dashes in prose (outside fenced code):
for f in $(find docs -name '*.md'); do awk 'BEGIN{c=0} /^```/{c=!c;next} {if(!c && /—/) print FILENAME":"FNR}' "$f"; done | grep -v '| —'
# stale/internal links:
grep -rn "roadmap/\|product/\|architecture/decisions/\|_changelog/\|dev_docs" docs --include=*.md
# build with link checking (writes elsewhere so it never touches the committed site/):
python3 -m mkdocs build --strict --site-dir /tmp/craw_site 2>&1 | grep -iE "does not contain|not found|WARNING|ERROR"
```

## Pages to rewrite

(fill in absolute paths, grouped so each agent owns a few related pages)
