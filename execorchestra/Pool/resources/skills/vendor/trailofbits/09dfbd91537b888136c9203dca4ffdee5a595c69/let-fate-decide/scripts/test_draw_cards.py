#!/usr/bin/env python3
"""Tests for draw_cards.py."""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent))
import draw_cards

SKILL_DIR = Path(__file__).parent.parent


def test_build_deck_has_78_cards():
    deck = draw_cards.build_deck()
    assert len(deck) == 78, f"Expected 78 cards, got {len(deck)}"


def test_build_deck_has_22_major_arcana():
    deck = draw_cards.build_deck()
    majors = [c for c in deck if c[0] == "major"]
    assert len(majors) == 22, f"Expected 22 major arcana, got {len(majors)}"


def test_build_deck_has_56_minor_arcana():
    deck = draw_cards.build_deck()
    minors = [c for c in deck if c[0] != "major"]
    assert len(minors) == 56, f"Expected 56 minor arcana, got {len(minors)}"


def test_build_minor_deck_has_56_cards():
    deck = draw_cards.build_minor_deck()
    assert len(deck) == 56, f"Expected 56 minor cards, got {len(deck)}"


def test_build_minor_deck_excludes_major_arcana():
    deck = draw_cards.build_minor_deck()
    assert all(suit != "major" for suit, _ in deck)


def test_build_deck_all_unique():
    deck = draw_cards.build_deck()
    card_ids = [c[1] for c in deck]
    assert len(card_ids) == len(set(card_ids)), "Duplicate card IDs found"


def test_build_deck_four_suits_14_each():
    deck = draw_cards.build_deck()
    suits = Counter(c[0] for c in deck if c[0] != "major")
    for suit in ["wands", "cups", "swords", "pentacles"]:
        assert suits[suit] == 14, f"Expected 14 {suit}, got {suits[suit]}"


def test_draw_cards_returns_requested_count():
    for n in [1, 2, 4, 10]:
        hand = draw_cards.draw_cards(n)
        assert len(hand) == n, f"draw({n}) returned {len(hand)} cards"


def test_draw_cards_default_is_4():
    hand = draw_cards.draw_cards()
    assert len(hand) == 4


def test_draw_zodiac_spread_default_shape():
    hand = draw_cards.draw_zodiac_spread()
    assert hand["spread"] == draw_cards.SPREAD_NAME
    assert len(hand["houses"]) == 12


def test_draw_cards_clamps_to_78():
    hand = draw_cards.draw_cards(100)
    assert len(hand) == 78


def test_draw_cards_zero_returns_empty():
    hand = draw_cards.draw_cards(0)
    assert len(hand) == 0


def test_draw_cards_card_structure():
    hand = draw_cards.draw_cards(1)
    card = hand[0]
    assert "suit" in card
    assert "card_id" in card
    assert "reversed" in card
    assert "position" in card
    assert "file" in card
    assert isinstance(card["reversed"], bool)
    assert card["position"] == 1
    assert card["file"].startswith("cards/")
    assert card["file"].endswith(".md")


def test_draw_cards_positions_are_sequential():
    hand = draw_cards.draw_cards(4)
    positions = [c["position"] for c in hand]
    assert positions == [1, 2, 3, 4]


def test_draw_cards_no_duplicate_cards():
    hand = draw_cards.draw_cards(78)
    card_ids = [c["card_id"] for c in hand]
    assert len(card_ids) == len(set(card_ids)), "Duplicate cards drawn"


def test_zodiac_spread_shape():
    spread = draw_cards.draw_zodiac_spread()
    assert spread["spread"] == "12 Houses of the Zodiac"
    bits = spread["entropy_bits"]
    expected_major = round(math.log2(math.comb(22, 12)), 2)
    expected_minor = round(math.log2(math.comb(56, 24)), 2)
    assert bits["major_arcana"] == expected_major
    assert bits["minor_arcana"] == expected_minor
    assert bits["reversals"] == 36.0
    assert bits["total"] == round(expected_major + expected_minor + 36.0, 2)
    assert bits["total"] >= 100, "Entropy budget must clear the 100-bit floor"
    assert len(spread["houses"]) == 12
    for house in spread["houses"]:
        assert set(house) == {"house", "name", "focus", "file", "cards"}
        assert house["file"].startswith("houses/")
        assert house["file"].endswith(".md")
        assert len(house["cards"]) == 3


