from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetNameTranslation:
    name_cn: str
    status: str
    search_text: str


FUTURES_NAME_CN = {
    "10-Year Yield Futures": "10年期美债收益率期货",
    "Australian Dollar Futures": "澳元期货",
    "Canadian Dollar Futures": "加元期货",
    "Japanese Yen Futures": "日元期货",
    "Brazilian Real Futures": "巴西雷亚尔期货",
    "Mexican Peso Futures": "墨西哥比索期货",
    "Swiss Franc Futures": "瑞士法郎期货",
    "Cast Aluminium Alloy Futures": "铸造铝合金期货",
    "Silver Futures": "白银期货",
    "Aluminium High Grade Futures": "高级铝期货",
    "Aluminum Futures": "铝期货",
    "Aluminum Oxide Futures": "氧化铝期货",
    "Fresh Apple Futures": "苹果期货",
    "Gold Futures": "黄金期货",
    "Bloomberg Commodity Index Futures": "彭博商品指数期货",
    "Butadiene Rubber Futures": "丁二烯橡胶期货",
    "Brent Crude Futures": "布伦特原油期货",
    "Bitumen Futures": "沥青期货",
    "Grade A Copper Futures": "A级铜期货",
    "Cocoa Futures": "可可期货",
    "Cotton Futures": "棉花期货",
    "Dried Jujube Futures": "红枣期货",
    "Crude Oil Futures": "原油期货",
    "Cotton No. 2 Futures": "2号棉花期货",
    "Copper Cathode Futures": "阴极铜期货",
    "Cotton Yarn futures": "棉纱期货",
    "US Dollar Index® Futures": "美元指数期货",
    "European Union Allowance (EUA) Futures": "欧盟碳排放配额期货",
    "E-mini S&P MidCap 400 Futures": "E-mini 标普中型股400指数期货",
    "E-mini S&P 500 Futures": "E-mini 标普500指数期货",
    "Flat Glass Futures": "玻璃期货",
    "Fuel Oil Futures": "燃料油期货",
    "Feeder Cattle Futures": "育肥牛期货",
    "Hot Rolled Coils Futures": "热轧卷板期货",
    "Lean Hog Futures": "瘦肉猪期货",
    "Copper Futures": "铜期货",
    "NY Harbor ULSD Futures": "纽约港超低硫柴油期货",
    "Hang Seng Index Futures": "恒生指数期货",
    "CSI 500 Index Futures": "中证500股指期货",
    "CSI 300 Index Futures": "沪深300股指期货",
    "SSE 50 Index Futures": "上证50股指期货",
    "CSI 1000 Index Futures": "中证1000股指期货",
    "LNG Japan/Korea Marker (Platts) Futures": "JKM日韩液化天然气期货",
    "Coffee C Futures": "咖啡C期货",
    "KC HRW Wheat Futures": "堪萨斯硬红冬小麦期货",
    "Lumber Futures": "木材期货",
    "Live Cattle Futures": "活牛期货",
    "Micro E-mini Russell 2000 Index Futures": "微型E-mini罗素2000指数期货",
    "Methanol Futures": "甲醇期货",
    "MSCI Emerging Markets Index Futures": "MSCI新兴市场指数期货",
    "Henry Hub Natural Gas Futures": "亨利港天然气期货",
    "Nickel Futures": "镍期货",
    "GIFT NIFTY 50 INDEX FUTURES": "GIFT NIFTY 50指数期货",
    "Nikkei (USD) Futures": "日经225美元计价期货",
    "E-mini Nasdaq-100 Futures": "E-mini 纳斯达克100指数期货",
    "Rapeseed Oil Futures": "菜籽油期货",
    "Frozen Concentrate Orange Juice A Futures": "冷冻浓缩橙汁A期货",
    "Palladium Futures": "钯金期货",
    "Lead Futures": "铅期货",
    "Polyester Staple Fiber Futures": "短纤期货",
    "Peanut Kernel Futures": "花生期货",
    "Platinum Futures": "铂金期货",
    "Propylene Futures": "丙烯期货",
    "Polyethylene Terephthalate Resin For Bottles Futures": "PET瓶片期货",
    "p-Xylene Futures": "对二甲苯期货",
    "E-mini Natural Gas Futures": "E-mini 天然气期货",
    "RBOB Gasoline Futures": "RBOB汽油期货",
    "Steel Rebar Futures": "螺纹钢期货",
    "Robusta Coffee Futures": "罗布斯塔咖啡期货",
    "Rapeseed Meal Futures": "菜粕期货",
    "Canola Futures": "加拿大油菜籽期货",
    "Rapeseed Futures": "油菜籽期货",
    "E-mini Russell 2000 Index Futures": "E-mini 罗素2000指数期货",
    "Natural Rubber Futures": "天然橡胶期货",
    "Soda Ash Futures": "纯碱期货",
    "Sugar No. 11 Futures": "11号原糖期货",
    "Ferrosilicon Futures": "硅铁期货",
    "Sodium Hydroxide Futures": "烧碱期货",
    "Manganese Silicon Futures": "锰硅期货",
    "Tin Futures": "锡期货",
    "Bleached Softwood Kraft Pulp Futures": "漂白针叶浆期货",
    "White Sugar Futures": "白糖期货",
    "Three-Month SOFR Futures": "三个月SOFR期货",
    "Stainless Steel Futures": "不锈钢期货",
    "10-year CGB Futures": "10年期国债期货",
    "Purified Terephthalic Acid (PTA) Futures": "PTA期货",
    "5-year CGB Futures": "5年期国债期货",
    "30-year CGB Futures": "30年期国债期货",
    "Ultra 10-Year U.S. Treasury Note Futures": "超长期10年期美债期货",
    "2-year CGB Futures": "2年期国债期货",
    "Dutch TTF Natural Gas Calendar Month Futures": "荷兰TTF天然气月度期货",
    "Ultra U.S. Treasury Bond Futures": "超长期美国国债期货",
    "Urea Futures": "尿素期货",
    "UxC Uranium U3O8 Futures": "U3O8铀期货",
    "Cboe Volatility Index (VIX) Futures": "VIX波动率指数期货",
    "Wire Rod Futures": "线材期货",
    "XRP Futures": "XRP期货",
    "E-mini Dow Jones Industrial Average Index Futures": "E-mini 道琼斯工业平均指数期货",
    "U.S. Treasury Bond Futures": "美国长期国债期货",
    "Corn Futures": "玉米期货",
    "Thermal Coal Futures": "动力煤期货",
    "5-Year T-Note Futures": "5年期美债期货",
    "Soybean Oil Futures": "豆油期货",
    "Soybean Meal Futures": "豆粕期货",
    "10-Year T-Note Futures": "10年期美债期货",
    "Zinc Futures": "锌期货",
    "Oat Futures": "燕麦期货",
    "30 Day Federal Funds Futures": "30天联邦基金利率期货",
    "Rough Rice Futures": "糙米期货",
    "Soybean Futures": "大豆期货",
    "Special High Grade Zinc Futures": "特级锌期货",
    "2-Year T-Note Futures": "2年期美债期货",
    "Chicago SRW Wheat Futures": "芝加哥软红冬小麦期货",
}


