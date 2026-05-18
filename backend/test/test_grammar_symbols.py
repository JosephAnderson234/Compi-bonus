"""Tests unitarios para grammar_symbols."""

from __future__ import annotations

import _paths  # noqa: F401

from grammar_symbols import fresh_prime_name, symbols_in_grammar


def test_fresh_prime_name_skips_used():
    used = {"E", "E'", "id"}
    assert fresh_prime_name("E", used) == "E''"


def test_symbols_in_grammar_includes_terminals():
    prods = {"S": [["a"]]}
    used = symbols_in_grammar(prods, terminals={"a", "b"})
    assert "a" in used and "b" in used and "S" in used


def test_lr0_augmented_avoids_nt_and_terminal_prime():
    from lr0_parser import LR0Parser

    p = LR0Parser("E -> T\nE' -> x\nT -> E'", "E", "x")
    p._parse_grammar()
    p._build_augmented_grammar()
    assert p.aug_start == "E''"


def test_lr1_augmented_avoids_terminal_prime():
    from lr_base import Grammar

    g = Grammar.from_text("E -> T\nT -> E'", simbolo_inicial="E")
    assert g.productions[0].non_terminal == "E''"
    assert g.productions[0].transaction == ["E"]


def test_ll1_transform_avoids_terminal_prime():
    from ll1_parser import LL1Parser

    p = LL1Parser(
        "A -> A a | b\nS -> A' b",
        "A",
        "b",
    )
    p.parse_grammar()
    p.transform_grammar()
    sug = p.suggested_grammar or ""
    heads = [ln.split(" ->")[0].strip() for ln in sug.splitlines() if "->" in ln]
    assert "A''" in heads
    assert "A'" not in heads


if __name__ == "__main__":
    test_fresh_prime_name_skips_used()
    test_symbols_in_grammar_includes_terminals()
    test_lr0_augmented_avoids_nt_and_terminal_prime()
    test_lr1_augmented_avoids_terminal_prime()
    test_ll1_transform_avoids_terminal_prime()
    print("test_grammar_symbols: todos pasaron")