def test_zodiac_house_files_exist():
    spread = draw_cards.draw_zodiac_spread()
    for house in spread["houses"]:
        path = SKILL_DIR / house["file"]
        assert path.exists(), f"Missing house file: {path}"


def test_zodiac_focus_matches_house_domain():
    spread = draw_cards.draw_zodiac_spread()
    for house in spread["houses"]:
        text = (SKILL_DIR / house["file"]).read_text()
        domain = next(
            line[len("**Domain**: ") :].strip()
            for line in text.splitlines()
            if line.startswith("**Domain**: ")
        )
        assert house["focus"] == domain, (
            f"focus/Domain drift in {house['file']}: {house['focus']!r} != {domain!r}"
        )


def test_zodiac_house_files_cover_technical_contexts():
    spread = draw_cards.draw_zodiac_spread()
    for house in spread["houses"]:
        text = (SKILL_DIR / house["file"]).read_text()
        assert "## Building New Projects" in text
        assert "## Vulnerability Discovery" in text
        assert "## Correctness Verification" in text
        assert "## Technical Workflow Lenses" in text


def test_technical_context_lenses_reference_exists():
    reference = SKILL_DIR / "references" / "TECHNICAL_CONTEXT_LENSES.md"
    text = reference.read_text()
    assert "## Audit Pipeline Stage" in text
    assert "## Evidence Mode" in text
    assert "## Domain Lens" in text
    assert "## Failure Class Lens" in text
    assert "## Human and Organizational Lens" in text
    assert "## House Affinity Map" in text


def test_security_framing_requires_evidence():
    skill_text = (SKILL_DIR / "SKILL.md").read_text()
    guide_text = (SKILL_DIR / "references" / "INTERPRETATION_GUIDE.md").read_text()
    assert "Security and Correctness Use" in skill_text
    assert "never sufficient by itself" in skill_text
    assert "only evidence can dismiss a security or correctness concern" in skill_text
    assert "cannot prove safety, dismiss a finding, or replace" in guide_text


def test_numbered_ranks_are_numeric_across_all_suits():
    word_ranks = ("Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten")
    for card_file in (SKILL_DIR / "cards").glob("*/*.md"):
        if card_file.parent.name == "major":
            continue
        text = card_file.read_text()
        for word in word_ranks:
            assert f"**Rank**: {word}" not in text, (
                f"{card_file} still uses word-form rank '{word}'; use the digit form"
            )


def test_reviewed_cards_avoid_unsafe_shortcuts():
    """Regression guard: these exact phrases were removed in 1.2.0; do not reintroduce.

    This is an exact-string blacklist, not a semantic check. Add new bad phrases
    here as they are identified during review; rewordings of existing phrases
    will not trip this test and must be caught manually.
    """
    risky_phrases = (
        "Follow your intuition on this one",
        "The solution that feels right probably is",
        "Ship it.",
        "The approach is sound.",
        "The approach will succeed.",
        "Speed matters here—refine later.",
    )
    for card_file in (SKILL_DIR / "cards").glob("*/*.md"):
        text = card_file.read_text()
        for phrase in risky_phrases:
            assert phrase not in text, f"{phrase!r} still appears in {card_file}"


def test_zodiac_spread_content_includes_house_content():
    spread = draw_cards.draw_zodiac_spread(include_content=True)
    for house in spread["houses"]:
        assert "content" in house
        assert house["content"].startswith("# ")


def test_zodiac_spread_uses_one_major_per_house():
    spread = draw_cards.draw_zodiac_spread()
    major_cards = []
    for house in spread["houses"]:
        card = house["cards"][0]
        assert card["role"] == "major_arcana"
        assert card["suit"] == "major"
        major_cards.append(card["card_id"])
    assert len(major_cards) == 12
    assert len(set(major_cards)) == 12


def test_zodiac_spread_uses_two_minors_per_house():
    spread = draw_cards.draw_zodiac_spread()
    minor_cards = []
    for house in spread["houses"]:
        for card in house["cards"][1:]:
            assert card["role"] in {"minor_arcana_1", "minor_arcana_2"}
            assert card["suit"] != "major"
            minor_cards.append(card["card_id"])
    assert len(minor_cards) == 24
    assert len(set(minor_cards)) == 24