EXACT_NAME_CN = {
    "A50": "富时中国A50",
    "1000ETF": "中证1000ETF",
    "ZZ1000": "中证1000",
    "ZZ100": "中证100",
    "5G50ETF": "5G 50 ETF",
    "500ETF": "中证500ETF",
    "225ETF": "日经225ETF",
    "5GETF": "5G ETF",
    "800ETF": "中证800ETF",
    "Alerian MLP ETF": "Alerian MLP能源基础设施 ETF",
    "Invesco Senior Loan ETF": "景顺优先贷款 ETF",
    "Bitwise Web3 ETF": "Bitwise Web3主题 ETF",
    "Eldridge BBB-B CLO ETF": "Eldridge BBB-B级CLO ETF",
    "State Street SPDR S&P Kensho Clean Power ETF": "SPDR S&P Kensho清洁电力 ETF",
    "VanEck ChiNext Innovators ETF": "VanEck创业板创新者 ETF",
    "ALPS Disruptive Technologies ETF": "ALPS颠覆性科技 ETF",
    "MicroSectors FANG+ 3 Leveraged ETNs": "MicroSectors FANG+ 三倍杠杆 ETN",
    "iShares Biotechnology ETF": "iShares生物科技 ETF",
    "iShares Russell Top 200 ETF": "iShares罗素前200 ETF",
    "Roundhill Meme ETF": "Roundhill Meme主题 ETF",
    "State Street Blackstone Senior Loan ETF": "State Street Blackstone优先贷款 ETF",
    "ProShares VIX Mid-Term Futures ETF": "ProShares VIX中期期货 ETF",
}


