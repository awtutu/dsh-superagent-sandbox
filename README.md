# dsh-superagent-sandbox
Sandbox for dsh-superagent setup

## KB 断链检查工具

`tools/check_kb_links.py` 扫描 Markdown 文件中的相对链接（含图片、引用式定义和 HTML 的 `href`/`src` 属性），报告目标文件不存在的链接。只依赖 Python 3.8+ 标准库。

```bash
python3 tools/check_kb_links.py            # 扫描当前目录
python3 tools/check_kb_links.py kb docs    # 扫描指定目录（或单个 .md 文件）
```

输出示例：

```text
kb/chapter/notes.md:12: broken link '../missing.md' -> kb/missing.md
FAILED: 1 broken link(s) in 3 Markdown file(s)
```

退出码：

| 退出码 | 含义 |
| --- | --- |
| 0 | 所有相对链接均存在 |
| 1 | 存在断链，缺失路径已打印 |
| 2 | 参数错误（例如目录不存在） |

说明：

- 忽略带协议的链接（`https:`、`mailto:` 等）、`//host/...` 协议相对链接、以 `/` 开头的站内根路径，以及纯 `#锚点` 链接。
- 代码块（``` 或 ~~~）中的链接不会被检查。
- 链接中的 `#fragment` 与 `?query` 会被去掉，百分号编码会先解码再比较。

### 测试

测试在临时目录中构造 Markdown 目录树，可重复运行：

```bash
python3 -m unittest discover -s tests -v
# 或（若已安装 pytest）
python3 -m pytest tests
```
