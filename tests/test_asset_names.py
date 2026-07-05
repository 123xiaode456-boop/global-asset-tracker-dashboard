from asset_tracker.asset_names import translate_asset_name


def test_translate_futures_names_to_specific_chinese_names():
    gold = translate_asset_name("GC1!", "Gold Futures")
    propylene = translate_asset_name("PL1!", "Propylene Futures")
    platinum = translate_asset_name("PL1!", "Platinum Futures")

    assert gold.name_cn == "黄金期货"
    assert gold.status == "mapped"
    assert propylene.name_cn == "丙烯期货"
    assert platinum.name_cn == "铂金期货"


def test_translate_common_etf_name_to_chinese_searchable_name():
    translated = translate_asset_name("ARKK", "ARK Innovation ETF")

    assert translated.name_cn == "ARK 创新 ETF"
    assert translated.status == "generated"
    assert "创新" in translated.search_text


def test_translate_unknown_name_is_reported_as_unmapped():
    translated = translate_asset_name("ZZZ", "Obscure Abbreviation")

    assert translated.name_cn == ""
    assert translated.status == "unmapped"


def test_translate_forex_and_crypto_pairs_to_chinese_names():
    aud_jpy = translate_asset_name("AUDJPY", "AUD/JPY")
    bnb = translate_asset_name("BNBUSDT", "Binance Coin / TetherUS")

    assert aud_jpy.name_cn == "澳元/日元"
    assert aud_jpy.status == "mapped"
    assert bnb.name_cn == "币安币/泰达币"
    assert bnb.status == "mapped"