CODE_NAME_CN = {
    "CAC40": "法国CAC40指数",
    "DAX": "德国DAX 40指数",
    "SX5E": "欧洲斯托克50指数",
    "STOXX 50": "欧洲斯托克50指数",
    "TRIP": "Tripadvisor 公司",
}


FX_CURRENCY_CN = {
    "AUD": "澳元",
    "BRL": "巴西雷亚尔",
    "CAD": "加元",
    "CHF": "瑞士法郎",
    "CNH": "离岸人民币",
    "CNY": "人民币",
    "EUR": "欧元",
    "GBP": "英镑",
    "IDR": "印尼盾",
    "INR": "印度卢比",
    "JPY": "日元",
    "KRW": "韩元",
    "MXN": "墨西哥比索",
    "NOK": "挪威克朗",
    "NZD": "纽元",
    "SEK": "瑞典克朗",
    "SGD": "新加坡元",
    "THB": "泰铢",
    "TRY": "土耳其里拉",
    "USD": "美元",
    "ZAR": "南非兰特",
}


CRYPTO_CN = {
    "BNB": "币安币",
    "DOGE": "狗狗币",
    "ETH": "以太坊",
    "LINK": "Chainlink",
    "SOL": "Solana",
    "SUI": "SUI",
    "TRX": "波场",
    "USDT": "泰达币",
}


