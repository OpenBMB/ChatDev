#!/usr/bin/env python3
"""Draw Tarot cards using the secrets module for cryptographic randomness.

The default draw is the 12 Houses of the Zodiac spread: each house gets one
Major Arcana card plus two Minor Arcana cards. Each card has an independent
50/50 chance of being reversed.
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import math
import os
import secrets
import sys

SPREAD_NAME = "12 Houses of the Zodiac"


def _entropy_bits():
    """Conservative unordered-card entropy budget for the default spread."""
    major = math.log2(math.comb(22, 12))
    minor = math.log2(math.comb(56, 24))
    reversals = 36.0
    return {
        "major_arcana": round(major, 2),
        "minor_arcana": round(minor, 2),
        "reversals": reversals,
        "total": round(major + minor + reversals, 2),
    }


ENTROPY_BITS = _entropy_bits()

MAJOR_ARCANA = (
    ("major", "00-the-fool"),
    ("major", "01-the-magician"),
    ("major", "02-the-high-priestess"),
    ("major", "03-the-empress"),
    ("major", "04-the-emperor"),
    ("major", "05-the-hierophant"),
    ("major", "06-the-lovers"),
    ("major", "07-the-chariot"),
    ("major", "08-strength"),
    ("major", "09-the-hermit"),
    ("major", "10-wheel-of-fortune"),
    ("major", "11-justice"),
    ("major", "12-the-hanged-man"),
    ("major", "13-death"),
    ("major", "14-temperance"),
    ("major", "15-the-devil"),
    ("major", "16-the-tower"),
    ("major", "17-the-star"),
    ("major", "18-the-moon"),
    ("major", "19-the-sun"),
    ("major", "20-judgement"),
    ("major", "21-the-world"),
)

RANKS = (
    "ace",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "page",
    "knight",
    "queen",
    "king",
)

SUITS = ("wands", "cups", "swords", "pentacles")

ZODIAC_HOUSES = (
    (
        "First House",
        "Self, identity, agency, and first motion",
        "01-first-house",
    ),
    (
        "Second House",
        "Resources, values, constraints, and preservation",
        "02-second-house",
    ),
    (
        "Third House",
        "Communication, learning, interfaces, and local connections",
        "03-third-house",
    ),
    (
        "Fourth House",
        "Foundations, history, context, and hidden dependencies",
        "04-fourth-house",
    ),
    (
        "Fifth House",
        "Creativity, experimentation, expressiveness, and delight",
        "05-fifth-house",
    ),
    (
        "Sixth House",
        "Practice, service, quality, routine, and maintenance",
        "06-sixth-house",
    ),
    (
        "Seventh House",
        "Partnership, contracts, users, and external counterparts",
        "07-seventh-house",
    ),
    (
        "Eighth House",
        "Transformation, risk, shared state, secrets, and deep change",
        "08-eighth-house",
    ),
    (
        "Ninth House",
        "Exploration, principles, standards, and broader strategy",
        "09-ninth-house",
    ),
    (
        "Tenth House",
        "Delivery, reputation, public outcome, and long-term direction",
        "10-tenth-house",
    ),
    (
        "Eleventh House",
        "Community, networks, systems, and shared aspirations",
        "11-eleventh-house",
    ),
    (
        "Twelfth House",
        "Blind spots, hidden costs, endings, and unconscious assumptions",
        "12-twelfth-house",
    ),
)


def build_deck():
    """Build the full 78-card Tarot deck."""
    return list(MAJOR_ARCANA) + build_minor_deck()


def build_minor_deck():
    """Build the 56-card Minor Arcana deck."""
    return [(suit, f"{rank}-of-{suit}") for suit in SUITS for rank in RANKS]


def fisher_yates_shuffle(deck):
    """Shuffle deck in-place using Fisher-Yates with secrets.randbelow()."""
    for i in range(len(deck) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    return deck


def is_reversed():
    """Return True with 50% probability using secrets.randbits()."""
    return secrets.randbits(1) == 1


def card_record(suit, card_id, position, role, include_content=False):
    """Return the JSON-serializable record for a drawn card."""
    card = {
        "suit": suit,
        "card_id": card_id,
        "reversed": is_reversed(),
        "position": position,
        "role": role,
        "file": f"cards/{suit}/{card_id}.md",
    }
    if include_content:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cards_dir = os.path.join(os.path.dirname(script_dir), "cards")
        path = os.path.join(cards_dir, suit, f"{card_id}.md")
        try:
            with open(path) as f:
                card["content"] = f.read()
        except OSError as e:
            card["content"] = f"(error reading card file {path}: {e})"
    return card


def read_reference_file(relative_file):
    """Read a skill-local reference file for --content output."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    path = os.path.join(skill_dir, relative_file)
    try:
        with open(path) as f:
            return f.read()
    except OSError as e:
        return f"(error reading reference file {path}: {e})"


