# 数据文件

`web/data/` 里的每个 JSON 都是一个静态文件，由浏览器直接读取。坐标统一是**地图公里**：Albers 等积圆锥投影
（标准纬线 25°N / 47°N，中央经线 105°E），原点在左上角，y 轴向下。逐格数组的长度都是 `grid.cols × grid.rows`，
下标为 `row * cols + col`（尖顶六边形，odd-r 排布）。`null` 一律表示"没有数据"，从不拿 `0` 冒充。

| 文件 | 内容 |
|---|---|
| `world.json` | 网格与地形：`grid`、投影参数、`owner`（省份索引，-1 水域 / -2 境外陆地）、`county`、`elev`、`elev_max`、`water`、`relief`、`cover`、`pct`、`states`、`counties`、`rivers`、`lakes`、`inset`（南海诸岛附图）、`notice` |
| `cities.json` | 344 面城市旗标，按人口降序：`id`（6 位行政区代码）、`name`、`full`、`kind`、`states`、`x`/`y`/`cell`、`population`、`yields`（food / production / gold / science / culture）、`gdp`、`gdp_by_industry`、`ranks`、`footprint` |
| `states.json` | 34 个省级行政区：代码、简称、名称、人口、产出、GDP、排名 |
| `nation.json` | 全国合计与产出定义：`yields[]` 里每一项的中文名、颜色、单位、口径说明与覆盖率 |
| `lenses.json` | 27 个透镜图层：分组、名称、单位、色带、`values`（逐格数组）、`domain`、说明与来源 |
| `resources.json` | 资源站点：类型定义与条目（`x`/`y`/`cell`/`value`）、按类型的全国合计 |
| `infrastructure.json` | 铁路与高速（折线段）、机场、港口 |
| `wonders.json` | 奇观：入选规则、条目、未能定位的名单 |
| `sources.json` | 数据来源清单：发布者、许可、网址、年份、用于哪些文件 |
| `pinyin.json` | 城市与省份的拼音全拼与首字母，供搜索使用 |

## world.json 的格子语义

* `owner[i] >= 0` 是中国陆地，值是 `states` 的索引；`-1` 是水域，`-2` 是境外陆地。
* `elev` 是格内陆地样本的平均海拔（米），`elev_max` 是最高样本，用来画雪线。
* `water`：0 陆地、1 远海、2 近岸、3 湖泊。
* `relief`：0 平原、1 丘陵、2 山地、3 高峰。
* `cover` 是土地覆盖类型编号，名称与颜色在 `tables.cover` 里。

## 产出的单位

`food`、`production`、`gold`、`science`、`culture` 全部以**人民币元**计（`nation.json` 的 `currency` 为 `CNY`）：
粮食 = 第一产业增加值，生产力 = 第二产业增加值，金币 = GDP，科研 = R&D 经费内部支出，文化 = 文化产业增加值。
全国总量取自国家统计局；科研与文化按各市的产出指数分摊，`nation.json` 的说明里写明了这一点。
