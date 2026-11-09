#!/usr/bin/env python3
"""
Validate a Survey Automator export JSON against the bundled schema
AND a set of structural/semantic rules that the schema alone cannot express.

Usage:
    python validate.py <path-to-survey.json> [--existing <project-survey.json>]
    python validate.py <update.json> [--base <survey-export.json>]   (Survey Update Mode)

Exit code 0 means the file is valid. Non-zero means problems were found; they
are printed one per line to stdout.

The schema check is implemented natively (no third-party dependency) by a
small interpreter for the JSON-Schema subset that references/schema.json
actually uses: $ref, type, properties, required, additionalProperties, items,
enum, pattern, minimum. This makes the validator fully self-contained — it
behaves identically whether or not `jsonschema` is installed, including in
network-restricted sandboxes where pip is unavailable. If the schema is ever
extended with a keyword outside this subset, the validator fails loudly
rather than silently skipping the rule (see _SUPPORTED_KEYWORDS).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "references" / "schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Native schema validation (JSON-Schema subset interpreter)
# --------------------------------------------------------------------------

# Structural keywords this interpreter understands. Annotation-only keywords
# ($schema, $id, title, description, examples, definitions) are ignored.
_SUPPORTED_KEYWORDS = {
    "$ref", "type", "properties", "required", "additionalProperties",
    "items", "enum", "pattern", "minimum",
}
_ANNOTATION_KEYWORDS = {
    "$schema", "$id", "title", "description", "examples", "definitions",
}

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
    "null": type(None),
}


def _assert_schema_supported(schema, path="#") -> None:
    """Fail loudly if the schema uses a structural keyword we don't implement,
    so a future schema edit can never be silently un-enforced."""
    if isinstance(schema, dict):
        unknown = (
            set(schema.keys()) - _SUPPORTED_KEYWORDS - _ANNOTATION_KEYWORDS
        )
        # Keys inside `properties` are field names, not keywords — recurse
        # into the values only. Same for definitions.
        for kw in ("properties", "definitions"):
            if kw in schema and isinstance(schema[kw], dict):
                for name, sub in schema[kw].items():
                    _assert_schema_supported(sub, f"{path}/{kw}/{name}")
        for kw in ("items", "additionalProperties"):
            if isinstance(schema.get(kw), dict):
                _assert_schema_supported(schema[kw], f"{path}/{kw}")
        if unknown:
            raise SystemExit(
                f"ERROR: schema.json uses unsupported keyword(s) {sorted(unknown)} "
                f"at {path}. Extend the interpreter in validate.py (and "
                f"_SUPPORTED_KEYWORDS) before relying on these rules."
            )


def _type_ok(value, expected) -> bool:
    """Check a value against a JSON-Schema `type` (string or list of strings)."""
    names = [expected] if isinstance(expected, str) else list(expected)
    for name in names:
        py = _TYPE_MAP.get(name)
        if py is None:
            continue
        # bool is a subclass of int in Python; JSON treats them as distinct.
        if name in ("integer", "number") and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False


def _validate_node(value, schema, root, path, errors) -> None:
    if not isinstance(schema, dict):
        return

    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise SystemExit(f"ERROR: unsupported $ref '{ref}' in schema.json")
        target = root
        for part in ref[2:].split("/"):
            target = target[part]
        _validate_node(value, target, root, path, errors)
        return

    loc = path or "<root>"

    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"[schema] {loc}: expected type {schema['type']!r}, got {type(value).__name__}")
        return  # further keyword checks assume the right type

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"[schema] {loc}: {value!r} is not one of {schema['enum']}")

    if "pattern" in schema and isinstance(value, str):
        if not re.search(schema["pattern"], value):
            errors.append(f"[schema] {loc}: {value!r} does not match pattern {schema['pattern']!r}")

    if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema["minimum"]:
            errors.append(f"[schema] {loc}: {value!r} is less than the minimum of {schema['minimum']}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"[schema] {loc}: '{req}' is a required property")
        addl = schema.get("additionalProperties", True)
        for key, sub_value in value.items():
            sub_path = f"{path}/{key}" if path else key
            if key in props:
                _validate_node(sub_value, props[key], root, sub_path, errors)
            elif addl is False:
                errors.append(f"[schema] {loc}: additional properties are not allowed ('{key}' was unexpected)")
            elif isinstance(addl, dict):
                _validate_node(sub_value, addl, root, sub_path, errors)

    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            sub_path = f"{path}/{i}" if path else str(i)
            _validate_node(item, schema["items"], root, sub_path, errors)


def validate_schema(data) -> list[str]:
    schema = load_json(SCHEMA_PATH)
    _assert_schema_supported(schema)
    errors: list[str] = []
    _validate_node(data, schema, schema, "", errors)
    return errors


def _tokenize_condition(s: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Tokenize a condition definition string.

    Returns (tokens, errors). Each token is (kind, value) where kind is one of:
      'LPAREN', 'RPAREN', 'AND', 'OR', 'NOT', 'COLON',
      'CMP'    — one of >, >=, <, <=, =, <>
      'ARITH'  — one of +, -, *, /
      'NUM'    — numeric literal (int or float as a string)
      'REF'    — a {Identifier} reference; value is the identifier inside the braces
      'ROW'    — '.N' directly after a REF: grid row N ({Grid}.N); value is N
      'AREF'   — 'A<n>' after a COLON: the answer at position n; value is n
      'VREF'   — 'V<n>VALUEN' or 'VALUEN' after a COLON: the numeric value of the Open
                 answer at position n (0 = the question's own open answer); value is n
      'PREF'   — a [Identifier] points reference (sum of answer points); value is the identifier
    """
    tokens: list[tuple[str, str]] = []
    errors: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "(":
            tokens.append(("LPAREN", c)); i += 1; continue
        if c == ")":
            tokens.append(("RPAREN", c)); i += 1; continue
        if c == ":":
            tokens.append(("COLON", c)); i += 1; continue
        if c == "{":
            j = s.find("}", i + 1)
            if j == -1:
                errors.append(f"unmatched '{{' at position {i}")
                return tokens, errors
            ident = s[i + 1 : j]
            if not ident:
                errors.append(f"empty reference '{{}}' at position {i}")
            tokens.append(("REF", ident))
            i = j + 1
            # a grid row by its position: {Grid}.N
            row = re.match(r"\.(\d+)", s[i:])
            if row:
                tokens.append(("ROW", row.group(1)))
                i += row.end()
            continue
        if c == "[":
            j = s.find("]", i + 1)
            if j == -1:
                errors.append(f"unmatched '[' at position {i}")
                return tokens, errors
            ident = s[i + 1 : j]
            if not ident:
                errors.append(f"empty points reference '[]' at position {i}")
            tokens.append(("PREF", ident))
            i = j + 1
            continue
        if c in "+-*/":
            tokens.append(("ARITH", c)); i += 1; continue
        if c in "<>=":
            # Two-char operators: >=, <=, <>
            if i + 1 < n and s[i : i + 2] in (">=", "<=", "<>"):
                tokens.append(("CMP", s[i : i + 2])); i += 2; continue
            tokens.append(("CMP", c)); i += 1; continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            saw_dot = False
            while j < n and (s[j].isdigit() or (s[j] == "." and not saw_dot)):
                if s[j] == ".":
                    saw_dot = True
                j += 1
            tokens.append(("NUM", s[i:j]))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            after_colon = bool(tokens) and tokens[-1][0] == "COLON"
            answer_pos = re.fullmatch(r"A(\d+)", word) if after_colon else None
            open_value = re.fullmatch(r"(?:V(\d+))?VALUEN", word) if after_colon else None
            if word in ("AND", "OR", "NOT"):
                tokens.append((word, word))
            elif answer_pos:
                tokens.append(("AREF", answer_pos.group(1)))
            elif open_value:
                tokens.append(("VREF", open_value.group(1) or "0"))
            else:
                errors.append(f"unexpected word '{word}' at position {i} (expected AND, OR, NOT, a number, or a {{...}} reference)")
            i = j
            continue
        errors.append(f"unexpected character '{c}' at position {i}")
        i += 1
    return tokens, errors


class _Parser:
    """Recursive-descent parser for the condition expression grammar.

    Grammar:
      expr        := or_expr
      or_expr     := and_expr ('OR' and_expr)*
      and_expr    := not_expr ('AND' not_expr)*
      not_expr    := 'NOT' not_expr | comparison
      comparison  := primary (CMP arith)?           — when primary is an arith expression
                   | answer_atom                    — ref COLON (REF | AREF), e.g. {Q}:{A}, {Q}.2:A3
      arith       := term (('+'|'-') term)*
      term        := factor (('*'|'/') factor)*
      factor      := NUM | ref (COLON VREF)? | PREF | '(' arith ')'
      ref         := REF ROW?                       — {Q}, or grid row N as {Grid}.N

    Note: an answer_atom is a boolean leaf. Anything else at boolean-leaf
    position is parsed as an arith expression that must then be followed by a
    comparison operator and another arith expression. The value of a calculated
    Open answer is a plain arith expression (parse_value).
    """

    def __init__(self, tokens: list[tuple[str, str]]):
        self.toks = tokens
        self.pos = 0
        self.errors: list[str] = []
        # Collect references encountered so the caller can semantically check them.
        # A reference is (identifier, row number or None).
        # answer_refs is list of (reference, 'id' | 'position', answer id or position)
        # value_refs  is list of (reference, Open answer position or None) in arithmetic
        #             position; None is the bare {Q}, 0 the question's own open answer
        self.answer_refs: list[tuple[tuple[str, int | None], str, str]] = []
        self.value_refs: list[tuple[tuple[str, int | None], int | None]] = []
        # points_refs is list of question_or_row_id from [Q] / [Q.N] references
        self.points_refs: list[str] = []

    def _atom_length(self, i: int) -> int:
        """Number of tokens of the answer atom starting at token i, 0 when there is none."""
        if i >= len(self.toks) or self.toks[i][0] != "REF":
            return 0
        k = i + 1
        if k < len(self.toks) and self.toks[k][0] == "ROW":
            k += 1
        if k + 1 < len(self.toks) and self.toks[k][0] == "COLON" and self.toks[k + 1][0] in ("REF", "AREF"):
            return k + 2 - i
        return 0

    def _ref(self) -> tuple[str, int | None]:
        """Consume REF ROW? and return (identifier, row number or None)."""
        ident = self.toks[self.pos][1]
        self.pos += 1
        row = None
        if self._peek() and self._peek()[0] == "ROW":
            row = int(self._peek()[1])
            self.pos += 1
        return (ident, row)

    def parse_value(self):
        """Parse an arithmetic expression - the value of a calculated Open answer."""
        self._arith()
        if self.pos < len(self.toks):
            tok = self.toks[self.pos]
            self.errors.append(f"unexpected trailing token '{tok[1]}' (a value is an arithmetic expression)")

    def _peek(self, offset: int = 0):
        idx = self.pos + offset
        if idx >= len(self.toks):
            return None
        return self.toks[idx]

    def _eat(self, kind: str):
        tok = self._peek()
        if tok is None or tok[0] != kind:
            got = "end of input" if tok is None else f"'{tok[1]}'"
            self.errors.append(f"expected {kind} but got {got}")
            return None
        self.pos += 1
        return tok

    def parse(self):
        self._or_expr()
        if self.pos < len(self.toks):
            tok = self.toks[self.pos]
            self.errors.append(f"unexpected trailing token '{tok[1]}'")

    def _or_expr(self):
        self._and_expr()
        while self._peek() and self._peek()[0] == "OR":
            self.pos += 1
            self._and_expr()

    def _and_expr(self):
        self._not_expr()
        while self._peek() and self._peek()[0] == "AND":
            self.pos += 1
            self._not_expr()

    def _not_expr(self):
        if self._peek() and self._peek()[0] == "NOT":
            self.pos += 1
            self._not_expr()
            return
        self._comparison()

    def _comparison(self):
        # Distinguish answer_atom (ref COLON REF|AREF) from arith CMP arith.
        if self._atom_length(self.pos):
            ref = self._ref()
            self.pos += 1  # COLON
            kind, value = self._peek()
            self.pos += 1
            self.answer_refs.append((ref, "id" if kind == "REF" else "position", value))
            return
        # Parenthesized boolean group: '(...)' where ... contains AND/OR/CMP/atom.
        # Treat the whole group as a boolean leaf — no surrounding CMP required.
        if self._peek() and self._peek()[0] == "LPAREN":
            self.pos += 1  # consume '('
            if self._contains_boolean_to_rparen():
                self._or_expr()
                self._eat("RPAREN")
                return
            # Otherwise it's a parenthesized arith expression — fall through
            # to the arith comparison path. Re-parse from before the '(' by
            # backing up so _arith sees it.
            self.pos -= 1
        # Otherwise: arith CMP arith (CMP required for a boolean leaf)
        self._arith()
        if self._peek() and self._peek()[0] == "CMP":
            self.pos += 1
            self._arith()
        else:
            self.errors.append(
                "expected a comparison operator (>, >=, <, <=, =, <>) after the arithmetic expression, "
                "or use the '{Q}:{A}' form for an answer-selection check"
            )

    def _arith(self):
        self._term()
        while self._peek() and self._peek()[0] == "ARITH" and self._peek()[1] in ("+", "-"):
            self.pos += 1
            self._term()

    def _term(self):
        self._factor()
        while self._peek() and self._peek()[0] == "ARITH" and self._peek()[1] in ("*", "/"):
            self.pos += 1
            self._factor()

    def _factor(self):
        tok = self._peek()
        if tok is None:
            self.errors.append("unexpected end of expression")
            return
        kind = tok[0]
        if kind == "NUM":
            self.pos += 1
            return
        if kind == "REF":
            ref = self._ref()
            open_position = None
            if self._peek() and self._peek()[0] == "COLON" and self._peek(1) and self._peek(1)[0] == "VREF":
                open_position = int(self._peek(1)[1])
                self.pos += 2
            self.value_refs.append((ref, open_position))
            return
        if kind == "PREF":
            self.points_refs.append(tok[1])
            self.pos += 1
            return
        if kind == "LPAREN":
            self.pos += 1
            # Inside parens we re-enter the boolean expression grammar so that
            # both '({Age} >= 18 AND {Age} < 65)' and '(({A} + {B}) > 10)' work.
            # Distinguish: if the contents look like a comparison/boolean, use
            # _or_expr; otherwise use _arith. Cheap heuristic: scan ahead for
            # a CMP/AND/OR/answer-atom before the matching RPAREN.
            if self._contains_boolean_to_rparen():
                self._or_expr()
            else:
                self._arith()
            self._eat("RPAREN")
            return
        self.errors.append(f"unexpected token '{tok[1]}' (expected a number, a {{reference}}, a [points reference], or '(')")
        self.pos += 1  # consume to avoid infinite loop

    def _contains_boolean_to_rparen(self) -> bool:
        depth = 1
        i = self.pos
        while i < len(self.toks) and depth > 0:
            k = self.toks[i][0]
            if k == "LPAREN":
                depth += 1
            elif k == "RPAREN":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1 and k in ("AND", "OR", "NOT", "CMP"):
                return True
            elif depth == 1 and self._atom_length(i):
                return True
            i += 1
        return False


def _is_own_open_answer(a: dict) -> bool:
    """The question's own open answer (id 0, or connected to another answer) - it gets no position (itemid)."""
    return a.get("type") == "Open" and (str(a.get("id")) == "0" or bool(a.get("connectedTo")))


def _numbered_answers(q: dict) -> list:
    """The answers that get a position (itemid) on import: 'A<n>' and 'V<n>VALUEN' count in this list."""
    return [a for a in (q.get("answers") or []) if isinstance(a, dict) and not _is_own_open_answer(a)]


def _has_own_open_answer(q: dict) -> bool:
    return q.get("type") == "open" or any(isinstance(a, dict) and _is_own_open_answer(a) for a in (q.get("answers") or []))


