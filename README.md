# rules

每天自动构建的代理分流规则集，Surge / Clash / Quantumult X / sing-box / V2Ray 全格式开箱即用。

[![Build Rules](https://github.com/dmulle12/rules/actions/workflows/build.yml/badge.svg)](https://github.com/dmulle12/rules/actions/workflows/build.yml)
[![上游规则源监控](https://github.com/dmulle12/rules/actions/workflows/upstream-monitor.yml/badge.svg)](https://github.com/dmulle12/rules/actions/workflows/upstream-monitor.yml)

## 30 秒上手

每天自动构建，订阅一次就行，链接永久有效。把 `streaming-cn` 换成下表任意 tag 即可：

**Surge**（RULE-SET / DOMAIN-SET）

```text
https://github.com/dmulle12/rules/raw/rel/streaming-cn.list
```

**Clash**（Rule Provider）

```yaml
rule-providers:
  streaming-cn:
    type: http
    behavior: domain
    url: https://github.com/dmulle12/rules/raw/rel/streaming-cn.yaml
    path: ./ruleset/streaming-cn.yaml
    interval: 86400
```

**Quantumult X**（Filter）

```text
https://github.com/dmulle12/rules/raw/rel/streaming-cn.quanx
```

**sing-box**（Rule Set）

```text
https://github.com/dmulle12/rules/raw/rel/streaming-cn.srs
```

## 规则 tag 一览

| Tag | 内容 | 典型用途 |
|-----|------|----------|
| `streaming-cn` | 大陆流媒体：网易云、 B 站、爱奇艺、优酷、腾讯视频、抖音、快手、喜马拉雅、酷狗、酷我 | 回国节点分流 |
| `douyin` | 抖音域名 + ByteDance 公共 SDK 域名（`snssdk.com`） | 抖音走独立节点 |
| `loc-cn` | 大陆直连域名（`geolocation-cn` + 全量 `@cn` 属性规则 + 手工补充） | 直连 / 回国 |
| `microsoft` | 微软全家桶（M365 / Outlook / OneDrive / Xbox / Azure / Bing）+ 美国学校域名 | 美国节点 |
| `reject` | 去广告（含 `@ads` 属性规则 + 手工维护） | 全客户端 |
| `gfw` / `gfw-skip` | GFWList 需代理域名 / 白名单直连域名 | 代理分流 |
| `loc-!cn` | 非大陆域名 | 海外直连分流 |

每种 tag 提供 4 种格式：`.yaml`（Clash）、`.list`（Surge）、`.quanx`（Quantumult X）、`.srs`（sing-box）。
另有 V2Ray `geosite.dat` 系列与 Surge 专用中国 IP 库 `chnroutes.mmdb`（配合 `GEOIP,CN` 使用）：

```ini
[General]
geoip-maxmind-url = https://github.com/dmulle12/rules/raw/rel/chnroutes.mmdb
```

`source/` 下还有自维护的去广告 Rewrite（`ext/*.quanx`）与 Surge 模块（`ext/*.sgmodule`），如 B 站去广告。

## 自动构建

- GitHub Actions 每天构建一次，`main` 分支有更新时也会触发，产物发布到 `rel` 分支（只保留最新版）。
- 上游数据源（`v2fly/domain-list-community` 各分类）每天做指纹监控，变化自动开 Issue 提醒跟进。

## 数据来源（致谢）

- [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community)（MIT）—— 规则数据源
- [gfwlist/gfwlist](https://github.com/gfwlist/gfwlist)（LGPL-2.1）—— GFWList 数据源
- [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip)（CC-BY-SA-4.0）—— 中国 IP 数据

## 本地构建

需要 Python 3.12、[uv](https://docs.astral.sh/uv/) 与 [sing-box](https://sing-box.sagernet.org/)：

```bash
uv sync
uv run python main.py
```

产物生成在 `dist/`。

