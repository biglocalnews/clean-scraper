# Deprecate `scrape` method

Removes `clean` modules `scrape` method with a PR in favor of `scrape_meta` to focus development and testing around a JSON spec source of truth for other scrapers and analysis to use further downstream.

## Problems

- How do we scrape/download assets related to law enforcement accountability in a consistent manner?
- How do we associate multiple assets with with a single incident reference ID?

## Proposal

This is a two-part proposal. By deprecating one method we can focus development cycles around a reliable schema for consumers.

1. Delete the `scrape` method in individual scrapers with a single PR (GitHub will record the code)
2. Add stricter tests/types for `scrape_meta` to ensure it produces consistent results

## Implications

Please refer back to this document in discussions, code reviews, or additional proposals if additional implications arise.

### Pros

- Consistent outputs
- Test coverage strategy

### Cons

- Additional cognitive and testing overheads
- Upfront costs for onboarding new contributors

### Risks

- More documentation and friction to development

## Outcome

Adopted