PHRASE_CN = {
    "Hang Seng TECH": "恒生科技",
    "HKD Counter": "港币柜台",
    "ACWI": "全球股票",
    "EAFE": "发达市场",
    "ex U.S.": "除美国",
    "U.S.": "美国",
    "US": "美国",
    "USA": "美国",
    "United States": "美国",
    "Eurozone": "欧元区",
    "Euro": "欧元",
    "Pound": "英镑",
    "British Pound": "英镑",
    "Japanese Yen": "日元",
    "Chinese Yuan": "人民币",
    "Offshore Chinese Yuan": "离岸人民币",
    "U.S. Dollar": "美元",
    "US Dollar": "美元",
    "United States Dollar": "美元",
    "ESG Aware": "ESG精选",
    "ESG Optimized": "ESG优化",
    "Min Vol": "低波动",
    "Minimum Volatility": "低波动",
    "Low Volatility": "低波动",
    "Volatility": "波动率",
    "High Beta": "高贝塔",
    "GARP": "合理价格成长",
    "Equal Weight": "等权重",
    "Revenue": "收入",
    "Buyback Achievers": "回购成就股",
    "Preferred": "优先股",
    "Semiconductors": "半导体",
    "Semiconductor": "半导体",
    "Software": "软件",
    "Telecom": "电信",
    "Telecommunications": "电信",
    "Communication Services": "通信服务",
    "Financials": "金融",
    "Financial": "金融",
    "Basic Materials": "基础材料",
    "Materials": "材料",
    "Transportation": "运输",
    "Homebuilders": "住宅建筑商",
    "Home Construction": "住宅建筑",
    "Housing": "住房",
    "Insurance": "保险",
    "Regional Banks": "地区银行",
    "Regional Banking": "地区银行",
    "Bank": "银行",
    "Retail": "零售",
    "Online Retail": "线上零售",
    "E-Commerce": "电商",
    "Medical Devices": "医疗器械",
    "Health Care Equipment": "医疗设备",
    "Health Care Services": "医疗服务",
    "Health Care": "医疗保健",
    "Pet Care": "宠物护理",
    "Weight Loss": "减重",
    "Weight Loss Drug": "减重药",
    "Treatment": "治疗",
    "Leisure and Entertainment": "休闲娱乐",
    "Video Gaming and eSports": "电子游戏与电竞",
    "Video Games": "电子游戏",
    "eSports": "电竞",
    "Social Sentiment": "社交情绪",
    "Meme": "Meme",
    "Web3": "Web3",
    "Digital Transformation": "数字化转型",
    "Genomic Revolution": "基因革命",
    "Merger Arbitrage": "并购套利",
    "Tail Risk": "尾部风险",
    "Hedge Replication": "对冲复制",
    "Interest Rate Hedge": "利率对冲",
    "Interest Rate": "利率",
    "Inflation Expectations": "通胀预期",
    "Inflation Hedge": "通胀对冲",
    "Carbon Transition": "碳转型",
    "Readiness": "准备度",
    "Aware": "精选",
    "Active": "主动",
    "AAA CLO": "AAA级CLO",
    "B-BBB CLO": "B-BBB级CLO",
    "CLO": "CLO",
    "Mortgage-Backed Securities": "抵押贷款支持证券",
    "Mortgage-Backed": "抵押贷款支持",
    "MBS": "抵押贷款支持证券",
    "T-Bill": "短期国债",
    "Floating Rate": "浮动利率",
    "Investment Grade": "投资级",
    "Physical Precious Metals Basket Shares": "实物贵金属篮子份额",
    "Physical Palladium Shares": "实物钯金份额",
    "Physical Platinum Shares": "实物铂金份额",
    "Precious Metals": "贵金属",
    "Palladium": "钯金",
    "Platinum": "铂金",
    "Rare Earth and Strategic Metals": "稀土与战略金属",
    "Rare Earth/Strategic Metals": "稀土与战略金属",
    "Metals & Mining": "金属与矿业",
    "Steel": "钢铁",
    "Agribusiness": "农业企业",
    "Cannabis": "大麻",
    "Alternative Harvest": "另类收获",
    "Uranium Miners": "铀矿商",
    "Uranium and Nuclear": "铀与核能",
    "Nuclear": "核能",
    "Solar": "太阳能",
    "Natural Resources": "自然资源",
    "North American Natural Resources": "北美自然资源",
    "Travel Tech": "旅行科技",
    "Dry Bulk Shipping": "干散货航运",
    "Sports Betting & iGaming": "体育博彩和线上娱乐",
    "Crypto Industry Innovators": "加密产业创新者",
    "Ethereum Staking": "以太坊质押",
    "Ethereum": "以太坊",
    "TetherUS": "泰达币",
    "Binance Coin": "币安币",
    "Dogecoin": "狗狗币",
    "ChainLink": "Chainlink",
    "TRON": "波场",
    "Saudi Arabia": "沙特阿拉伯",
    "United Arab Emirates": "阿联酋",
    "UAE": "阿联酋",
    "Denmark": "丹麦",
    "Indonesia": "印度尼西亚",
    "Israel": "以色列",
    "Philippines": "菲律宾",
    "Poland": "波兰",
    "Australia": "澳大利亚",
    "Canada": "加拿大",
    "Sweden": "瑞典",
    "Germany": "德国",
    "Hong Kong": "香港",
    "Italy": "意大利",
    "Belgium": "比利时",
    "Switzerland": "瑞士",
    "Malaysia": "马来西亚",
    "Netherlands": "荷兰",
    "Spain": "西班牙",
    "France": "法国",
    "Singapore": "新加坡",
    "Taiwan": "台湾",
    "United Kingdom": "英国",
    "Mexico": "墨西哥",
    "South Korea": "韩国",
    "Brazil": "巴西",
    "Thailand": "泰国",
    "Turkey": "土耳其",
    "Vietnam": "越南",
    "Qatar": "卡塔尔",
    "Latin America": "拉丁美洲",
    "Innovation": "创新",
    "Artificial Intelligence": "人工智能",
    "Technology": "科技",
    "Robotics": "机器人",
    "Cybersecurity": "网络安全",
    "Blockchain": "区块链",
    "Bitcoin": "比特币",
    "Ether": "以太坊",
    "Gold": "黄金",
    "Silver": "白银",
    "Copper": "铜",
    "Oil": "石油",
    "Natural Gas": "天然气",
    "Clean Energy": "清洁能源",
    "Energy": "能源",
    "Water": "水资源",
    "Agriculture": "农业",
    "Commodity": "商品",
    "Base Metals": "基本金属",
    "Treasury": "美国国债",
    "Bond": "债券",
    "Bonds": "债券",
    "High Yield": "高收益",
    "Dividend": "股息",
    "Emerging Markets": "新兴市场",
    "Emerging Market": "新兴市场",
    "International": "国际",
    "Global": "全球",
    "China": "中国",
    "Japan": "日本",
    "Europe": "欧洲",
    "Asia": "亚洲",
    "Africa": "非洲",
    "Argentina": "阿根廷",
    "Chile": "智利",
    "India": "印度",
    "Consumer Staples": "必需消费",
    "Consumer Discretionary": "可选消费",
    "Healthcare": "医疗保健",
    "Biotech": "生物科技",
    "Real Estate": "房地产",
    "Industrial": "工业",
    "Industrials": "工业",
    "Infrastructure": "基础设施",
    "Utilities": "公用事业",
    "Cloud Computing": "云计算",
    "Internet": "互联网",
    "Autonomous": "自动驾驶",
    "Electric Vehicles": "电动车",
    "Battery": "电池",
    "Lithium": "锂",
    "Defense": "国防",
    "Aerospace": "航空航天",
    "Space": "太空",
    "Small Cap": "小盘股",
    "MidCap": "中盘股",
    "Large Cap": "大盘股",
    "Value": "价值",
    "Growth": "成长",
    "Quality": "质量",
    "Momentum": "动量",
    "Income": "收益",
    "Short": "做空",
    "Long": "做多",
    "Bull": "看多",
    "Bear": "看空",
    "Ultra": "杠杆",
    "2x": "2倍",
    "2X": "2倍",
    "3X": "3倍",
    "Daily": "每日",
    "Option Income": "期权收益",
    "Managed Futures": "管理期货",
    "Strategy": "策略",
    "Index": "指数",
    "ETF": "ETF",
    "Fund": "基金",
    "Trust": "信托",
    "Equity": "股票",
    "Stock Market": "股票市场",
    "Broad Market": "宽基市场",
    "Core": "核心",
    "Factor": "因子",
    "Multifactor": "多因子",
    "Multi-factor": "多因子",
    "Fundamental": "基本面",
    "Company": "公司",
    "Mega-Cap": "超大盘",
    "Micro-Cap": "微盘股",
    "Small-Cap": "小盘股",
    "SmallCap": "小盘股",
    "Mid-Cap": "中盘股",
    "Mid Cap": "中盘股",
    "Large Company": "大公司",
    "Small Company": "小公司",
    "Total Return Tactical": "总回报战术",
    "Developed World": "发达世界",
    "Developed Markets": "发达市场",
    "World": "全球",
    "Total World": "全球总市场",
    "Total Stock Market": "股票总市场",
    "Extended Market": "扩展市场",
    "Export Leaders": "出口龙头",
    "Wide Moat": "宽护城河",
    "Final Frontiers": "前沿科技",
    "Smart Mobility": "智能出行",
    "Self-driving EV & Tech": "自动驾驶电动车与科技",
    "S&P 500": "标普500",
    "S&P500": "标普500",
    "S&P 100": "标普100",
    "Russell 1000": "罗素1000",
    "Russell2000": "罗素2000",
    "Russell 2000": "罗素2000",
    "R2000": "罗素2000",
    "NASDAQ 100": "纳斯达克100",
    "Nasdaq 100": "纳斯达克100",
    "QQQ": "QQQ",
    "UltraShort": "反向杠杆",
    "UltraPro": "三倍杠杆",
    "Weekly Distribution": "周度分派",
    "BuyWrite": "备兑看涨",
    "REIT": "房地产投资信托",
    "TIPS": "通胀保值债券",
    "FANG+": "FANG+",
}