class _References:
    """What expressions may refer to: the file's questions and grid rows, and with --existing the
    questions of the project the file is imported into. The import resolves the file's own items first,
    then the project's - and the project's questions are all placed before the imported ones."""

    def __init__(self, questions: list, existing: list | None = None):
        # identifier -> (question, row or None, position of the question)
        self.items: dict[str, tuple[dict, dict | None, int]] = {}
        # '<grid id>.<row number>' -> grid: the default row id, which is not a reference
        self.default_row_ids: dict[str, dict] = {}
        for position, q in enumerate(questions or []):
            self._add(q, position)
        for q in existing or []:
            self._add(q, -1)

    def _add(self, q, position: int) -> None:
        if not isinstance(q, dict) or not q.get("id"):
            return
        qid = q["id"]
        self.items.setdefault(qid, (q, None, position))
        for n, row in enumerate(q.get("rows") or [], 1):
            rid = row.get("id") if isinstance(row, dict) else None
            if not rid:
                continue
            if rid == f"{qid}.{n}":
                self.default_row_ids.setdefault(rid, q)
            else:
                self.items.setdefault(rid, (q, row, position))

    def resolve(self, ref: tuple[str, int | None]):
        """(question, row, position, error) of a reference (identifier, row number). For a grid row the
        question is the grid, which holds the answers."""
        ident, row = ref
        item = self.items.get(ident)
        if row is None:
            if item:
                return (*item, None)
            grid = self.default_row_ids.get(ident)
            if grid is not None:
                return (None, None, 0, f"'{{{ident}}}' is a row id - refer to a grid row as {{{grid['id']}}}.{ident.rsplit('.', 1)[1]}")
            return (None, None, 0, f"unknown question or row '{{{ident}}}'")
        text = f"{{{ident}}}.{row}"
        if not item:
            return (None, None, 0, f"unknown question '{{{ident}}}' in '{text}'")
        if item[1] is not None or not item[0].get("rows"):
            return (None, None, 0, f"'{text}': '{ident}' is not a grid (a matrix question with rows)")
        rows = item[0]["rows"]
        if not 1 <= row <= len(rows):
            return (None, None, 0, f"'{text}': grid '{ident}' has no row {row}")
        return (item[0], rows[row - 1], item[2], None)

    def points_target(self, ident: str):
        """The question of a [Q] / [Q.N] points reference, or None."""
        item = self.items.get(ident)
        return item[0] if item else self.default_row_ids.get(ident)


def _reference_text(ref: tuple[str, int | None]) -> str:
    return f"{{{ref[0]}}}" + (f".{ref[1]}" if ref[1] is not None else "")


def _validate_condition(
    definition: str,
    refs: _References,
    owner_position: int | None = None,
    is_value: bool = False,
) -> list[str]:
    """Validate a condition definition - or with is_value, the value of a calculated Open answer.
    owner_position: the position of the calculation's question; references must be placed before it.
    Returns a list of error messages."""
    errors: list[str] = []
    # The platform needs NOT directly followed by '(' - 'NOT(…)', never 'NOT …' or 'NOT (…)'.
    outside = re.sub(r"\{[^{}]*\}|\[[^\[\]]*\]", lambda m: " " * len(m.group(0)), definition)
    for m in re.finditer(r"\bNOT\b", outside):
        if outside[m.end():m.end() + 1] != "(":
            errors.append(
                f"NOT at position {m.start()} must be followed directly by '(' with no space - "
                f"write NOT({{Q}}:{{1}}) or NOT({{Q}}:{{1}} OR {{Q}}:{{2}})"
            )
    tokens, tok_errors = _tokenize_condition(definition)
    errors.extend(tok_errors)
    if not tokens:
        if not tok_errors:
            errors.append("empty condition")
        return errors

    parser = _Parser(tokens)
    if is_value:
        parser.parse_value()
    else:
        parser.parse()
    errors.extend(parser.errors)

    coded_reported: set[str] = set()

    def check_not_coded(q, text: str) -> None:
        # A display condition (owner_position None: question condition, screenout/error, text field)
        # can't use a coded question yet: the coding is not done while the respondent answers.
        # Remove this check when the platform gets online coded variables.
        if owner_position is None and q is not None and q.get("coded") is not None and q.get("id") not in coded_reported:
            coded_reported.add(q.get("id"))
            errors.append(
                f"references '{text}', a coded question - coded questions can't be used in conditions yet "
                f"(the coding is not done while the respondent answers). Branch on a closed question instead"
            )

    def resolve(ref):
        q, row, position, error = refs.resolve(ref)
        if error:
            errors.append(f"references {error}")
            return None
        check_not_coded(q, _reference_text(ref))
        if owner_position is not None and position >= owner_position:
            errors.append(
                f"references '{_reference_text(ref)}', which is not placed before this question - "
                f"a calculation may only use earlier questions"
            )
        return q

    for ref, kind, value in parser.answer_refs:
        q = resolve(ref)
        if q is None:
            continue
        if kind == "id":
            if value not in {a.get("id") for a in (q.get("answers") or []) if isinstance(a, dict)}:
                errors.append(f"references unknown answer id '{value}' on '{_reference_text(ref)}'")
        elif not 1 <= int(value) <= len(_numbered_answers(q)):
            errors.append(f"'{_reference_text(ref)}:A{value}': there is no answer at position {value}")

    for ref, open_position in parser.value_refs:
        q = resolve(ref)
        if q is None:
            continue
        if open_position == 0:
            if not _has_own_open_answer(q):
                errors.append(f"'{_reference_text(ref)}:VALUEN': the question has no open answer of its own")
            continue
        if open_position is not None:
            numbered = _numbered_answers(q)
            if not (1 <= open_position <= len(numbered) and numbered[open_position - 1].get("type") == "Open"):
                errors.append(f"'{_reference_text(ref)}:V{open_position}VALUEN': answer {open_position} is not an Open answer")
            continue
        # A bare {Q} is the value of the question's open answer. Numeric arithmetic
        # only makes sense against integer-typed open questions.
        qtype = q.get("type")
        answers = q.get("answers") or []
        is_int_open = (
            qtype == "open"
            and answers
            and answers[0].get("type") == "Open"
            and answers[0].get("dataType") == "integer"
        )
        if not is_int_open:
            errors.append(
                f"arithmetic reference '{_reference_text(ref)}' is to a non-integer question "
                f"(type='{qtype}'); arithmetic comparisons expect open questions with dataType='integer'"
            )

    for qref in parser.points_refs:
        ref_q = refs.points_target(qref)
        if ref_q is None:
            errors.append(f"points reference '[{qref}]' points to unknown question/row")
            continue
        check_not_coded(ref_q, f"[{qref}]")
        qtype = ref_q.get("type")
        if qtype not in ("single", "multiple", "open"):
            errors.append(
                f"points reference '[{qref}]' is to a '{qtype}' item; points only exist on "
                f"single, multiple and open questions (and grids / grid rows)"
            )
            continue
        # Platform import bug (reported 2026-10-17): when a [Q] points reference is compared with a
        # number and Q has an open answer of its own, the import rewrites it to [Qxxx:VALUEN], which
        # fails with "Syntax error: Expecting 'A'". [Q] used as a plain value (no comparison) is fine.
        if _has_own_open_answer(ref_q) and re.search(r"[<>=]", outside):
            errors.append(
                f"points reference '[{qref}]' is used in a comparison, but '{qref}' has an open answer of "
                f"its own - the platform import turns it into '[Q:VALUEN]' and fails (known platform bug). "
                f"Write the rule with answer atoms instead, e.g. 'at least 2 of answers 1-3' as "
                f"({{Q}}:{{1}} AND {{Q}}:{{2}}) OR ({{Q}}:{{1}} AND {{Q}}:{{3}}) OR ({{Q}}:{{2}} AND {{Q}}:{{3}})"
            )

    return errors


# --------------------------------------------------------------------------
# Calculated variables: answer/row 'calculation', 'coded', 'period', 'categoryVariable'
# --------------------------------------------------------------------------

PERIOD_TYPES = ("Year", "HalfYear", "Quarter", "Month", "Week", "Day")
GENERATED_TYPES = ("period", "categoryVariable")

# a coded source: {Q}, {Grid}.N, {Row}, or a system id Q12 - optionally with an answer {id}, {0} or A<n>
_SOURCE_RE = re.compile(r"^\s*(?:\{([^{}]*)\}|([^\s.:{}]+))(?:\.(\d+))?\s*(?::\s*(?:\{([^{}]*)\}|A(\d+)))?\s*$")


def _coded_sources(coded) -> list:
    sources = coded.get("sources") if isinstance(coded, dict) else coded
    if isinstance(sources, str):
        return [sources]
    return sources if isinstance(sources, list) else []


def _is_computed(q: dict) -> bool:
    """True when the platform produces the question's values: calculated, coded, period, categoryVariable."""
    answers = [a for a in (q.get("answers") or []) if isinstance(a, dict)]
    rows = [r for r in (q.get("rows") or []) if isinstance(r, dict)]
    return (
        q.get("type") in GENERATED_TYPES
        or q.get("coded") is not None
        or bool(q.get("calculated"))
        or any("calculation" in a for a in answers)
        or any("calculation" in r or r.get("calculated") for r in rows)
    )


def _validate_rule(rule, is_open: bool, refs: _References, owner_position: int, where: str) -> list[str]:
    """One calculation rule: a string (the condition, or the value of an Open answer) or the long form."""
    errors: list[str] = []
    if isinstance(rule, str):
        parts = {"value" if is_open else "condition": rule}
    elif isinstance(rule, dict):
        parts = {k: rule[k] for k in ("condition", "value") if k in rule}
        if not parts:
            errors.append(f"{where}: a calculation object needs 'condition' and/or 'value'")
    else:
        return errors  # reported by the schema check
    if "value" in parts and not is_open:
        errors.append(f"{where}: 'value' is only valid on an Open answer - a normal answer is selected by its 'condition'")
    for key, text in parts.items():
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{where}: calculation {key} must be a non-empty string")
            continue
        for e in _validate_condition(text, refs, owner_position, is_value=(key == "value")):
            errors.append(f"{where}: calculation {key}: {e}")
    return errors


def _validate_coded_source(source, refs: _References, owner_position: int, where: str) -> list[str]:
    m = _SOURCE_RE.match(source) if isinstance(source, str) else None
    if not m:
        return [f"{where}: coded source {source!r} is not a reference - use {{Q}}, {{Grid}}.N, {{Q}}:{{0}}, {{Q}}:{{id}} or {{Q}}:A<n>"]
    ident = m.group(1) if m.group(1) is not None else m.group(2)
    ref = (ident, int(m.group(3)) if m.group(3) else None)
    q, row, position, error = refs.resolve(ref)
    if error:
        return [f"{where}: coded source {source!r} references {error}"]
    errors: list[str] = []
    if position >= owner_position:
        errors.append(f"{where}: coded source {source!r} is not placed before this question - sources must be earlier questions")
    answers = [a for a in (q.get("answers") or []) if isinstance(a, dict)]
    if q.get("type") != "open" and not any(a.get("type") == "Open" for a in answers):
        errors.append(f"{where}: coded source {source!r} has no open answers to code")
    answer_id, answer_position = m.group(4), m.group(5)
    if answer_id == "0":
        if not _has_own_open_answer(q):
            errors.append(f"{where}: coded source {source!r}: the question has no open answer of its own ({{0}})")
    elif answer_id is not None:
        a = next((a for a in answers if a.get("id") == answer_id), None)
        if a is None or a.get("type") != "Open":
            errors.append(f"{where}: coded source {source!r}: answer {{{answer_id}}} is not an Open answer of the question")
    elif answer_position is not None:
        numbered = _numbered_answers(q)
        n = int(answer_position)
        if not (1 <= n <= len(numbered) and numbered[n - 1].get("type") == "Open"):
            errors.append(f"{where}: coded source {source!r}: answer {n} is not an Open answer of the question")
    return errors


def _validate_calculated_variables(questions: list, refs: _References) -> list[str]:
    errors: list[str] = []
    for position, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        qid, qtype = q.get("id"), q.get("type")
        where = f"[semantics] question '{qid}'"
        answers = [a for a in (q.get("answers") or []) if isinstance(a, dict)]
        rows = [r for r in (q.get("rows") or []) if isinstance(r, dict)]
        coded = q.get("coded")
        is_generated = qtype in GENERATED_TYPES

        # the keys that say how the values are produced belong to one kind of question each
        if "period" in q and qtype != "period":
            errors.append(f"{where}: 'period' is only valid on type='period'")
        if "category" in q and qtype != "categoryVariable":
            errors.append(f"{where}: 'category' is only valid on type='categoryVariable' (a 'category' question is respondent background data)")
        if qtype == "period":
            period = q.get("period")
            period_type = period if isinstance(period, str) else period.get("periodType") if isinstance(period, dict) else None
            if period is None:
                errors.append(f"{where}: type='period' requires 'period', e.g. \"period\": \"Month\"")
            elif period_type not in PERIOD_TYPES:
                errors.append(f"{where}: period type {period_type!r} is not one of {', '.join(PERIOD_TYPES)}")
        if qtype == "categoryVariable":
            category = q.get("category")
            path = category if isinstance(category, str) else category.get("path") if isinstance(category, dict) else None
            if not isinstance(path, str) or not path.strip():
                errors.append(f"{where}: type='categoryVariable' requires 'category' with a category path, e.g. \"category\": \"org\"")

        for a in answers:
            aid = a.get("id")
            if is_generated:
                extra = sorted(set(a) - {"id", "color"})
                if extra:
                    errors.append(
                        f"{where}: answer '{aid}' has {', '.join(extra)} - answers of a {qtype} question are generated "
                        f"and only list report colours as {{\"id\", \"color\"}}"
                    )
                continue
            if "color" in a:
                errors.append(f"{where}: answer '{aid}': 'color' is only valid on answers of period and categoryVariable questions")
            if "codes" in a and coded is None:
                errors.append(f"{where}: answer '{aid}': 'codes' is only valid on a coded question")
            if "calculation" not in a:
                continue
            if coded is not None:
                errors.append(f"{where}: answer '{aid}': 'calculation' cannot be combined with 'coded'")
                continue
            if rows:
                errors.append(f"{where}: answer '{aid}': a grid's rules belong in each row's 'calculation' map, not on the answers")
                continue
            if _is_own_open_answer(a):
                errors.append(
                    f"{where}: answer '{aid}' is the question's own open answer, which cannot be calculated - "
                    f"use an Open answer with another id on a type='multiple' question"
                )
                continue
            errors.extend(_validate_rule(a["calculation"], a.get("type") == "Open", refs, position, f"{where} answer '{aid}'"))

        if is_generated:
            for key in ("coded", "calculated", "rows"):
                if key in q:
                    errors.append(f"{where}: '{key}' is not valid on type='{qtype}'")
            continue

        computed = coded is not None or bool(q.get("calculated")) or any("calculation" in a for a in answers) or any("calculation" in r or r.get("calculated") for r in rows)
        if computed and qtype not in ("single", "multiple"):
            errors.append(f"{where}: calculated and coded questions must be type 'single' or 'multiple' (got '{qtype}')")

        if coded is not None:
            if rows:
                errors.append(f"{where}: 'coded' is only supported on questions, not on grids")
            for source in _coded_sources(coded):
                errors.extend(_validate_coded_source(source, refs, position, where))

        answer_by_id = {a.get("id"): a for a in answers}
        for row in rows:
            rule_map = row.get("calculation")
            if not isinstance(rule_map, dict):
                continue
            for key, rule in rule_map.items():
                a = answer_by_id.get(key)
                if a is None:
                    errors.append(f"{where} row '{row.get('id')}': calculation key '{key}' is not an answer id of the grid")
                    continue
                errors.extend(_validate_rule(rule, a.get("type") == "Open", refs, position, f"{where} row '{row.get('id')}' answer '{key}'"))
    return errors


