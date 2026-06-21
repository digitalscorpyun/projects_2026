#!/usr/bin/env python3
"""
search_query_helper.py

Build precise Google-style search queries using common research operators.

Features:
- site:
- exclude sites with -site:
- exact phrases with quotes
- excluded words with minus operator
- filetype:
- intitle:
- inurl:
- before:/after:
- numeric ranges
- AROUND(n)
- OR groups
- optional Verbatim reminder
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


def _quote_if_needed(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if text.startswith('"') and text.endswith('"'):
        return text
    if " " in text:
        return f'"{text}"'
    return text


@dataclass
class SearchQueryBuilder:
    terms: List[str] = field(default_factory=list)
    exact_phrases: List[str] = field(default_factory=list)
    any_of: List[str] = field(default_factory=list)
    exclude_terms: List[str] = field(default_factory=list)
    sites: List[str] = field(default_factory=list)
    exclude_sites: List[str] = field(default_factory=list)
    filetypes: List[str] = field(default_factory=list)
    intitles: List[str] = field(default_factory=list)
    inurls: List[str] = field(default_factory=list)
    before: Optional[str] = None
    after: Optional[str] = None
    number_range: Optional[tuple[str, str]] = None
    around: Optional[tuple[str, str, int]] = None

    def add_term(self, term: str) -> "SearchQueryBuilder":
        term = term.strip()
        if term:
            self.terms.append(term)
        return self

    def add_terms(self, *terms: str) -> "SearchQueryBuilder":
        for term in terms:
            self.add_term(term)
        return self

    def add_exact_phrase(self, phrase: str) -> "SearchQueryBuilder":
        phrase = phrase.strip()
        if phrase:
            self.exact_phrases.append(phrase)
        return self

    def add_or_group(self, *options: str) -> "SearchQueryBuilder":
        cleaned = [opt.strip() for opt in options if opt.strip()]
        self.any_of.extend(cleaned)
        return self

    def exclude(self, term: str) -> "SearchQueryBuilder":
        term = term.strip()
        if term:
            self.exclude_terms.append(term)
        return self

    def site(self, domain: str) -> "SearchQueryBuilder":
        domain = domain.strip()
        if domain:
            self.sites.append(domain)
        return self

    def exclude_site(self, domain: str) -> "SearchQueryBuilder":
        domain = domain.strip()
        if domain:
            self.exclude_sites.append(domain)
        return self

    def filetype(self, ext: str) -> "SearchQueryBuilder":
        ext = ext.strip().lstrip(".")
        if ext:
            self.filetypes.append(ext)
        return self

    def intitle(self, phrase: str) -> "SearchQueryBuilder":
        phrase = phrase.strip()
        if phrase:
            self.intitles.append(phrase)
        return self

    def inurl(self, text: str) -> "SearchQueryBuilder":
        text = text.strip()
        if text:
            self.inurls.append(text)
        return self

    def date_after(self, value: str) -> "SearchQueryBuilder":
        self.after = value.strip()
        return self

    def date_before(self, value: str) -> "SearchQueryBuilder":
        self.before = value.strip()
        return self

    def set_number_range(self, low: str, high: str) -> "SearchQueryBuilder":
        self.number_range = (low.strip(), high.strip())
        return self

    def set_around(self, left: str, right: str, distance: int) -> "SearchQueryBuilder":
        self.around = (left.strip(), right.strip(), distance)
        return self

    def build(self) -> str:
        parts: List[str] = []

        parts.extend(self.terms)
        parts.extend(_quote_if_needed(p) for p in self.exact_phrases)

        if self.any_of:
            or_group = " OR ".join(_quote_if_needed(opt) for opt in self.any_of)
            parts.append(f"({or_group})")

        for domain in self.sites:
            parts.append(f"site:{domain}")

        for domain in self.exclude_sites:
            parts.append(f"-site:{domain}")

        for ext in self.filetypes:
            parts.append(f"filetype:{ext}")

        for phrase in self.intitles:
            parts.append(f'intitle:{_quote_if_needed(phrase)}')

        for text in self.inurls:
            parts.append(f"inurl:{text}")

        if self.after:
            parts.append(f"after:{self.after}")

        if self.before:
            parts.append(f"before:{self.before}")

        if self.number_range:
            low, high = self.number_range
            parts.append(f"{low}..{high}")

        if self.around:
            left, right, distance = self.around
            parts.append(f"{left} AROUND({distance}) {right}")

        for term in self.exclude_terms:
            if " " in term:
                parts.append(f'-"{term}"')
            else:
                parts.append(f"-{term}")

        return " ".join(parts).strip()


def example_queries() -> None:
    examples = {
        "Government PDF search": (
            SearchQueryBuilder()
            .add_exact_phrase("climate policy")
            .site("gov")
            .filetype("pdf")
            .set_number_range("2016", "2020")
            .build()
        ),
        "Exclude a company site": (
            SearchQueryBuilder()
            .add_terms("electric", "vehicles")
            .exclude_site("tesla.com")
            .build()
        ),
        "Human opinions, not listicles": (
            SearchQueryBuilder()
            .add_exact_phrase("can anyone recommend")
            .add_terms("noise-canceling headphones")
            .set_number_range("$100", "$200")
            .build()
        ),
        "Academic-style proximity search": (
            SearchQueryBuilder()
            .set_around("climate", "policy", 3)
            .site("edu")
            .build()
        ),
        "Date-bounded site search": (
            SearchQueryBuilder()
            .site("theatlantic.com")
            .add_term("AI")
            .date_after("2023")
            .build()
        ),
        "Open directory search": (
            SearchQueryBuilder()
            .intitle("index of")
            .add_exact_phrase("/pdf")
            .add_exact_phrase("media literacy")
            .build()
        ),
    }

    print("\nExample queries:\n")
    for name, query in examples.items():
        print(f"{name}:")
        print(f"  {query}\n")


def interactive_mode() -> None:
    print("Advanced Search Query Builder")
    print("-" * 32)

    builder = SearchQueryBuilder()

    terms = input("Base terms (comma-separated): ").strip()
    if terms:
        for term in terms.split(","):
            builder.add_term(term)

    exacts = input("Exact phrases (comma-separated): ").strip()
    if exacts:
        for phrase in exacts.split(","):
            builder.add_exact_phrase(phrase)

    ors = input("OR group options (comma-separated): ").strip()
    if ors:
        builder.add_or_group(*[opt.strip() for opt in ors.split(",")])

    sites = input("Restrict to sites/domains (comma-separated): ").strip()
    if sites:
        for domain in sites.split(","):
            builder.site(domain.strip())

    excluded_sites = input("Exclude sites/domains (comma-separated): ").strip()
    if excluded_sites:
        for domain in excluded_sites.split(","):
            builder.exclude_site(domain.strip())

    filetypes = input("Filetypes (comma-separated, e.g. pdf,ppt): ").strip()
    if filetypes:
        for ext in filetypes.split(","):
            builder.filetype(ext.strip())

    intitles = input("Title-must-contain phrases (comma-separated): ").strip()
    if intitles:
        for phrase in intitles.split(","):
            builder.intitle(phrase.strip())

    inurls = input("URL-must-contain tokens (comma-separated): ").strip()
    if inurls:
        for token in inurls.split(","):
            builder.inurl(token.strip())

    after = input("After date/year (optional): ").strip()
    if after:
        builder.date_after(after)

    before = input("Before date/year (optional): ").strip()
    if before:
        builder.date_before(before)

    range_low = input("Numeric range low bound (optional): ").strip()
    range_high = input("Numeric range high bound (optional): ").strip()
    if range_low and range_high:
        builder.set_number_range(range_low, range_high)

    prox_left = input("AROUND left term (optional): ").strip()
    prox_right = input("AROUND right term (optional): ").strip()
    prox_dist = input("AROUND distance (optional integer): ").strip()
    if prox_left and prox_right and prox_dist.isdigit():
        builder.set_around(prox_left, prox_right, int(prox_dist))

    excludes = input("Exclude terms (comma-separated): ").strip()
    if excludes:
        for term in excludes.split(","):
            builder.exclude(term.strip())

    query = builder.build()

    print("\nBuilt query:\n")
    print(query)
    print("\nTip: For exact-result testing in Google, turn on Verbatim mode manually.")


def main() -> None:
    print("1) Show example queries")
    print("2) Build a custom query")
    choice = input("Choose 1 or 2: ").strip()

    if choice == "1":
        example_queries()
    elif choice == "2":
        interactive_mode()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()