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
> - `streaming-cn`: Mainland China streaming and entertainment services (NetEase Cloud Music, Bilibili, iQIYI, Youku, Tencent Video, Douyin, Kuaishou, Ximalaya, Kugou, Kuwo), intended for 回国-style routing
> - `microsoft`: Microsoft services (Microsoft 365/Office, Outlook, OneDrive, Xbox, Azure, Bing), intended for routing via US nodes

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

## Project Structure

```text
.
├── main.py                    # Rule generator
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
