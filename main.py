import json
import logging
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.request import urlopen

import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

BLOCK_DOMAIN_SUFFIX = (
    "miaozhen.com",
    "tqt.weibo.cn",
    "qzs.gdtimg.com",
    "adsmind.gdtimg.com",
    "gdt.qq.com",
    "mazu.m.qq.com",
    "e.kuaishou.cn",
    "e.kuaishou.com",
    "umeng.com",
    "umengcloud.com",
    "fapi.xdrun.com",
    "mix-mind.com",
    "in-neo.com",
    "rtbasia.com",
    "gridsum.com",
    "addnewer.com",
    "msmp.abchina.com.cn",
    "statics.adanxing.com",
    "promotion-partner.kuaishou.com",
    "qttunion.com",
    "1sapp.com",
    "shenshiads.com",
    "domob.cn",
    "aiclk.com",
    "guanggao-prod.cn-shanghai.log.aliyuncs.com",
)

DIRECT_DOMAIN = ("api.github.com",)

DIRECT_DOMAIN_SUFFIX = (
    "cn",
    "local",
    "steamserver.net",
    "steamcontent.com",
    "msftconnecttest.com",
    "msftncsi.com",
    "hotmail.com",
    "baozimh.com",
    "baozicdn.com",
)

# ═══════════════════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Upstream
# ═══════════════════════════════════════════════════════════════════════════════

DomainResult = tuple[
    list[str],  # domain
    list[str],  # domain_suffix
    list[str],  # domain_keyword
    list[str],  # domain_regex
]

GeoSiteRules = dict[str, DomainResult]

GEOSITE_TAGS = (
    "reject",
    "loc-!cn",
    "loc-cn",
)

GFWLIST_TAGS = ("gfw", "gfw-skip")


def parse_dlc_plain(url: str, tags: tuple[str, ...]) -> GeoSiteRules:
    """Extract flattened tags and supplement them with matching global attributes."""
    log.info("Downloading %s", url)
    with urlopen(url) as response:
        lists = yaml.safe_load(response).get("lists", [])

    remaining = set(tags)
    result: GeoSiteRules = {}
    attribute_targets = {
        attribute: tag
        for attribute, tag in (("cn", "geolocation-cn"), ("ads", "category-ads-all"))
        if tag in tags
    }
    attribute_rules: GeoSiteRules = {
        attribute: ([], [], [], []) for attribute in attribute_targets
    }
    rule_indexes = {"full": 0, "domain": 1, "keyword": 2, "regexp": 3}
    for item in lists:
        tag = item.get("name")
        selected = tag in remaining
        if not selected and not attribute_targets:
            continue

        values: DomainResult = ([], [], [], [])
        for raw_rule in item.get("rules", []):
            # Upstream serializes attributes as :@attr1,@attr2.
            rule, _, attributes = raw_rule.partition(":@")
            matching_attributes = attribute_targets.keys() & set(attributes.split(",@"))
            if not selected and not matching_attributes:
                continue
            rule_type, separator, value = rule.partition(":")
            if not separator or rule_type not in rule_indexes:
                raise ValueError(f"Unsupported DLC rule: {raw_rule!r}")
            index = rule_indexes[rule_type]
            if selected:
                values[index].append(value)
            for attribute in matching_attributes:
                attribute_rules[attribute][index].append(value)

        if selected:
            result[tag] = values
            remaining.remove(tag)
        if not remaining and not attribute_targets:
            break

    if remaining:
        raise ValueError(f"Missing DLC tags: {', '.join(sorted(remaining))}")
    for attribute, target in attribute_targets.items():
        for destination, additions in zip(result[target], attribute_rules[attribute]):
            destination[:] = dict.fromkeys(destination + additions)
    return result


def _gfwlist_host(rule: str) -> str:
    """Extract a host from an AutoProxy URL or domain-anchor rule."""
    if rule.startswith("||"):
        return re.split(r"[/:^|]", rule[2:], maxsplit=1)[0]

    parsed = urlsplit(rule.removeprefix("|"))
    return parsed.hostname or ""