def test_zodiac_spread_all_cards_can_be_reversed():
    spread = draw_cards.draw_zodiac_spread()
    cards = [card for house in spread["houses"] for card in house["cards"]]
    assert len(cards) == 36
    assert all(isinstance(card["reversed"], bool) for card in cards)


def test_zodiac_spread_positions_are_sequential():
    spread = draw_cards.draw_zodiac_spread()
    positions = [card["position"] for house in spread["houses"] for card in house["cards"]]
    assert positions == list(range(1, 37))


def test_fisher_yates_preserves_elements():
    deck = draw_cards.build_deck()
    original = sorted(deck)
    draw_cards.fisher_yates_shuffle(deck)
    assert sorted(deck) == original, "Shuffle changed deck elements"


def test_fisher_yates_single_element():
    deck = [("major", "00-the-fool")]
    draw_cards.fisher_yates_shuffle(deck)
    assert deck == [("major", "00-the-fool")]


def test_fisher_yates_empty():
    deck = []
    draw_cards.fisher_yates_shuffle(deck)
    assert deck == []


def test_is_reversed_returns_bool():
    for _ in range(20):
        assert isinstance(draw_cards.is_reversed(), bool)


def test_shuffle_produces_varying_orders():
    """Run 5 shuffles; at least 2 should differ (p(all same) ~ 0)."""
    orders = []
    for _ in range(5):
        deck = draw_cards.build_deck()
        draw_cards.fisher_yates_shuffle(deck)
        orders.append(tuple(c[1] for c in deck))
    assert len(set(orders)) >= 2, "All 5 shuffles identical"


def test_reversal_produces_both_values():
    """Over 100 flips, both True and False should appear."""
    results = {draw_cards.is_reversed() for _ in range(100)}
    assert True in results, "Never got reversed=True in 100 flips"
    assert False in results, "Never got reversed=False in 100 flips"


def test_no_os_urandom_import():
    """Verify os.urandom is not used; os may be imported for path operations."""
    source = Path(__file__).parent / "draw_cards.py"
    text = source.read_text()
    assert "os.urandom" not in text, "os.urandom still referenced"


def test_uses_secrets_module():
    """Verify secrets module is used."""
    source = Path(__file__).parent / "draw_cards.py"
    text = source.read_text()
    assert "import secrets" in text
    assert "secrets.randbelow" in text
    assert "secrets.randbits" in text


def test_cli_default_output():
    """Run the script and verify JSON output with the default spread."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    spread = json.loads(result.stdout)
    assert spread["spread"] == draw_cards.SPREAD_NAME
    assert len(spread["houses"]) == 12


def test_cli_legacy_custom_count():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py"), "--legacy", "2"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    cards = json.loads(result.stdout)
    assert len(cards) == 2


def test_cli_legacy_default_count():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py"), "--legacy"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    cards = json.loads(result.stdout)
    assert len(cards) == 4


def test_cli_positional_count_without_legacy_is_error():
    """Positional count requires --legacy; the new default has a fixed shape."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py"), "4"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "--legacy" in result.stderr


def test_cli_invalid_arg():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py"), "--legacy", "abc"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Error" in result.stderr


def test_cli_out_of_range():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py"), "--legacy", "0"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1

    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "draw_cards.py"), "--legacy", "79"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_no_secure_randbelow_function():
    """Regression: the custom secure_randbelow must be removed."""
    source = Path(__file__).parent / "draw_cards.py"
    text = source.read_text()
    assert "def secure_randbelow" not in text, "Custom secure_randbelow still exists"


def test_constants_are_immutable():
    """Constants must be tuples to prevent mutation."""
    assert isinstance(draw_cards.MAJOR_ARCANA, tuple), "MAJOR_ARCANA is not a tuple"
    assert isinstance(draw_cards.RANKS, tuple), "RANKS is not a tuple"
    assert isinstance(draw_cards.SUITS, tuple), "SUITS is not a tuple"
    assert isinstance(draw_cards.ZODIAC_HOUSES, tuple), "ZODIAC_HOUSES is not a tuple"


def test_draw_cards_rejects_non_int():
    """draw_cards() must reject non-int types cleanly."""
    for bad in [None, "3", 2.5, True, False, [4]]:
        try:
            draw_cards.draw_cards(bad)
            assert False, f"draw_cards({bad!r}) should have raised TypeError"
        except TypeError:
            pass


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS  {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {test.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {test.__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)