def translate_asset_name(asset_code: str, asset_name: str) -> AssetNameTranslation:
    code = str(asset_code or "").strip()
    name = str(asset_name or "").strip()
    if not name:
        return AssetNameTranslation("", "unmapped", code)
    if _has_chinese(name):
        return _result(name, "original", code, name)

    exact = EXACT_NAME_CN.get(name)
    if exact:
        return _result(exact, "mapped", code, name)
    code_exact = CODE_NAME_CN.get(code) or CODE_NAME_CN.get(name)
    if code_exact:
        return _result(code_exact, "mapped", code, name)

    pair_name = _translate_pair(code, name)
    if pair_name:
        return _result(pair_name, "mapped", code, name)

    futures = FUTURES_NAME_CN.get(name)
    if futures:
        return _result(futures, "mapped", code, name)

    generated = _generate_name_cn(name)
    if generated:
        return _result(generated, "generated", code, name)
    return _result("", "unmapped", code, name)


def display_asset_name(row: dict[str, Any], include_original: bool = False) -> str:
    name = str(row.get("asset_name") or "").strip()
    name_cn = str(row.get("asset_name_cn") or "").strip()
    if not name_cn:
        return name
    if include_original and name and name != name_cn:
        return f"{name_cn}（{name}）"
    return name_cn


