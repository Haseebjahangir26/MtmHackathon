"""Input manager: split a raw message pack into individual messages, verbatim."""
from __future__ import annotations

import hashlib
import re

NUM_HDR = re.compile(r"^\s*(?:#\s*|msg\s*|message\s*)?\(?\d{1,3}\s*(?:[\.\):\]\-|,]|\s{2,}|\t)\s*\S"
                     r"|^\s*(?:#|message|msg)\s*\d{1,3}\b", re.IGNORECASE)
SEP = re.compile(r"^\s*([-=*_~#]{3,})\s*$")


def split_pack(raw: str) -> list[str]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip("\n﻿ ")
    if not text.strip():
        return []
    lines = text.split("\n")

    # 1) explicit separator lines
    if sum(1 for l in lines if SEP.match(l)) >= 1:
        parts, cur = [], []
        for l in lines:
            if SEP.match(l):
                parts.append("\n".join(cur)); cur = []
            else:
                cur.append(l)
        parts.append("\n".join(cur))
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            return parts

    # 2) numbered message headers
    idx = [i for i, l in enumerate(lines) if NUM_HDR.match(l)]
    if len(idx) >= 2:
        parts = []
        if idx[0] > 0:
            pre = "\n".join(lines[: idx[0]]).strip()
            if pre:
                parts.append(pre)
        for a, b in zip(idx, idx[1:] + [len(lines)]):
            parts.append("\n".join(lines[a:b]).strip())
        return [p for p in parts if p]

    # 3) blank-line separated paragraphs
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) >= 2:
        return paras

    # 4) one message per non-empty line
    return [l.strip() for l in lines if l.strip()]


def fingerprint(text: str) -> str:
    t = re.sub(r"\W+", " ", text.lower()).strip()
    return hashlib.sha1(t.encode()).hexdigest()[:16]