def _short_form_advice(questions: list) -> list[str]:
    """Long forms that hold nothing but their main key or default values, and redundant defaults:
    the short form is the expected one (it is what the export writes)."""
    advice: list[str] = []

    def rule_advice(rule, is_open: bool, where: str):
        if not isinstance(rule, dict):
            return
        if rule.get("disabled") is False:
            advice.append(f"{where}: 'disabled': false is the default - omit it")
        main = "value" if is_open else "condition"
        if set(rule) - {"disabled"} == {main} and not rule.get("disabled"):
            advice.append(f"{where}: use the short form \"calculation\": {json.dumps(rule[main])}")

    for q in questions:
        if not isinstance(q, dict):
            continue
        qid, qtype = q.get("id"), q.get("type")
        answers = [a for a in (q.get("answers") or []) if isinstance(a, dict)]
        rows = [r for r in (q.get("rows") or []) if isinstance(r, dict)]
        for a in answers:
            if "calculation" in a:
                rule_advice(a["calculation"], a.get("type") == "Open", f"question '{qid}' answer '{a.get('id')}'")
        answer_by_id = {a.get("id"): a for a in answers}
        for row in rows:
            for key, rule in (row.get("calculation") or {}).items() if isinstance(row.get("calculation"), dict) else []:
                rule_advice(rule, answer_by_id.get(key, {}).get("type") == "Open", f"question '{qid}' row '{row.get('id')}' answer '{key}'")
        if q.get("calculated") and (any("calculation" in a for a in answers) or any("calculation" in r for r in rows)):
            advice.append(f"question '{qid}': 'calculated': true is only needed when no answer or row has a calculation - omit it")

        coded = q.get("coded")
        if isinstance(coded, dict):
            defaults = {"matchMode": "search", "multipleCodes": qtype == "multiple"}
            redundant = [k for k, v in defaults.items() if k in coded and coded[k] == v]
            if redundant:
                advice.append(f"question '{qid}': coded {', '.join(redundant)} has the default value - omit it")
            if all(k == "sources" or k in redundant for k in coded):
                advice.append(f"question '{qid}': use the short form \"coded\": {json.dumps(coded.get('sources'))}")
        if isinstance(coded, list) and len(coded) == 1:
            advice.append(f"question '{qid}': one coded source is written as a string: \"coded\": {json.dumps(coded[0])}")

        for key, main, defaults in (
            ("period", "periodType", {"periodBase": "EventDate", "periodLength": 1}),
            ("category", "path", {"startLevel": 1, "sortPropertyName": "Order", "sortPropertyIsNumeric": False, "directConnections": False}),
        ):
            value = q.get(key)
            if not isinstance(value, dict):
                continue
            redundant = [k for k, v in defaults.items() if k in value and value[k] == v]
            if redundant:
                advice.append(f"question '{qid}': {key} {', '.join(redundant)} has the default value - omit it")
            if all(k == main or k in redundant for k in value):
                advice.append(f"question '{qid}': use the short form \"{key}\": {json.dumps(value.get(main))}")

        if qtype in GENERATED_TYPES and q.get("excluded") is True:
            advice.append(f"question '{qid}': {qtype} questions are hidden by default - omit 'excluded': true")
    return advice


# --------------------------------------------------------------------------
# Texts: formatting tags, {field} tokens, media, object form (format-questions.md "Texts")
# --------------------------------------------------------------------------

_TEXT_URL_RE = re.compile(r"^(?:~/|https?://|//|/|mailto:)", re.IGNORECASE)
_TEXT_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)(?:\s[^<>]*)?/?>")
_TEXT_TAGS = {"b", "i", "u", "a", "ul", "li", "br"}
_TEXT_BUILTINS = {"space", "empty", "company name", "companyname"}
# participant field names and ids the import recognises (spaces and case are ignored), plus data0, data1, ...
_PARTICIPANT_FIELDS = {
    "firstname", "lastname", "department", "alternateemail", "phonenumber", "phone", "companyphone",
    "externalreference", "externalid", "address1", "eventdate",
    "fname", "lname", "depart", "perphone", "comphone", "email", "email2", "extref", "extid", "title",
    "company", "comment", "address", "address2", "address3", "state", "city", "zip", "country", "evdate",
}
# an unknown token that looks like an id is reported - any other unknown token renders as plain text
_ID_TOKEN_RE = re.compile(r"[A-Za-z0-9_.]+")


def _plain_text(t) -> str | None:
    """The string of a text: a plain string, or the 'text' / 'html' of the object form."""
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        value = t.get("text", t.get("html"))
        return value if isinstance(value, str) else None
    return None


def _is_participant_field(name: str) -> bool:
    key = re.sub(r"\s", "", name).lower()
    return key in _PARTICIPANT_FIELDS or re.fullmatch(r"data\d+", key) is not None


def _token_end(s: str, start: int) -> int:
    """The index of the } that ends the token starting at s[start] == '{' - braces inside are counted. -1 if none."""
    depth = 0
    for j in range(start, len(s)):
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        elif c == "\n":
            return -1
    return -1


def _text_tokens(s: str) -> list[tuple[str, str]]:
    """The {token}s of a text, each with the character after it."""
    tokens = []
    i = 0
    while i < len(s):
        if s[i] == "{":
            end = _token_end(s, i)
            if end > i + 1:
                tokens.append((s[i + 1:end], s[end + 1:end + 2]))
                i = end + 1
                continue
        i += 1
    return tokens


