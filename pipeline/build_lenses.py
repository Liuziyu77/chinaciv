"""Build web/data/lenses.json — the "paint an indicator onto the map" layers.

Input:  a directory of per-hex layer files and the grid file that gives every hex centre's lon/lat. Each layer
        file holds one JSON object with a `hex` field: parallel arrays indexed by hex id, one value per hex.
        The figures in them are the publicly documented per-hex statistics that web/data/lenses.json describes.
Output: web/data/lenses.json (groups + lenses, one value array of length cols*rows per lens).

The layer grid and this site's grid share one projection (spherical Albers, parallels 25°N/47°N, central
meridian 105°E) but not one pitch: the layers are packed at 25,000 m between hex centres, this site uses a
25 km *circumradius* (≈43.3 km between centres). So every layer hex centre is projected into this site's map
kilometres and dropped into the cell that contains it; each cell then aggregates the few hexes that landed in it.

Aggregation per field:
  sum     extensive totals (people, yuan, MW, tonnes)          -> added up
  area    intensive per-area values on equal-area hexes        -> plain mean
  pop     per-person values (income, exposure, life expectancy)-> mean weighted by resident population
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys

SQRT3 = math.sqrt(3)
R_EARTH_KM = 6371.0088

# --- projection (mirrors pipeline note in web/js/world.js and the reference project's core/geo.py) -------------


class Albers:
    """Spherical Albers equal-area. Returns km, y *up*."""

    def __init__(self, lat1=25.0, lat2=47.0, lat0=0.0, lon0=105.0):
        p1, p2, p0 = map(math.radians, (lat1, lat2, lat0))
        self.lon0 = math.radians(lon0)
        self.n = (math.sin(p1) + math.sin(p2)) / 2
        self.c = math.cos(p1) ** 2 + 2 * self.n * math.sin(p1)
        self.rho0 = R_EARTH_KM * math.sqrt(self.c - 2 * self.n * math.sin(p0)) / self.n

    def __call__(self, lon, lat):
        rho = R_EARTH_KM * math.sqrt(self.c - 2 * self.n * math.sin(math.radians(lat))) / self.n
        theta = self.n * (math.radians(lon) - self.lon0)
        return rho * math.sin(theta), self.rho0 - rho * math.cos(theta)


class Grid:
    def __init__(self, radius, cols, rows, proj):
        self.radius, self.cols, self.rows = radius, cols, rows
        self.proj = proj

    def cell_at(self, x, y):
        """Pointy-top odd-r: (col, row) centre at (√3·R·(col + ½·(row&1)), 1.5·R·row)."""
        q = (SQRT3 / 3 * x - y / 3) / self.radius
        r = (2 / 3 * y) / self.radius
        cx, cz = q, r
        cy = -cx - cz
        rx, ry, rz = math.floor(cx + 0.5), math.floor(cy + 0.5), math.floor(cz + 0.5)
        dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy <= dz:
            rz = -rx - ry
        row = rz
        col = rx + (row - (row & 1)) // 2
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return row * self.cols + col
        return -1


def load_projection(world):
    p = world["projection"]

    class MapProjection:
        def __init__(self):
            self.albers = Albers(p["lat1"], p["lat2"], p["lat0"], p["lon0"])
            self.min_x, self.max_y, self.margin = p["min_x"], p["max_y"], p["margin"]

        def __call__(self, lon, lat):
            x, y = self.albers(lon, lat)
            return x - self.min_x + self.margin, self.max_y - y + self.margin

    return MapProjection()


# --- layer fields ---------------------------------------------------------------------------------------------
# (lens id, group, Chinese name, emoji, icon, unit, format, scale, aggregation, layer, field, factor, desc)

POP_RAMP = ["#1b1035", "#4b2377", "#9a3b8a", "#e0645e", "#f9b24a", "#fff3a8"]
GOLD_RAMP = ["#241705", "#5c3a0c", "#a8641a", "#e0a13a", "#f6d98a", "#fffbe6"]
BLUE_RAMP = ["#071a2b", "#12375c", "#1f5f8c", "#3f93ac", "#84c7b8", "#e8f7e0"]
GREEN_RAMP = ["#0b1f14", "#16472c", "#2b7444", "#57a35e", "#a2d183", "#f0fbd4"]
EARTH_RAMP = ["#171009", "#402a17", "#6f4a26", "#9d7440", "#c9ab7c", "#f2e6cf"]
FIRE_RAMP = ["#1b0507", "#4d0f16", "#8c1c22", "#c93a30", "#ef8a5b", "#fde3c4"]
TEAL_RAMP = ["#041a1e", "#0b3a40", "#15606a", "#2e8f95", "#79c4bd", "#e3f6ef"]

GROUPS = [
    ("people", "人口"),
    ("prosperity", "经济"),
    ("knowledge", "知识"),
    ("life", "民生"),
    ("land", "土地"),
    ("hazards", "灾害"),
    ("connect", "交通能源"),
]

SPECS = [
    # --- people
    dict(id="density", group="people", name="人口密度", emoji="👥", icon="l-density",
         unit="人/km²", format="int", scale="log", agg="area", layer="population", field="density",
         ramp=POP_RAMP, higher="neutral", src="population.city.pop / 面积",
         desc="每平方公里陆地面积上的常住人口。地级市的常住人口按 WorldPop 2020 空间权重摊到格；"
              "颜色覆盖第 2–98 百分位，超出部分以两端颜色表示。"),
    dict(id="pop", group="people", name="每格人口", emoji="👥", icon="l-people",
         unit="人", format="int", scale="log", agg="sum", layer="population", field="pop",
         ramp=POP_RAMP, higher="neutral", src="population.city.pop",
         desc="六边形内的常住人口合计（地级市 2023–2025 年常住人口按 WorldPop 2020 分布摊分到格）。"),
    dict(id="growth", group="people", name="人口增长", emoji="📈", icon="l-people",
         unit="%", format="float", scale="linear", agg="area", layer="population", field="growth1020",
         ramp=TEAL_RAMP, higher="neutral", src="population.growth1020（七普 vs 六普）",
         desc="2010–2020 年常住人口的年均变化率（六普到七普）。东北与川渝农村为负，珠三角与西部省会为正。"),
    dict(id="urban", group="people", name="城镇化率", emoji="🏙️", icon="l-developed",
         unit="%", format="float", scale="linear", agg="area", layer="population", field="urbanRate",
         ramp=GOLD_RAMP, higher="good", src="population.urbanRate",
         desc="城镇常住人口占常住人口的比重（地市级，2023–2024 年）。"),
    dict(id="elderly", group="people", name="老龄化率", emoji="🧓", icon="l-age",
         unit="%", format="float", scale="linear", agg="area", layer="population", field="share65p",
         ramp=FIRE_RAMP, higher="bad", src="population.share65p",
         desc="65 岁及以上人口占常住人口的比重（七普县级口径，地市级取加权平均）。"),
    # --- prosperity
    dict(id="gdp", group="prosperity", name="每格 GDP", emoji="💰", icon="l-income",
         unit="亿元", format="float", scale="log", agg="sum", layer="economy", field="gdp",
         ramp=GOLD_RAMP, higher="good", src="economy.city.gdp2025",
         desc="六边形内的地区生产总值合计，单位亿元（2024–2025 年各地统计公报；县级按已知增速回推）。"),
    dict(id="gdpdensity", group="prosperity", name="GDP 密度", emoji="🏭", icon="l-income",
         unit="万元/km²", format="float", scale="log", agg="area", layer="economy", field="gdpDensity",
         factor=10000.0, ramp=GOLD_RAMP, higher="good", src="economy.gdpDensity",
         desc="每平方公里 GDP，单位万元。沿海城市核心区最高，西部地广人稀处最低。"),
    dict(id="income", group="prosperity", name="可支配收入", emoji="💵", icon="l-income",
         unit="元", format="int", scale="log", agg="pop", layer="livelihood", field="income",
         ramp=GOLD_RAMP, higher="good", src="livelihood.city.income",
         desc="全体居民人均可支配收入（元/年，多数为 2024–2025 年数据），按人口加权平均到格。"),
    dict(id="wage", group="prosperity", name="平均工资", emoji="🧾", icon="l-income",
         unit="元", format="int", scale="log", agg="pop", layer="livelihood", field="avgWage",
         ramp=GOLD_RAMP, higher="good", src="livelihood.city.avgWage",
         desc="城镇非私营单位就业人员年平均工资（元），按人口加权平均到格。"),
    # --- knowledge
    dict(id="college", group="knowledge", name="大学学历", emoji="🎓", icon="l-degrees",
         unit="人/10万人", format="int", scale="linear", agg="area", layer="census", field="collegePer100k",
         ramp=BLUE_RAMP, higher="good", src="七普（2020）县级受教育程度",
         desc="每 10 万人中拥有大学（大专及以上）文化程度的人数（七普县级表，地市级取加权平均）。"),
    dict(id="eduyears", group="knowledge", name="受教育年限", emoji="📚", icon="l-degree",
         unit="年", format="float", scale="linear", agg="area", layer="census", field="avgYears15",
         ramp=BLUE_RAMP, higher="good", src="七普（2020）",
         desc="15 岁及以上人口的平均受教育年限（年，七普县级表）。"),
    dict(id="science", group="knowledge", name="科研产出", emoji="🔬", icon="l-degrees",
         unit="指数", format="float", scale="log", agg="sum", layer="science", field="science",
         ramp=BLUE_RAMP, higher="good", src="science.*（高校、R&D、国家重点实验室）",
         desc="科研产出指数：高校（双一流、本科、在校生）、R&D 经费与国家级科研机构的合成分数，"
              "按机构所在地落到格。北京海淀、上海杨浦、合肥、西安等为高值区。"),
    # --- life
    dict(id="doctors", group="life", name="医师密度", emoji="🩺", icon="l-uninsured",
         unit="人/千人", format="float", scale="linear", agg="pop", layer="livelihood", field="doctorsPer1k",
         ramp=GREEN_RAMP, higher="good", src="livelihood.city.doctorsPer1k",
         desc="每千人口执业（助理）医师数（地市级卫生统计，按人口加权平均到格）。"),
    dict(id="lifeexp", group="life", name="预期寿命", emoji="⏳", icon="l-age",
         unit="岁", format="years", scale="linear", agg="pop", layer="livelihood", field="lifeExp",
         ramp=GREEN_RAMP, higher="good", src="livelihood.city.lifeExp（中国 CDC Weekly 等）",
         desc="人均预期寿命（岁）。京沪与东部沿海最高，青藏高原与西南山区较低。"),
    dict(id="consumption", group="life", name="消费支出", emoji="🛒", icon="l-income",
         unit="元", format="int", scale="log", agg="pop", layer="livelihood", field="consumption",
         ramp=GREEN_RAMP, higher="good", src="livelihood.city.consumption",
         desc="全体居民人均消费支出（元/年），按人口加权平均到格。"),
    dict(id="pm25", group="life", name="PM2.5", emoji="🌫️", icon="l-disasters",
         unit="μg/m³", format="float", scale="log", agg="pop", layer="hazards", field="pm25_2021",
         ramp=FIRE_RAMP, higher="bad", src="hazards.pm25（ACAG/Washington）",
         desc="2021 年 PM2.5 年均浓度（微克/立方米），按人口加权平均到格 —— 人口越密的地方权重越高，"
              "所以它读起来更像「人实际吸入的污染」。"),
    # --- land
    dict(id="elev", group="land", name="平均海拔", emoji="⛰️", icon="l-forest",
         unit="米", format="int", scale="linear", agg="area", layer="terrain", field="elevMean",
         ramp=EARTH_RAMP, higher="neutral", src="ETOPO/COP-DEM",
         desc="六边形内的平均海拔（米）。第一阶梯的青藏高原普遍 4000 米以上，第三阶梯多在 500 米以下。"),
    dict(id="relief", group="land", name="地形起伏", emoji="🏔️", icon="l-forest",
         unit="米", format="float", scale="log", agg="area", layer="terrain", field="elevRange",
         ramp=EARTH_RAMP, higher="neutral", src="terrain.elevRange",
         desc="六边形内最高与最低海拔之差（米）—— 山地的「立体感」。横断山区最大，平原最小。"),
    dict(id="grain", group="land", name="粮食产量", emoji="🌾", icon="l-farmland",
         unit="万吨", format="float", scale="log", agg="sum", layer="agriculture", field="grain",
         factor=1e-4, ramp=GREEN_RAMP, higher="good", src="agriculture.grain（GAEZ/SPAM 2010 + 2025 产量校准）",
         desc="六边形内粮食产量合计（万吨）。东北平原、黄淮海平原与长江中下游是三大高产区。"),
    # --- hazards
    dict(id="quake", group="hazards", name="地震活动", emoji="🌋", icon="l-disasters",
         unit="次/50年", format="float", scale="log", agg="sum", layer="hazards", field="eqCount50",
         ramp=FIRE_RAMP, higher="bad", src="hazards.eqCount50（USGS 目录）",
         desc="过去 50 年（约 1975–2025）该格附近记录到的 M≥4.5 地震次数。青藏高原东缘、川滇、新疆西部最密集。"),
    dict(id="flood", group="hazards", name="洪水风险", emoji="🌊", icon="l-disasters",
         unit="%", format="float", scale="linear", agg="area", layer="hazards", field="floodFrac100",
         factor=100.0, ramp=BLUE_RAMP, higher="bad", src="hazards.floodFrac100（JRC 百年一遇）",
         desc="百年一遇洪水下可能被淹没的面积占比（JRC 全球洪水图）。长江中下游、珠江三角洲与黄淮平原最高。"),
    dict(id="typhoon", group="hazards", name="台风频次", emoji="🌀", icon="l-disasters",
         unit="次/年", format="float", scale="linear", agg="area", layer="hazards", field="tcPerYear",
         ramp=TEAL_RAMP, higher="bad", src="hazards.tcPerYear（IBTrACS）",
         desc="每年途经该格的台风次数（1980–2025 年 IBTrACS 轨迹平均）。东南沿海与海南最高，内陆骤降。"),
    dict(id="risk", group="hazards", name="灾害风险", emoji="⚠️", icon="l-disasters",
         unit="指数", format="float", scale="linear", agg="area", layer="hazards", field="riskTotal",
         ramp=FIRE_RAMP, higher="bad", src="hazards.riskTotal",
         desc="地震、洪水、台风、干旱、滑坡与沙尘六类风险的加权指数（0–1）。"),
    # --- connect / energy
    dict(id="power", group="connect", name="发电装机", emoji="⚡", icon="r-nuclear",
         unit="MW", format="float", scale="log", agg="sum", layer="energy", field="capTotalMW",
         ramp=GOLD_RAMP, higher="good", src="energy.capTotalMW（GEM）",
         desc="六边形内发电装机容量合计（兆瓦）。火电基地（晋陕蒙）、水电（云贵川）、风光大基地（西北）与"
              "沿海核电都在这张图上成片出现。"),
    dict(id="hsr", group="connect", name="高铁密度", emoji="🚄", icon="l-commute",
         unit="km/千km²", format="float", scale="linear", agg="area", layer="transport", field="hsrKm",
         factor=0.6157, ramp=TEAL_RAMP, higher="good",
         src="transport.hsrKm（OSM）",
         desc="每千平方公里国土上的高速铁路里程（km）。换算系数 = 1000 / 本网格单格面积 1623.8 km²。"),
    dict(id="airport", group="connect", name="机场客流", emoji="✈️", icon="l-commute",
         unit="万人次", format="float", scale="log", agg="sum", layer="transport", field="airportPax",
         factor=1e-4, ramp=TEAL_RAMP, higher="good", src="transport.airportPax（民航局 2025）",
         desc="六边形内机场年旅客吞吐量合计（万人次，2025 年民航局公报）。"),
    dict(id="metro", group="connect", name="地铁", emoji="🚇", icon="l-commute",
         unit="km", format="float", scale="log", agg="sum", layer="transport", field="metroKm",
         ramp=TEAL_RAMP, higher="good", src="transport.metroKm（OSM）",
         desc="六边形内的城市轨道交通（地铁、轻轨、市域快线）里程（公里）。"),
]


def pctile(sorted_vals, q):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)


def round_sig(v, sig=4):
    if v == 0:
        return 0
    return round(v, -int(math.floor(math.log10(abs(v)))) + sig - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default=os.path.join(os.path.dirname(__file__), "..", "web"))
    ap.add_argument("--layers", required=True, help="directory of per-hex layer JSON files")
    ap.add_argument("--grid", required=True, help="grid.json giving each hex centre's lon/lat")
    args = ap.parse_args()

    web = os.path.abspath(args.web)
    world = json.load(open(os.path.join(web, "data", "world.json"), encoding="utf-8"))
    g = world["grid"]
    proj = load_projection(world)
    grid = Grid(g["radius"], g["cols"], g["rows"], proj)
    n = g["cols"] * g["rows"]

    gridfile = json.load(open(args.grid, encoding="utf-8"))
    hexes = gridfile["hexes"]
    print(f"layer grid: {len(hexes)} hexes; this site: {g['cols']}x{g['rows']} = {n} cells", file=sys.stderr)

    # hex id -> this site's cell
    cell_of = []
    per_cell = [0] * n
    for h in hexes:
        x, y = proj(h["lon"], h["lat"])
        c = grid.cell_at(x, y)
        cell_of.append(c)
        if c >= 0:
            per_cell[c] += 1
    land_cells = sum(1 for i in range(n) if world["owner"][i] >= 0)
    print(f"cells receiving >=1 layer hex: {sum(1 for k in per_cell if k)} "
          f"(land cells: {land_cells}); mean hexes/cell {sum(per_cell)/max(1,sum(1 for k in per_cell if k)):.2f}",
          file=sys.stderr)

    lenses = []
    for spec in SPECS:
        layer = json.load(open(os.path.join(args.layers, spec["layer"] + ".json"), encoding="utf-8"))
        field = layer["hex"].get(spec["field"])
        if field is None:
            print(f"  !! missing field {spec['layer']}.{spec['field']}", file=sys.stderr)
            continue
        pop = None
        if spec["agg"] == "pop":
            pop = json.load(open(os.path.join(args.layers, "population.json"), encoding="utf-8"))["hex"]["pop"]

        factor = spec.get("factor", 1.0)
        acc = [0.0] * n
        wsum = [0.0] * n
        for i, h in enumerate(hexes):
            c = cell_of[i]
            if c < 0:
                continue
            v = field[i]
            if v is None:
                continue
            w = 1.0
            if pop is not None:
                p = pop[i]
                w = max(1.0, p) if isinstance(p, (int, float)) else 1.0
            acc[c] += v * w
            wsum[c] += w

        values = [None] * n
        for c in range(n):
            if wsum[c] > 0:
                values[c] = round_sig(acc[c] / wsum[c] * factor)
        # nothing on foreign/water cells: the engine never paints them, but keep the contract tidy
        for c in range(n):
            if world["owner"][c] < 0:
                values[c] = None

        finite = sorted(v for v in values if v is not None)
        d0, d1 = pctile(finite, 0.02), pctile(finite, 0.98)
        if spec["scale"] == "log":
            positive = [v for v in finite if v > 0]
            d0 = max(d0 if d0 and d0 > 0 else pctile(positive, 0.02), min(positive) if positive else 1e-6)
        if d0 == d1:
            d1 = d0 * 1.01 if d0 else 1.0

        lenses.append({
            "id": spec["id"], "group": spec["group"], "name": spec["name"],
            "icon": spec["icon"], "emoji": spec["emoji"], "unit": spec["unit"],
            "format": spec["format"], "scale": spec["scale"], "ramp": spec["ramp"],
            "higher_is": spec["higher"], "source": "lens_layers",
            "description": spec["desc"], "values": values,
            "domain": [round_sig(d0), round_sig(d1)],
            "_srcField": spec["src"],
        })
        cov = sum(1 for v in values if v is not None)
        print(f"  {spec['id']:12s} cover {cov:5d}/{land_cells}  domain {lenses[-1]['domain']}", file=sys.stderr)

    out = {
        "vintage": "七普 2020；2023–2025 年统计公报；OSM / USGS / IBTrACS / GEM（详见各图层说明）",
        "groups": [{"id": i, "name": nm} for i, nm in GROUPS],
        "lenses": lenses,
    }
    path = os.path.join(web, "data", "lenses.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {path} ({os.path.getsize(path)/1e6:.2f} MB, {len(lenses)} lenses)", file=sys.stderr)


if __name__ == "__main__":
    main()