def _append_gfwlist_host(
    host: str, domain: list[str], domain_suffix: list[str], *, suffix: bool
) -> None:
    host = host.lower().strip(".")
    if not host:
        raise ValueError("GFWList rule has no host")

    if "*" in host:
        # Domain-only formats cannot retain a wildcard label. Keep the stable
        # suffix after the final wildcard so all generated clients agree.
        host = host.rsplit("*", maxsplit=1)[1].lstrip(".")
        if not host:
            raise ValueError("GFWList wildcard rule has no domain suffix")
        suffix = True

    (domain_suffix if suffix else domain).append(host)


def _append_gfwlist_rule(rule: str, values: DomainResult) -> None:
    domain, domain_suffix, _, domain_regex = values
    if rule.startswith("/"):
        pattern = rule[1:-1] if rule.endswith("/") else rule[1:]
        # GFWList regexes match complete URLs. Generated GeoSite/sing-box
        # files match domains, so remove the anchored URL-scheme portion.
        pattern = pattern.removeprefix(r"^https?:\/\/")
        lookahead = re.fullmatch(r"\(\?=\.\*\?\(([^)]+)\)\)(\[[^]]+\])\+(.*)", pattern)
        if lookahead:
            alternatives, character_class, tail = lookahead.groups()
            pattern = f"^{character_class}*(?:{alternatives}){character_class}*{tail}"
        domain_regex.append(pattern)
        return
    if rule.startswith("||"):
        _append_gfwlist_host(_gfwlist_host(rule), domain, domain_suffix, suffix=True)
        return
    if rule.startswith(("|http://", "|https://")):
        _append_gfwlist_host(_gfwlist_host(rule), domain, domain_suffix, suffix=False)
        return
    if re.fullmatch(r"[A-Za-z0-9._-]+", rule):
        _append_gfwlist_host(rule, domain, domain_suffix, suffix=False)
        return
    raise ValueError(f"Unsupported GFWList rule: {rule!r}")


def parse_gfwlist_text(content: bytes) -> GeoSiteRules:
    """Convert the plaintext AutoProxy GFWList into domain-only rule sets."""
    try:
        text = content.decode()
    except UnicodeDecodeError as error:
        raise ValueError("Invalid UTF-8 GFWList") from error
    if not text.startswith("[AutoProxy "):
        raise ValueError("Invalid GFWList header")

    result: GeoSiteRules = {
        "gfw": ([], [], [], []),
        "gfw-skip": ([], [], [], []),
    }

    for raw_rule in text.splitlines():
        rule = raw_rule.strip()
        if not rule or rule.startswith(("!", "[")):
            continue
        tag = "gfw"
        if rule.startswith("@@"):
            tag = "gfw-skip"
            rule = rule[2:]
        _append_gfwlist_rule(rule, result[tag])

    for tag, (domain, domain_suffix, _, domain_regex) in result.items():
        log.info(
            "Parsed GFWList tag %s: %d domains, %d suffixes, %d regexes",
            tag,
            len(domain),
            len(domain_suffix),
            len(domain_regex),
        )
    return result


def parse_gfwlist(url: str) -> GeoSiteRules:
    """Download and parse the official plaintext GFWList."""
    log.info("Downloading %s", url)
    with urlopen(url) as response:
        return parse_gfwlist_text(response.read())


# ═══════════════════════════════════════════════════════════════════════════════
# Release — generate output files for all supported proxy platforms
# ═══════════════════════════════════════════════════════════════════════════════


