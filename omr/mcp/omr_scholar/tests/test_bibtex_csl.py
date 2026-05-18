from omr_scholar.bibtex import assign_keys, citation_key, to_bibtex
from omr_scholar.csl import to_csl_json


def test_citation_key_format():
    rec = {
        "title": "Attention Is All You Need",
        "authors": [{"family": "Vaswani", "given": "Ashish"}],
        "year": 2017,
    }
    assert citation_key(rec) == "vaswani2017attention"


def test_citation_key_string_authors_and_stopword_skip():
    rec = {"title": "A Survey of Transformers",
           "authors": "Smith, Alice and Doe, Jane", "year": 2021}
    assert citation_key(rec) == "smith2021survey"


def test_assign_keys_collision_suffix():
    recs = [
        {"title": "Survey Work", "authors": [{"family": "Smith"}], "year": 2021},
        {"title": "Survey Work", "authors": [{"family": "Smith"}], "year": 2021},
        {"title": "Survey Work", "authors": [{"family": "Smith"}], "year": 2021},
    ]
    keys = assign_keys(recs)
    assert keys == ["smith2021survey", "smith2021surveya", "smith2021surveyb"]
    assert len(set(keys)) == 3


def test_to_bibtex_emits_stable_key_and_fields():
    recs = [{
        "title": "Attention Is All You Need",
        "authors": [{"family": "Vaswani", "given": "Ashish"}],
        "year": 2017, "doi": "10.5555/x",
        "venue": "NeurIPS", "url": "https://doi.org/10.5555/x",
    }]
    bib = to_bibtex(recs)
    assert "@article{vaswani2017attention," in bib
    assert "title = {Attention Is All You Need}" in bib
    assert "author = {Vaswani, Ashish}" in bib
    assert "year = {2017}" in bib
    assert "doi = {10.5555/x}" in bib
    # no unbalanced braces injected from data
    assert bib.count("{") == bib.count("}")


def test_to_bibtex_deterministic():
    recs = [{"title": "X", "authors": [{"family": "Ng"}], "year": 2019}]
    assert to_bibtex(recs) == to_bibtex(recs)


def test_to_csl_json_shape_and_ids_match_bibtex():
    recs = [{
        "title": "BERT", "authors": [{"family": "Devlin", "given": "Jacob"}],
        "year": 2019, "doi": "10.1/bert", "venue": "NAACL",
    }]
    csl = to_csl_json(recs)
    assert isinstance(csl, list) and len(csl) == 1
    item = csl[0]
    assert item["id"] == "devlin2019bert"
    assert item["type"] == "article-journal"
    assert item["title"] == "BERT"
    assert item["issued"] == {"date-parts": [[2019]]}
    assert item["DOI"] == "10.1/bert"
    assert item["author"] == [{"family": "Devlin", "given": "Jacob"}]
    # id parity with bibtex keys
    assert item["id"] == assign_keys(recs)[0]
