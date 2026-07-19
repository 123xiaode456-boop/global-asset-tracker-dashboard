from datetime import date
from zipfile import ZipFile, ZIP_DEFLATED

from asset_tracker.parsers import (
    CANONICAL_COLUMNS,
    MOMENTUM_CANONICAL_COLUMNS,
    MOMENTUM_SOURCE_COLUMNS,
    SOURCE_COLUMNS,
    detect_metadata,
    parse_dataset_file,
)

from conftest import BETTING_PDF, CORE_PDF


def test_detects_dataset_date_and_type_from_filename():
    core = detect_metadata(CORE_PDF)
    betting = detect_metadata(BETTING_PDF)

    assert core.dataset_date == date(2026, 6, 9)
    assert core.dataset_type == "core"
    assert betting.dataset_date == date(2026, 6, 9)
    assert betting.dataset_type == "betting"


def test_detects_domestic_main_and_momentum_dataset_types():
    domestic = detect_metadata("26-07-17 数据总表（国内主连）（趋势识别＋相对比价＋资金监控）（测试）.xlsx")
    momentum = detect_metadata("26-07-17 动量状态（测试）（核心数据集）.xlsx")

    assert domestic.dataset_type == "domestic_main"
    assert momentum.dataset_type == "momentum"


def test_parse_core_pdf_extracts_235_rows_with_standard_columns():
    parsed = parse_dataset_file(CORE_PDF)

    assert parsed.metadata.dataset_date == date(2026, 6, 9)
    assert parsed.metadata.dataset_type == "core"
    assert parsed.row_count == 235
    assert parsed.source_hash
    assert list(parsed.rows[0].keys()) == CANONICAL_COLUMNS
    assert parsed.rows[0]["asset_code"] == "10Y1!"
    assert parsed.rows[0]["asset_name"] == "10-Year Yield Futures"
    assert parsed.rows[0]["day_trend"] == "无趋势"
    assert parsed.rows[0]["relative_state"] == "lead"
    assert isinstance(parsed.rows[0]["capital_daily_change"], float)


def test_parse_betting_pdf_extracts_959_rows_with_standard_columns():
    parsed = parse_dataset_file(BETTING_PDF)

    assert parsed.metadata.dataset_type == "betting"
    assert parsed.row_count == 959
    assert list(parsed.rows[0].keys()) == CANONICAL_COLUMNS
    assert parsed.rows[0]["asset_code"] == "003067"
    assert parsed.rows[0]["asset_name"] == "iShares Hang Seng TECH ETF HKD Counter"
    assert parsed.rows[0]["capital_state"] == "加杠杆"


def test_parse_daily_excel_extracts_standard_columns(tmp_path):
    workbook = tmp_path / "26-06-10 数据总表（趋势识别＋相对比价＋资金监控）（核心数据集）.xlsx"
    _write_minimal_xlsx(
        workbook,
        [
            SOURCE_COLUMNS,
            [
                "SPY",
                "SPDR S&P 500 ETF Trust",
                "上行趋势",
                1,
                "上行趋势",
                2,
                "上行趋势",
                3,
                0.75,
                105.5,
                103.2,
                101.1,
                1,
                "lead",
                2.4,
                "Improving",
                1.2,
                5,
                1,
                "加杠杆",
                1.5,
                "去杠杆",
                -0.8,
                88.2,
                2.1,
            ],
            [
                "EFA",
                "iShares MSCI EAFE ETF",
                "无趋势",
                4,
                "下行趋势",
                5,
                "无趋势",
                6,
                0.35,
                96.0,
                98.5,
                99.1,
                2,
                "Lag",
                -1.4,
                "Weakening",
                -0.9,
                3,
                2,
                "去杠杆",
                -1.5,
                "加杠杆",
                0.8,
                44.2,
                -2.1,
            ],
        ],
    )

    parsed = parse_dataset_file(workbook)

    assert parsed.metadata.dataset_date == date(2026, 6, 10)
    assert parsed.metadata.dataset_type == "core"
    assert parsed.row_count == 2
    assert list(parsed.rows[0].keys()) == CANONICAL_COLUMNS
    assert parsed.rows[0]["asset_code"] == "SPY"
    assert parsed.rows[0]["day_trend"] == "上行趋势"
    assert parsed.rows[0]["relative_strength"] == 105.5
    assert parsed.rows[1]["capital_state"] == "去杠杆"


