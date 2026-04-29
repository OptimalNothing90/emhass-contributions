# rfcs/

Design proposals for upstream EMHASS features. Each RFC is a markdown document arguing for a specific change before any code is written.

## Naming

`NNNN-short-slug.md`, where `NNNN` is the next free 4-digit number. Slugs are lowercase, hyphenated, max ~5 words.

## Lifecycle

- **Draft** — RFC committed here, but no upstream issue yet
- **Issue-filed** — corresponding issue opened on `davidusb-geek/emhass`, link added in RFC header
- **Approved** — maintainer green-lit (issue comment), prototype work can start
- **Shipped** — feature merged upstream → next submodule bump pulls it → corresponding prototype removed

## Template

```markdown
# RFC NNNN: <Title>

**Status:** Draft | Issue-filed | Approved | Shipped
**Issue:** <link>
**Board card:** <link>
**Author:** OptimalNothing90
**Date:** YYYY-MM-DD

## Motivation

Why does this matter? What problem does it solve?

## Proposed change

What exactly changes in EMHASS?

## API / contract

If endpoints / schemas / file formats change, what do they look like?

## Threat model

Per #808 maintainer comment: code-injection focus. Confirm: no FS/DB writes, no shell-out, no user-controlled deserialization, no path-traversal vector.

## Backward compatibility

Default-config still works? Existing consumers unaffected?

## Open questions

What hasn't been decided yet?
```

## Current RFCs

(none yet — RFC 0001 will be /api/last-run when the corresponding prototype is staged)
