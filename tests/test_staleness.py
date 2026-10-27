from kb.authority import authority_score, is_likely_stale_for_rates


def test_calculator_low_authority():
    assert authority_score("https://www.dupaco.com/calculators/mortgage-payment") < 0.3


def test_product_page_high_authority():
    assert authority_score("https://www.dupaco.com/personal/savings-account") >= 0.99


def test_info_dupaco_stale():
    assert is_likely_stale_for_rates("https://info.dupaco.com/x", "Rates 5%") is True