def validate_semantics(data, existing: list | None = None) -> list[str]:
    """Checks that go beyond JSON Schema.
    existing: the questions of the project the file will be imported into (--existing) - expressions
    and coded sources may refer to them."""
    errors: list[str] = []

    # Mutual exclusion: a file represents either collected responses OR an
    # invite list of participants, never both. A participant has no answers;
    # a respondent already has them. Mixing them in one file is always a
    # modelling mistake — one of the two should be split off into its own file.
    if isinstance(data, dict):
        has_responses = isinstance(data.get("responses"), list) and len(data["responses"]) > 0
        has_participants = isinstance(data.get("participants"), list) and len(data["participants"]) > 0
        if has_responses and has_participants:
            errors.append(
                "[semantics] a file cannot contain both 'responses' and 'participants' — "
                "responses are people who have answered the survey, participants are "
                "people who have been invited but not yet answered. Pick one per file."
            )

    # Top-level key order: 'responses' and 'participants' are the "respondent
    # data" keys and whichever is present must be the LAST top-level key. The
    # other keys (questions, surveyMessages, messages) may appear in any order
    # before it. Relies on json.load preserving insertion order from the
    # source file, which Python's stdlib json module does.
    if isinstance(data, dict):
        keys = list(data.keys())
        for trailing_key in ("responses", "participants"):
            # Only check keys that are actually non-empty arrays — an empty
            # 'responses: []' before 'messages' is harmless boilerplate.
            v = data.get(trailing_key)
            if not (isinstance(v, list) and len(v) > 0):
                continue
            idx = keys.index(trailing_key)
            trailing = keys[idx + 1:]
            if trailing:
                errors.append(
                    f"[semantics] '{trailing_key}' must be the last top-level key, "
                    f"but is followed by: {', '.join(trailing)}"
                )

    questions = data.get("questions", [])
    responses = data.get("responses", [])
    participants = data.get("participants", [])

    # Collect valid keys and per-question answer ids
    question_by_id: dict[str, dict] = {}
    valid_response_keys: dict[str, dict] = {}  # key -> question definition
    matrix_row_ids: set[str] = set()
    # open grid cell key '<row id>:<answer id>' -> the row id, which is the other key of the same cell
    open_grid_cells: dict[str, str] = {}
    connected_open_keys: set[str] = set()
    # Keys eligible to appear in a participant object (system + category questions only)
    participant_eligible_keys: set[str] = set()

    VALID_TYPES = {"single", "multiple", "open", "header", "system", "category", "screenout", "error", "period", "categoryVariable"}

    # Declared group ids (form B: top-level 'groups' array + question 'groupId').
    declared_group_ids: set[str] = set()
    groups = data.get("groups")
    if groups is not None:
        if not isinstance(groups, list):
            errors.append("[semantics] top-level 'groups' must be an array")
        else:
            for gi, g in enumerate(groups):
                if not isinstance(g, dict):
                    continue
                gid = g.get("id")
                if gid in declared_group_ids:
                    errors.append(f"[semantics] duplicate group id: {gid}")
                if gid:
                    declared_group_ids.add(gid)

    for q in questions:
        qid = q.get("id")
        qtype = q.get("type")
        if qtype not in VALID_TYPES:
            errors.append(
                f"[semantics] question '{qid}': invalid type '{qtype}' "
                f"(must be one of: {', '.join(sorted(VALID_TYPES))}). "
                f"Note: matrix questions use type='single' with a 'rows' array, not type='matrix'."
            )
        if not qid:
            continue
        if qid in question_by_id:
            errors.append(f"[semantics] duplicate question id: {qid}")
        question_by_id[qid] = q

        # Grouping (optional). Two mutually exclusive forms:
        #   A. 'group'   — a plain label string; platform derives groups.
        #   B. 'groupId' — a reference into the top-level 'groups' array.
        if q.get("group") is not None and q.get("groupId") is not None:
            errors.append(
                f"[semantics] question '{qid}': set either 'group' (label string) "
                f"or 'groupId' (reference), not both"
            )
        gref = q.get("groupId")
        if gref is not None and gref not in declared_group_ids:
            errors.append(
                f"[semantics] question '{qid}': groupId '{gref}' does not match any "
                f"id in the top-level 'groups' array"
            )
        if q.get("layout") is not None and qtype != "header":
            errors.append(
                f"[semantics] question '{qid}': 'layout' is only valid on header items (got type='{qtype}')"
            )


        if qtype == "header":
            continue

        if qtype in ("screenout", "error"):
            # Flow-control items: require condition, forbid data-collection fields,
            # produce no response keys. The condition itself is validated in the
            # post-pass below (same as for regular questions).
            if not q.get("condition"):
                errors.append(
                    f"[semantics] {qtype} '{qid}': 'condition' is required — "
                    f"an unconditional {qtype} would fire for every respondent"
                )
            if not q.get("surveyText"):
                errors.append(
                    f"[semantics] {qtype} '{qid}': 'surveyText' is required — "
                    f"this is the message shown to the respondent when the {qtype} fires"
                )
            forbidden = [
                "min", "max", "answers", "rows", "interface",
                "randomAnswers", "scale", "scaleLeft", "scaleRight",
                "scaleDK", "excluded", "pagebreak",
            ]
            for field in forbidden:
                if q.get(field) is not None:
                    errors.append(
                        f"[semantics] {qtype} '{qid}': field '{field}' is not allowed on flow-control items"
                    )
            continue

        rows = q.get("rows")
        if rows:
            for n, row in enumerate(rows, 1):
                rid = row.get("id")
                if not rid:
                    continue
                # '<QuestionId>.<RowNumber>' is the normal row id. A row may instead have its own id
                # (a row reference, as exported), but '<QuestionId>.<n>' must then be its own position.
                numbered = re.fullmatch(re.escape(f"{qid}.") + r"(\d+)", rid)
                if numbered and int(numbered.group(1)) != n:
                    errors.append(
                        f"[semantics] row id '{rid}' in question '{qid}' is row {n} - use '{qid}.{n}'"
                    )
                if rid in valid_response_keys or rid in question_by_id:
                    errors.append(f"[semantics] duplicate row id: {rid}")
                valid_response_keys[rid] = q
                matrix_row_ids.add(rid)
                if qtype == "open":
                    # an open grid cell may also be keyed '<row id>:<answer id>'
                    for a in q.get("answers") or []:
                        if isinstance(a, dict) and a.get("type") == "Open" and a.get("id") is not None:
                            cell = f"{rid}:{a.get('id')}"
                            valid_response_keys[cell] = q
                            matrix_row_ids.add(cell)
                            open_grid_cells[cell] = rid
        else:
            valid_response_keys[qid] = q
            if qtype in ("system", "category"):
                participant_eligible_keys.add(qid)

        # Interface field validation
        iface = q.get("interface")
        # `noInterfaceValidation: true` suppresses the opinionated interface rules
        # below (long-label, short-list-should-be-buttons, missing dropdown
        # placeholder). Structural rules — vertical-needs-rows, dropdown is
        # single-only, placeholder only on dropdown — always apply, because
        # those describe invalid combinations rather than style advice.
        # Calculated variables are not shown to respondents - rendering advice doesn't apply.
        skip_iface_advice = bool(q.get("noInterfaceValidation")) or _is_computed(q)

        if iface == "vertical" and not rows:
            errors.append(
                f"[semantics] question '{qid}': interface='vertical' requires a 'rows' array (matrix questions only)."
            )
        if iface == "dropdown" and qtype != "single":
            errors.append(
                f"[semantics] question '{qid}': interface='dropdown' is only valid on type='single' (got '{qtype}')."
            )
        # Special grid interfaces. All of them are grid-only (require 'rows').
        #   slider   — choice slider over the answers (type 'single'), or a
        #              numeric slider (type 'open', one integer Open answer
        #              with minValue/maxValue as the slider ends).
        #   dragdrop — rows dragged into one box per answer (type 'single').
        #   ranking  — rows dragged into rank order (type 'single'); answers are
        #              the rank positions, so there can't be more than rows.
        #   alpha / numeric — automatic A,B,C / 1,2,3 legend (single or
        #              multiple grids). Rare; vertical/buttons are preferred.
        # These are structural rules and always apply.
        if iface in ("slider", "dragdrop", "ranking", "alpha", "numeric") and not rows:
            errors.append(
                f"[semantics] question '{qid}': interface='{iface}' is a grid interface and requires a 'rows' array."
            )
        if iface == "slider":
            sl_answers = q.get("answers") or []
            if qtype == "open":
                if (
                    len(sl_answers) != 1
                    or sl_answers[0].get("type") != "Open"
                    or sl_answers[0].get("dataType") != "integer"
                ):
                    errors.append(
                        f"[semantics] question '{qid}': a numeric slider (interface='slider' on type='open') "
                        f"needs exactly one answer with type='Open' and dataType='integer'."
                    )
                else:
                    a0 = sl_answers[0]
                    lo, hi = a0.get("minValue"), a0.get("maxValue")
                    if lo is None or hi is None:
                        errors.append(
                            f"[semantics] question '{qid}': a numeric slider needs both 'minValue' and "
                            f"'maxValue' on its Open answer (the slider's ends)."
                        )
                    else:
                        try:
                            if int(lo) >= int(hi):
                                errors.append(
                                    f"[semantics] question '{qid}': slider minValue ({lo}) must be below maxValue ({hi})."
                                )
                        except ValueError:
                            errors.append(
                                f"[semantics] question '{qid}': slider minValue/maxValue must be integer strings (got {lo!r}, {hi!r})."
                            )
            elif qtype != "single":
                errors.append(
                    f"[semantics] question '{qid}': interface='slider' is only valid on single-select grids "
                    f"(type='single') or numeric open grids (type='open'); got '{qtype}'."
                )
        if iface in ("dragdrop", "ranking") and qtype != "single":
            errors.append(
                f"[semantics] question '{qid}': interface='{iface}' is only valid on single-select grids "
                f"(type='single'); got '{qtype}'."
            )
        if iface == "ranking" and rows:
            n_ranks = len(q.get("answers") or [])
            if n_ranks > len(rows):
                errors.append(
                    f"[semantics] question '{qid}': ranking has {n_ranks} rank positions (answers) but only "
                    f"{len(rows)} rows — there can't be more ranks than items to rank."
                )
        if iface in ("alpha", "numeric") and qtype not in ("single", "multiple"):
            errors.append(
                f"[semantics] question '{qid}': interface='{iface}' is only valid on single/multiple grids; got '{qtype}'."
            )
        # minValue/maxValue only make sense on integer Open answers.
        for a in (q.get("answers") or []):
            if (a.get("minValue") is not None or a.get("maxValue") is not None) and (
                a.get("type") != "Open" or a.get("dataType") != "integer"
            ):
                errors.append(
                    f"[semantics] question '{qid}': minValue/maxValue on answer '{a.get('id')}' "
                    f"require type='Open' and dataType='integer'."
                )

        # Question-level placeholder is the empty-state prompt for a dropdown
        # ('Select a country…'). It is only meaningful there.
        q_placeholder = q.get("placeholder")
        if q_placeholder is not None and iface != "dropdown":
            errors.append(
                f"[semantics] question '{qid}': question-level 'placeholder' is only valid on "
                f"interface='dropdown' (got interface={iface!r}). "
                f"For open-text prompts, set 'placeholder' on the Open answer instead."
            )
        # Long labels don't fit in a button strip. If any answer label exceeds
        # 25 characters, interface='buttons' is almost always the wrong choice:
        # recommend 'vertical' for grids (has rows) and the default (drop the
        # interface) for non-grids. Suppressed by "noInterfaceValidation": true.
        if iface == "buttons" and not skip_iface_advice:
            long_labels = [
                _plain_text(a.get("text")) for a in (q.get("answers") or [])
                if len(_plain_text(a.get("text")) or "") > 25
            ]
            if long_labels:
                rec = "'vertical'" if rows else "no interface (the default)"
                example = max(long_labels, key=len)
                errors.append(
                    f"[semantics] question '{qid}': interface='buttons' has an answer "
                    f"label longer than 25 characters (e.g. '{example}', "
                    f"{len(example)} chars). Recommend {rec}. "
                    f"If buttons are intended anyway, set \"noInterfaceValidation\": true on the question."
                )
        # Inverse rule: a short, small answer set renders better as a button
        # strip than as default radios/checkboxes. When the interface is absent
        # and every answer label is under 15 chars with 6 or fewer answers,
        # recommend 'buttons'. Applies to closed-list questions and grids.
        # Excludes polarity Likert scales (scale/scaleLeft/scaleRight/scaleDK),
        # which are deliberately rendered as anchored scales, not buttons.
        # Suppressed by "noInterfaceValidation": true.
        is_polarity_scale = any(
            q.get(k) for k in ("scale", "scaleLeft", "scaleRight", "scaleDK")
        )
        if (
            iface is None
            and qtype in ("single", "multiple")
            and not skip_iface_advice
            and not is_polarity_scale
        ):
            answer_texts = [
                _plain_text(a.get("text")) for a in (q.get("answers") or [])
                if isinstance(_plain_text(a.get("text")), str)
            ]
            if (
                answer_texts
                and len(answer_texts) <= 6
                and all(len(t) < 15 for t in answer_texts)
            ):
                errors.append(
                    f"[semantics] question '{qid}': all {len(answer_texts)} answer labels "
                    f"are short (<15 chars) and there are 6 or fewer — recommend "
                    f"interface='buttons' instead of default rendering. "
                    f"To keep the default, set \"noInterfaceValidation\": true on the question."
                )

        # Answer id uniqueness per question + connectedTo validation
        answers = q.get("answers", []) or []
        connected_opens = [a for a in answers if a.get("connectedTo") is not None]
        if len(connected_opens) == 1 and str(connected_opens[0].get("id")) != "0":
            errors.append(
                f"[semantics] question '{qid}': the connected Open answer must have id \"0\" "
                f"(got '{connected_opens[0].get('id')}'), as the platform stores it. "
                f"Put it first in the answers list; the Other option keeps its own id."
            )
        seen = set()
        sibling_ids = {a.get("id") for a in answers if a.get("id") is not None}
        for a in answers:
            aid = a.get("id")
            if aid is None:
                continue
            if aid in seen:
                errors.append(f"[semantics] duplicate answer id '{aid}' in question '{qid}'")
            seen.add(aid)
            ct = a.get("connectedTo")
            if ct is not None:
                if a.get("type") != "Open":
                    errors.append(f"[semantics] question '{qid}': connectedTo only allowed on Open answers (answer id '{aid}')")
                if ct not in sibling_ids:
                    errors.append(f"[semantics] question '{qid}': connectedTo='{ct}' on answer '{aid}' does not reference a sibling answer id")
                else:
                    # Register the connected-Open response key
                    valid_response_keys[f"{qid}.{ct}"] = q
                    connected_open_keys.add(f"{qid}.{ct}")

            # 'exclusive' only makes sense on multiple-choice questions
            if a.get("exclusive") is not None and qtype != "multiple":
                errors.append(
                    f"[semantics] question '{qid}': 'exclusive' on answer '{aid}' is only meaningful on type='multiple' questions (got type='{qtype}')"
                )

        # min/max sanity
        mn, mx = q.get("min"), q.get("max")
        if mn is not None and mx is not None and mn > mx:
            errors.append(f"[semantics] question '{qid}': min ({mn}) > max ({mx})")

        # Scale rules:
        # 1. 'Ordinal' (capital O) is the only defined value for 'scale' —
        #    catch casing slips ('ordinal') and typos early.
        # 2. Answers tagged Positive/Negative are scale anchors, which only
        #    make sense on an ordered scale — so any question carrying them
        #    MUST declare scale: "Ordinal". This is a hard rule, not style
        #    advice, and is therefore NOT suppressed by noInterfaceValidation.
        scale_val = q.get("scale")
        if scale_val is not None and scale_val != "Ordinal":
            errors.append(
                f"[semantics] question '{qid}': scale='{scale_val}' is not a valid value — "
                f"the only defined scale type is 'Ordinal' (note the capital O)."
            )
        anchor_tags = {
            a.get("type") for a in answers
            if a.get("type") in ("Positive", "Negative")
        }
        if anchor_tags and scale_val != "Ordinal":
            tags = "/".join(sorted(anchor_tags))
            errors.append(
                f"[semantics] question '{qid}': has answers tagged {tags} (scale anchors) "
                f"but no scale: \"Ordinal\". Questions whose answers form an ordered sequence "
                f"must set scale: \"Ordinal\"."
            )

        # Anchored-scale label rule (opinionated, suppressed by noInterfaceValidation):
        # when scaleLeft/scaleRight are set, the answers are points on a spectrum
        # and every answer text must be compact (<= 2 chars, e.g. '1'-'10', '?').
        # The error message computes WHICH remediation applies so the fix is
        # mechanical:
        #   A: only the first/last answers are long -> their labels belong in
        #      scaleLeft/scaleRight (existing anchors take precedence).
        #   C: only middle answers are long -> keep anchors, use interface
        #      'vertical' with numeric symbolText.
        #   B: long answers at both edge and middle -> drop the anchors and
        #      render as buttons/vertical instead.
        # The DontKnow answer is checked too, but with its own recipe: its
        # text/symbolText must be '?' and the label belongs in scaleDK.
        if (q.get("scaleLeft") or q.get("scaleRight")) and not skip_iface_advice:
            non_dk = [a for a in answers if a.get("type") != "DontKnow"]
            for a in answers:
                if a.get("type") == "DontKnow" and len(_plain_text(a.get("text")) or "") > 2:
                    errors.append(
                        f"[semantics] question '{qid}': DontKnow answer text "
                        f"'{a.get('text')}' is too long for an anchored scale — set its "
                        f"text and symbolText to '?' and put the label in scaleDK. "
                        f"To keep it, set \"noInterfaceValidation\": true."
                    )
            long_idx = {
                i for i, a in enumerate(non_dk)
                if len(_plain_text(a.get("text")) or "") > 2
            }
            edges = {0, len(non_dk) - 1} if non_dk else set()
            if long_idx and long_idx <= edges:
                recipes = []
                for pos, field in ((0, "scaleLeft"), (len(non_dk) - 1, "scaleRight")):
                    if pos not in long_idx:
                        continue
                    a = non_dk[pos]
                    existing = q.get(field)
                    if existing and existing != a.get("text"):
                        recipes.append(
                            f"{field}='{existing}' takes precedence — replace answer "
                            f"'{a.get('id')}''s text '{a.get('text')}' with a compact "
                            f"numeral (mirrored in symbolText)"
                        )
                    else:
                        recipes.append(
                            f"move answer '{a.get('id')}''s text '{a.get('text')}' into "
                            f"{field} and replace the answer text with a compact numeral "
                            f"(mirrored in symbolText)"
                        )
                errors.append(
                    f"[semantics] question '{qid}': anchored scale (scaleLeft/scaleRight) "
                    f"has answer texts longer than 2 characters — {'; '.join(recipes)}. "
                    f"To keep them, set \"noInterfaceValidation\": true."
                )
            elif long_idx and not (long_idx & edges):
                errors.append(
                    f"[semantics] question '{qid}': anchored scale has long middle answer "
                    f"text(s) (e.g. '{non_dk[min(long_idx)].get('text')}') — keep "
                    f"scaleLeft/scaleRight, set interface: \"vertical\" and give every "
                    f"answer a numeric symbolText. "
                    f"To keep the current rendering, set \"noInterfaceValidation\": true."
                )
            elif long_idx:
                all_texts = [_plain_text(a.get("text")) or "" for a in answers]
                if len(answers) <= 6 and all(len(t) <= 25 for t in all_texts):
                    rec = "\"buttons\""
                elif rows:
                    rec = "\"vertical\""
                else:
                    rec = "no interface (the default)"
                errors.append(
                    f"[semantics] question '{qid}': anchored scale has multiple long "
                    f"answer texts — remove scaleLeft/scaleRight/scaleDK, keep "
                    f"scale: \"Ordinal\", use {rec}, and give any DontKnow answer a "
                    f"readable text. "
                    f"To keep the anchors, set \"noInterfaceValidation\": true."
                )

        # Non-header questions should have answers, EXCEPT open questions,
        # which may legitimately omit the answers array entirely (a single
        # implicit Open box with id 0).
        if qtype in ("single", "multiple") and not answers:
            errors.append(f"[semantics] question '{qid}' of type '{qtype}' has no answers array")

        # A type='open' question is a single free-text box. It must either:
        #   - have NO answers array (the box is implicit, id 0), or
        #   - contain exactly one answer, of type 'Open', with id == 0.
        # Anything else — multiple Open answers, a non-zero id, a non-Open
        # type, or extra answers — must instead be modeled as type='multiple'
        # (which may carry any number of Open answers with any ids).
        # (multi/single questions may also contain Open answers — those are
        # the "connected" free-text inputs attached to an Other option, and
        # are validated separately above.)
        # An open question with rows is an open grid (e.g. a numeric grid): exactly
        # one Open answer, with an id other than 0 - the import drops an Open
        # answer with id 0 in a grid, which leaves the grid without inputs.
        if qtype == "open" and q.get("rows"):
            if len(answers) != 1 or answers[0].get("type") != "Open":
                errors.append(
                    f"[semantics] open grid '{qid}' (an open question with rows) must have exactly one answer, "
                    f"of type='Open' with id '1'; found {len(answers)} answers."
                )
            elif str(answers[0].get("id")) == "0":
                errors.append(
                    f"[semantics] open grid '{qid}': its Open answer must not have id 0 - use id '1'. "
                    f"In a grid an Open answer with id 0 is dropped on import, and the grid gets no inputs."
                )
        elif qtype == "open":
            if not answers:
                pass  # implicit single open box with id 0 — fine
            elif len(answers) != 1:
                errors.append(
                    f"[semantics] open question '{qid}' must have either no answers "
                    f"or exactly one answer of type='Open' with id 0; found {len(answers)} answers. "
                    f"Use type='multiple' for multiple open-ended answers in one question."
                )
            else:
                a = answers[0]
                atype, aid = a.get("type"), a.get("id")
                if atype != "Open":
                    errors.append(
                        f"[semantics] open question '{qid}': its single answer must have type='Open' (got '{atype}')"
                    )
                if aid != 0 and str(aid) != "0":
                    errors.append(
                        f"[semantics] open question '{qid}': its single Open answer must have id 0 (got '{aid}'). "
                        f"Use type='multiple' for open-ended answers with non-zero ids."
                    )

    # Expressions and coded sources refer to the file's questions and rows, and to --existing ones
    refs = _References(questions, existing)

    # Calculated variables (post-pass so all question + row ids are known)
    errors.extend(_validate_calculated_variables(questions, refs))

    # Validate conditions (post-pass so all question + row ids are known)
    for q in questions:
        cond = q.get("condition")
        if not cond:
            continue
        qid = q.get("id")
        if not isinstance(cond, dict):
            errors.append(f"[semantics] question '{qid}': 'condition' must be an object")
            continue
        definition = cond.get("definition")
        if not definition or not isinstance(definition, str):
            errors.append(f"[semantics] question '{qid}': condition.definition is required and must be a string")
            continue
        cond_errors = _validate_condition(definition, refs)
        for e in cond_errors:
            errors.append(f"[semantics] question '{qid}': condition: {e}")

    # Validate texts and their bookmarks (post-pass so question ordering is known).
    # A text is a string or an object {"text" | "html", "fields"} (format-questions.md "Texts").
    # Its {tokens}: a field of "fields", a URL (picture, video, sound, link),
    # SPACE / EMPTY / Company name, a bookmark {Q} / {Q.1} / {Q:3} (open answer 3,
    # 0 = the question's own open answer), or a participant field ({First name}).
    # A bookmark's resolution depends on the TARGET item's type:
    #   - single / multiple / open  -> a data question; must sit on an EARLIER PAGE
    #     than the referencing text (at least one pagebreak=true between them), since
    #     a page's answers aren't available until that page is submitted.
    #   - category / system         -> background/sample data, always available; no
    #     page-break requirement.
    #   - header / screenout / error -> nothing to pipe; never a valid target.
    # An unknown token renders as plain text, but an unknown id or a wrong-type/same-
    # page target is an authoring mistake worth flagging. The {Q}:{A} condition-atom
    # form is NOT a bookmark and is skipped here.
    _BOOKMARK_DATA_TYPES = {"single", "multiple", "open"}
    _BOOKMARK_BACKGROUND_TYPES = {"category", "system"}
    question_order = {q.get("id"): idx for idx, q in enumerate(questions) if q.get("id")}
    question_type = {q.get("id"): q.get("type") for q in questions if q.get("id")}
    # row id ('Q.1' or a row's own id) -> the id of its matrix question
    row_owner = {
        row.get("id"): q.get("id")
        for q in questions if q.get("id")
        for row in (q.get("rows") or []) if isinstance(row, dict) and row.get("id")
    }
    # pagebreaks_before[i] = number of pagebreak=true items at index < i
    pagebreaks_before = [0] * (len(questions) + 1)
    for i, q in enumerate(questions):
        pagebreaks_before[i + 1] = pagebreaks_before[i] + (1 if q.get("pagebreak") else 0)

    def _question_of(ident: str):
        """The question id of a question or row id, or None."""
        if ident in question_order:
            return ident
        return row_owner.get(ident) or (ident.split(".")[0] if ident.split(".")[0] in question_order else None)

    def _check_target(token: str, base: str, where: str, owner_idx) -> None:
        # owner_idx is the index of the item carrying the text, or None for
        # surveyMessages (shown at end of flow, so the page-break rule is moot).
        ttype = question_type.get(base)
        if ttype in _BOOKMARK_BACKGROUND_TYPES:
            return  # always available, no page-break requirement
        if ttype not in _BOOKMARK_DATA_TYPES:
            errors.append(
                f"[semantics] {where}: bookmark '{{{token}}}' references '{base}' of type "
                f"'{ttype}', which has no answer to pipe (only single/multiple/open "
                f"questions or category/system fields can be bookmarked)"
            )
            return
        if owner_idx is None:
            return  # surveyMessages: target is a data question, always reached
        target_idx = question_order[base]
        # A page break must occur after the target, up to and including owner.
        if pagebreaks_before[owner_idx + 1] <= pagebreaks_before[target_idx + 1]:
            errors.append(
                f"[semantics] {where}: bookmark '{{{token}}}' references question '{base}' "
                f"on the same page (need a pagebreak between them — bookmarks only pipe answers from earlier pages)"
            )

    def _check_answer_field(token: str, question: str, answer, where: str, owner_idx) -> None:
        """{Q}, {Q.1} or {Q:answer}: the answer's question must exist, the open answer too."""
        base = _question_of(question)
        if base is None:
            errors.append(f"[semantics] {where}: bookmark '{{{token}}}' references unknown question id '{question}'")
            return
        if answer is not None:
            answer = str(answer)
            q = questions[question_order[base]]
            if answer == "0":
                found = _has_own_open_answer(q)
            else:
                found = any(
                    isinstance(a, dict) and a.get("type") == "Open" and str(a.get("id")) == answer
                    for a in (q.get("answers") or [])
                )
            if not found:
                errors.append(
                    f"[semantics] {where}: '{{{token}}}': question '{base}' has no open answer '{answer}'"
                    + (" (0 is the question's own open answer)" if answer == "0" else "")
                )
                return
        _check_target(token, base, where, owner_idx)

    def _check_field_text(d: dict, prop: str, where: str) -> None:
        """A field's own text (conditionalText text, link text, altText) is shown as written: no nesting."""
        t = d.get(prop)
        if t is None:
            return
        if isinstance(t, dict):
            errors.append(
                f"[semantics] {where}: '{prop}' must be a plain string - fields cannot be nested. "
                f"Put the parts as sibling fields with the same condition (see texts.md)."
            )
            return
        if not isinstance(t, str):
            return
        for m in _TEXT_TAG_RE.finditer(t):
            if m.group(2).lower() not in _TEXT_TAGS:
                errors.append(f"[semantics] {where}: <{m.group(2)}> is not a formatting tag - it would show as text.")
                break
        for token, after in _text_tokens(t):
            if after == ":":
                continue
            errors.append(
                f"[semantics] {where}: '{{{token}}}' in '{prop}' is not replaced - bookmarks and fields cannot be "
                f"nested inside a field. Give it its own sibling field with the same condition (see texts.md, "
                f"'Conditional content that contains a bookmark')."
            )

    def _check_field(key: str, d, where: str, owner_idx) -> None:
        """A field of a text's "fields" (its structure is checked by the schema)."""
        if not isinstance(d, dict):
            return
        ftype = d.get("type")
        where = f"{where} field '{key}'"
        if ftype == "answer":
            if not d.get("question"):
                errors.append(f"[semantics] {where}: 'question' is required")
            else:
                _check_answer_field(key, d["question"], d.get("answer"), where, owner_idx)
        elif ftype == "participant":
            name = d.get("field") or ""
            if not (_is_participant_field(name) or question_type.get(name) == "system"):
                errors.append(f"[semantics] {where}: unknown participant field '{name}'")
        elif ftype == "category":
            if not d.get("category"):
                errors.append(f"[semantics] {where}: 'category' is required")
        elif ftype in ("picture", "video", "sound", "link"):
            if not d.get("url"):
                errors.append(f"[semantics] {where}: 'url' is required")
            _check_field_text(d, "text", where)
            _check_field_text(d, "altText", where)
        elif ftype == "conditionalText":
            if not _plain_text(d.get("text")):
                errors.append(f"[semantics] {where}: 'text' is required")
            _check_field_text(d, "text", where)
        condition = d.get("condition")
        if isinstance(condition, str):
            for e in _validate_condition(condition, refs):
                errors.append(f"[semantics] {where}: condition: {e}")

    def _check_text(t, where: str, owner_idx) -> None:
        if t is None:
            return
        fields = {}
        is_html = False
        if isinstance(t, dict):
            if ("text" in t) == ("html" in t):
                errors.append(f"[semantics] {where}: a text object needs exactly one of 'text' and 'html'")
            is_html = "html" in t
            if isinstance(t.get("fields"), dict):
                fields = t["fields"]
        s = _plain_text(t)
        if not isinstance(s, str):
            return
        if not is_html:
            for m in _TEXT_TAG_RE.finditer(s):
                if m.group(2).lower() not in _TEXT_TAGS:
                    errors.append(
                        f"[semantics] {where}: <{m.group(2)}> is not a formatting tag "
                        f"(b, i, u, a href, ul, li) - it would show as text. For HTML code use {{\"html\": \"...\"}}."
                    )
                    break
        for token, after in _text_tokens(s):
            if after == ":":
                continue  # the {Q}:{A} condition-atom form, not a field
            name = token.strip()
            if name in fields:
                _check_field(name, fields[name], where, owner_idx)
            elif _TEXT_URL_RE.match(name) or name.lower() in _TEXT_BUILTINS:
                continue
            elif ":" in name and _question_of(name.rsplit(":", 1)[0].strip()) is not None:
                question, answer = name.rsplit(":", 1)
                _check_answer_field(name, question.strip(), answer.strip(), where, owner_idx)
            elif _question_of(name) is not None:
                _check_answer_field(name, name, None, where, owner_idx)
            elif _is_participant_field(name):
                continue
            elif not is_html and _ID_TOKEN_RE.fullmatch(name):
                errors.append(
                    f"[semantics] {where}: bookmark '{{{name}}}' references unknown question id '{name.split('.')[0]}'"
                )
            # anything else - and any unknown token in HTML code, e.g. CSS - is plain text

    for idx, q in enumerate(questions):
        qid = q.get("id")
        # 'text' is the respondent text too when there is no 'surveyText'
        _check_text(q.get("surveyText", q.get("text")), f"question '{qid}' {'surveyText' if 'surveyText' in q else 'text'}", idx)
        for prop in ("comment", "scaleLeft", "scaleRight", "scaleDK"):
            _check_text(q.get(prop), f"question '{qid}' {prop}", idx)
        for ans in (q.get("answers") or []):
            for prop in ("text", "surveyText", "symbolText"):
                _check_text(ans.get(prop), f"question '{qid}' answer '{ans.get('id')}' {prop}", idx)
        for row in (q.get("rows") or []):
            for prop in ("text", "surveyText"):
                _check_text(row.get(prop), f"question '{qid}' row '{row.get('id')}' {prop}", idx)

    # surveyMessages are shown at end of flow: existence and target-type checks
    # apply, but the page-break rule does not (owner_idx=None).
    survey_messages = data.get("surveyMessages")
    if isinstance(survey_messages, dict):
        for mkey, mval in survey_messages.items():
            if isinstance(mval, dict):
                for skey in ("header", "body", "footer"):
                    _check_text(mval.get(skey), f"surveyMessages '{mkey}.{skey}'", None)

    # Validate responses
    for i, resp in enumerate(responses):
        if not isinstance(resp, dict):
            errors.append(f"[semantics] response[{i}] is not an object")
            continue
        # Ranking grids: each rank position (answer id) may go to one row only.
        _rank_seen = {}
        for key, value in resp.items():
            rq = valid_response_keys.get(key)
            if rq is None or key not in matrix_row_ids or rq.get("interface") != "ranking":
                continue
            seen_key = (rq.get("id"), value)
            if seen_key in _rank_seen:
                errors.append(
                    f"[semantics] response[{i}]: rank '{value}' on ranking grid '{rq.get('id')}' is given to "
                    f"both '{_rank_seen[seen_key]}' and '{key}' — each rank can be used once."
                )
            else:
                _rank_seen[seen_key] = key
        for key, value in resp.items():
            if key not in valid_response_keys:
                errors.append(
                    f"[semantics] response[{i}] has unknown key '{key}' (no matching question or row id)"
                )
                continue
            if key in open_grid_cells and open_grid_cells[key] in resp:
                errors.append(
                    f"[semantics] response[{i}] has both '{open_grid_cells[key]}' and '{key}' - "
                    f"they are the same open grid cell, use one key"
                )
            if not isinstance(value, str):
                errors.append(
                    f"[semantics] response[{i}]['{key}'] must be a string, got {type(value).__name__}"
                )
                continue

            q = valid_response_keys[key]
            if key in connected_open_keys:
                # Free-text value attached to an Other option — no further validation
                continue
            qtype = q.get("type")
            if qtype == "categoryVariable":
                errors.append(
                    f"[semantics] response[{i}]['{key}']: a categoryVariable question has no response values"
                )
                continue
            # 'period' values are period texts such as '2025-03' - any string is accepted
            answers = q.get("answers", []) or []
            answer_ids = {a.get("id") for a in answers}

            if key in matrix_row_ids:
                # Matrix row. How a cell is keyed depends on the parent question:
                #   - shared answer is type 'Open'  -> respondent-typed value:
                #       free text, or an integer when dataType='integer'.
                #   - type 'multiple'               -> semicolon-separated list of
                #       answer ids (same rule as a flat 'multiple'), honouring the
                #       question's per-cell min/max.
                #   - otherwise (type 'single')     -> a single answer id from the
                #       shared scale.
                shared_open = (
                    len(answers) == 1 and answers[0].get("type") == "Open"
                )
                if shared_open:
                    # Numeric / open grid: the cell stores the typed value.
                    if answers[0].get("dataType") == "integer":
                        try:
                            ival = int(value)
                        except ValueError:
                            errors.append(
                                f"[semantics] response[{i}]['{key}']='{value}' is not a valid integer for numeric grid '{q.get('id')}'"
                            )
                        else:
                            lo, hi = answers[0].get("minValue"), answers[0].get("maxValue")
                            try:
                                if lo is not None and ival < int(lo):
                                    errors.append(
                                        f"[semantics] response[{i}]['{key}']={value} is below minValue={lo} for grid '{q.get('id')}'"
                                    )
                                if hi is not None and ival > int(hi):
                                    errors.append(
                                        f"[semantics] response[{i}]['{key}']={value} is above maxValue={hi} for grid '{q.get('id')}'"
                                    )
                            except ValueError:
                                pass  # malformed bounds are reported on the question
                    # free-text Open cell: any string is acceptable
                elif qtype == "multiple":
                    # Multi-select grid: each cell is a ';'-separated list of ids.
                    parts = value.split(";") if value else []
                    for p in parts:
                        if p not in answer_ids:
                            errors.append(
                                f"[semantics] response[{i}]['{key}']: answer id '{p}' not found in multi-select grid '{q.get('id')}'"
                            )
                    mn, mx = q.get("min"), q.get("max")
                    if mn is not None and len(parts) < mn:
                        errors.append(
                            f"[semantics] response[{i}]['{key}']: {len(parts)} selections is below min={mn}"
                        )
                    if mx is not None and len(parts) > mx:
                        errors.append(
                            f"[semantics] response[{i}]['{key}']: {len(parts)} selections exceeds max={mx}"
                        )
                elif value not in answer_ids:
                    errors.append(
                        f"[semantics] response[{i}]['{key}']='{value}' is not a valid answer id for matrix question '{q.get('id')}'"
                    )
            elif qtype == "single":
                if value not in answer_ids:
                    errors.append(
                        f"[semantics] response[{i}]['{key}']='{value}' is not a valid answer id for question '{key}'"
                    )
            elif qtype == "category":
                # Category values are checked against the answers list when one is
                # defined; free-text categories (no 'answers') accept any string.
                if answers and value not in answer_ids:
                    errors.append(
                        f"[semantics] response[{i}]['{key}']='{value}' is not a valid answer id for category question '{key}'"
                    )
            elif qtype == "multiple":
                parts = value.split(";") if value else []
                for p in parts:
                    if p not in answer_ids:
                        errors.append(
                            f"[semantics] response[{i}]['{key}']: answer id '{p}' not found in question '{key}'"
                        )
                mn, mx = q.get("min"), q.get("max")
                if mn is not None and len(parts) < mn:
                    errors.append(
                        f"[semantics] response[{i}]['{key}']: {len(parts)} selections is below min={mn}"
                    )
                if mx is not None and len(parts) > mx:
                    errors.append(
                        f"[semantics] response[{i}]['{key}']: {len(parts)} selections exceeds max={mx}"
                    )
            elif qtype == "open":
                # Integer open questions must parse as int
                if answers and answers[0].get("dataType") == "integer":
                    try:
                        int(value)
                    except ValueError:
                        errors.append(
                            f"[semantics] response[{i}]['{key}']='{value}' is not a valid integer"
                        )
            elif qtype == "system":
                # Most system fields are free-form, but a few platform-recognised
                # ones carry a known shape. Match case-insensitively on the key.
                norm = _normalize_token(key)
                if norm == "statustext":
                    if value not in SYSTEM_STATUS_VALUES:
                        errors.append(
                            f"[semantics] response[{i}]['{key}']='{value}' is not a valid "
                            f"StatusText (expected one of: {', '.join(sorted(SYSTEM_STATUS_VALUES))})"
                        )
                elif norm in ("endtime", "starttime"):
                    if not re.fullmatch(r"\d{14}", value):
                        errors.append(
                            f"[semantics] response[{i}]['{key}']='{value}' is not a valid "
                            f"timestamp — expected 14 digits YYYYMMDDHHMMSS (e.g. '20240814160018')"
                        )

    # Validate participants
    # Participants are pre-loaded invitees: each object may only contain keys
    # that reference 'system' or 'category' questions. Survey-question keys
    # (single/multiple/open/matrix rows/connected-Open) are rejected.
    for i, p in enumerate(participants):
        if not isinstance(p, dict):
            errors.append(f"[semantics] participant[{i}] is not an object")
            continue
        for key, value in p.items():
            if key not in valid_response_keys:
                errors.append(
                    f"[semantics] participant[{i}] has unknown key '{key}' (no matching question id)"
                )
                continue
            if key not in participant_eligible_keys:
                bad_q = valid_response_keys[key]
                errors.append(
                    f"[semantics] participant[{i}]['{key}']: participants may only contain "
                    f"'system' or 'category' question keys (got type='{bad_q.get('type')}')"
                )
                continue
            if not isinstance(value, str):
                errors.append(
                    f"[semantics] participant[{i}]['{key}'] must be a string, got {type(value).__name__}"
                )
                continue

            q = valid_response_keys[key]
            if q.get("type") == "category":
                answers = q.get("answers", []) or []
                if answers:
                    answer_ids = {a.get("id") for a in answers}
                    if value not in answer_ids:
                        errors.append(
                            f"[semantics] participant[{i}]['{key}']='{value}' is not a valid answer id for category question '{key}'"
                        )
            # 'system' values: free-form strings, no further checks.

    # Validate surveyMessages
    # An optional top-level object holding platform-level message overrides.
    # Five keys are allowed; each is an object with header/body/footer (all
    # optional strings). surveyComplete additionally allows redirectURL.
    sm = data.get("surveyMessages")
    if sm is not None:
        if not isinstance(sm, dict):
            errors.append(f"[semantics] surveyMessages must be an object, got {type(sm).__name__}")
        else:
            VALID_MESSAGE_KEYS = {
                "surveyComplete", "screenedOut", "invalidPassword",
                "alreadyCompleted", "surveyClosed",
            }
            BASE_FIELDS = {"header", "body", "footer"}
            for mkey, mval in sm.items():
                if mkey not in VALID_MESSAGE_KEYS:
                    errors.append(
                        f"[semantics] surveyMessages: unknown key '{mkey}' "
                        f"(allowed: {', '.join(sorted(VALID_MESSAGE_KEYS))})"
                    )
                    continue
                if not isinstance(mval, dict):
                    errors.append(
                        f"[semantics] surveyMessages.{mkey} must be an object, "
                        f"got {type(mval).__name__}"
                    )
                    continue
                allowed = BASE_FIELDS | ({"redirectURL"} if mkey == "surveyComplete" else set())
                for fkey, fval in mval.items():
                    if fkey not in allowed:
                        if fkey == "redirectURL":
                            errors.append(
                                f"[semantics] surveyMessages.{mkey}: 'redirectURL' is only "
                                f"allowed on 'surveyComplete'"
                            )
                        else:
                            errors.append(
                                f"[semantics] surveyMessages.{mkey}: unknown field '{fkey}' "
                                f"(allowed: {', '.join(sorted(allowed))})"
                            )
                        continue
                    # header/body/footer are texts: a string or the object form; redirectURL is a string
                    if not isinstance(fval, str) and not (fkey != "redirectURL" and isinstance(fval, dict)):
                        errors.append(
                            f"[semantics] surveyMessages.{mkey}.{fkey} must be "
                            f"{'a string' if fkey == 'redirectURL' else 'a text (a string or a text object)'}, "
                            f"got {type(fval).__name__}"
                        )

    # Validate outbound messages (the top-level `messages` array — invitations,
    # reminders, thank-yous, notifications). This is unrelated to surveyMessages
    # (end-of-flow screens) — different concept, similar name.
    errors.extend(_validate_messages(data, question_by_id))

    return errors


