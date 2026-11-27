"""Fill the two yields the base dataset leaves empty: 科研 (science) and 文化 (culture).

The base data refuses to publish a yield unless one definition covers ≥75% of cities, and no official city-level
R&D / culture-industry series does. This builder uses published city-level output indices
(university + R&D + national labs for science; heritage sites, museums, historic towns and intangible heritage for
culture), which cover every prefecture, and maps them onto the two official *national* totals:

    city yield = index / 100000 × national total

so a city's value is a share of a real, published national number — a small-area allocation, not an invented
figure. Both the anchor, the index and the method are written into the Almanac text in nation.json.
"""

from __future__ import annotations

import argparse
import json
import os

# 2022 年全国 R&D 经费内部支出 30,870 亿元（国家统计局《2022 年全国科技经费投入统计公报》）
NATIONAL_RD_YUAN = 30870e8
# 2022 年全国文化及相关产业增加值约 5.4 万亿元（国家统计局）
NATIONAL_CULTURE_YUAN = 5.4e12

DESCRIPTIONS = {
    "science": (
        "科研 = 研究与试验发展（R&D）经费内部支出（元，当年价）。全国口径锚定 2022 年 30,870 亿元"
        "（国家统计局《2022 年全国科技经费投入统计公报》），按各市的科研产出指数分摊到城市。指数由三部分组成："
        "高校（双一流、本科在校生规模）、R&D 经费（有公开值的城市）与国家级科研机构（中科院院属单位、"
        "全国重点实验室）的加权计分。覆盖全部 344 个城市；港澳台不在分摊范围内，置空（非 0）。"
        "注意：城市值是「全国总量 × 份额」的估算，不是各市公报的原始 R&D 数字。"
    ),
    "culture": (
        "文化 = 文化及相关产业增加值（元，当年价）。全国口径锚定 2022 年约 5.4 万亿元（国家统计局），"
        "按各市的文化产出指数分摊到城市。指数由世界文化遗产、全国重点文物保护单位、一级博物馆、"
        "国家历史文化名城/名镇/名村与国家级非物质文化遗产计分，并按各市的旅游产出（5A 景区、风景名胜区、"
        "国家公园）做少量加权。覆盖全部 344 个城市；港澳台不在分摊范围内，置空（非 0）。"
        "注意：城市值是「全国总量 × 份额」的估算，不是各市公报的原始文化产业增加值。"
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default=os.path.join(os.path.dirname(__file__), "..", "web"))
    ap.add_argument("--civ", required=True, help="civ.json holding the per-city output indices")
    args = ap.parse_args()

    web = os.path.abspath(args.web)
    data = os.path.join(web, "data")
    cities = json.load(open(os.path.join(data, "cities.json"), encoding="utf-8"))
    nation = json.load(open(os.path.join(data, "nation.json"), encoding="utf-8"))
    civ = json.load(open(args.civ, encoding="utf-8"))
    comp = {str(c["adcode"]): c for c in civ["cities"]}

    filled = {"science": 0, "culture": 0}
    for city in cities:
        src = comp.get(str(city["id"]))
        if not src:
            continue
        y = src.get("yields") or {}
        for key, total in (("science", NATIONAL_RD_YUAN), ("culture", NATIONAL_CULTURE_YUAN)):
            idx = y.get(key)
            if not isinstance(idx, (int, float)):
                continue
            city["yields"][key] = int(round(idx / 100000.0 * total))
            filled[key] += 1

    # national totals: the official anchors, not the sum of the allocated city values
    nation["nation"]["yields"]["science"] = int(NATIONAL_RD_YUAN)
    nation["nation"]["yields"]["culture"] = int(NATIONAL_CULTURE_YUAN)
    for entry in nation["yields"]:
        if entry["key"] in DESCRIPTIONS:
            entry["unit"] = "cny"
            entry["basis"] = "rd_expenditure" if entry["key"] == "science" else "culture_va"
            entry["industries"] = []
            entry["coverage"] = 1.0
            entry["description"] = DESCRIPTIONS[entry["key"]]
            entry["estimated"] = True

    # ranks: recompute science/culture ranks over the cities that have a value
    for key in ("science", "culture"):
        vals = [(c["yields"].get(key), c["id"]) for c in cities if c["yields"].get(key) is not None]
        vals.sort(key=lambda t: (-t[0], t[1]))
        rank = {cid: k + 1 for k, (_, cid) in enumerate(vals)}
        for c in cities:
            c.setdefault("ranks", {})
            c["ranks"][key] = rank.get(c["id"])

    json.dump(cities, open(os.path.join(data, "cities.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(nation, open(os.path.join(data, "nation.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"filled {filled} of {len(cities)} cities; national anchors written")


if __name__ == "__main__":
    main()
