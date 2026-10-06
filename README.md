# 数学公式单行排版后端

将结构化公式树排版为单行、自包含的 SVG（仅含字形轮廓路径与横线矩形，
不依赖字体文件、外链、脚本或 foreignObject）。使用
fonts/STIXTwoMath-Regular.otf 的真实字形轮廓、前进宽度、斜体修正与
OpenType MATH 表度量，不做等宽估算。

## 运行

    .venv/bin/uvicorn mathrender.app:app --port 8123

## 接口

POST /render

    {
      "font_size": 48,
      "formula": { "type": "...", ... }
    }

返回 200:

    { "svg": "<svg ...>", "width": 196.03, "height": 121.92, "baseline": 82.56 }

width / height / baseline（基线距 SVG 顶部的距离）与 font_size 同一单位。
校验失败返回 422 与 {"detail": "..."}，不交付半成品。

## 节点格式

- {"type":"text","value":"x+1"}        纯文本（仅字体覆盖的字符）
- {"type":"row","children":[...]}      横向序列，基线对齐
- {"type":"frac","num":N,"den":N}      分式，横线居中于数学轴
- {"type":"scripts","base":N,"sup":N?,"sub":N?}  上标/下标，可单独或同时出现
- {"type":"sqrt","radicand":N}         平方根，横线覆盖被开方内容
- {"type":"paren","child":N,"left":"(","right":")"}  括号包围；
  left/right 可选 ( ) [ ] { } |，默认圆括号

节点可任意组合嵌套。上下标随层级按 MATH 表 ScriptPercentScaleDown /
ScriptScriptPercentScaleDown 缩小，同现时保持最小间距并计入基字斜体修正。
括号与根号高度超出普通符号时先选伸展变体（.s1...sN），再按 GlyphAssembly
连接信息拼装伸展部件，绝不纵向拉伸完整字形。嵌套后外层尺寸自动重算，
viewBox 按全部墨迹与横线的实际包围盒计算，不发生裁切。

## 示例

    curl -X POST localhost:8123/render -H 'Content-Type: application/json' -d '{
      "font_size": 48,
      "formula": {"type":"paren","child":{"type":"row","children":[
        {"type":"scripts","base":{"type":"text","value":"x"},
                           "sup":{"type":"text","value":"2"}},
        {"type":"text","value":"+"},
        {"type":"frac","num":{"type":"text","value":"1"},
          "den":{"type":"sqrt","radicand":
            {"type":"scripts","base":{"type":"text","value":"y"},
                              "sub":{"type":"text","value":"i"}}}}
      ]}}}'

## 自测

    .venv/bin/python -m mathrender.selftest

## 代码结构

- mathrender/font.py    字体读取：度量、MATH 常量、轮廓路径、伸展变体与拼装
- mathrender/nodes.py   公式树校验（深度/节点数/字号/字符覆盖限制）
- mathrender/layout.py  递归布局：行、分式、上下标、根号、括号
- mathrender/svg.py     SVG 绘制与包围盒/基线计算
- mathrender/app.py     FastAPI HTTP 交付
- mathrender/selftest.py 自测

## 范围与限制

- 仅处理字体覆盖的文字；不解析 LaTeX，不做换行，输出恒为单行。
- 缺字、未知节点、缺子项、非有限或非正字号、过深（>64 层）或过大
  （>5000 节点）的输入一律拒绝。
- 排版结果确定：同一输入产生完全相同的 SVG；输入树不被修改。
