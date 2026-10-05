"""Extract facts only from recognized official schemas, binding them to snapshot checksums."""
import re
from decimal import Decimal
from html.parser import HTMLParser

from .benchmarks import TableParser
from .common import BRONZE, RES, read_json, write_json


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def dollars(cell, *, discounted=False):
    if cell == "Free":
        return "0"
    matches = re.findall(r"\$(\d+(?:\.\d+)?)", cell)
    if len(matches) == 1:
        return matches[0]
    if discounted and len(matches) == 2:
        return matches[-1]
    return None


def extract_official(manifest):
    facts, warnings = [], []
    for source in manifest.get("documents", []):
        if source.get("id") not in {"openai-sol", "openai-astra", "anthropic-pricing", "zai-pricing", "minimax-pricing"}:
            continue
        html = (BRONZE / source["file"]).read_text(encoding="utf-8")
        text_parser = TextParser()
        text_parser.feed(html)
        text = " ".join(" ".join(text_parser.parts).split())
        parser = TableParser()
        parser.feed(html)
        before = len(facts)

        def emit(model_id, name, provider, pricing, conditions, attributes=None, tier="standard"):
            facts.append({"model_id": model_id, "name": name, "provider": provider,
                          "pricing": {k: v for k, v in pricing.items() if v is not None}, "facts": attributes or {},
                          "conditions": conditions, "tier": tier, "source_url": source["url"],
                          "source_sha256": source["sha256"], "extraction": "recognized official schema; no inferred release date"})

        if source["id"] in {"openai-sol", "openai-astra"}:
            match = re.search(r"Text tokens Per 1M tokens Input \$(\d+(?:\.\d+)?) Cached input \$(\d+(?:\.\d+)?)(?: Cache writes \$(\d+(?:\.\d+)?))? Output \$(\d+(?:\.\d+)?)", text)
            limits = re.search(r"([\d,]+) context window ([\d,]+) max output tokens", text)
            if match and limits:
                name = "GPT-5.6 Sol" if source["id"] == "openai-sol" else "GPT-6 Astra"
                slug = "openai/gpt-5.6-sol" if source["id"] == "openai-sol" else "openai/gpt-6-astra"
                price = dict(zip(["prompt", "input_cache_read", "input_cache_write", "completion"], match.groups()))
                attrs = {"contextLength": int(limits[1].replace(",", "")), "maxOutputTokens": int(limits[2].replace(",", ""))}
                if source["id"] == "openai-sol" and "complex professional work" in text:
                    attrs["description"] = "Provider describes a flagship for complex professional work."
                if source["id"] == "openai-astra" and "complex reasoning" in text and "document creation" in text:
                    attrs["description"] = "Provider describes capabilities in reasoning, coding, computer use, research and document creation."
                cutoff = re.search(r"([A-Za-z]{3} \d{1,2}, \d{4}) knowledge cutoff", text)
                if cutoff:
                    attrs["knowledgeCutoff"] = cutoff[1]
                conditions = "Standard text token rates; see source for service/tool charges."
                long_context = re.search(r"Prompts with (?:>|more than )([\d,]+K?) input tokens are priced at ([\d.]+)x input(?: and cache rates)? and ([\d.]+)x output", text)
                if long_context:
                    conditions += f" Long-context boundary: {long_context[1]} input tokens; input multiplier {long_context[2]}, output multiplier {long_context[3]}."
                promotion = re.search(r"promotional pricing is available at least through ([A-Za-z]+ \d{1,2}, \d{4})", text)
                if promotion:
                    conditions += " Published promotional guarantee through " + promotion[1] + "."
                cache = re.search(r"Cache writes are billed at ([\d.]+)x the uncached input token rate", text)
                if cache:
                    conditions += " Cache-write multiplier " + cache[1] + "."
                    if price.get("input_cache_write") is None:
                        price["input_cache_write"] = str(Decimal(price["prompt"]) * Decimal(cache[1]))
                batch = re.search(r"Batch and Flex are priced at ([\d.]+)% of Standard rates", text)
                fast = re.search(r"Fast mode is priced at ([\d.]+)x the applicable rates", text)
                if batch:
                    conditions += " Batch/Flex factor " + batch[1] + "% of standard."
                if fast:
                    conditions += " Fast factor " + fast[1] + "."
                emit(slug, name, "OpenAI", price, conditions, attrs)
        elif source["id"] == "anthropic-pricing":
            # Only the model pricing table, not token multipliers or third-party cloud tables.
            for table in parser.tables:
                if len(table) < 2 or table[1] != ["Name", "Input", "Output", "5m writes", "1h writes", "Hits and refreshes"]:
                    continue
                for row in table[2:]:
                    if len(row) != 6:
                        continue
                    name_match = re.match(r"Claude (Opus|Sonnet|Haiku|Fable|Mythos) (\d+(?:\.\d+)?)\b", row[0])
                    if not name_match:
                        continue
                    family, version = name_match.groups()
                    pricing = dict(zip(["prompt", "completion", "input_cache_write", "input_cache_write_1h", "input_cache_read"], map(dollars, row[1:])))
                    if pricing["prompt"] is None or pricing["completion"] is None:
                        continue
                    emit("anthropic/claude-" + family.lower() + "-" + version, "Claude " + family + " " + version,
                         "Anthropic", pricing, "Base global Claude API token rates; 5m/1h cache writes distinguished; geography, batch, fast and platform modifiers may apply. Legacy rows do not assert current availability.")
                break
        elif source["id"] == "zai-pricing":
            for table in parser.tables:
                if not table or table[0] != ["Model", "Input", "Cached Input", "Cached Input Storage", "Output"]:
                    continue
                for row in table[1:]:
                    if len(row) != 5 or not re.fullmatch(r"GLM-[A-Za-z0-9.\-]+", row[0]):
                        continue
                    price = {"prompt": dollars(row[1]), "input_cache_read": dollars(row[2]), "completion": dollars(row[4])}
                    if price["prompt"] is not None and price["completion"] is not None:
                        emit("z-ai/" + row[0].lower(), row[0], "Z.AI", price,
                             "Z.AI API USD/1M tokens; cache storage pricing omitted because duration/billing unit differs.")
        elif source["id"] == "minimax-pricing":
            for table_index, table in enumerate(parser.tables):
                if not table or table[0] not in (["Model", "Input", "Output", "Prompt caching Read"],
                                                 ["Model", "Input", "Output", "Prompt caching Read", "Prompt caching Write"]):
                    continue
                for row in table[1:]:
                    if len(row) != len(table[0]):
                        continue
                    match = re.match(r"(MiniMax-M[\d.]+(?:-highspeed)?)\b", row[0])
                    if not match:
                        continue
                    name = match[1]
                    is_m3 = name == "MiniMax-M3"
                    # M3 tables distinguish standard/priority and discounted/struck-through prices.
                    if is_m3 and ("Permanent 50% off" not in row[0] or table_index not in (0, 1)):
                        continue
                    price = dict(zip(["prompt", "completion", "input_cache_read", "input_cache_write"],
                                     [dollars(cell, discounted=is_m3) for cell in row[1:]]))
                    if price["prompt"] is None or price["completion"] is None:
                        continue
                    tier = ("priority" if table_index == 1 else "standard") if is_m3 else "standard"
                    if is_m3:
                        tier += ":long_context" if "> 512k" in row[0] else ":up_to_512k"
                    emit("minimax/" + name.lower(), name, "MiniMax", price,
                         (row[0] + "; current discounted amount (last displayed amount); " + tier) if is_m3 else
                         "MiniMax text API USD/1M tokens; highspeed is a distinct model ID; legacy availability not asserted.", tier=tier)
        if len(facts) == before:
            warnings.append({"source_id": source["id"], "error": "recognized pricing schema missing; no facts emitted"})
    return facts, warnings


def main():
    facts, warnings = extract_official(read_json(BRONZE / "manifest.json"))
    write_json(RES / "official-model-facts.json", facts)
    write_json(RES / "official-extraction-report.json", {"facts": len(facts), "warnings": warnings})
    print(f"Official model/offering records: {len(facts)}; schema warnings: {len(warnings)}")


if __name__ == "__main__":
    main()
