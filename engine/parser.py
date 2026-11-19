"""Parser markdown -> modello a blocchi, condiviso da DOCX e PPTX.
Il PDF usa direttamente l'HTML di markdown-it."""
import re
import yaml
from markdown_it import MarkdownIt


def split_front_matter(text):
    m = re.match(r'^﻿?---\s*\n(.*?)\n---\s*\n', text, re.S)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, text[m.end():]


def md_instance():
    # html=False: l'HTML grezzo nel markdown viene mostrato come testo, mai eseguito
    return MarkdownIt("commonmark", {"html": False}).enable("table").enable("strikethrough")


def _close_index(tokens, i):
    t = tokens[i]
    j = i + 1
    while j < len(tokens):
        if tokens[j].nesting == -1 and tokens[j].level == t.level:
            return j
        j += 1
    return len(tokens) - 1


def inline_runs(inline_token):
    runs = []
    bold = italic = strike = 0
    href = None
    for c in (inline_token.children or []):
        t = c.type
        if t == "strong_open":
            bold += 1
        elif t == "strong_close":
            bold -= 1
        elif t == "em_open":
            italic += 1
        elif t == "em_close":
            italic -= 1
        elif t == "s_open":
            strike += 1
        elif t == "s_close":
            strike -= 1
        elif t == "link_open":
            href = c.attrGet("href")
        elif t == "link_close":
            href = None
        elif t == "text":
            runs.append(dict(text=c.content, bold=bold > 0, italic=italic > 0,
                             strike=strike > 0, code=False, href=href))
        elif t == "code_inline":
            runs.append(dict(text=c.content, bold=bold > 0, italic=italic > 0,
                             strike=False, code=True, href=href))
        elif t in ("softbreak", "hardbreak"):
            runs.append(dict(text=" " if t == "softbreak" else "\n", bold=False,
                             italic=False, strike=False, code=False, href=None))
        elif t == "image":
            alt = c.content or ""
            if alt:
                runs.append(dict(text=f"[{alt}]", bold=False, italic=True,
                                 strike=False, code=False, href=None))
    return runs


def runs_text(runs):
    return "".join(r["text"] for r in runs)


def parse_blocks(tokens):
    blocks = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        ty = t.type
        if ty == "heading_open":
            blocks.append(dict(type="heading", level=int(t.tag[1]),
                               runs=inline_runs(tokens[i + 1])))
            i = _close_index(tokens, i) + 1
        elif ty == "paragraph_open":
            blocks.append(dict(type="paragraph", runs=inline_runs(tokens[i + 1])))
            i = _close_index(tokens, i) + 1
        elif ty in ("bullet_list_open", "ordered_list_open"):
            end = _close_index(tokens, i)
            items = []
            j = i + 1
            while j < end:
                if tokens[j].type == "list_item_open":
                    ie = _close_index(tokens, j)
                    items.append(dict(blocks=parse_blocks(tokens[j + 1:ie])))
                    j = ie + 1
                else:
                    j += 1
            blocks.append(dict(type="list", ordered=(ty == "ordered_list_open"), items=items))
            i = end + 1
        elif ty == "blockquote_open":
            end = _close_index(tokens, i)
            blocks.append(dict(type="quote", blocks=parse_blocks(tokens[i + 1:end])))
            i = end + 1
        elif ty in ("fence", "code_block"):
            blocks.append(dict(type="code", text=t.content.rstrip("\n")))
            i += 1
        elif ty == "hr":
            blocks.append(dict(type="hr"))
            i += 1
        elif ty == "table_open":
            end = _close_index(tokens, i)
            header, rows, aligns = [], [], []
            row = None
            in_head = False
            j = i + 1
            while j < end:
                tj = tokens[j]
                if tj.type == "thead_open":
                    in_head = True
                elif tj.type == "thead_close":
                    in_head = False
                elif tj.type == "tr_open":
                    row = []
                elif tj.type == "tr_close":
                    (header.extend(row) if in_head else rows.append(row))
                    row = None
                elif tj.type in ("th_open", "td_open"):
                    style = tj.attrGet("style") or ""
                    al = "left"
                    if "center" in style:
                        al = "center"
                    elif "right" in style:
                        al = "right"
                    if in_head:
                        aligns.append(al)
                    row.append(inline_runs(tokens[j + 1]))
                j += 1
            blocks.append(dict(type="table", header=header, rows=rows, aligns=aligns))
            i = end + 1
        else:
            i += 1
    return blocks


def parse_markdown(text):
    """Ritorna (meta, blocks). Se manca il titolo nel front matter,
    il primo H1 diventa il titolo e viene tolto dal corpo."""
    meta, body = split_front_matter(text)
    blocks = parse_blocks(md_instance().parse(body))
    if not meta.get("title"):
        for k, b in enumerate(blocks):
            if b["type"] == "heading" and b["level"] == 1:
                meta["title"] = runs_text(b["runs"])
                blocks.pop(k)
                break
            if b["type"] != "heading":
                break
    return meta, blocks, body
