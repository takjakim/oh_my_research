from omr_scholar.normalize import (
    first_significant_word,
    normalize_doi,
    normalize_title,
    token_set_ratio,
)


def test_normalize_title_strips_punct_accents_and_case():
    assert normalize_title("Attention Is All You Need!") == "attention is all you need"
    assert normalize_title("Café  Déjà-Vu") == "cafe deja vu"
    assert normalize_title(None) == ""
    assert normalize_title("") == ""


def test_normalize_doi_prefix_stripping():
    assert normalize_doi("https://doi.org/10.1/AbC") == "10.1/abc"
    assert normalize_doi("doi:10.1/x") == "10.1/x"
    assert normalize_doi("10.1/X") == "10.1/x"
    assert normalize_doi(None) == ""


def test_token_set_ratio_identical_is_one():
    assert token_set_ratio("attention is all you need",
                            "Attention Is All You Need!") == 1.0


def test_token_set_ratio_reordered_high():
    r = token_set_ratio("deep residual learning recognition",
                         "residual learning deep recognition")
    assert r == 1.0


def test_token_set_ratio_disjoint_low():
    assert token_set_ratio("alpha beta gamma", "delta epsilon zeta") == 0.0


def test_token_set_ratio_empty_both():
    assert token_set_ratio("", "") == 1.0
    assert token_set_ratio("x", "") == 0.0


def test_first_significant_word_skips_stopwords():
    assert first_significant_word("A Survey of Transformer Models") == "survey"
    assert first_significant_word("The Annotated Transformer") == "annotated"