# Reserved merge tokens (case-insensitive). These are built into every message
# by the platform and don't need a corresponding question.
RESERVED_MERGE_TOKENS = {"dslink", "optouturl", "dspwd", "dspwdnum"}

# Allowed values for the platform's built-in StatusText system field.
SYSTEM_STATUS_VALUES = {"Completed", "Started", "Screenout"}

VALID_SEND_TYPES = {"invitation", "reminder", "thanks", "notification"}
VALID_MESSAGE_TYPES = {"email", "sms"}

EMAIL_BODY_FIELDS = {
    "subject", "title", "bodyBeforeLink", "linkLabel",
    "bodyAfterLink", "footer", "optOutLabel",
}
EMAIL_REQUIRED_FIELDS = {"subject", "bodyBeforeLink", "linkLabel"}
SMS_BODY_FIELDS = {"body"}
SMS_REQUIRED_FIELDS = {"body"}

# Token regex: #SomeName# — letters, digits, spaces, underscores between hashes.
_TOKEN_RE = re.compile(r"#([A-Za-z0-9 _]+)#")


def _extract_tokens(text: str) -> list[str]:
    """Return all #...# merge tokens found in text, in order, raw (without #s)."""
    if not isinstance(text, str):
        return []
    return _TOKEN_RE.findall(text)


def _normalize_token(tok: str) -> str:
    """Lowercase + strip whitespace for case-insensitive, whitespace-insensitive match."""
    return tok.replace(" ", "").replace("_", "").lower()


def _validate_message_condition(definition: str) -> list[str]:
    """Validate a message condition definition.

    Stricter than question conditions: only {Q}:{A} atoms combined with
    AND / OR and parentheses. No arithmetic, no comparisons.
    """
    errors: list[str] = []
    if not isinstance(definition, str) or not definition.strip():
        errors.append("condition.definition must be a non-empty string")
        return errors

    # Reuse the existing tokenizer to check overall structure, but reject
    # any token kinds that aren't allowed in message conditions.
    tokens, tok_errs = _tokenize_condition(definition)
    errors.extend(tok_errs)

    disallowed_kinds = {"CMP", "ARITH", "NUM", "PREF", "NOT", "ROW", "VREF"}
    for kind, val in tokens:
        if kind in disallowed_kinds:
            errors.append(
                f"condition.definition contains '{val}' — message conditions "
                f"only support {{Q}}:{{A}} atoms combined with AND/OR and parentheses"
            )

    # Walk REF COLON REF structure to make sure atoms are well-formed.
    # The existing tokenizer emits REF, COLON, REF for an atom {Q}:{A}.
    i = 0
    while i < len(tokens):
        kind, val = tokens[i]
        if kind == "REF":
            # Expect: REF COLON REF
            if i + 2 >= len(tokens) or tokens[i + 1][0] != "COLON" or tokens[i + 2][0] != "REF":
                errors.append(
                    f"condition.definition: malformed atom near '{{{val}}}' "
                    f"— expected '{{QuestionId}}:{{AnswerId}}'"
                )
            i += 3
        else:
            i += 1
    return errors


