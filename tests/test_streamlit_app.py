from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_single_asset_page_renders_decision_and_quadrant_sections():
    app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py"), default_timeout=15)
    app.run()

    app.tabs[3].run()

    markdown_text = "\n".join(element.value for element in app.markdown)
    subheaders = [element.value for element in app.subheader]

    assert "当天结论" in markdown_text
    assert "行情与指标对比" in subheaders
    assert "四象限位置变化" in subheaders
    assert "历史明细" in subheaders
    assert any("检索单资产" in item.label for item in app.text_input)


def test_main_page_exposes_visible_chinese_futures_quadrant_link():
    app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py"), default_timeout=15)
    app.run()

    markdown_text = "\n".join(element.value for element in app.markdown)

    assert "页面导航" in markdown_text
    assert "期货品种四象限" in markdown_text
    assert "/期货品种四象限" in markdown_text


def test_quadrant_page_renders_market_map_and_asset_trajectory():
    app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py"), default_timeout=15)
    app.run()

    app.tabs[2].run()

    subheaders = [element.value for element in app.subheader]

    assert "全市场四象限分布" in subheaders
    assert "当日机会排名" in subheaders
    assert "单品种象限轨迹" in subheaders


def test_quadrant_page_renders_selected_asset_decision_and_opportunity():
    app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py"), default_timeout=15)
    app.run()

    app.tabs[2].run()

    markdown_text = "\n".join(element.value for element in app.markdown)

    assert "当天结论" in markdown_text
    assert "所选日期机会解读" in markdown_text


def test_unmapped_page_renders_price_coverage_queue():
    app = AppTest.from_file(str(PROJECT_ROOT / "streamlit_app.py"), default_timeout=15)
    app.run()

    app.tabs[4].run()

    subheaders = [element.value for element in app.subheader]

    assert "行情覆盖" in subheaders
    assert "缺行情资产" in subheaders


def test_futures_quadrant_page_renders_separate_asset_chart_grid():
    app = AppTest.from_file(str(PROJECT_ROOT / "pages" / "期货品种四象限.py"), default_timeout=20)
    app.run()

    titles = [element.value for element in app.title]
    markdown_text = "\n".join(element.value for element in app.markdown)
    captions = [element.value for element in app.caption]
    subheaders = [element.value for element in app.subheader]
    text_input_labels = [element.label for element in app.text_input]
    selectbox_labels = [element.label for element in app.selectbox]
    main_children = app._tree[0].children

    assert "期货品种四象限位置变化" in titles
    assert "页面导航" in markdown_text
    assert "主仪表盘" in markdown_text
    assert any("每个小图展示一个品种" in value for value in captions)
    assert {"化工品", "贵金属", "有色", "农产品"}.issubset(set(subheaders))
    assert text_input_labels == ["数据库"]
    assert selectbox_labels == ["观察日期"]
    assert len(main_children) > 10
    assert len(app.dataframe) == 0