def release(
    domain: list[str],
    domain_suffix: list[str],
    domain_keyword: list[str],
    domain_regex: list[str],
    tag: str,
    *,
    quanx_policy: str = "direct",
) -> DomainResult:
    """Generate output files (Surge, Clash, QuanX, sing-box) for *tag*."""
    log.info("Releasing tag: %s", tag)
    domain, domain_suffix = clean_domains(domain, domain_suffix)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(release_surge_file, tag, domain, domain_suffix),
            pool.submit(release_clash_file, tag, domain, domain_suffix),
            pool.submit(
                release_quanx_file,
                tag,
                domain,
                domain_suffix,
                domain_keyword,
                quanx_policy,
            ),
            pool.submit(
                release_singbox_file,
                tag,
                domain,
                domain_suffix,
                domain_regex,
                domain_keyword,
            ),
        ]
        for future in futures:
            future.result()

    return domain, domain_suffix, domain_keyword, domain_regex


def release_surge_file(tag: str, domain: list[str], domain_suffix: list[str]) -> None:
    filename = f"dist/{tag}.list"
    with open(filename, "w") as f:
        f.writelines(s + "\n" for s in domain)
        f.writelines("." + s + "\n" for s in domain_suffix)


def release_clash_file(tag: str, domain: list[str], domain_suffix: list[str]) -> None:
    filename = f"dist/{tag}.yaml"
    with open(filename, "w") as f:
        yaml.dump(
            {"payload": domain + ["." + s for s in domain_suffix]},
            f,
            default_flow_style=False,
            allow_unicode=True,
        )


def release_quanx_file(
    tag: str,
    domain: list[str],
    domain_suffix: list[str],
    domain_keyword: list[str],
    policy: str = "direct",
) -> None:
    filename = f"dist/{tag}.quanx"
    with open(filename, "w", buffering=65536) as f:
        f.writelines(f"host, {s}, {policy}\n" for s in domain)
        f.writelines(f"host-suffix, {s}, {policy}\n" for s in domain_suffix)
        f.writelines(f"host-keyword, {s}, {policy}\n" for s in domain_keyword)


