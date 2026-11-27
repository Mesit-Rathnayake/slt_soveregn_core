import re
from pathlib import Path


class SLTPackageCatalog:
    """
    Structured SLTMobitel Package & Plan Catalog.
    Dynamically parses verified Markdown tables from `slt_customer_kb_catalog.md`
    and enables multi-parameter filtering by price, speed, category, and data policy.
    """

    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self.packages = self._load_packages()

    @staticmethod
    def _parse_price(val: str) -> float | None:
        if not val:
            return None
        m = re.search(r"Rs\.?\s*([0-9,]+(?:\.[0-9]+)?)", val, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
        m2 = re.search(r"([0-9,]+(?:\.[0-9]+)?)", val)
        if m2:
            return float(m2.group(1).replace(",", ""))
        return None

    @staticmethod
    def _parse_speed_mbps(val: str) -> int | None:
        if not val:
            return None
        m = re.search(r"(\d+)\s*(?:/\s*\d+)?\s*Mbps", val, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _load_packages(self) -> list[dict]:
        if not self.catalog_path.exists():
            return []
        text = self.catalog_path.read_text(encoding="utf-8")
        sections = re.split(r"\n(?=##\s+)", text)
        all_packages = []

        for sec in sections:
            lines = [l.strip() for l in sec.strip().splitlines() if l.strip()]
            if not lines:
                continue
            header = lines[0].lower()
            cat = "other"
            if "fibre" in header:
                cat = "fibre"
            elif "4g" in header or "lte" in header:
                cat = "lte"
            elif "peotv" in header:
                cat = "peotv"
            elif "add-on" in header or "addon" in header:
                cat = "addons"
            else:
                continue

            table_lines = [l for l in lines if l.startswith("|")]
            if len(table_lines) >= 3:
                raw_headers = [c.strip().lower() for c in table_lines[0].split("|") if c.strip()]
                price_idx = next((i for i, h in enumerate(raw_headers) if "price" in h or "rental" in h), 1)
                vol_idx = next(
                    (i for i, h in enumerate(raw_headers) if "volume" in h or "channel" in h or "benefit" in h or "data" in h),
                    2
                )
                speed_idx = next(
                    (i for i, h in enumerate(raw_headers) if "speed" in h or "validity" in h or "policy" in h),
                    3
                )
                notes_idx = next(
                    (i for i, h in enumerate(raw_headers) if "type" in h or "notes" in h or "details" in h or "validity" in h),
                    -1
                )

                for line in table_lines[2:]:
                    cols = [c.strip() for c in line.split("|") if c.strip()]
                    if not cols or len(cols) <= max(price_idx, 1):
                        continue
                    name = cols[0]
                    price_val = self._parse_price(cols[price_idx]) if price_idx < len(cols) else None
                    vol_val = cols[vol_idx] if vol_idx < len(cols) else ""
                    speed_val = cols[speed_idx] if speed_idx < len(cols) else ""
                    notes_val = cols[notes_idx] if (notes_idx != -1 and notes_idx < len(cols)) else ""

                    combined_txt = f"{name} {vol_val} {speed_val} {notes_val}".lower()
                    speed_mbps = self._parse_speed_mbps(speed_val) or self._parse_speed_mbps(vol_val)
                    is_unl = "unlimited" in combined_txt

                    all_packages.append({
                        "name": name,
                        "category": cat,
                        "price_rs": price_val,
                        "volume": vol_val,
                        "speed": speed_val,
                        "speed_mbps": speed_mbps,
                        "is_unlimited": is_unl,
                        "notes": notes_val
                    })

        return all_packages

    def filter_packages(
        self,
        category: str = "all",
        max_price: float | None = None,
        min_price: float | None = None,
        min_speed_mbps: int | None = None,
        is_unlimited: bool | None = None,
        search_term: str | None = None,
        limit: int = 6,
        sort_order: str = "asc"
    ) -> dict:
        results = []
        cat_lower = (category or "all").lower().strip()
        term_lower = (search_term or "").lower().strip()

        for p in self.packages:
            if cat_lower != "all" and p["category"] != cat_lower:
                continue
            if max_price is not None and p["price_rs"] is not None and p["price_rs"] > max_price:
                continue
            if min_price is not None and p["price_rs"] is not None and p["price_rs"] < min_price:
                continue
            if min_speed_mbps is not None and (p["speed_mbps"] is None or p["speed_mbps"] < min_speed_mbps):
                continue
            if is_unlimited is not None and p["is_unlimited"] != is_unlimited:
                continue
            if term_lower:
                combined_p = f"{p['name']} {p['volume']} {p['speed']} {p['notes']}".lower()
                if term_lower not in combined_p:
                    continue
            results.append(p)

        if str(sort_order or "asc").lower() == "desc":
            results.sort(key=lambda x: (x["price_rs"] is None, -(x["price_rs"] or 0)))
        else:
            results.sort(key=lambda x: (x["price_rs"] is None, x["price_rs"] or 0))

        bullets = []
        for r in results[:limit]:
            price_tag = f"Rs. {r['price_rs']:,.0f}" if r["price_rs"] is not None else "Custom"
            vol_tag = f" | {r['volume']}" if r["volume"] else ""
            speed_tag = f" | {r['speed']}" if r["speed"] and r["speed"] != r["volume"] else ""
            notes_tag = f" ({r['notes']})" if r["notes"] and r["notes"] not in (r["volume"], r["speed"]) else ""
            bullets.append(f"**{r['name']}:** {price_tag}{vol_tag}{speed_tag}{notes_tag}")

        criteria_parts = []
        if cat_lower != "all":
            criteria_parts.append(cat_lower.upper())
        if max_price is not None:
            criteria_parts.append(f"under Rs. {max_price:,.0f}")
        if min_price is not None:
            criteria_parts.append(f"above Rs. {min_price:,.0f}")
        if min_speed_mbps is not None:
            criteria_parts.append(f">= {min_speed_mbps} Mbps")
        if is_unlimited:
            criteria_parts.append("Unlimited")
        if term_lower:
            criteria_parts.append(f"matching '{term_lower}'")

        criteria_str = " ".join(criteria_parts) if criteria_parts else "available"
        headline = f"Found {len(results)} {criteria_str} package(s):"

        return {
            "count": len(results),
            "matched_packages": results[:limit],
            "headline": headline,
            "summary_markdown": "\n".join([f"- {b}" for b in bullets]),
            "bullets": bullets
        }
