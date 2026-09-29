from backend.relevance import is_relevant, relevance_score, split_query_tokens, qty_matches_offer
from backend.robot import _parse_unit_price
from backend.typo import correct_query


def test_relevance():
    assert split_query_tokens("süt 1L") == (["sut"], ["1l"])
    title = "Dost %0.5 Yağlı Süt 1 Lt"
    assert is_relevant(title, "süt 1L", volume="1 L")
    assert relevance_score(title, "süt 1L", volume="1 L") >= 4
    assert qty_matches_offer(title, "1 L", ["1l"])
    assert not qty_matches_offer("Sek Süt 200 Ml", "200 ML", ["1l"])


def test_unit():
    assert abs(_parse_unit_price({"title": "Ekmek 1 Adet", "price": 17.5, "volume": "1 Adet"})[0] - 17.5) < 0.01
    assert _parse_unit_price({"title": "Ekmek 1 Adet", "price": 17.5, "volume": "1 Adet"})[1] == "adet"
    assert abs(_parse_unit_price({"title": "Yumurta", "price": 95.0, "volume": "10 Adet"})[0] - 9.5) < 0.01
    assert abs(_parse_unit_price({"title": "Süt", "price": 32.0, "volume": "1 L"})[0] - 32.0) < 0.01
    assert _parse_unit_price({"title": "Süt", "price": 32.0, "volume": "1 L"})[1] == "L"
    assert abs(_parse_unit_price({"title": "Yağ", "price": 449.0, "volume": "5 L"})[0] - 89.8) < 0.01


def test_typo():
    r = correct_query("peinir")
    assert r["corrected"] is True
    assert "peynir" in r["query"].casefold() or "peynir" in r["query"]
    r2 = correct_query("yumrta 30lu")
    assert "yumurta" in r2["query"].casefold()
    r3 = correct_query("pirnic")
    assert "pirinç" in r3["query"] or "pirinc" in r3["query"].casefold()
    r4 = correct_query("kaşar")
    assert r4["query"] == "kaşar" or "kaşar" in r4["query"]
    # başlıkta yakın yazım (çikolata / cikolata)
    assert relevance_score("Ülker Çikolata", "cikolata") >= 3
    r5 = correct_query("makrana")
    assert "makarna" in r5["query"].casefold()


if __name__ == "__main__":
    test_relevance()
    test_unit()
    test_typo()
    print("unit_ok")
