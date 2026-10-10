"""Values that customers say on the phone, turned into the form that a tool API needs.

Customers say amounts and dates in words, give digits as words ("nine nine oh four"), and correct themselves. The
model converts most of them, but not every time. These functions run in a pre-hook (lib/tools_from_openapi.py), so
the bank gets the right value even when the model sends the words. They change a value only when the result is
clear: an ISO date or a plain number stays as it is.

SOURCE is the same code as text, for a Freya hook or code step (standard library only, no '{{' or '}}').
"""

SOURCE = r'''
import re, datetime

_UNITS = {"zero": 0, "oh": 0, "o": 0, "nought": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
        "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
        "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

def _tokens(text):
    t = str(text).lower().replace("-", " ").replace(",", " ")
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    return [w for w in re.split(r"[^a-z0-9.]+", t) if w and w not in ("and", "a", "the", "of", "dollars", "dollar", "usd", "euros", "euro", "pounds")]

def words_to_number(text):
    """'four hundred and fifty-five' -> 455, '1,250' -> 1250, '126.50' -> 126.5, 'five forty' -> 540. None if unclear."""
    s = str(text).strip().lower().replace(",", "")
    m = re.fullmatch(r"\$?\s*(\d+(?:\.\d+)?)\s*(dollars?|usd)?", s)
    if m:
        return float(m.group(1))
    toks = _tokens(text)
    if not toks:
        return None
    cents = None
    if "point" in toks:
        i = toks.index("point")
        frac = "".join(str(_UNITS[w]) for w in toks[i + 1:] if w in _UNITS and _UNITS[w] < 10)
        cents = float("0." + frac) if frac else None
        toks = toks[:i]
    low = str(text).lower()
    if re.search(r"\bcents?\b", low):
        # '126 dollars and 50 cents', 'one hundred twenty six dollars and fifty cents'
        m2 = re.match(r"(.*?)\bdollars?\b(.*?)\bcents?\b", low)
        if not m2:
            return None
        d = words_to_number(m2.group(1)) if m2.group(1).strip() else 0.0
        c = words_to_number(m2.group(2).replace("and", " ")) if m2.group(2).strip() else 0.0
        return None if d is None or c is None or c >= 100 else d + c / 100.0
    total, cur, groups = 0, 0, []
    for w in toks:
        if w.isdigit():
            groups.append(int(w))
            continue
        if w in _UNITS:
            cur += _UNITS[w]
        elif w in _TENS:
            cur += _TENS[w]
        elif w == "hundred":
            cur = (cur or 1) * 100
        elif w == "thousand":
            total += (cur or 1) * 1000
            cur = 0
        else:
            return None
    if groups and not (total or cur):
        value = float("".join(str(g) for g in groups)) if len(groups) > 1 else float(groups[0])
    else:
        value = float(total + cur)
        # Two groups without 'hundred' ("five forty", "twelve fifty") can be 540 or 5.40: not clear, so no value.
        if not total and len(toks) >= 2 and toks[0] in _UNITS and toks[1] in _TENS:
            return None
    if cents is not None:
        value += cents
    return value

def digits(text):
    """'nine nine oh four' -> '9904', 'double five two one' -> '5521', '99 04' -> '9904'. '' if a word is not a digit."""
    out, toks, i = "", _tokens(text), 0
    while i < len(toks):
        w = toks[i]
        if w in ("double", "triple") and i + 1 < len(toks):
            n = 2 if w == "double" else 3
            d = digits(toks[i + 1])
            if len(d) != 1:
                return ""
            out += d * n
            i += 2
            continue
        if w.isdigit():
            out += w
        elif w in _UNITS and _UNITS[w] < 10:
            out += str(_UNITS[w])
        elif w in _TENS:
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if nxt in _UNITS and 0 < _UNITS[nxt] < 10:
                out += str(_TENS[w] + _UNITS[nxt])
                i += 1
            else:
                out += str(_TENS[w])
        elif w in _UNITS:
            out += str(_UNITS[w])
        else:
            return ""
        i += 1
    return out

def _year(toks):
    """'nineteen eighty eight' -> 1988, 'two thousand and one' -> 2001, '1988' -> 1988."""
    for w in toks:
        if w.isdigit() and len(w) == 4:
            return int(w)
    words = [w for w in toks if w in _UNITS or w in _TENS or w in ("hundred", "thousand")]
    if not words:
        return None
    if "thousand" in words:
        n = words_to_number(" ".join(words))
        return int(n) if n and 1900 <= n <= 2100 else None
    # two two-digit halves: nineteen | eighty eight
    first, rest = words[0], words[1:]
    if first in _UNITS and _UNITS[first] >= 10 or first in _TENS:
        hi = _UNITS.get(first, _TENS.get(first))
        lo = words_to_number(" ".join(rest)) if rest else 0
        if lo is not None and lo < 100:
            y = hi * 100 + int(lo)
            return y if 1900 <= y <= 2100 else None
    return None

def spoken_date(text, order="DMY", default_year=None):
    """A date said by a customer -> 'YYYY-MM-DD', or '' when it is not clear.
    'the twenty-second of October' (+ default_year), '14 March 1988', 'March 14th, 1988', '14/03/1988' (order DMY),
    'nineteen eighty eight, March fourteenth'. An ISO date stays as it is."""
    s = str(text).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})[./ -](\d{1,2})[./ -](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + (1900 if y > 30 else 2000) if y < 100 else y
        d, mo = (a, b) if order == "DMY" else (b, a)
        try:
            return datetime.date(y, mo, d).isoformat()
        except Exception:
            return ""
    toks = _tokens(s)
    mo = next((i + 1 for i, name in enumerate(_MONTHS) for w in toks if w == name or (len(w) >= 3 and name.startswith(w) and w not in ("mar", "may") ) or w == name[:3]), None)
    if not mo:
        return ""
    mname = _MONTHS[mo - 1]
    rest = [w for w in toks if not (w == mname or w == mname[:3] or (len(w) >= 3 and mname.startswith(w)))]
    day, used = None, set()
    for i, w in enumerate(rest):
        if w in _ORD:
            day = _ORD[w]
            used.add(i)
            if i > 0 and rest[i - 1] in _TENS and rest[i - 1] in ("twenty", "thirty"):
                day += _TENS[rest[i - 1]]
                used.add(i - 1)
            break
        if w.isdigit() and 1 <= int(w) <= 31 and len(w) <= 2:
            day = int(w)
            used.add(i)
            break
    if day is None:
        for i, w in enumerate(rest):
            if w in ("twenty", "thirty") and i + 1 < len(rest) and rest[i + 1] in _UNITS and _UNITS[rest[i + 1]] < 10:
                day = _TENS[w] + _UNITS[rest[i + 1]]
                used.update({i, i + 1})
                break
            if w in _UNITS and 1 <= _UNITS[w] <= 31:
                day = _UNITS[w]
                used.add(i)
                break
    year = _year([w for i, w in enumerate(rest) if i not in used]) or default_year
    if not (day and year):
        return ""
    try:
        return datetime.date(int(year), mo, day).isoformat()
    except Exception:
        return ""
'''

exec(SOURCE)