def _validate_messages(data, question_by_id: dict) -> list[str]:
    errors: list[str] = []
    messages = data.get("messages")
    if messages is None:
        return errors
    if not isinstance(messages, list):
        errors.append(
            f"[semantics] messages must be an array, got {type(messages).__name__}"
        )
        return errors

    # Build lookups of system question id/text (whitespace-stripped, lowercased)
    # for merge-field resolution.
    system_keys: set[str] = set()
    for q in question_by_id.values():
        if q.get("type") == "system":
            for attr in ("id", "text"):
                v = q.get(attr)
                if isinstance(v, str) and v:
                    system_keys.add(_normalize_token(v))

    # Recipient-field requirements. The platform routes by messageType:
    #   email messages  -> sent to the participant's `Email` system field
    #   sms messages    -> sent to the participant's `Phone` system field
    # If a corresponding message exists, the matching system question must too.
    has_email_msg = any(
        isinstance(m, dict) and m.get("messageType") == "email" for m in messages
    )
    has_sms_msg = any(
        isinstance(m, dict) and m.get("messageType") == "sms" for m in messages
    )
    if has_email_msg and "email" not in system_keys:
        errors.append(
            "[semantics] messages: file contains email messages but no system question "
            "for 'Email' — emails are sent to the participant's Email field "
            "(add a question with type: 'system' and id/text 'Email')"
        )
    if has_sms_msg and "phone" not in system_keys:
        errors.append(
            "[semantics] messages: file contains SMS messages but no system question "
            "for 'Phone' — SMS messages are sent to the participant's Phone field "
            "(add a question with type: 'system' and id/text 'Phone')"
        )

    for i, msg in enumerate(messages):
        prefix = f"messages[{i}]"
        if not isinstance(msg, dict):
            errors.append(f"[semantics] {prefix}: must be an object, got {type(msg).__name__}")
            continue

        name = msg.get("name", "<unnamed>")
        if isinstance(name, str) and name:
            prefix = f"messages[{i}] ('{name}')"

        # Required base fields
        for req in ("name", "sendType", "messageType", "senderName"):
            if req not in msg:
                errors.append(f"[semantics] {prefix}: missing required field '{req}'")

        send_type = msg.get("sendType")
        if send_type is not None and send_type not in VALID_SEND_TYPES:
            errors.append(
                f"[semantics] {prefix}: sendType='{send_type}' is not valid "
                f"(allowed: {', '.join(sorted(VALID_SEND_TYPES))})"
            )

        msg_type = msg.get("messageType")
        if msg_type is not None and msg_type not in VALID_MESSAGE_TYPES:
            errors.append(
                f"[semantics] {prefix}: messageType='{msg_type}' is not valid "
                f"(allowed: {', '.join(sorted(VALID_MESSAGE_TYPES))})"
            )

        # Field-set checks by messageType
        if msg_type == "email":
            for req in EMAIL_REQUIRED_FIELDS:
                if not msg.get(req):
                    errors.append(
                        f"[semantics] {prefix}: email messages require '{req}'"
                    )
            # SMS-only fields must not appear
            stray_sms = SMS_BODY_FIELDS & set(msg.keys())
            for f in sorted(stray_sms):
                errors.append(
                    f"[semantics] {prefix}: field '{f}' is SMS-only and must not appear on email messages"
                )
        elif msg_type == "sms":
            for req in SMS_REQUIRED_FIELDS:
                if not msg.get(req):
                    errors.append(
                        f"[semantics] {prefix}: SMS messages require '{req}'"
                    )
            # SMS sender name (alphanumeric sender ID): max 11 chars, A-Za-z0-9
            # only — no spaces or punctuation. e.g. "RA Survey" is invalid (space);
            # "RASurvey" is fine.
            sender = msg.get("senderName")
            if isinstance(sender, str) and sender:
                if not re.fullmatch(r"[A-Za-z0-9]{1,11}", sender):
                    errors.append(
                        f"[semantics] {prefix}: SMS senderName '{sender}' is invalid — "
                        f"must be 1–11 characters, letters and digits only (no spaces or punctuation)"
                    )
            # Email-only fields must not appear
            stray_email = EMAIL_BODY_FIELDS & set(msg.keys())
            for f in sorted(stray_email):
                errors.append(
                    f"[semantics] {prefix}: field '{f}' is email-only and must not appear on SMS messages"
                )
            # SMS body must contain #DsLink#
            body = msg.get("body") or ""
            if isinstance(body, str) and body:
                tokens_in_body = [_normalize_token(t) for t in _extract_tokens(body)]
                if "dslink" not in tokens_in_body:
                    errors.append(
                        f"[semantics] {prefix}: SMS body must contain '#DsLink#' "
                        f"(otherwise the recipient has no way to open the survey)"
                    )

        # Collect all merge tokens across every string field on this message
        # and verify each non-reserved token resolves to a system question.
        text_fields = [
            "subject", "title", "bodyBeforeLink", "linkLabel",
            "bodyAfterLink", "footer", "optOutLabel", "body",
            "senderName",
        ]
        for fname in text_fields:
            v = msg.get(fname)
            if not isinstance(v, str):
                continue
            for tok in _extract_tokens(v):
                norm = _normalize_token(tok)
                if norm in RESERVED_MERGE_TOKENS:
                    continue
                if norm not in system_keys:
                    errors.append(
                        f"[semantics] {prefix}: merge token '#{tok}#' in field "
                        f"'{fname}' has no matching system question "
                        f"(add a question with type 'system' and id or text '{tok}', "
                        f"or check spelling)"
                    )

        # Condition
        cond = msg.get("condition")
        if cond is not None:
            if not isinstance(cond, dict):
                errors.append(
                    f"[semantics] {prefix}: condition must be an object, "
                    f"got {type(cond).__name__}"
                )
            else:
                definition = cond.get("definition")
                if definition is None:
                    errors.append(f"[semantics] {prefix}: condition.definition is required")
                else:
                    cond_errs = _validate_message_condition(definition)
                    for e in cond_errs:
                        errors.append(f"[semantics] {prefix}: {e}")
                    # Verify referenced question ids exist (system or category).
                    if isinstance(definition, str):
                        for qid in re.findall(r"\{([^{}:]+)\}\s*:", definition):
                            qid_stripped = qid.strip()
                            if qid_stripped not in question_by_id:
                                errors.append(
                                    f"[semantics] {prefix}: condition references "
                                    f"unknown question id '{qid_stripped}'"
                                )

    return errors


def collect_warnings(data) -> list[str]:
    """Non-fatal advisories. The file is still considered valid even if any
    of these fire. Currently checks:

    - Participants with a 'Phone' value not in international '+CC...' format.
      The platform requires this for SMS delivery but we don't reject the file
      because Phone may be unused or only present for analytics.
    - Dropdown questions without a 'placeholder'. The file is valid, but a
      dropdown reads better with an empty-state prompt (e.g. 'Select a country…').
    - Answers with an explicit 'points': 1 (the default, which exports omit).
    - A 'multiple' question whose max is at least its number of answers (limits nothing).
    """
    warnings: list[str] = []
    # A max equal to (or above) the number of selectable answers limits nothing - leave max out.
    for q in (data.get("questions") or []) if isinstance(data, dict) else []:
        if not isinstance(q, dict) or q.get("type") != "multiple" or not isinstance(q.get("max"), int):
            continue
        n = sum(1 for a in (q.get("answers") or []) if isinstance(a, dict) and a.get("type") != "Open")
        if n and q["max"] >= n:
            warnings.append(
                f"question '{q.get('id')}': max={q['max']} with {n} answers limits nothing - remove 'max' "
                f"(no max allows any number of answers)"
            )
    if not isinstance(data, dict):
        return warnings

    # Dropdowns without a placeholder: valid, but a relevant prompt improves UX.
    dd_missing = [
        q.get("id")
        for q in data.get("questions", [])
        if isinstance(q, dict)
        and q.get("interface") == "dropdown"
        and not q.get("noInterfaceValidation")
        and not (isinstance(q.get("placeholder"), str) and q["placeholder"].strip())
    ]
    if dd_missing:
        ids = ", ".join(str(i) for i in dd_missing[:5])
        more = f" (+{len(dd_missing) - 5} more)" if len(dd_missing) > 5 else ""
        warnings.append(
            f"{len(dd_missing)} dropdown question(s) have no 'placeholder': {ids}{more}. "
            f"Add a relevant empty-state prompt, e.g. \"placeholder\": \"Select a country…\"."
        )

    # Explicit "points": 1 — valid but redundant; the platform omits the default.
    default_pts = []
    for q in data.get("questions", []):
        if not isinstance(q, dict):
            continue
        for a in q.get("answers") or []:
            if isinstance(a, dict) and a.get("points") == 1:
                default_pts.append(f"{q.get('id')}:{a.get('id')}")
    if default_pts:
        ids = ", ".join(default_pts[:5])
        more = f" (+{len(default_pts) - 5} more)" if len(default_pts) > 5 else ""
        warnings.append(
            f"{len(default_pts)} answer(s) set 'points': 1, which is the default: {ids}{more}. "
            f"Omit 'points' when it is 1."
        )

    # Calculated variables: long forms where the short form would do, and default values.
    warnings.extend(_short_form_advice(data.get("questions") or []))

    # Find the system question that represents Phone, if any. Match by
    # normalized id/text so e.g. 'Phone', 'phone', 'Phone number' all count.
    phone_keys: set[str] = set()
    for q in data.get("questions", []):
        if isinstance(q, dict) and q.get("type") == "system":
            for attr in ("id", "text"):
                v = q.get(attr)
                if isinstance(v, str) and _normalize_token(v) == "phone":
                    # Use the raw id as the dict key in participants (per format spec)
                    qid = q.get("id")
                    if isinstance(qid, str):
                        phone_keys.add(qid)

    if not phone_keys:
        return warnings

    participants = data.get("participants", [])
    if not isinstance(participants, list):
        return warnings

    bad = 0
    examples: list[str] = []
    for p in participants:
        if not isinstance(p, dict):
            continue
        for k in phone_keys:
            v = p.get(k)
            if isinstance(v, str) and v.strip() and not v.strip().startswith("+"):
                bad += 1
                if len(examples) < 3:
                    examples.append(v.strip())
                break  # one warning per participant
    if bad:
        ex_str = f" (examples: {', '.join(examples)})" if examples else ""
        warnings.append(
            f"{bad} participant(s) have a Phone value not in international "
            f"'+CC...' format{ex_str}. SMS delivery will fail for these. "
            f"Use e.g. '+46701234567' for Sweden."
        )
    return warnings


# --------------------------------------------------------------------------
# Survey Update Mode (updateMode: true) - mirrors the platform's update importer.
# See references/task-update.md. Without --base: the file's own rules. With --base
# <survey export>: everything the importer checks before its review dialog, except
# what needs the project itself (shared answer lists, reserved ids of earlier
# renames, per-question response counts when the export has no responses).
# --------------------------------------------------------------------------

UPDATE_ACTIONS = ("add", "edit", "replace", "move", "remove")
UPDATE_CHANGES = ("text", "order", "additions", "structure")
_UPDATE_FILE_KEYS = ("updateMode", "baseVersion", "questions")
_UPDATE_KEYS = ("action", "change", "placeAfter", "oldId", "note")
_UPDATE_TEXT_PROPS = {
    "text", "surveyText", "comment", "scaleLeft", "scaleRight", "scaleDK",
    "answerAlternativeHeaderText", "answerAlternativeHeaderText2", "answerAlternativeHeaderText3",
}
# properties an edit changes in place; any other changed property rebuilds the question
_UPDATE_IN_PLACE = _UPDATE_TEXT_PROPS | {"id", "condition", "conditionId", "pagebreak", "excluded", "answers", "rows"}
_UPDATE_NO_TEXT = {
    "id", "type", "scale", "interface", "layout", "excluded", "pagebreak", "condition", "conditionId", "groupId",
    "update", "min", "max", "randomAnswers", "cssClass", "reports", "comparison", "calculated", "calculation",
    "coded", "period", "category", "points", "color", "label", "exclusive", "tag", "connectedTo",
}
_UPDATE_TOKEN = re.compile(r"(?P<colon>:\s*)?\{(?P<name>[^{}]*)\}")
_TYPO_MAX_DISTANCE = 3


def survey_version(survey: dict) -> str:
    """The surveyVersion the platform writes in a survey export: 8 hex of SHA-256 over questions + conditions."""
    canonical = {"questions": survey.get("questions") or [], "conditions": survey.get("conditions") or []}
    s = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def _upd_items(q: dict, name: str) -> list:
    v = q.get(name) if isinstance(q, dict) else None
    return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []


def _upd_strip(q: dict) -> dict:
    q = copy.deepcopy(q)
    q.pop("update", None)
    for name in ("answers", "rows"):
        for item in _upd_items(q, name):
            item.pop("update", None)
    return q


def _upd_plain(t) -> str:
    if t is None:
        return ""
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        return t.get("text") or t.get("html") or json.dumps(t, ensure_ascii=False)
    return json.dumps(t, ensure_ascii=False)


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _is_typo_fix(old, new) -> bool:
    return _levenshtein(_upd_plain(old), _upd_plain(new)) <= _TYPO_MAX_DISTANCE


def _upd_condition_strings(q: dict) -> list[str]:
    c = q.get("condition")
    out = []
    for t in (c if isinstance(c, list) else [c]):
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, dict) and isinstance(t.get("definition"), str):
            out.append(t["definition"])
    return out


def _upd_text_strings(o: dict, inside_fields=False) -> list[str]:
    out = []

    def walk(v, in_fields):
        if isinstance(v, str):
            if not in_fields:
                out.append(v)
        elif isinstance(v, dict):
            for k, sub in v.items():
                walk(sub, in_fields or k == "fields")
        elif isinstance(v, list):
            for sub in v:
                walk(sub, in_fields)

    for k, v in o.items():
        if k in _UPDATE_NO_TEXT or k in ("answers", "rows"):
            continue
        walk(v, inside_fields)
    return out


def _upd_fields(q) -> list[dict]:
    out = []
    if isinstance(q, dict):
        for k, v in q.items():
            if k == "fields" and isinstance(v, dict):
                out += [f for f in v.values() if isinstance(f, dict) and isinstance(f.get("question"), str)]
            else:
                out += _upd_fields(v)
    elif isinstance(q, list):
        for v in q:
            out += _upd_fields(v)
    return out


def _upd_split_answers(s: str) -> list[str]:
    return [a.strip() for a in s.split(",") if a.strip() and "-" not in a and "*" not in a]


def _upd_references(q: dict, known) -> list[tuple[str, str, list[str]]]:
    """(kind, name, answer ids) for each reference of a question to a known question or row id."""
    refs = []

    def parse(s, kind):
        last = None
        for m in _UPDATE_TOKEN.finditer(s):
            name = m.group("name").strip()
            if m.group("colon"):
                if last is not None:
                    last[2].extend(_upd_split_answers(name))
                continue
            last = None
            answer = None
            if ":" in name[1:]:
                name, answer = name.split(":", 1)
                name = name.strip()
            if not name or not known(name):
                continue
            last = (kind, name, _upd_split_answers(answer) if answer else [])
            refs.append(last)

    for s in _upd_condition_strings(q):
        parse(s, "condition")
    strings = _upd_text_strings(q)
    for name in ("answers", "rows"):
        for item in _upd_items(q, name):
            strings += _upd_text_strings(item)
    for s in strings:
        parse(s, "text")
    for f in _upd_fields(q):
        if known(f["question"]):
            refs.append(("text", f["question"], [f["answer"]] if isinstance(f.get("answer"), str) else []))
    return refs