def draw_cards(n=4, include_content=False):
    """Shuffle the full deck and draw n cards, each possibly reversed."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n must be int, got {type(n).__name__}")
    deck = build_deck()
    fisher_yates_shuffle(deck)
    hand = []
    for i in range(min(n, len(deck))):
        suit, card_id = deck[i]
        hand.append(card_record(suit, card_id, i + 1, "card", include_content))
    return hand


def _build_house_record(
    *,
    house_number,
    house_meta,
    major_card,
    minor_pair,
    position,
    include_content,
):
    """Build the JSON record for one zodiac house."""
    house_name, focus, house_id = house_meta
    major_suit, major_id = major_card
    (m1_suit, m1_id), (m2_suit, m2_id) = minor_pair
    house_file = f"houses/{house_id}.md"
    record = {
        "house": house_number,
        "name": house_name,
        "focus": focus,
        "file": house_file,
        "cards": [
            card_record(major_suit, major_id, position, "major_arcana", include_content),
            card_record(m1_suit, m1_id, position + 1, "minor_arcana_1", include_content),
            card_record(m2_suit, m2_id, position + 2, "minor_arcana_2", include_content),
        ],
    }
    if include_content:
        record["content"] = read_reference_file(house_file)
    return record


def draw_zodiac_spread(include_content=False):
    """Draw the default 12 Houses of the Zodiac spread."""
    major_deck = list(MAJOR_ARCANA)
    minor_deck = build_minor_deck()
    fisher_yates_shuffle(major_deck)
    fisher_yates_shuffle(minor_deck)

    houses = []
    for i, house_meta in enumerate(ZODIAC_HOUSES):
        houses.append(
            _build_house_record(
                house_number=i + 1,
                house_meta=house_meta,
                major_card=major_deck[i],
                minor_pair=(minor_deck[2 * i], minor_deck[2 * i + 1]),
                position=1 + 3 * i,
                include_content=include_content,
            )
        )

    bits = ENTROPY_BITS
    return {
        "spread": SPREAD_NAME,
        "houses": houses,
        "entropy_bits": bits,
        "entropy_note": (
            "Assumes secrets.randbelow() provides cryptographically secure "
            "bounded draws. This is a conservative unordered-card budget: "
            f"{bits['major_arcana']} bits from Major Arcana selection, "
            f"{bits['minor_arcana']} bits from Minor Arcana selection, and "
            f"{bits['reversals']} reversal bits. Ordered house assignment "
            "contains more entropy."
        ),
    }


USAGE = "Usage: draw_cards.py [--content] [--legacy [count]]"


def _parse_args(argv):
    """Parse CLI argv into (include_content, legacy, count). Exits on error."""
    args = list(argv)
    include_content = "--content" in args
    if include_content:
        args.remove("--content")
    legacy = "--legacy" in args
    if legacy:
        args.remove("--legacy")
    count = None
    if args:
        if not legacy:
            print(
                f"Error: positional count requires --legacy. {USAGE}",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            count = int(args[0])
        except ValueError:
            print(
                f"Error: '{args[0]}' is not a valid integer. {USAGE}",
                file=sys.stderr,
            )
            sys.exit(1)
        if count < 1 or count > 78:
            print(f"Error: card count must be 1-78, got {count}", file=sys.stderr)
            sys.exit(1)
    return include_content, legacy, count


def main():
    include_content, legacy, count = _parse_args(sys.argv[1:])
    try:
        if legacy:
            hand = draw_cards(count if count is not None else 4, include_content=include_content)
        else:
            hand = draw_zodiac_spread(include_content=include_content)
    except OSError as e:
        print(f"Error: failed to read system entropy source: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(hand, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: draw_cards.py failed: {e}", file=sys.stderr)
        sys.exit(1)