def test_parse_daily_excel_accepts_reordered_columns(tmp_path):
    workbook = tmp_path / "26-06-17 数据总表（趋势识别＋相对比价＋资金监控）（押注工具）.xlsx"
    reordered_columns = [
        "代码",
        "标的名称",
        "相对强度",
        "强度动量",
        "早期转折",
        "当前比价状态持续时间",
        "当前比价状态",
        "当前比价状态涨幅",
        "此前比价状态",
        "此前比价状态涨幅",
        "此前比价状态持续时间",
        "日级别趋势",
        "日级别趋势持续时间",
        "周级别趋势",
        "周级别趋势持续时间",
        "月级别趋势",
        "月级别趋势持续时间",
        "收盘价对比60日位置",
        "当前杠杆资金状态持续时间",
        "当前杠杆资金状态",
        "当前杠杆资金状态涨幅",
        "此前杠杆资金状态",
        "此前杠杆资金状态涨幅",
        "杠杆资金数值",
        "杠杆资金相比前日变动",
    ]
    values_by_column = {
        "代码": "159667",
        "标的名称": "工业母机",
        "日级别趋势": "上行趋势",
        "日级别趋势持续时间": 2,
        "周级别趋势": "上行趋势",
        "周级别趋势持续时间": 3,
        "月级别趋势": "无趋势",
        "月级别趋势持续时间": 4,
        "收盘价对比60日位置": 0.88,
        "相对强度": 118.88,
        "强度动量": 107.27,
        "早期转折": 102.95,
        "当前比价状态持续时间": 6,
        "当前比价状态": "lead",
        "当前比价状态涨幅": 7.79,
        "此前比价状态": "Weakening",
        "此前比价状态涨幅": 1.2,
        "此前比价状态持续时间": 2,
        "当前杠杆资金状态持续时间": 1,
        "当前杠杆资金状态": "加杠杆",
        "当前杠杆资金状态涨幅": 0.5,
        "此前杠杆资金状态": "去杠杆",
        "此前杠杆资金状态涨幅": -0.5,
        "杠杆资金数值": 77.7,
        "杠杆资金相比前日变动": 3.3,
    }
    _write_minimal_xlsx(
        workbook,
        [
            reordered_columns,
            [values_by_column[column] for column in reordered_columns],
        ],
    )

    parsed = parse_dataset_file(workbook)

    assert parsed.metadata.dataset_type == "betting"
    assert parsed.row_count == 1
    assert parsed.rows[0]["asset_code"] == "159667"
    assert parsed.rows[0]["asset_name"] == "工业母机"
    assert parsed.rows[0]["day_trend"] == "上行趋势"
    assert parsed.rows[0]["relative_strength"] == 118.88
    assert parsed.rows[0]["capital_state"] == "加杠杆"


def test_parse_momentum_excel_extracts_typed_columns(tmp_path):
    workbook = tmp_path / "26-07-17 动量状态（测试）（核心数据集）.xlsx"
    _write_minimal_xlsx(
        workbook,
        [
            MOMENTUM_SOURCE_COLUMNS,
            ["SPY", "SPDR S&P 500 ETF Trust", 1, "正动能", 2.5, "打点", 0.2, 1.25, 0.35],
        ],
    )

    parsed = parse_dataset_file(workbook)

    assert parsed.metadata.dataset_type == "momentum"
    assert parsed.row_count == 1
    assert list(parsed.rows[0]) == MOMENTUM_CANONICAL_COLUMNS
    assert parsed.rows[0]["current_momentum_state_duration"] == 1
    assert parsed.rows[0]["current_momentum_state"] == "正动能"
    assert parsed.rows[0]["momentum_value"] == 1.25
    assert parsed.rows[0]["momentum_daily_change"] == 0.35


def _write_minimal_xlsx(path, rows):
    sheet = _sheet_xml(rows)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def _sheet_xml(rows):
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                escaped = (
                    str(value)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                )
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        "</worksheet>"
    )


def _column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
