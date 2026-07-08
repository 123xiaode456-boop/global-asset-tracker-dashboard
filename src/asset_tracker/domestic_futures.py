from __future__ import annotations

from typing import Any


DOMESTIC_FUTURES_SYMBOL_BY_NAME = {
    "白银期货": "AG0",
    "铝期货": "AL0",
    "氧化铝期货": "AO0",
    "苹果期货": "AP0",
    "黄金期货": "AU0",
    "丁二烯橡胶期货": "BR0",
    "沥青期货": "BU0",
    "玉米期货": "C0",
    "棉花期货": "CF0",
    "红枣期货": "CJ0",
    "阴极铜期货": "BC0",
    "铜期货": "CU0",
    "棉纱期货": "CY0",
    "玻璃期货": "FG0",
    "燃料油期货": "FU0",
    "热轧卷板期货": "HC0",
    "甲醇期货": "MA0",
    "豆粕期货": "M0",
    "镍期货": "NI0",
    "菜籽油期货": "OI0",
    "铅期货": "PB0",
    "短纤期货": "PF0",
    "花生期货": "PK0",
    "丙烯期货": "PL0",
    "PET瓶片期货": "PR0",
    "对二甲苯期货": "PX0",
    "菜粕期货": "RM0",
    "油菜籽期货": "RS0",
    "天然橡胶期货": "RU0",
    "纯碱期货": "SA0",
    "硅铁期货": "SF0",
    "烧碱期货": "SH0",
    "锡期货": "SN0",
    "漂白针叶浆期货": "SP0",
    "白糖期货": "SR0",
    "不锈钢期货": "SS0",
    "PTA期货": "TA0",
    "尿素期货": "UR0",
    "线材期货": "WR0",
    "豆油期货": "Y0",
    "动力煤期货": "ZC0",
    "锌期货": "ZN0",
}

DOMESTIC_FUTURES_GROUP_BY_SYMBOL = {
    "AG0": "贵金属",
    "AU0": "贵金属",
    "AL0": "有色",
    "AO0": "有色",
    "BC0": "有色",
    "CU0": "有色",
    "HC0": "有色",
    "NI0": "有色",
    "PB0": "有色",
    "SF0": "有色",
    "SN0": "有色",
    "SS0": "有色",
    "WR0": "有色",
    "ZN0": "有色",
    "BR0": "化工品",
    "BU0": "化工品",
    "FG0": "化工品",
    "FU0": "化工品",
    "MA0": "化工品",
    "PF0": "化工品",
    "PL0": "化工品",
    "PR0": "化工品",
    "PX0": "化工品",
    "RU0": "化工品",
    "SA0": "化工品",
    "SH0": "化工品",
    "SP0": "化工品",
    "TA0": "化工品",
    "UR0": "化工品",
    "ZC0": "化工品",
    "AP0": "农产品",
    "C0": "农产品",
    "CF0": "农产品",
    "CJ0": "农产品",
    "CY0": "农产品",
    "M0": "农产品",
    "OI0": "农产品",
    "PK0": "农产品",
    "RM0": "农产品",
    "RS0": "农产品",
    "SR0": "农产品",
    "Y0": "农产品",
}

DOMESTIC_FUTURES_SYMBOL_BY_ROOT = {
    symbol[:-1]: symbol for symbol in DOMESTIC_FUTURES_GROUP_BY_SYMBOL
}

FOREIGN_FUTURES_HINTS = (
    "RBOB",
    "Platinum",
    "铂金",
    "Canola",
    "加拿大",
    "Corn Futures",
    "玉米期货",
    "T-Note",
    "Treasury",
    "Yield",
    "美债",
)


def is_domestic_commodity_future(row: dict[str, Any]) -> bool:
    return domestic_futures_symbol(row) is not None


def domestic_futures_symbol(row: dict[str, Any]) -> str | None:
    name = _contract_name(row)
    symbol = DOMESTIC_FUTURES_SYMBOL_BY_NAME.get(name)
    if not symbol and not _has_foreign_hint(row):
        symbol = DOMESTIC_FUTURES_SYMBOL_BY_ROOT.get(_root_code(row))
    return f"{symbol}.CNFUT" if symbol else None


def domestic_futures_group(row: dict[str, Any]) -> str | None:
    symbol = domestic_futures_symbol(row)
    if not symbol:
        return None
    return DOMESTIC_FUTURES_GROUP_BY_SYMBOL.get(symbol.split(".", 1)[0])


def _contract_name(row: dict[str, Any]) -> str:
    name_cn = str(row.get("asset_name_cn") or "").strip()
    if name_cn:
        return name_cn
    original = str(row.get("asset_name") or "").strip()
    for name in DOMESTIC_FUTURES_SYMBOL_BY_NAME:
        if name in original:
            return name
    return ""


def _root_code(row: dict[str, Any]) -> str:
    code = str(row.get("asset_code") or "").strip().upper()
    return code.split("1!", 1)[0] if "1!" in code else ""


def _has_foreign_hint(row: dict[str, Any]) -> bool:
    text = f"{row.get('asset_name_cn') or ''} {row.get('asset_name') or ''}"
    return any(hint in text for hint in FOREIGN_FUTURES_HINTS)
