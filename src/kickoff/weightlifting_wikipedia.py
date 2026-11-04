"""Pure, revision-bound adult weight-class facts from MediaWiki's parsed HTML."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urlencode, urlsplit

COMPETITIONS = {
    "IWF_WORLDS": "{year} World Weightlifting Championships",
    "WEIGHTLIFTING_EUROPE": "{year} European Weightlifting Championships",
    "WEIGHTLIFTING_ASIA": "{year} Asian Weightlifting Championships",
    "WEIGHTLIFTING_PAN_AMERICA": "{year} Pan American Weightlifting Championships",
    "WEIGHTLIFTING_AFRICA": "{year} African Weightlifting Championships",
    "WEIGHTLIFTING_OCEANIA": "{year} Oceania Weightlifting Championships",
    "WEIGHTLIFTING_COMMONWEALTH_GAMES": "Weightlifting at the {year} Commonwealth Games",
    "WEIGHTLIFTING_ASIAN_GAMES": "Weightlifting at the {year} Asian Games",
}
CLASS = re.compile(r"(Men|Women)['’]s\s+(\+?\d+)\s*kg", re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "wbr"}
EMPTY = {"", "-", "–", "—", "−", "―", "---", "X", "DNF", "DNS", "DSQ", "NM", "N/A", "Did not start"}
RECORD = r"(?:WR|OR|GR|CR|OC|AR|ER|NR|WJR|WYR|YWR|EJR|AF|AS|AM)"


def competition_title(league: str, year: int) -> str | None:
    return COMPETITIONS[league].format(year=year) if league in COMPETITIONS else None


def api_url(title: str) -> str:
    return "https://en.wikipedia.org/w/api.php?" + urlencode(
        {"action": "parse", "page": title, "prop": "text|links|revid", "format": "json", "formatversion": 2}
    )


def _competition(title: str) -> dict | None:
    for league, template in COMPETITIONS.items():
        match = re.fullmatch(re.escape(template).replace(r"\{year\}", r"(\d{4})"), title)
        if match:
            return {"competition": title, "league": league, "year": int(match[1])}
    return None


def _class(title: str) -> dict | None:
    match = re.fullmatch(r"(.+) [–-] (" + CLASS.pattern + r")", title, re.I)
    if not match:
        return None
    base = _competition(match[1])
    return (
        {**base, "gender": "men" if match[3].lower() == "men" else "women", "weight_class": match[4]} if base else None
    )


def _payload(content: bytes | None, input_url: str, checked_date: str) -> tuple[dict, dict] | None:
    if content is None:
        return None
    date.fromisoformat(checked_date)
    url = urlsplit(input_url)
    query = parse_qs(url.query)
    if url.scheme != "https" or url.netloc != "en.wikipedia.org" or url.path != "/w/api.php":
        return None
    if query.get("action") != ["parse"]:
        return None
    payload = json.loads(content).get("parse")
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("title"), str)
        or type(payload.get("revid")) is not int
    ):
        return None
    if payload["revid"] <= 0:
        return None
    requested = query.get("page")
    if requested and (len(requested) != 1 or requested[0].replace("_", " ") != payload["title"]):
        return None
    if query.get("oldid") and query["oldid"] != [str(payload["revid"])]:
        return None
    if not requested and not query.get("oldid"):
        return None
    scope = _class(payload["title"]) or _competition(payload["title"])
    return (payload, scope) if scope else None


def class_requests(content: bytes | None, *, input_url: str, checked_date: str) -> list[dict]:
    """Actual existing article links, with no invented class page or request cap."""
    try:
        parsed = _payload(content, input_url, checked_date)
        if parsed is None:
            return []
        payload, parent = parsed
        found = {}
        for link in payload.get("links", []):
            title = link.get("title", "")
            scope = _class(title)
            if (
                link.get("ns") == 0
                and link.get("exists") is True
                and scope
                and scope["competition"] == parent["competition"]
            ):
                found[title] = {**scope, "title": title, "input_url": api_url(title)}
        return list(found.values())
    except (ValueError, TypeError, KeyError, AttributeError):
        return []


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    headings: tuple = ()


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.headings = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), headings=tuple(self.headings))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack) - 1, 0, -1) if self.stack[i].tag == tag), None)
        if index is None:
            return
        node = self.stack[index]
        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self.headings = [heading for heading in self.headings if heading[0] < level]
            self.headings.append((level, _text(node), node.attrs.get("id")))
        del self.stack[index:]

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _nodes(node: Node, tag: str):
    for child in node.children:
        if isinstance(child, Node):
            if child.tag == tag:
                yield child
            yield from _nodes(child, tag)


def _text(node: Node, *, skip_abbr=False) -> str:
    if node.tag in {"sup", "script", "style"} or (skip_abbr and node.tag == "abbr"):
        return ""
    if {"reference", "sortkey", "flagicon"} & set(node.attrs.get("class", "").split()):
        return ""
    return " ".join(
        " ".join(
            child if isinstance(child, str) else _text(child, skip_abbr=skip_abbr) for child in node.children
        ).split()
    )


def _rows(table: Node) -> list[list[Node]]:
    rows = []

    def visit(node):
        for child in node.children:
            if not isinstance(child, Node) or child.tag == "table":
                continue
            if child.tag == "tr":
                rows.append([cell for cell in child.children if isinstance(cell, Node) and cell.tag in {"td", "th"}])
            else:
                visit(child)

    visit(table)
    return [row for row in rows if row]


def _grid(rows: list[list[Node]]) -> list[list[Node]]:
    pending = {}
    grid = []
    for row in rows:
        cells = {column: value[0] for column, value in pending.items()}
        pending = {column: (node, remaining - 1) for column, (node, remaining) in pending.items() if remaining > 1}
        column = 0
        for cell in row:
            while column in cells:
                column += 1
            # HTML's nonnegative-integer rule uses the leading digits. One
            # actual source header has rowspan='2width="275"'; browsers read2.
            spans = [re.match(r"^\s*(\d+)", str(cell.attrs.get(key, 1))) for key in ["colspan", "rowspan"]]
            if not all(spans):
                raise ValueError("Invalid table span")
            colspan, rowspan = (int(match[1]) for match in spans)
            if colspan <= 0 or rowspan <= 0:
                raise ValueError("Invalid table span")
            for offset in range(colspan):
                position = column + offset
                if position in cells:
                    raise ValueError("Overlapping source cells")
                cells[position] = cell
                if rowspan > 1:
                    pending[position] = cell, rowspan - 1
            column += colspan
        if sorted(cells) != list(range(len(cells))):
            raise ValueError("Source row has holes")
        grid.append([cells[i] for i in range(len(cells))])
    return grid


def _rank(cell: Node) -> int | None:
    text = _text(cell)
    medals = {
        int(match[1])
        for img in _nodes(cell, "img")
        if (match := re.match(r"([123])(?:st|nd|rd) place", img.attrs.get("alt", "")))
    }
    if text.isdigit():
        medals.add(int(text))
    elif text not in EMPTY:
        raise ValueError("Unknown explicit rank")
    if len(medals) > 1 or 0 in medals:
        raise ValueError("Contradictory rank")
    return next(iter(medals), None)


def _number(cell: Node) -> int | None:
    value = _text(cell)
    if value in EMPTY:
        return None
    match = re.fullmatch(rf"(\d+)(?:\s*kg)?(?:\s*,?\s*{RECORD})*", value)
    if not match:
        raise ValueError("Unknown numeric result")
    return int(match[1])


def _attempt(cell: Node) -> dict:
    value = _text(cell)
    if value in {"-", "–", "—", "−", "―", "---", "Did not start"}:
        return {"weight_kg": None, "status": "unused"}
    match = re.fullmatch(rf"([−-]?)(\d+)(?:\s*,?\s*{RECORD})*", value)
    if not match or int(match[2]) <= 0:
        raise ValueError("Missing or malformed explicit attempt")
    struck = []

    def visit(node, inherited=False):
        strike = inherited or node.tag in {"s", "strike", "del"} or "line-through" in node.attrs.get("style", "")
        for child in node.children:
            if isinstance(child, Node):
                if child.tag != "sup":
                    visit(child, strike)
            elif re.search(r"\d", child):
                struck.append(strike)

    visit(cell)
    if struck and any(struck) != all(struck):
        raise ValueError("Mixed attempt strike marks")
    return {"weight_kg": int(match[2]), "status": "missed" if match[1] or any(struck) else "made"}


def _athlete(cell: Node, country: Node | None = None) -> dict:
    breaks = [i for i, child in enumerate(cell.children) if isinstance(child, Node) and child.tag == "br"]
    if country is None and len(breaks) == 1:
        after = Node("td", children=cell.children[breaks[0] + 1 :])
        if any("flagicon" in span.attrs.get("class", "").split() for span in _nodes(after, "span")):
            # The overview's explicit athlete <br> flag/country structure.
            country, cell = after, Node("td", children=cell.children[: breaks[0]])
    codes = {
        match[1]
        for node in [cell, country]
        if node
        for abbr in _nodes(node, "abbr")
        if (match := re.fullmatch(r"\(?\s*([A-Z]{3})\s*\)?", _text(abbr)))
    }
    linked_codes = set()
    for span in _nodes(cell, "span"):
        literal = _text(span)
        match = re.fullmatch(r"\(\s*([A-Z]{3})\s*\)", literal)
        links = list(_nodes(span, "a"))
        if match and _text(cell).endswith(literal) and len(links) == 1:
            label = re.fullmatch(r"\(?\s*([A-Z]{3})\s*\)?", _text(links[0]))
            if label and label[1] == match[1] and links[0].attrs.get("href", "").startswith("/wiki/"):
                linked_codes.add(match[1])
    codes.update(linked_codes)
    if len(codes) > 1:
        raise ValueError("Ambiguous athlete nation")
    nation = next(iter(codes), _text(country) if country else "")
    name = re.sub(r"\(\s*\)", "", _text(cell, skip_abbr=True)).strip()
    if linked_codes:
        name = re.sub(r"\(\s*" + re.escape(nation) + r"\s*\)\s*$", "", name).strip()
    guest = bool(re.search(r"[\[(]\s*guest\s*[\])]", name, re.I))
    name = re.sub(r"\s*[\[(]\s*guest\s*[\])]", "", name, flags=re.I).strip()
    if not name or name in EMPTY or name.casefold() in {"not awarded", "vacant", "none"}:
        raise ValueError("Missing athlete name")
    person = {"name": name, "nation": nation, "guest": guest}
    links = [
        a.attrs["href"]
        for a in _nodes(cell, "a")
        if a.attrs.get("href", "").startswith("/wiki/")
        and _text(a) == name
        and "new" not in a.attrs.get("class", "").split()
    ]
    if len(set(links)) == 1:
        person["source_article_url"] = "https://en.wikipedia.org" + links[0]
    return person


def _category(table: Node, scope: dict) -> dict | None:
    heading = next(
        ((CLASS.fullmatch(text), anchor) for _, text, anchor in reversed(table.headings) if CLASS.fullmatch(text)), None
    )
    if heading:
        literal, anchor = heading
        category = {"gender": "men" if literal[1].lower() == "men" else "women", "weight_class": literal[2]}
        if "gender" in scope and any(scope[key] != category[key] for key in category):
            raise ValueError("Class title contradicts section")
        return {**scope, **category, "_source_anchor": anchor}
    return scope if "gender" in scope else None


def _podiums(rows: list[dict], lift: str) -> list[dict]:
    rank_field = {"total": "total_rank", "snatch": "snatch_rank", "clean_and_jerk": "clean_and_jerk_rank"}[lift]
    result = []
    for row in rows:
        if row[rank_field] in {1, 2, 3} and not row["guest"]:
            medal = {key: row[key] for key in ["name", "nation", "gender", "weight_class"]}
            if row.get("source_article_url"):
                medal["source_article_url"] = row["source_article_url"]
            medal["rank"] = row[rank_field]
            if lift == "total" and row["total_kg"] is not None:
                medal["weight_kg"] = row["total_kg"]
            result.append(medal)
    return result


def _full_table(table: Node, scope: dict) -> dict | None:
    original = _rows(table)
    if len(original) < 3:
        return None
    header = [_text(cell).casefold() for cell in original[0]]
    if not any(value in {"athlete", "name"} for value in header) or not any("snatch" in value for value in header):
        return None
    category = _category(table, scope)
    if category is None:
        return None
    grid = _grid(original)
    paths = [list(dict.fromkeys(_text(grid[row][col]).casefold() for row in [0, 1])) for col in range(len(grid[0]))]
    labels = [" ".join(path) for path in paths]

    def find(label):
        return next((i for i, value in enumerate(labels) if value == label), None)

    name = find("athlete") if find("athlete") is not None else find("name")
    total, rank, group, country = find("total"), find("rank"), find("group"), find("country")
    attempts = {
        lift: [
            next((i for i, path in enumerate(paths) if path[-1] == str(n) and marker in path[0]), None)
            for n in [1, 2, 3]
        ]
        for lift, marker in [("snatch", "snatch"), ("clean_and_jerk", "clean")]
    }
    if (
        name is None
        or total is None
        or rank is None
        or any(i is None for indices in attempts.values() for i in indices)
    ):
        return None
    ranks = {
        lift: next((i for i, path in enumerate(paths) if marker in path[0] and path[-1] == "rank"), None)
        for lift, marker in [("snatch", "snatch"), ("clean_and_jerk", "clean")]
    }
    athletes, omitted = [], 0
    for index, cells in enumerate(grid[2:]):
        if len(cells) != len(labels):
            omitted += 1
            continue
        try:
            person = _athlete(cells[name], cells[country] if country is not None else None)
            row = {
                **person,
                "gender": category["gender"],
                "weight_class": category["weight_class"],
                "group": _text(cells[group]) if group is not None else None,
                "_row_index": index,
            }
            for lift, indices in attempts.items():
                row[lift] = [_attempt(cells[i]) for i in indices]
                row[f"{lift}_rank"] = _rank(cells[ranks[lift]]) if ranks[lift] is not None else None
                best_index = indices[-1] + 1
                if best_index < len(paths) and paths[best_index][-1] == "result":
                    made = [a["weight_kg"] for a in row[lift] if a["status"] == "made"]
                    if _number(cells[best_index]) != (max(made) if made else None):
                        raise ValueError("Explicit result contradicts attempt marks")
            row["total_kg"], row["total_rank"] = _number(cells[total]), _rank(cells[rank])
            made = [[a["weight_kg"] for a in row[lift] if a["status"] == "made"] for lift in attempts]
            if row["total_kg"] is not None and (
                not all(made) or sum(max(values) for values in made) != row["total_kg"]
            ):
                raise ValueError("Total contradicts explicit made attempts")
            athletes.append(row)
        except (ValueError, TypeError, KeyError):
            omitted += 1
    keys = [(row["name"], row["nation"]) for row in athletes]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate athlete identity")
    total_medals = _podiums(athletes, "total")
    return {
        **category,
        "athletes": athletes,
        "total_medalists": total_medals,
        "snatch_medalists": _podiums(athletes, "snatch"),
        "clean_and_jerk_medalists": _podiums(athletes, "clean_and_jerk"),
        "_complete": omitted == 0 and {row["rank"] for row in total_medals} == {1, 2, 3},
        "_omitted_rows": omitted,
        "_completion_evidence": "explicit_class_result_table",
    }


def _overview(table: Node, scope: dict) -> list[dict]:
    rows = _rows(table)
    if not rows or "event" not in {_text(cell).casefold() for cell in rows[0]}:
        return []
    grid = _grid(rows)
    header = [_text(cell).casefold() for cell in grid[0]]
    if not {"gold", "silver", "bronze"} <= set(header):
        return []
    heading = next(
        (
            (text.casefold(), anchor)
            for _, text, anchor in reversed(table.headings)
            if text.casefold() in {"men", "women"}
        ),
        None,
    )
    if heading is None:
        return []
    gender, anchor = heading
    output, current_weight = {}, None
    for cells in grid[1:]:
        weight = re.match(r"[–−-]?\s*(\+?\s*\d+)\s*kg", _text(cells[0]))
        if len(cells) != len(header):
            continue
        if weight:
            current_weight = weight[1].replace(" ", "")
            if all(cell is cells[0] for cell in cells):
                continue
        elif current_weight is None:
            continue
        label = _text(cells[1] if weight else cells[0]).casefold().replace("&", "and")
        lift = {
            "total": "total",
            "snatch": "snatch",
            "clean and jerk": "clean_and_jerk",
            "clean & jerk": "clean_and_jerk",
        }.get(label)
        if lift is None:
            continue
        weight_class = current_weight
        row = output.setdefault(
            weight_class,
            {
                **scope,
                "gender": gender,
                "weight_class": weight_class,
                "athletes": [],
                "total_medalists": [],
                "snatch_medalists": [],
                "clean_and_jerk_medalists": [],
                "_complete": False,
                "_completion_evidence": "medal_overview_only",
                "_source_anchor": anchor,
            },
        )
        for title, rank in [("gold", 1), ("silver", 2), ("bronze", 3)]:
            positions = [i for i, value in enumerate(header) if value == title]
            if len(positions) != 2:
                continue
            try:
                person = _athlete(cells[positions[0]])
                value = _number(cells[positions[1]])
                row[f"{lift}_medalists"].append(
                    {
                        **person,
                        "gender": gender,
                        "weight_class": weight_class,
                        "rank": rank,
                        **({"weight_kg": value} if value is not None else {}),
                    }
                )
            except (ValueError, TypeError):
                continue
    return list(output.values())


def _class_date(root: Node, year: int) -> str | None:
    for table in _nodes(root, "table"):
        if "infobox" not in table.attrs.get("class", "").split():
            continue
        for row in _rows(table):
            if len(row) == 2 and _text(row[0]).casefold() in {"date", "dates"}:
                text = _text(row[1])
                if not re.search(r"\b\d{4}\b", text):
                    text += f" {year}"  # Year is explicit in this class article's title.
                # An explicit class date is an upper calendar bound, not a clock.
                for pattern in [
                    r"(\d{1,2} \w+ \d{4})",
                    r"\d{1,2}[–-](\d{1,2} \w+ \d{4})",
                    r"\d{1,2} \w+ [–-] (\d{1,2} \w+ \d{4})",
                ]:
                    match = re.fullmatch(pattern, text)
                    if match:
                        return datetime.strptime(match[1], "%d %B %Y").date().isoformat()
    return None


def parse_classes(content: bytes | None, *, input_url: str, checked_date: str) -> list[dict]:
    """All explicit class tables/medals in one real API response, no HTTP or PDFs.

    Partial medal-only facts never imply six attempts or source finality. Private
    row indices are local references, not published athlete IDs or source LOTs.
    """
    try:
        parsed = _payload(content, input_url, checked_date)
        if parsed is None:
            return []
        payload, scope = parsed
        html = payload.get("text")
        html = html.get("*") if isinstance(html, dict) else html
        if not isinstance(html, str):
            return []
        parser = Tables()
        parser.feed(html)
        source_date = _class_date(parser.root, scope["year"]) if "gender" in scope else None
        by_class, ambiguous = {}, set()
        for table in _nodes(parser.root, "table"):
            try:
                full = _full_table(table, scope)
                for result in [full] if full else _overview(table, scope):
                    key = result["gender"], result["weight_class"]
                    if key in ambiguous:
                        continue
                    previous = by_class.get(key)
                    if previous and previous["athletes"] and result["athletes"]:
                        ambiguous.add(key)
                        del by_class[key]
                        continue
                    if previous and previous["athletes"]:
                        continue
                    by_class[key] = result
            except (ValueError, TypeError, KeyError, IndexError):
                continue
        provenance = {
            "kind": "weightlifting",
            "source_url": "https://en.wikipedia.org/w/index.php?"
            + urlencode({"title": payload["title"], "oldid": payload["revid"]}),
            "input_url": input_url,
            "checked_date": checked_date,
            "revision": str(payload["revid"]),
            "sha256": hashlib.sha256(content).hexdigest(),
            "hash_scope": "raw MediaWiki API JSON response bytes",
        }
        results = []
        for result in by_class.values():
            if not result["athletes"] and not any(
                result[key] for key in ["total_medalists", "snatch_medalists", "clean_and_jerk_medalists"]
            ):
                continue
            anchor = result.pop("_source_anchor", None)
            results.append(
                {
                    **result,
                    **provenance,
                    "source_url": provenance["source_url"] + ("#" + quote(anchor) if anchor else ""),
                    "_source_date": source_date,
                    "_ended_before": (date.fromisoformat(source_date) + timedelta(days=1)).isoformat()
                    if source_date
                    else None,
                }
            )
        return results
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return []


def classes_for_session(classes: list[dict], session: dict, *, reviewed_sessions: list[dict]) -> list[dict]:
    """Literal class/group joins; global class medals are not group medals."""
    output = []
    for category in session.get("categories", []):
        weight = category["weight_class"].removesuffix(" kg").replace(">", "+").strip()
        matches = [
            row
            for row in classes
            if row["league"] == session["league"]
            and row["year"] == int(session["start_date"][:4])
            and row["gender"] == category["gender"]
            and row["weight_class"] == weight
        ]
        full = [row for row in matches if row["athletes"]]
        if len(full) == 1:
            matches = full
        if len(matches) != 1:
            continue
        result = deepcopy(matches[0])
        peers = [
            row
            for row in reviewed_sessions
            if row["league"] == session["league"]
            and row["start_date"][:4] == session["start_date"][:4]
            and any(
                c["gender"] == category["gender"]
                and c["weight_class"].removesuffix(" kg").replace(">", "+").strip() == weight
                for c in row.get("categories", [])
            )
        ]
        group = category.get("group")
        if group is not None and result["athletes"] and all(row["group"] is not None for row in result["athletes"]):
            same_group = [
                row
                for row in peers
                if any(
                    c.get("group") == group
                    and c["gender"] == category["gender"]
                    and c["weight_class"].removesuffix(" kg").replace(">", "+").strip() == weight
                    for c in row["categories"]
                )
            ]
            selected = [row for row in result["athletes"] if row["group"] == group]
            if len(same_group) == 1 and same_group[0]["id"] == session["id"] and selected:
                result["athletes"] = selected
            else:
                result["athletes"], result["_complete"] = [], False
        elif group is not None or len(peers) != 1 or peers[0]["id"] != session["id"]:
            result["athletes"], result["_complete"] = [], False
        output.append(result)
    if len(output) != len(session.get("categories", [])):
        for result in output:
            result["_complete"] = False
    return output