def release_singbox_file(
    tag: str,
    domain: list[str],
    domain_suffix: list[str],
    domain_regex: list[str],
    domain_keyword: list[str],
) -> None:
    filename = f"tmp/{tag}.json"
    rule = {
        key: values
        for key, values in (
            ("domain", domain),
            ("domain_suffix", domain_suffix),
            ("domain_regex", domain_regex),
            ("domain_keyword", domain_keyword),
        )
        if values
    }

    with open(filename, "w") as f:
        json.dump({"version": 2, "rules": [rule]}, f, separators=(",", ":"))

    output = f"dist/{tag}.srs"
    log.info("Compiling sing-box file: %s", filename)
    subprocess.run(
        ["sing-box", "rule-set", "compile", "--output", output, filename],
        check=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# V2Ray GeoSite output
# ══════════════════════════════════════════════════════════════════════════════


def _protobuf_varint(value: int) -> bytes:
    """Encode a non-negative integer using the protobuf varint format."""
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _protobuf_field(field_number: int, wire_type: int, value: bytes) -> bytes:
    key = _protobuf_varint((field_number << 3) | wire_type)
    if wire_type == 2:
        return key + _protobuf_varint(len(value)) + value
    return key + value


def _encode_geosite_domain(domain_type: int, value: str) -> bytes:
    # v2ray routercommon.Domain: type = 1, value = 2.
    return _protobuf_field(1, 0, _protobuf_varint(domain_type)) + _protobuf_field(
        2, 2, value.encode()
    )


def _encode_geosite(tag: str, rules: DomainResult) -> bytes:
    # v2ray routercommon.GeoSite: country_code = 1, domain = 2.
    domain, domain_suffix, domain_keyword, domain_regex = rules
    fields = [_protobuf_field(1, 2, tag.upper().encode())]
    typed_rules = (
        (3, domain),  # Full
        (2, domain_suffix),  # RootDomain
        (0, domain_keyword),  # Plain
        (1, domain_regex),  # Regex
    )
    for domain_type, values in typed_rules:
        for value in dict.fromkeys(values):
            encoded = _encode_geosite_domain(domain_type, value)
            fields.append(_protobuf_field(2, 2, encoded))
    return b"".join(fields)


def write_geosite_file(filename: str, rules_by_tag: GeoSiteRules) -> None:
    """Write a V2Ray-compatible GeoSiteList protobuf file."""
    # routercommon.GeoSiteList has one repeated GeoSite field named entry (1).
    with open(filename, "wb") as f:
        f.writelines(
            _protobuf_field(1, 2, _encode_geosite(tag, rules_by_tag[tag]))
            for tag in sorted(rules_by_tag)
        )
    log.info("Wrote GeoSite file: %s (%d tags)", filename, len(rules_by_tag))


def release_geosite_files(
    rules_by_tag: GeoSiteRules, gfwlist_rules: GeoSiteRules
) -> None:
    """Generate the general, CN-only, and GFWList GeoSite databases."""
    complete_rules = {tag: rules_by_tag[tag] for tag in GEOSITE_TAGS}
    write_geosite_file("dist/geosite.dat", complete_rules)
    write_geosite_file("dist/geosite-cn.dat", {"loc-cn": rules_by_tag["loc-cn"]})
    write_geosite_file(
        "dist/geosite-gfw.dat",
        {tag: gfwlist_rules[tag] for tag in GFWLIST_TAGS},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════════


def clean_domains(
    domain: list[str], domain_suffix: list[str]
) -> tuple[list[str], list[str]]:
    """Remove domains whose parent is already covered by a domain suffix."""
    log.info(
        "Cleaning domains: %d domains, %d suffixes", len(domain), len(domain_suffix)
    )

    unique_suffixes = dict.fromkeys(domain_suffix)

    def covered(value: str) -> bool:
        while (dot := value.find(".")) >= 0:
            value = value[dot + 1 :]
            if value in unique_suffixes:
                return True
        return False

    return (
        [value for value in dict.fromkeys(domain) if not covered(value)],
        [value for value in unique_suffixes if not covered(value)],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    shutil.rmtree("dist", ignore_errors=True)
    os.makedirs("dist")
    os.makedirs("tmp", exist_ok=True)

    try:
        _run()
    finally:
        shutil.rmtree("tmp", ignore_errors=True)


def _run() -> None:
    rule_tags = (
        ("category-ads-all", "reject", (), BLOCK_DOMAIN_SUFFIX),
        ("geolocation-!cn", "loc-!cn", (), ()),
        ("geolocation-cn", "loc-cn", DIRECT_DOMAIN, DIRECT_DOMAIN_SUFFIX),
    )
    upstream_rules = parse_dlc_plain(
        "https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat_plain.yml",
        tuple(rule[0] for rule in rule_tags),
    )

    geosite_rules: GeoSiteRules = {}
    for upstream_tag, output_tag, extra_domains, extra_suffixes in rule_tags:
        domain, domain_suffix, domain_keyword, domain_regex = upstream_rules[
            upstream_tag
        ]
        domain.extend(extra_domains)
        domain_suffix.extend(extra_suffixes)
        geosite_rules[output_tag] = release(
            domain, domain_suffix, domain_keyword, domain_regex, output_tag
        )

    gfwlist_rules = parse_gfwlist(
        "https://raw.githubusercontent.com/gfwlist/gfwlist/master/list.txt"
    )
    gfwlist_rules["gfw-skip"][0].extend(DIRECT_DOMAIN)
    gfwlist_rules["gfw-skip"][1].extend(DIRECT_DOMAIN_SUFFIX)
    for tag, quanx_policy in (("gfw", "proxy"), ("gfw-skip", "direct")):
        gfwlist_rules[tag] = release(
            *gfwlist_rules[tag], tag, quanx_policy=quanx_policy
        )

    release_geosite_files(geosite_rules, gfwlist_rules)


if __name__ == "__main__":
    main()