def _upd_rewrite(q: dict, qmap: dict, amaps: dict) -> None:
    """Rewrites references for renames, all at once (qmap: old question/row id -> new; amaps: new question id -> answer map)."""
    if not qmap and not amaps:
        return

    def rewrite(s):
        last = [None]

        def rep(m):
            name = m.group("name")
            if m.group("colon"):
                answers = amaps.get(last[0])
                if not answers:
                    return m.group(0)
                return m.group("colon") + "{" + ",".join(answers.get(a.strip(), a) for a in name.split(",")) + "}"
            answer = None
            if ":" in name[1:]:
                name, answer = name.split(":", 1)
            trimmed = name.strip()
            if trimmed in qmap:
                name = trimmed = qmap[trimmed]
            last[0] = trimmed
            if answer is not None:
                answers = amaps.get(trimmed)
                if answers:
                    answer = ",".join(answers.get(a.strip(), a) for a in answer.split(","))
                return "{" + name + ":" + answer + "}"
            return "{" + name + "}"

        return _UPDATE_TOKEN.sub(rep, s) if "{" in s else s

    def walk(o, key=None, cond=False):
        # rewrites strings in conditions and texts; leaves non-text properties alone
        if isinstance(o, dict):
            for k in list(o.keys()):
                v = o[k]
                if k == "condition":
                    if isinstance(v, str):
                        o[k] = rewrite(v)
                    else:
                        walk(v, k, True)
                elif k in ("answers", "rows"):
                    for item in v if isinstance(v, list) else []:
                        walk(item)
                elif k == "fields" and isinstance(v, dict):
                    for f in v.values():
                        if isinstance(f, dict) and isinstance(f.get("question"), str):
                            new = qmap.get(f["question"], f["question"])
                            f["question"] = new
                            if isinstance(f.get("answer"), str) and new in amaps:
                                f["answer"] = amaps[new].get(f["answer"], f["answer"])
                elif cond and k == "definition" and isinstance(v, str):
                    o[k] = rewrite(v)
                elif k in _UPDATE_NO_TEXT:
                    continue
                elif isinstance(v, str):
                    o[k] = rewrite(v)
                else:
                    walk(v, k, cond)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, str):
                    o[i] = rewrite(v)
                else:
                    walk(v, key, cond)

    walk(q)


def _upd_inline_conditions(q: dict, defs: dict) -> None:
    """conditionId (export form) -> inline condition, as the importer compares them."""
    cid = q.get("conditionId")
    if cid is None:
        return
    ids = cid if isinstance(cid, list) else [cid]
    if not all(isinstance(i, str) and i in defs for i in ids):
        return  # like the importer: left as it is when a condition has no definition
    found = [defs[i] for i in ids]
    q.pop("conditionId")
    if "condition" not in q and found:
        q["condition"] = found[0] if len(found) == 1 else found


def _upd_same_content(sent: dict, cur: dict) -> bool:
    for k, v in sent.items():
        if k == "id":
            continue
        if k in ("answers", "rows"):
            if not isinstance(v, list):
                return False
            cur_items = _upd_items(cur, k)
            sent_items = [i for i in v if isinstance(i, dict)]
            cur_ids = [i.get("id") for i in cur_items]
            sent_ids = [i.get("id") for i in sent_items]
            if all(i in sent_ids for i in cur_ids) and cur_ids != sent_ids:
                return False
            for s in sent_items:
                c = next((i for i in cur_items if i.get("id") == s.get("id")), None)
                if c is None or not _upd_same_content(s, c):
                    return False
        elif v != cur.get(k) and not (v is None and k not in cur):
            return False
    return True


def _upd_moved(order: list, reference: list, weight) -> set:
    """Existing questions in `order` that changed position against `reference`: those outside the heaviest
    increasing subsequence of reference positions (weight prefers keeping questions that did not ask to move)."""
    existing = [i for i in order if i in reference]
    pos = [reference.index(i) for i in existing]
    n = len(existing)
    best = [weight(existing[i]) for i in range(n)]
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if pos[j] < pos[i] and best[j] + weight(existing[i]) > best[i]:
                best[i] = best[j] + weight(existing[i])
                prev[i] = j
    keep = set()
    if n:
        k = max(range(n), key=lambda i: (best[i], -i))
        while k >= 0:
            keep.add(existing[k])
            k = prev[k]
    return {i for i in existing if i not in keep}


def _upd_question_schema_errors(body: dict, where: str, partial: bool) -> list[str]:
    """Schema check of one entry's question (update markup removed). partial (edit): required properties may be left
    out, and null clears a property."""
    schema = load_json(SCHEMA_PATH)
    q = {k: v for k, v in _upd_strip(body).items() if not (partial and v is None) and k != "conditionId"}
    # the importer also takes the export's inline form: the definition as a string (or an array of them)
    c = q.get("condition")
    if isinstance(c, str) or (isinstance(c, list) and c and all(isinstance(x, str) for x in c)):
        q["condition"] = {"definition": c if isinstance(c, str) else " AND ".join(f"({x})" for x in c)}
    errs: list[str] = []
    _validate_node(q, {"$ref": "#/definitions/question"}, schema, where, errs)
    if partial:
        errs = [e for e in errs if "is a required property" not in e]
    return [e.replace("[schema] ", "[update] ") for e in errs]


def update_markup_in_create_file(data) -> list[str]:
    """A normal (create) import rejects update markup."""
    if not isinstance(data, dict):
        return []
    found = [k for k in ("updateMode", "baseVersion") if k in data]
    for q in data.get("questions") or []:
        if isinstance(q, dict) and ("update" in q or any("update" in i for n in ("answers", "rows") for i in _upd_items(q, n))):
            found.append(f"update (question '{q.get('id')}')")
            break
    if not found:
        return []
    return [f"[update] {', '.join(found)} is only allowed in an update file (\"updateMode\": true). "
            "A new survey has no update markup; to change an existing survey see references/task-update.md"]


