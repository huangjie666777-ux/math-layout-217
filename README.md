# mathsvg — 数学公式单行 SVG 排版后端

将结构化的公式 JSON 树排版为单行、自包含的 SVG。字形轮廓、前进宽度、
斜体修正与所有排版参数均取自 `fonts/STIXTwoMath-Regular.otf` 的实际
字形与 OpenType MATH 表，不做任何等宽估算。

## 运行

```sh
.venv/bin/python -m uvicorn mathsvg.service:app --port 8317
```

自测（无需启动服务）：

```sh
.venv/bin/python selftest.py
```

## HTTP 接口

`POST /typeset`，请求体：

```json
{"size": 32, "formula": {"type": "text", "text": "x+1"}}
```

- `size`：字号（有限正数，上限 1000），即 0 级字号的 em 大小，
  也是所有返回尺寸的单位。
- 成功返回 `{"svg", "width", "height", "baseline"}`：`width`/`height`
  为 SVG 画布尺寸，`baseline` 为基线距画布顶部的距离，三者同单位。
- 非法输入（未知节点、缺子项、字体未覆盖的字符、非有限或非正字号、
  过深/过大的树）返回 400 与 `{"detail": ...}`，不交付半成品。

示例（嵌套：上下标 + 根号 + 分式 + 括号）：

```sh
curl -s -X POST localhost:8317/typeset \
  -H "Content-Type: application/json" -d '{
  "size": 32,
  "formula": {"type": "row", "children": [
    {"type": "script", "base": {"type": "text", "text": "x"},
     "sup": {"type": "text", "text": "2"},
     "sub": {"type": "text", "text": "n"}},
    {"type": "text", "text": "="},
    {"type": "sqrt", "radicand": {"type": "frac",
      "numerator": {"type": "parens", "child": {"type": "row", "children": [
        {"type": "script", "base": {"type": "text", "text": "a"},
         "sup": {"type": "text", "text": "2"}},
        {"type": "text", "text": "+b"}]}},
      "denominator": {"type": "text", "text": "2c"}}}
  ]}}'
```

## 节点格式

所有节点都是含 `type` 字段的对象，可任意组合嵌套：

| type     | 字段                            | 说明                 |
|----------|---------------------------------|----------------------|
| `text`   | `text`                          | 纯文本（逐字映射字形）|
| `row`    | `children`（非空数组）          | 横向序列，基线对齐    |
| `frac`   | `numerator`, `denominator`      | 分式，横线居数学轴    |
| `script` | `base`，`sup` 和/或 `sub`       | 上下标，可单独或同现  |
| `sqrt`   | `radicand`                      | 平方根                |
| `parens` | `child`                         | 圆括号包围            |

## 排版规则要点

- 横排按基线对齐；分式横线置于数学轴，分子/分母与横线保留
  MATH 表规定的最小间距。
- 上下标按 `ScriptPercentScaleDown`/`ScriptScriptPercentScaleDown` 逐级
  缩小；同现时保证 `SubSuperscriptGapMin` 间隔；上标计入基字的斜体修正。
- 根号横线覆盖被开方内容；括号覆盖内容的上下范围并关于数学轴居中。
- 超高内容先选 MATH 伸展变体（如 `parenleft.s1`…），再高则由连接部件
  （上钩/下钩/延伸件）按连接长度搭接拼装，绝不纵向拉伸完整字形。
- 嵌套后外层尺寸重新计算；SVG 画布取布局盒与真实墨迹边界的并集，
  字形墨迹、横线与伸展部件均不被裁切。
- SVG 只含 `<path>`/`<rect>`，不依赖字体文件、外链、脚本或
  `foreignObject`；相同输入产生相同输出，且不修改输入树。

## 代码结构

- `mathsvg/model.py` — JSON 树校验，构建不可变节点（深度/节点数限制）。
- `mathsvg/font.py` — 字体读取：轮廓路径、墨迹边界、前进宽度、斜体修正、
  MATH 常量、竖向变体选择与部件拼装。
- `mathsvg/layout.py` — 递归布局，产出相对基线定位的绘制项。
- `mathsvg/render.py` — 绘制项到自包含 SVG，计算画布与基线。
- `mathsvg/service.py` — FastAPI 交付层（`POST /typeset`、`GET /health`）。
- `selftest.py` — 自测：排版正确性、确定性、输入不可变、拒绝路径。

## 范围

仅处理字体覆盖的字符；不解析 LaTeX，不做换行，不做字距调整（kerning）
与运算符间距等完整数学排版规则。

