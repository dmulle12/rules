>   Automatically generate and publish domain rules for Clash, Surge, Quantumult X, sing-box, and V2Ray GeoSite.

> ## Rules

> The rule data comes from
> [`v2fly/domain-list-community`](https://github.com/v2fly/domain-list-community)'s
> published `dlc.dat_plain.yml`, together with the plain-text rules from the official
> [`gfwlist/gfwlist`](https://github.com/gfwlist/gfwlist). The following tags are generated:

> - `reject`: Combines `category-ads-all`, rules with the `@ads` attribute from all lists, and manually maintained blocking rules
> - `gfw`: Proxy domains from the official GFWList
> - `gfw-skip`: GFWList whitelist entries and additional direct-connection domains
> - `loc-!cn`: Domains outside mainland China
> - `loc-cn`: Direct-connection rules for mainland China, combining `geolocation-cn`, rules with the `@cn` attribute from all lists, and manually maintained direct-connection rules
> - `streaming-cn`: Mainland China streaming and entertainment services (NetEase Cloud Music, Bilibili, iQIYI, Youku, Tencent Video, Kuaishou, Ximalaya, Kugou, Kuwo), intended for 回国-style routing (Douyin now ships as the dedicated `douyin` tag)
> - `douyin`: Douyin (Chinese TikTok) domains plus the shared ByteDance SDK domain (`snssdk.com`), intended for routing via a dedicated 回国 node/policy
> - `microsoft`: Microsoft services (Microsoft 365/Office, Outlook, OneDrive, Xbox, Azure, Bing) plus US school domains (Joliet Junior College: jjc.edu, Lane Community College: lanecc.edu), intended for routing via US nodes
> - `ads`: Ad/tracker blocklist converted from hagezi Multi PRO (`wildcard/pro.txt`, ~230k domains, recommended)
> - `ads-mini`: Lightweight ad/tracker blocklist converted from hagezi Multi PRO mini (`wildcard/pro.mini.txt`, ~60k domains)

> The `ads` / `ads-mini` rule data comes from
> [`hagezi/dns-blocklists`](https://github.com/hagezi/dns-blocklists), which is
> licensed under
> [GPL-3.0](https://github.com/hagezi/dns-blocklists/blob/main/LICENSE). The
> lists are converted here into proxy-tool formats; the original lists remain
> available at the upstream repository.

> DNS/domain-level blocking stops third-party ads and trackers. It cannot block
> in-feed ads served from the same first-party domain as the content itself
> (e.g. Facebook/TikTok feed ads) — blocking those domains would break the app.

> The upstream `domain-list-community` file already includes rule expansion, attribute filtering, and deduplication.

> URLs and wildcard rules in the GFWList are converted into domain rules, while whitelist exceptions are written separately to `gfw-skip`.

> This project extracts, supplements, and converts the rules into formats supported by various clients.

> `@cn` and `@ads` are matched by their complete attribute names. Other attributes such as `@!cn` and `@!ads` are not included. Rules are deduplicated after merging. The `@cn` attribute does not guarantee that a server is located inside mainland China. Rules containing both `@cn` and `@ads` are included in both corresponding tags.

## Releases

> GitHub Actions builds the rules once a day and automatically builds them whenever `main` is updated. Build artifacts are published to the `rel` branch; that branch is rebuilt on every release and retains only the latest results.

| Path              | Format                                             |
| ----------------- | -------------------------------------------------- |
| `<tag>.yaml`      | Clash Rule Provider                                |
| `<tag>.list`      | Surge Domain Set                                   |
| `<tag>.quanx`     | Quantumult X Filter                                |
| `<tag>.srs`       | sing-box Binary Rule Set                           |
| `chnroutes.mmdb`  | MaxMind-format China IP database for Surge `geoip-maxmind-url` |
| `geosite.dat`     | V2Ray GeoSite containing `reject`, `loc-!cn`, and `loc-cn` |
| `geosite-cn.dat`  | V2Ray GeoSite containing `loc-cn`                 |
| `geosite-gfw.dat` | V2Ray GeoSite containing `gfw` and `gfw-skip`     |
| `ext/*.quanx`     | Quantumult X Rewrite Rules                         |
| `ext/*.sgmodule`  | Surge Modules                                      |

> Download URL format:

```text
https://github.com/dmulle12/rules/raw/rel/<file>
```

> Examples:

```text
https://github.com/dmulle12/rules/raw/rel/loc-cn.srs
https://github.com/dmulle12/rules/raw/rel/ext/bili.quanx
https://github.com/dmulle12/rules/raw/rel/ext/bili.sgmodule
```

> Surge GEOIP database (updated daily from
> [`Loyalsoldier/geoip`](https://github.com/Loyalsoldier/geoip)):

```ini
[General]
geoip-maxmind-url = https://github.com/dmulle12/rules/raw/rel/chnroutes.mmdb
```

## Project Structure

```text
.
├── main.py                    # Rule generator
├── tools/mmdb/                # chnroutes.mmdb builder (Go, MaxMind format)
├── source/                    # Manually maintained rewrite rules and modules
├── js/                        # JavaScript scripts
├── example/                   # Client configuration examples
├── tests/                     # Rule parsing tests
├── .github/workflows/build.yml
├── pyproject.toml
└── uv.lock
```

## Local Build

> Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and
> [sing-box](https://sing-box.sagernet.org/).

```bash
uv sync
uv run python main.py
```

> Build artifacts are generated in `dist/`.