def validate_update(data, base: dict | None) -> tuple[list[str], list[str], list[str]]:
    """Validates a Survey Update Mode file. Returns (errors, warnings, review lines)."""
    errors: list[str] = []
    warnings: list[str] = []
    E = lambda msg: errors.append(f"[update] {msg}")  # noqa: E731

    # ---- the file on its own -------------------------------------------------
    if not isinstance(data, dict) or data.get("updateMode") is not True:
        return ["[update] not an update file: \"updateMode\": true is missing"], [], []
    for k in data:
        if k not in _UPDATE_FILE_KEYS:
            E(f"'{k}' is not supported in an update file. Only questions can be updated.")
    keys = list(data.keys())
    if keys and keys[0] != "updateMode":
        warnings.append("put updateMode, baseVersion and questions in that order")
    base_version = data.get("baseVersion")
    if not isinstance(base_version, str) or not base_version:
        E("baseVersion is missing. Copy surveyVersion from the survey export the update is made from.")
    elif not re.fullmatch(r"[0-9a-f]{8}", base_version):
        E(f"baseVersion '{base_version}' is not a surveyVersion (8 hex characters from the survey export).")
    questions = data.get("questions")
    if not isinstance(questions, list):
        E("the update file has no questions array.")
        return errors, warnings, []

    entries = []      # flagged: dict(id, action, change, oldId, placeAfter, hasPlaceAfter, note, body, index)
    unflagged = []
    for i, q in enumerate(questions):
        qid = q.get("id") if isinstance(q, dict) else None
        if not isinstance(qid, str) or not qid.strip():
            E(f"question {i + 1} in the file has no id.")
            continue
        body = {k: v for k, v in q.items() if k != "update"}
        if "update" not in q:
            unflagged.append({"id": qid, "body": body, "index": i, "flagged": False})
            continue
        u = q["update"]
        if not isinstance(u, dict):
            E(f"{qid}: update must be an object.")
            continue
        for k in u:
            if k not in _UPDATE_KEYS:
                E(f"{qid}: unknown update property '{k}' (allowed: {', '.join(_UPDATE_KEYS)}).")
        e = {"id": qid, "action": u.get("action"), "change": u.get("change"), "oldId": u.get("oldId"),
             "hasPlaceAfter": "placeAfter" in u, "placeAfter": u.get("placeAfter"), "note": u.get("note"),
             "body": body, "index": i, "flagged": True, "facets": set(), "flags": set()}
        a = e["action"]
        if a not in UPDATE_ACTIONS:
            E(f"{qid}: action must be one of {', '.join(UPDATE_ACTIONS)}.")
        if e["change"] is not None:
            if e["change"] not in UPDATE_CHANGES:
                E(f"{qid}: change must be one of {', '.join(UPDATE_CHANGES)}.")
            if a not in ("edit", "replace"):
                E(f"{qid}: change is only used with edit and replace.")
        for k in ("oldId", "note"):
            if u.get(k) is not None and not isinstance(u[k], str):
                E(f"{qid}: update.{k} must be a string.")
        if e["hasPlaceAfter"] and e["placeAfter"] is not None and not isinstance(e["placeAfter"], str):
            E(f"{qid}: placeAfter must be a question id or null (= first).")
        if e["hasPlaceAfter"] and a == "remove":
            E(f"{qid}: a removed question cannot be placed (remove + placeAfter).")
        if e["oldId"] is not None and a not in ("edit", "replace"):
            E(f"{qid}: oldId is only used with edit and replace.")
        if a in ("move", "remove") and any(k != "id" for k in body):
            E(f"{qid}: {a} sends only the id. Use edit to change the question as well.")
        if a == "move" and not e["hasPlaceAfter"]:
            E(f"{qid}: move needs placeAfter.")
        for name in ("answers", "rows"):
            for item in _upd_items(q, name):
                iu = item.get("update")
                if iu is None:
                    continue
                if not isinstance(iu, dict) or any(k != "oldId" for k in iu) or not isinstance(iu.get("oldId"), str):
                    E(f"{qid}: answers and rows only support update.oldId (removing an answer or row needs replace).")
        if a == "edit":
            for name in ("answers", "rows"):
                if name in body and body[name] is None:
                    E(f"{qid}: removing {name} needs replace.")
                elif name in body and not isinstance(body[name], list):
                    E(f"{qid}: {name} must be an array.")
        if a in ("add", "replace", "edit"):
            errors.extend(_upd_question_schema_errors(body, f"questions/{i} ({qid})", partial=(a == "edit")))
        if a == "add" and "type" not in body and "text" not in body:
            E(f"{qid}: a new question needs at least type and text.")
        entries.append(e)

    seen: dict[str, int] = {}
    for e in entries:
        seen[e["id"]] = seen.get(e["id"], 0) + 1
    for qid, n in seen.items():
        if n > 1:
            E(f"{qid} has {n} entries. Combine the changes in one entry (e.g. edit with placeAfter).")
    olds: dict[str, int] = {}
    for e in entries:
        if e["oldId"]:
            olds[e["oldId"]] = olds.get(e["oldId"], 0) + 1
    for o, n in olds.items():
        if n > 1:
            E(f"{o} is renamed by more than one entry.")
    if not entries:
        E("no question has an update object - nothing would change.")
    if errors or base is None:
        if base is None and not errors:
            warnings.append("checked the file on its own. Add --base <survey export> to run the importer's checks "
                            "(ids, merge, declared change, positions, references)")
        return errors, warnings, []

    # ---- against the base survey (the export the update is made from) -------
    expected = base.get("surveyVersion") or survey_version(base)
    if base_version != expected:
        E(f"baseVersion {base_version} does not match the base survey ({expected}). The importer refuses it: "
          "make the update from the latest export and copy its surveyVersion.")
    defs = {c.get("id"): c.get("definition") for c in base.get("conditions") or []
            if isinstance(c, dict) and isinstance(c.get("definition"), str)}
    current = []
    for q in base.get("questions") or []:
        if isinstance(q, dict) and isinstance(q.get("id"), str):
            q = copy.deepcopy(q)
            _upd_inline_conditions(q, defs)
            current.append(q)
    current_by_id = {q["id"]: q for q in current}
    # the importer reads conditionId in the file's entries as the inline condition, as in the current survey
    for x in entries + unflagged:
        _upd_inline_conditions(x["body"], defs)
    current_order = [q["id"] for q in current]

    # responses: the export's responses, if any (the importer reads the project's database)
    responses = [r for r in base.get("responses") or [] if isinstance(r, dict)]
    total = len(responses)

    def responses_of(qid):
        q = current_by_id.get(qid)
        if not q or not total:
            return 0
        keys = {qid} | {r.get("id") for r in _upd_items(q, "rows")}
        return sum(1 for r in responses if any(
            v not in (None, "") and (k in keys or k.split(":")[0] in keys or k.startswith(qid + "."))
            for k, v in r.items()))

    # renames, resolved simultaneously
    renames = {e["oldId"]: e["id"] for e in entries if e["oldId"] and e["action"] in ("edit", "replace")}
    renamed_away = set(renames)
    for e in entries:
        a, qid = e["action"], e["id"]
        e["currentId"] = None
        if a == "add":
            if qid in current_by_id:
                if qid in renamed_away:
                    E(f"{qid} was used before in this survey and is reserved. Choose another id.")
                else:
                    E(f"{qid} already exists. Use edit or replace to change it.")
            continue
        if e["oldId"]:
            if e["oldId"] not in current_by_id:
                E(f"{qid}: oldId {e['oldId']} does not exist.")
            elif e["oldId"] == qid:
                E(f"{qid}: oldId is the same as the id.")
            elif qid in current_by_id and qid not in renamed_away:
                E(f"{e['oldId']} cannot be renamed to {qid}: {qid} already exists.")
            else:
                e["currentId"] = e["oldId"]
            continue
        if qid in renamed_away:
            E(f"{qid} is renamed in this file. Use its new id.")
        elif qid not in current_by_id:
            E(f"{qid} does not exist in the survey.")
        else:
            e["currentId"] = qid
    for u in unflagged:
        if u["id"] in renamed_away:
            E(f"{u['id']} is renamed in this file. Use its new id.")
    if errors:
        return errors, warnings, []

    # row renames: a renamed question's rows follow its prefix; explicit update.oldId on rows and answers
    row_map: dict[str, str] = {}
    answer_maps: dict[str, dict] = {}
    for e in entries:
        if e["action"] not in ("edit", "replace") or not e["currentId"]:
            continue
        cur = current_by_id[e["currentId"]]
        if e["oldId"]:
            for r in _upd_items(cur, "rows"):
                rid = r.get("id")
                if isinstance(rid, str) and rid.startswith(e["oldId"] + "."):
                    row_map[rid] = e["id"] + rid[len(e["oldId"]):]
        for name in ("answers", "rows"):
            base_ids = [i.get("id") for i in _upd_items(cur, name)]
            mapped = [row_map.get(i, i) for i in base_ids] if name == "rows" else base_ids
            what = name[:-1]
            item_map = {}
            olds = {(x.get("update") or {}).get("oldId") for x in _upd_items(e["body"], name)
                    if isinstance(x.get("update"), dict)}
            for item in _upd_items(e["body"], name):
                old = (item.get("update") or {}).get("oldId") if isinstance(item.get("update"), dict) else None
                if not old:
                    continue
                iid = item.get("id")
                if old not in base_ids and old not in mapped:
                    E(f"{e['id']}: {what} oldId {old} does not exist.")
                elif old == iid:
                    E(f"{e['id']}: {what} {iid} has oldId equal to its id.")
                elif iid in mapped and iid not in olds:
                    E(f"{e['id']}: {what} {old} cannot be renamed to {iid}: {iid} already exists.")
                else:
                    item_map[old] = iid
            if item_map:
                e["facets"].add("rename")
                if name == "rows":
                    row_map.update(item_map)
                else:
                    answer_maps[e["id"]] = item_map
                    if total:
                        E(f"{e['id']}: answer ids cannot be renamed when the survey has responses "
                          "(answer ids are stored values; a rename would recode them).")
    if errors:
        return errors, warnings, []

    # the current survey under the new ids, references rewritten
    qmap = dict(renames, **row_map)
    renamed_current = {}
    for q in current:
        q = copy.deepcopy(q)
        new_id = renames.get(q["id"], q["id"])
        q["id"] = new_id
        for r in _upd_items(q, "rows"):
            if r.get("id") in row_map:
                r["id"] = row_map[r["id"]]
        for a in _upd_items(q, "answers"):
            if a.get("id") in answer_maps.get(new_id, {}):
                a["id"] = answer_maps[new_id][a["id"]]
        _upd_rewrite(q, qmap, answer_maps)
        renamed_current[new_id] = q
    final_order = [renames.get(i, i) for i in current_order]
    final = dict(renamed_current)

    # merge
    def merge_items(e, base_items, sent, name):
        base_ids = [i.get("id") for i in base_items]
        sent_items = [i for i in sent if isinstance(i, dict)]
        sent_ids = [i.get("id") for i in sent_items]
        for sid in set(sent_ids):
            if sid is None or sent_ids.count(sid) > 1:
                E(f"{e['id']}: {name} has a missing or repeated id ({sid}).")
        complete = all(i in sent_ids for i in base_ids)
        if not complete and len(base_ids) - sum(1 for i in base_ids if i in sent_ids) <= 2 \
                and any(i in sent_ids for i in base_ids) and len(base_ids) > 2:
            warnings.append(f"{e['id']}: {name} lists all but {len(base_ids) - sum(1 for i in base_ids if i in sent_ids)} "
                            "existing id(s), so its order is ignored and new items go last. List every id to set the order.")
        merged = {i.get("id"): copy.deepcopy(i) for i in base_items}
        added = []
        for s in sent_items:
            sid = s.get("id")
            if sid is None:
                continue
            target = merged.get(sid)
            if target is None:
                target = {}
                merged[sid] = target
                added.append(sid)
            for k, v in s.items():
                if k == "update":
                    continue
                if v is None:
                    target.pop(k, None)
                else:
                    target[k] = copy.deepcopy(v)
        order = [i for i in sent_ids if i is not None] if complete else base_ids + added
        return [merged[i] for i in order]

    for e in entries:
        a = e["action"]
        before = renamed_current.get(e["id"]) if e["currentId"] else None
        e["before"] = before
        if a == "add":
            after = _upd_strip(e["body"])
        elif a == "edit":
            after = copy.deepcopy(before)
            for k, v in e["body"].items():
                if k == "id":
                    continue
                if k in ("answers", "rows"):
                    if isinstance(v, list):
                        after[k] = merge_items(e, _upd_items(before, k), v, k)
                elif v is None:
                    after.pop(k, None)
                else:
                    after[k] = copy.deepcopy(v)
                if k == "condition":
                    after.pop("conditionId", None)
                if k == "conditionId":
                    after.pop("condition", None)
                    if v is not None:
                        ids = v if isinstance(v, list) else [v]
                        for cid in ids:
                            if cid not in defs:
                                E(f"{e['id']}: conditionId {cid} is not a condition of the survey. Use an inline condition.")
                        _upd_inline_conditions(after, defs)
        elif a == "replace":
            after = _upd_strip(e["body"])
            _upd_inline_conditions(after, defs)
        elif a == "move":
            after = copy.deepcopy(before)
        else:  # remove
            after = copy.deepcopy(before)
            after["excluded"] = True
        if after is not None:
            after["id"] = e["id"]
        e["after"] = after
        final[e["id"]] = after
    entry_by_id = {e["id"]: e for e in entries}

    for u in unflagged:
        if u["id"] not in renamed_current:
            E(f"{u['id']} is not in the survey. A new question needs update.action = add.")
        elif not _upd_same_content(u["body"], renamed_current[u["id"]]):
            E(f"{u['id']} differs from the survey but has no update. Flag every changed question.")
    if errors:
        return errors, warnings, []

    # a full file (lists every existing question): its array order is the final order
    listed = {x["id"] for x in entries + unflagged}
    is_full = bool(final_order) and all(i in listed for i in final_order)
    if is_full:
        removed = {e["id"] for e in entries if e["action"] == "remove"}
        everything = sorted(entries + unflagged, key=lambda x: x["index"])
        order = [x["id"] for x in everything if x["id"] not in removed]
        for i, qid in enumerate(final_order):
            if qid not in removed:
                continue
            j = i - 1
            while j >= 0 and final_order[j] in removed and final_order[j] not in order:
                j -= 1
            order.insert(0 if j < 0 else order.index(final_order[j]) + 1, qid)
        declared = {e["id"] for e in entries}
        moved = _upd_moved(order, final_order, lambda i: 1 if i in declared else 2)
        for idx, qid in enumerate(order):
            x = next((y for y in everything if y["id"] == qid), None)
            if x is None:
                continue
            pred = order[idx - 1] if idx else None
            if x["flagged"] and x["action"] == "add":
                x["hasPlaceAfter"], x["placeAfter"] = True, pred
            elif qid in moved:
                if x["flagged"]:
                    x["hasPlaceAfter"], x["placeAfter"] = True, pred
                else:
                    E(f"{qid} changed position but has no update. Flag it (move, or edit with placeAfter).")
            elif x["flagged"]:
                x["hasPlaceAfter"], x["placeAfter"] = False, None
    if errors:
        return errors, warnings, []

    # positions: entries in file order, placeAfter (null = first)
    order = list(final_order)
    for e in entries:
        if e["after"] is None:
            continue
        if e["action"] == "add" or e["hasPlaceAfter"]:
            if e["action"] != "add" and e["id"] in order:
                order.remove(e["id"])
            pa = e["placeAfter"]
            if not e["hasPlaceAfter"]:
                order.append(e["id"])
            elif pa is None:
                order.insert(0, e["id"])
            elif pa == e["id"]:
                E(f"{e['id']} cannot be placed after itself.")
            elif pa in order:
                order.insert(order.index(pa) + 1, e["id"])
            elif pa in renames:
                E(f"{e['id']}: placeAfter {pa} was renamed to {renames[pa]}. Use the new id.")
            elif any(x["id"] == pa and x["action"] == "add" for x in entries):
                E(f"{e['id']}: placeAfter {pa} is added later in the file. Put {pa} first.")
            else:
                E(f"{e['id']}: placeAfter {pa} does not exist.")
    if errors:
        return errors, warnings, []
    declared = {e["id"] for e in entries if e["hasPlaceAfter"]}
    moved = _upd_moved(order, final_order, lambda i: 1 if i in declared else 2)
    for e in entries:
        if e["action"] not in ("add", "remove") and e["id"] in moved:
            e["facets"].add("position")
    for qid in moved:
        if qid not in entry_by_id:
            E(f"{qid} changed position but has no update.")

    # computed change against the declared one
    level = {c: i for i, c in enumerate(UPDATE_CHANGES)}
    for e in entries:
        b, a = e["before"], e["after"]
        if b is None or a is None:
            continue
        if e["action"] in ("edit", "replace"):
            f, fl = e["facets"], e["flags"]
            if e["oldId"]:
                f.add("rename")
            for k in set(b) | set(a):
                if k in ("id", "answers", "rows") or b.get(k) == a.get(k):
                    continue
                if k in _UPDATE_TEXT_PROPS:
                    f.add("text")
                    if k in ("text", "surveyText") and not _is_typo_fix(b.get(k), a.get(k)):
                        fl.add("reworded")
                else:
                    f.add("structure")
                    fl.add("typeChanged" if k == "type" else "otherStructure")
                if k not in _UPDATE_IN_PLACE and e["action"] == "edit":
                    fl.add("rebuild")
            ordinal = b.get("scale") == "Ordinal" or a.get("scale") == "Ordinal"
            for name in ("answers", "rows"):
                bi, ai = _upd_items(b, name), _upd_items(a, name)
                bids, aids = [i.get("id") for i in bi], [i.get("id") for i in ai]
                if any(i not in aids for i in bids):
                    f.add("structure")
                    fl.add("itemsRemoved")
                if any(i not in bids for i in aids):
                    f.add("additions")
                kept = [i for i in bids if i in aids]
                if kept != [i for i in aids if i in kept]:
                    if ordinal and name == "answers":
                        f.add("structure")
                        fl.add("scaleReordered")
                    else:
                        f.add("order")
                if any(bids.index(i) != aids.index(i) for i in kept):
                    fl.add("itemPosition")
                for i in kept:
                    x, y = bi[bids.index(i)], ai[aids.index(i)]
                    for k in set(x) | set(y):
                        if k == "id" or x.get(k) == y.get(k):
                            continue
                        if k == "text":
                            f.add("text")
                            if not _is_typo_fix(x.get(k), y.get(k)):
                                fl.add("labelChanged")
                        else:
                            f.add("structure")
                            fl.add("otherStructure")
        if e["action"] == "remove":
            continue
        if not e["facets"] and e["action"] != "add":
            E(f"{e['id']} is flagged ({e['action']}) but nothing changes.")
            continue
        computed = max((level["structure"] if x == "rename" else level[x]
                        for x in e["facets"] if x != "position"), default=-1)
        if e["change"] in level and computed >= 0 and level[e["change"]] < computed:
            E(f"{e['id']} claims change '{e['change']}', but the change is '{UPDATE_CHANGES[computed]}'.")

    # the result: references in conditions and texts
    final_qs = [final[i] for i in order]
    index = {q["id"]: i for i, q in enumerate(final_qs)}
    page, p = {}, 0
    row_owner = {}
    for i, q in enumerate(final_qs):
        if i and q.get("pagebreak") is True:
            p += 1
        page[q["id"]] = p
        for r in _upd_items(q, "rows"):
            row_owner.setdefault(r.get("id"), q["id"])
    known = lambda n: n in index or n in row_owner  # noqa: E731
    removed_here = {e["id"] for e in entries if e["action"] == "remove"}
    for i, q in enumerate(final_qs):
        if q.get("excluded") is True:
            continue
        qid = q["id"]
        for kind, name, answers in _upd_references(q, known):
            target = name if name in index else row_owner[name]
            if qid not in entry_by_id and target not in entry_by_id:
                continue  # a problem the survey had before
            t = final[target]
            if target in removed_here:
                E(f"{target} cannot be removed: the {kind} of {qid} still references it.")
            elif t.get("excluded") is True:
                E(f"The {kind} of {qid} references {name}, which is excluded from the survey.")
            elif kind == "condition":
                if target == qid or index[target] > i:
                    E(f"The condition of {qid} references {name}, which does not come before it.")
                else:
                    aids = [x.get("id") for x in _upd_items(t, "answers")]
                    for aid in answers:
                        if aids and aid not in aids:
                            E(f"The condition of {qid} references answer {aid} of {name}, which does not exist.")
            elif target != qid and page[target] >= page[qid]:
                E(f"A text of {qid} shows the answer to {name}, which is not on an earlier page.")

    # data safety: responses are stored by answer/row position
    for e in entries:
        n = responses_of(e["currentId"]) if e.get("currentId") else 0
        e["responses"] = n
        if "itemPosition" in e["flags"] and n:
            E(f"{e['id']}: existing answers or rows would change position, but the question has {n} responses stored "
              "by position. Add new answers or rows last, and do not reorder or remove answers in the middle.")
        if "rebuild" in e["flags"]:
            warnings.append(f"{e['id']}: this edit changes more than texts, condition, page break, answers and rows, so "
                            "the importer rebuilds the question - its translations are reset.")
    if not total:
        warnings.append("the base export has no responses, so the data checks assumed none. The importer counts "
                        "the project's real responses: with data it refuses moving existing answers/rows and answer renames")

    # the merged survey must still pass the normal checks (only problems the update introduces are reported)
    def semantic_set(qs):
        qs = copy.deepcopy(qs)
        for q in qs:
            c = q.get("condition")
            if isinstance(c, str) or (isinstance(c, list) and c and all(isinstance(x, str) for x in c)):
                q["condition"] = {"definition": c if isinstance(c, str) else " AND ".join(f"({x})" for x in c)}
        return set(validate_semantics({"questions": qs}))
    before_errs = semantic_set([renamed_current[i] for i in final_order])
    for msg in sorted(semantic_set(final_qs) - before_errs):
        errors.append(f"[result] {msg}")

    # what the review dialog will show
    review = []
    if not errors:
        has_data = total > 0
        groups = {"attention": [], "new": [], "removed": [], "wording": [], "moved": [], "other": []}
        for e in entries:
            fl, f = e["flags"], e["facets"]
            chips = []
            if "typeChanged" in fl:
                chips.append("Type changed")
            else:
                if "otherStructure" in fl:
                    chips.append("Structure changed")
                if "itemsRemoved" in fl:
                    chips.append("Answer removed")
                if "scaleReordered" in fl:
                    chips.append("Scale reordered")
            if has_data and "rename" in f:
                chips.append("Renamed")
            if has_data and "reworded" in fl and (e["after"] or {}).get("type") in ("single", "multiple"):
                chips.append("Reworded")
            if has_data and "labelChanged" in fl and "typeChanged" not in fl:
                chips.append("Label changed")
            if e["action"] == "add":
                g = "new"
            elif e["action"] == "remove":
                g = "removed"
                if e["responses"]:
                    chips = [f"{e['responses']} responses"]
            elif chips:
                g = "attention"
            elif f and f <= {"text"}:
                g = "wording"
            elif f and f <= {"position"}:
                g = "moved"
            else:
                g = "other"
            shown = e["oldId"] or e["id"]
            groups[g].append(f"{shown}" + (f" [{', '.join(chips)}]" if chips else "") + (f" - {e['note']}" if e["note"] else ""))
        titles = {"attention": "Needs attention", "new": "New questions", "removed": "Removed questions",
                  "wording": "Wording only", "moved": "Moved only", "other": "Other safe changes"}
        review.append(f"Review dialog: {len(entries)} questions changed" + (f", {total} responses" if total else ""))
        for g, items in groups.items():
            if items:
                review.append(f"  {titles[g]} ({len(items)})")
                review += [f"    {x}" for x in items]
    return errors, warnings, review


USAGE = (
    "Usage: python validate.py <path-to-survey.json> [--existing <project-survey.json>]\n"
    "  --existing: the survey of the project the file will be imported into (e.g. from get_survey).\n"
    "              Conditions, calculations and coded sources may then refer to its questions.\n"
    "       python validate.py <update.json> [--base <survey-export.json>]\n"
    "  An update file (\"updateMode\": true) changes an existing survey. --base: the survey export it is made\n"
    "              from; runs the importer's checks against it."
)


# Reference files that explain a feature, by the words of its error messages.
# Printed after a failed validation so the right file gets read.
REFERENCE_HINTS = [
    (re.compile(r"calculat|coded|codes|'period'|period type|categoryVariable|--existing", re.I),
     "references/calculated-variables.md"),
    (re.compile(r"slider|dragdrop|ranking|rank '|minValue|maxValue|interface='(alpha|numeric)'", re.I),
     "references/grid-interfaces.md"),
    (re.compile(r"text object|formatting tag|field '|participant field|'html'", re.I),
     "references/texts.md"),
    (re.compile(r"^\[(update|result)\]"), "references/task-update.md"),
]


def reference_hints(errors: list[str]) -> list[str]:
    return [ref for rx, ref in REFERENCE_HINTS if any(rx.search(e) for e in errors)]


def main():
    # the messages contain non-ASCII characters (e.g. the warning sign) - a Windows console would fail on them
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    options = {}
    for opt in ("--existing", "--base"):
        if opt in args:
            i = args.index(opt)
            if i + 1 >= len(args):
                print(USAGE)
                sys.exit(2)
            options[opt] = Path(args[i + 1])
            del args[i : i + 2]
    if len(args) != 1:
        print(USAGE)
        sys.exit(2)
    existing_path = options.get("--existing")
    base_path = options.get("--base")

    path = Path(args[0])
    for p in (path, existing_path, base_path):
        if p is not None and not p.exists():
            print(f"ERROR: file not found: {p}")
            sys.exit(2)

    try:
        data = load_json(path)
        existing = load_json(existing_path).get("questions") if existing_path else None
        base = load_json(base_path) if base_path else None
    except json.JSONDecodeError as e:
        print(f"[json] invalid JSON: {e}")
        sys.exit(1)

    if isinstance(data, dict) and "updateMode" in data:
        errors, warnings, review = validate_update(data, base)
        errors = list(dict.fromkeys(errors))
        if errors:
            print(f"FAILED: {len(errors)} problem(s) found in update file {path}")
            for e in errors:
                print(f"  - {e}")
            for ref in reference_hints(errors):
                print(f"  → read {ref} for this feature")
            sys.exit(1)
        n = sum(1 for q in data.get("questions", []) if isinstance(q, dict) and "update" in q)
        print(f"OK: {path} is a valid update file ({n} changed questions"
              + (f", checked against {base_path}" if base_path else "") + ")")
        for line in review:
            print(f"  {line}")
        for w in warnings:
            print(f"  ⚠ {w}")
        sys.exit(0)
    if base_path:
        print("ERROR: --base is only used with an update file (\"updateMode\": true)")
        sys.exit(2)

    errors = validate_schema(data) + validate_semantics(data, existing) + update_markup_in_create_file(data)

    if errors:
        print(f"FAILED: {len(errors)} problem(s) found in {path}")
        for e in errors:
            print(f"  - {e}")
        for ref in reference_hints(errors):
            print(f"  → read {ref} for this feature")
        sys.exit(1)

    n_q = len(data.get("questions", []))
    n_r = len(data.get("responses", []))
    n_p = len(data.get("participants", []))
    n_sm = len(data.get("surveyMessages", {}) or {})
    n_om = len(data.get("messages", []) or [])
    parts = [f"{n_q} questions", f"{n_r} responses"]
    if n_p:
        parts.append(f"{n_p} participants")
    if n_sm:
        parts.append(f"{n_sm} survey messages")
    if n_om:
        parts.append(f"{n_om} outbound messages")
    print(f"OK: {path} is valid ({', '.join(parts)})")

    # Soft warnings — file is valid, but these may matter at send time.
    warnings = collect_warnings(data)
    for w in warnings:
        print(f"  ⚠ {w}")

    sys.exit(0)


if __name__ == "__main__":
    main()
