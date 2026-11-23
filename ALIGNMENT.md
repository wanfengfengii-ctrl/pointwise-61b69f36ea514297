# 判片复核的参考板对齐

白班用中心票指定两站共用的参考板，以及本站哪一次读数获准作为参考。夜班凭中心实际收存的两份站件，签出共同刻度下生产测次合池 AUC 的两端。普通双模型比较仍可照常办理。

## 站件交班

沿用 `review` 的 `open_source`、`open_archive`、`admit_board` 和 `record_pair`。新增下列调用。

```python
freeze_alignment(source, station, revision, model, anchors) -> str
accept_alignment(archive, payload, declared_source) -> dict
```

`revision` 是指定站的 V1 整数评分修订号。`model` 是该站有序模型对中的一个名称。`anchors` 是至少含一项的映射，键为中心票号，值为本站获准测次号。每个测次必须在指定快照中归属所标的那张票，采用该快照中实际可见的版本。未知评分修订抛 `MissingItem`，非法模型、参考选择或调用参数抛 `InvalidInput`。

冻结返回可直接交付的 JSON 文本。等价冻结申请返回同一个件号及正文，后续勘误也可凭旧边界重取。一个修订可用于不同参考选择。选中任何一张参考板后，它在本站的全部测次均退出生产计量，包括非获准读数和任意标签的读数。

V2 站件正文示例

```json
{
  "version": 2,
  "package_id": "east-alignment-1",
  "source": {"origin": "east-ledger", "station": "East", "revision": "9"},
  "model": "Line-A",
  "levels": [[0, 0], [2, 0]],
  "anchors": {"R": {"level": 0, "reading_revision": "8"}}
}
```

- `levels` 按本站所选模型原分从低到高列出生产测次或获准参考测次所在的全部等级。同一原分共用一个等级。数组下标从零起，各项为 `[正例重数, 负例重数]`，重数是非负整数。仅被参考锚引用的无生产计数等级可写为 `[0,0]`。
- `anchors` 按参考票号给出等级和该次读数的可见版本修订号。不同参考票可以共用一个等级，仍须保留各自的读数版本。站内测次号留站。`source.revision` 和 `reading_revision` 为正整数的十进制字符串，读数版本不得晚于冻结边界。站件按以上字段交接，名称和件号沿用 V1 的标识约定。
- `declared_source` 沿用 `EvidenceSource(origin, station, revision)`，三项须与正文完全匹配。中心独立核对声明和正文结构，成功后返回已收存站件的字典。选择和出签使用其 `package_id`。V2 实收绑定由 `source`、`model` 和完整的参考票到读数版本的映射共同确定。JSON 空白及对象键序不影响等价。绑定和正文等价的重交沿用首次实收件号，即使交来另一件号。占用的 V2 件号与异文冲突，同绑定异文也冲突。坏件、错源及冲突均抛 `InvalidEvidence`，无新增实收。站件格式按 V1 的严格 JSON 字段约定检查。

## 中心签发与领取

```python
issue_alignment(archive, package_ids) -> dict
read_alignment(archive, report_id, *, as_json=False) -> dict | str
```

`package_ids` 提供两个实际实收的 V2 件号，站名互异，所选模型名相同且参考票集合相同。两类入口各按本版本的实收目录解析号码。重复选件、未知件、混入旧件、错站或错配抛 `InvalidSelection`。

共同刻度给两站每个等级各赋一个有理数。各站的刻度按等级严格递增，同一等级共用值，同一参考票在两个站件中的等级取相同值。不同站的等级在满足这些条件时可以同值。用同一个共同刻度比较全部生产正负对，含站内及跨站。正分较高、相等、较低分别计 1、1/2、0，按正负等级重数之积累计，再除以全部正负对数。各端点分别提供一份达到该值的完整刻度，供持有两份实收证据的人员重算。多份达界刻度任选。

无相容刻度返回 `{"status":"incompatible"}`。存在相容刻度但合池缺少任一生产标签时返回 `{"status":"insufficient"}`。这两种返回均无新报告或回执。成功返回以下形状的定稿。

```json
{
  "status": "issued",
  "report_id": 1,
  "model": "Line-A",
  "min": {"auc": "1", "scale": {"East": ["0", "1"], "West": ["0"]}},
  "max": {"auc": "1", "scale": {"East": ["0", "1"], "West": ["0"]}},
  "sources": [
    {"package_id": "east-alignment-1", "origin": "east-ledger", "station": "East", "revision": "9"},
    {"package_id": "west-alignment-1", "origin": "west-ledger", "station": "West", "revision": "5"}
  ],
  "receipt": {"report_id": 1, "receipt_id": "receipt-1"}
}
```

`scale` 按站名给出与实收件 `levels` 等长且同序的数组。刻度和 AUC 均用约分的有理数字符串，整数可直接写成整数字符串。`sources` 按站名排序，保存指定的实际实收身份及冻结出处。报告、出处与其唯一回执一并持久提交。报告提交失败抛 `PublicationFailed`，保持原有定稿与实收件，可重新申请签发。

`read_alignment` 按 V2 报告号返回签存时的字典，`as_json=True` 导出同一内容的确定性 JSON 文本。未知合法报告号抛 `MissingItem`，报告号沿用 V1 的正整数规则。源库关闭、评分勘误和归档重开后均可领取原定稿。

## 交班样例与运行

`samples/reference-alignment.json` 的每个 `cases` 条目来自一套独立账。`measurements` 以站名为键，每行为 `[票号, 测次号, 标签, 第一模型分, 第二模型分]`。可按 `film-` 加票号生成实体名，为每条测次先登记送测资格。每站按列出的行序接纳，以本站最后一个返回的评分修订为冻结边界。`requests` 指定两站获准映射。`expected.auc` 依次为下界和上界，`production_counts` 为从双方站件核对的合池正、负例重数。

`reference-choice` 中西站生产负例与获准参考同级。换东站获准读数改变生产正例相对共同参考的方向。`exclusive-wins` 的每个站内正例都输给本站负例。两个跨站正例分别可胜，无法在同一共同刻度同时胜。`shared-tied-grade` 的两张参考票都把同一对等级固定在同一个值。`inconsistent-anchor-tie` 则要求同一个值同时匹配东站两个严格有序的等级。

交付时接通现有 `.pointwise-runtime.json`。保留 v1 清单结构及 CLI 类型，`setup` 为命令参数数组的列表，`verify` 和 `demo` 各为一条命令的参数数组。`verify` 继续执行 `python3 -B check_project.py` 的完整原回归，并实际核对参考对齐业务，核验失败时退出非零。`demo` 继续展示旧比较，并展示关源后两种参考选择的签发、归档重开后的原号领取和导出。