def _generate_name_cn(name: str) -> str:
    translated = name
    changed = False
    for phrase, replacement in sorted(PHRASE_CN.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", flags=re.IGNORECASE)
        translated, count = pattern.subn(replacement, translated)
        changed = changed or count > 0
    if not changed or not _has_chinese(translated):
        return ""
    translated = re.sub(r"\s+", " ", translated).strip()
    translated = translated.replace(" & ", " 和 ")
    return translated


def _translate_pair(code: str, name: str) -> str:
    normalized_code = code.replace("/", "").upper()
    if len(normalized_code) == 6:
        left, right = normalized_code[:3], normalized_code[3:]
        if left in FX_CURRENCY_CN and right in FX_CURRENCY_CN:
            return f"{FX_CURRENCY_CN[left]}/{FX_CURRENCY_CN[right]}"

    crypto_code = normalized_code
    for quote in ("USDT", "USD"):
        if crypto_code.endswith(quote) and len(crypto_code) > len(quote):
            base = crypto_code[: -len(quote)]
            if base in CRYPTO_CN:
                return f"{CRYPTO_CN[base]}/{CRYPTO_CN.get(quote, quote)}"

    text = name.upper().replace(" ", "")
    if "/" in name:
        parts = [part.strip().upper() for part in name.split("/", 1)]
        if len(parts) == 2:
            left = _pair_part_cn(parts[0])
            right = _pair_part_cn(parts[1])
            if left and right:
                return f"{left}/{right}"
    if " VS " in name.upper():
        parts = [part.strip().upper() for part in re.split(r"\bVS\b", name.upper(), maxsplit=1)]
        if len(parts) == 2:
            left = _pair_part_cn(parts[0])
            right = _pair_part_cn(parts[1])
            if left and right:
                return f"{left}/{right}"
    if text.endswith("USDOLLAR"):
        return ""
    return ""


def _pair_part_cn(value: str) -> str:
    cleaned = value.replace(".", "").replace(" ", "").replace("DOLLAR", "DOLLAR")
    aliases = {
        "US": "USD",
        "USDOLLAR": "USD",
        "UNITEDSTATESDOLLAR": "USD",
        "EURO": "EUR",
        "BRITISHPOUND": "GBP",
        "JAPANESEYEN": "JPY",
        "CHINESEYUAN": "CNY",
        "OFFSHORECHINESEYUAN": "CNH",
        "BRAZILIANREAL": "BRL",
        "INDONESIANRUPIAH": "IDR",
        "INDIANRUPEE": "INR",
        "SOUTHKOREANWON": "KRW",
        "MEXICANPESO": "MXN",
        "NORWEGIANKRONE": "NOK",
        "TURKISHNEWLIRA": "TRY",
        "SOUTHAFRICANRAND": "ZAR",
        "TETHERUS": "USDT",
        "BINANCECOIN": "BNB",
        "DOGECOIN": "DOGE",
        "ETHEREUM": "ETH",
        "CHAINLINK": "LINK",
        "TRON": "TRX",
    }
    code = aliases.get(cleaned, cleaned)
    return FX_CURRENCY_CN.get(code) or CRYPTO_CN.get(code, "")


def _result(name_cn: str, status: str, asset_code: str, asset_name: str) -> AssetNameTranslation:
    search_text = " ".join(part for part in [asset_code, asset_name, name_cn] if part)
    return AssetNameTranslation(name_cn=name_cn, status=status, search_text=search_text)


def _has_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value)))
