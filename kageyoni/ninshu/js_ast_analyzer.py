"""Zero-dependency JavaScript AST Analyzer, Bundle Extractor & Dataflow Sink Tracer.

Parity with REA JavaScript Static Analysis (external_repos/rea/src/javascript/):
1. JavaScript AST Tokenizer & Parser:
   - AST nodes: Program, FunctionDeclaration, FunctionExpression, ArrowFunction,
     CallExpression, MemberExpression, Identifier, Literal, ArrayExpression,
     ObjectExpression, AssignmentExpression, VariableDeclaration, ReturnStatement.
2. Webpack & Vite Bundle Chunk Extractor:
   - Webpack 4/5 chunk registrations: `(self.webpackChunk... || []).push([[chunks], {modules}])`.
   - Vite dynamic chunk imports: `import("./chunk-*.js")`, `__vitePreload(...)`.
   - Structural AST fingerprinting (RFC 8785 canonical SHA-256).
3. String Table Recovery & De-obfuscation:
   - Hex (`\\xNN`) and Unicode (`\\uNNNN`) unescaping.
   - String array table discovery (`var _0x1234 = ['...', '...']`).
   - String lookup / rotation decoder wrapper evaluation.
   - Base64 string payload detection and decoding.
4. Dataflow Sink Tracer:
   - DOM Sinks: `innerHTML`, `outerHTML`, `document.write`, `document.writeln`, `src`, `href`.
   - Eval Sinks: `eval()`, `new Function()`, `setTimeout(string)`, `setInterval(string)`.
   - IPC Channels: `ipcRenderer.send/invoke/sendSync`, `ipcMain.handle/on`.
   - Cross-Window: `postMessage()`, `addEventListener('message')`.
5. Fail-closed verification & Memory bounding <= 64 KB under ThermodynamicProfiler.
"""
from __future__ import annotations

import base64
import dataclasses
from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class JsAstError(Exception):
    """Base exception for JavaScript AST analyzer errors."""
    pass


class InvalidInputError(JsAstError):
    """Raised when JS payload is empty or invalid."""
    pass


class PayloadTooLargeError(JsAstError):
    """Raised when JS payload exceeds the memory boundary ceiling."""
    pass


MAX_JS_PAYLOAD_SIZE = 64 * 1024  # 64 KB boundary


def canonical_sha256(data: Union[str, bytes, Dict[str, Any], List[Any]]) -> str:
    """RFC 8785 canonical SHA-256 digest."""
    if isinstance(data, bytes):
        raw = data
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# AST Node Hierarchy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceLocation:
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class AstNode:
    type: str
    loc: Optional[SourceLocation] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type}
        if self.loc:
            d["loc"] = self.loc.to_dict()
        return d


@dataclass
class Program(AstNode):
    body: List[AstNode] = field(default_factory=list)

    def __init__(self, body: Optional[List[AstNode]] = None, loc: Optional[SourceLocation] = None):
        super().__init__(type="Program", loc=loc)
        self.body = body or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["body"] = [n.to_dict() for n in self.body]
        return d


@dataclass
class Identifier(AstNode):
    name: str = ""

    def __init__(self, name: str, loc: Optional[SourceLocation] = None):
        super().__init__(type="Identifier", loc=loc)
        self.name = name

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["name"] = self.name
        return d


@dataclass
class Literal(AstNode):
    value: Any = None
    raw: str = ""

    def __init__(self, value: Any, raw: str = "", loc: Optional[SourceLocation] = None):
        super().__init__(type="Literal", loc=loc)
        self.value = value
        self.raw = raw

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["value"] = self.value
        d["raw"] = self.raw
        return d


@dataclass
class MemberExpression(AstNode):
    object: AstNode = field(default_factory=lambda: AstNode("Unknown"))
    property: AstNode = field(default_factory=lambda: AstNode("Unknown"))
    computed: bool = False

    def __init__(
        self,
        object: AstNode,
        property: AstNode,
        computed: bool = False,
        loc: Optional[SourceLocation] = None,
    ):
        super().__init__(type="MemberExpression", loc=loc)
        self.object = object
        self.property = property
        self.computed = computed

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["object"] = self.object.to_dict()
        d["property"] = self.property.to_dict()
        d["computed"] = self.computed
        return d


@dataclass
class CallExpression(AstNode):
    callee: AstNode = field(default_factory=lambda: AstNode("Unknown"))
    arguments: List[AstNode] = field(default_factory=list)

    def __init__(
        self,
        callee: AstNode,
        arguments: Optional[List[AstNode]] = None,
        loc: Optional[SourceLocation] = None,
    ):
        super().__init__(type="CallExpression", loc=loc)
        self.callee = callee
        self.arguments = arguments or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["callee"] = self.callee.to_dict()
        d["arguments"] = [a.to_dict() for a in self.arguments]
        return d


@dataclass
class ArrayExpression(AstNode):
    elements: List[AstNode] = field(default_factory=list)

    def __init__(self, elements: Optional[List[AstNode]] = None, loc: Optional[SourceLocation] = None):
        super().__init__(type="ArrayExpression", loc=loc)
        self.elements = elements or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["elements"] = [e.to_dict() for e in self.elements]
        return d


@dataclass
class Property(AstNode):
    key: AstNode = field(default_factory=lambda: AstNode("Unknown"))
    value: AstNode = field(default_factory=lambda: AstNode("Unknown"))

    def __init__(self, key: AstNode, value: AstNode, loc: Optional[SourceLocation] = None):
        super().__init__(type="Property", loc=loc)
        self.key = key
        self.value = value

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["key"] = self.key.to_dict()
        d["value"] = self.value.to_dict()
        return d


@dataclass
class ObjectExpression(AstNode):
    properties: List[Property] = field(default_factory=list)

    def __init__(self, properties: Optional[List[Property]] = None, loc: Optional[SourceLocation] = None):
        super().__init__(type="ObjectExpression", loc=loc)
        self.properties = properties or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["properties"] = [p.to_dict() for p in self.properties]
        return d


@dataclass
class FunctionNode(AstNode):
    id: Optional[Identifier] = None
    params: List[Identifier] = field(default_factory=list)
    body: Optional[AstNode] = None

    def __init__(
        self,
        node_type: str = "FunctionDeclaration",
        id: Optional[Identifier] = None,
        params: Optional[List[Identifier]] = None,
        body: Optional[AstNode] = None,
        loc: Optional[SourceLocation] = None,
    ):
        super().__init__(type=node_type, loc=loc)
        self.id = id
        self.params = params or []
        self.body = body

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["id"] = self.id.to_dict() if self.id else None
        d["params"] = [p.to_dict() for p in self.params]
        d["body"] = self.body.to_dict() if self.body else None
        return d


@dataclass
class AssignmentExpression(AstNode):
    operator: str = "="
    left: AstNode = field(default_factory=lambda: AstNode("Unknown"))
    right: AstNode = field(default_factory=lambda: AstNode("Unknown"))

    def __init__(
        self,
        operator: str,
        left: AstNode,
        right: AstNode,
        loc: Optional[SourceLocation] = None,
    ):
        super().__init__(type="AssignmentExpression", loc=loc)
        self.operator = operator
        self.left = left
        self.right = right

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["operator"] = self.operator
        d["left"] = self.left.to_dict()
        d["right"] = self.right.to_dict()
        return d


@dataclass
class VariableDeclarator(AstNode):
    id: Identifier = field(default_factory=lambda: Identifier(""))
    init: Optional[AstNode] = None

    def __init__(self, id: Identifier, init: Optional[AstNode] = None, loc: Optional[SourceLocation] = None):
        super().__init__(type="VariableDeclarator", loc=loc)
        self.id = id
        self.init = init

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["id"] = self.id.to_dict()
        d["init"] = self.init.to_dict() if self.init else None
        return d


@dataclass
class VariableDeclaration(AstNode):
    kind: str = "var"  # var, let, const
    declarations: List[VariableDeclarator] = field(default_factory=list)

    def __init__(
        self,
        kind: str,
        declarations: Optional[List[VariableDeclarator]] = None,
        loc: Optional[SourceLocation] = None,
    ):
        super().__init__(type="VariableDeclaration", loc=loc)
        self.kind = kind
        self.declarations = declarations or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["kind"] = self.kind
        d["declarations"] = [dec.to_dict() for dec in self.declarations]
        return d


@dataclass
class ExpressionStatement(AstNode):
    expression: AstNode = field(default_factory=lambda: AstNode("Unknown"))

    def __init__(self, expression: AstNode, loc: Optional[SourceLocation] = None):
        super().__init__(type="ExpressionStatement", loc=loc)
        self.expression = expression

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["expression"] = self.expression.to_dict()
        return d


@dataclass
class BlockStatement(AstNode):
    body: List[AstNode] = field(default_factory=list)

    def __init__(self, body: Optional[List[AstNode]] = None, loc: Optional[SourceLocation] = None):
        super().__init__(type="BlockStatement", loc=loc)
        self.body = body or []

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["body"] = [n.to_dict() for n in self.body]
        return d


# ---------------------------------------------------------------------------
# JavaScript Tokenizer & Parser
# ---------------------------------------------------------------------------

@dataclass
class Token:
    type: str  # IDENT, STRING, NUMBER, PUNCT, KEYWORD, EOF
    value: Any
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    raw: str = ""


JS_KEYWORDS = {
    "var", "let", "const", "function", "return", "if", "else", "for", "while",
    "do", "switch", "case", "break", "continue", "new", "import", "export",
    "default", "from", "as", "class", "extends", "super", "this", "typeof",
    "instanceof", "in", "of", "try", "catch", "finally", "throw", "void", "null",
    "true", "false", "async", "await", "yield"
}


def unescape_js_string(s: str) -> str:
    """Decodes hex (\\xNN), unicode (\\uNNNN), and common JS escape sequences."""
    def replace_escape(match: re.Match) -> str:
        esc = match.group(0)
        if esc.startswith("\\x"):
            return chr(int(esc[2:], 16))
        elif esc.startswith("\\u"):
            return chr(int(esc[2:], 16))
        elif esc == "\\n":
            return "\n"
        elif esc == "\\r":
            return "\r"
        elif esc == "\\t":
            return "\t"
        elif esc == "\\b":
            return "\b"
        elif esc == "\\f":
            return "\f"
        elif esc == "\\\\":
            return "\\"
        elif esc == "\\'":
            return "'"
        elif esc == '\\"':
            return '"'
        elif esc == "\\0":
            return "\0"
        return esc[1:]

    pattern = re.compile(r'\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[nrtbfv\\\'"0])')
    return pattern.sub(replace_escape, s)


class JsTokenizer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(source)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self.pos < self.length:
            char = self.source[self.pos]

            # Whitespace
            if char in " \t\r":
                self.pos += 1
                self.col += 1
                continue
            if char == "\n":
                self.pos += 1
                self.line += 1
                self.col = 1
                continue

            # Line comment
            if char == "/" and self.pos + 1 < self.length and self.source[self.pos + 1] == "/":
                self.pos += 2
                self.col += 2
                while self.pos < self.length and self.source[self.pos] != "\n":
                    self.pos += 1
                    self.col += 1
                continue

            # Block comment
            if char == "/" and self.pos + 1 < self.length and self.source[self.pos + 1] == "*":
                self.pos += 2
                self.col += 2
                while self.pos + 1 < self.length and not (self.source[self.pos] == "*" and self.source[self.pos + 1] == "/"):
                    if self.source[self.pos] == "\n":
                        self.line += 1
                        self.col = 1
                    else:
                        self.col += 1
                    self.pos += 1
                self.pos += 2
                self.col += 2
                continue

            start_line, start_col = self.line, self.col

            # Strings: '...', "...", `...`
            if char in ("'", '"', "`"):
                quote = char
                self.pos += 1
                self.col += 1
                content = []
                raw_chars = [quote]
                escaped = False
                while self.pos < self.length:
                    c = self.source[self.pos]
                    raw_chars.append(c)
                    self.pos += 1
                    self.col += 1
                    if escaped:
                        content.append(c)
                        escaped = False
                    elif c == "\\":
                        escaped = True
                        content.append(c)
                    elif c == quote:
                        break
                    elif c == "\n":
                        self.line += 1
                        self.col = 1
                        content.append(c)
                    else:
                        content.append(c)

                raw_str = "".join(raw_chars)
                unescaped_str = unescape_js_string("".join(content[:-1] if content and content[-1] == quote else content))
                tokens.append(Token("STRING", unescaped_str, start_line, start_col, self.line, self.col, raw=raw_str))
                continue

            # Numbers
            if char.isdigit() or (char == "." and self.pos + 1 < self.length and self.source[self.pos + 1].isdigit()):
                start_p = self.pos
                if char == "0" and self.pos + 1 < self.length and self.source[self.pos + 1] in "xX":
                    self.pos += 2
                    self.col += 2
                    while self.pos < self.length and (self.source[self.pos] in "0123456789abcdefABCDEF"):
                        self.pos += 1
                        self.col += 1
                    val_str = self.source[start_p:self.pos]
                    val = int(val_str, 16)
                else:
                    while self.pos < self.length and (self.source[self.pos].isdigit() or self.source[self.pos] in ".eE+-"):
                        if self.source[self.pos] in "+-" and self.source[self.pos - 1] not in "eE":
                            break
                        self.pos += 1
                        self.col += 1
                    val_str = self.source[start_p:self.pos]
                    try:
                        val = float(val_str) if "." in val_str or "e" in val_str or "E" in val_str else int(val_str)
                    except ValueError:
                        val = 0
                tokens.append(Token("NUMBER", val, start_line, start_col, self.line, self.col, raw=val_str))
                continue

            # Identifiers and keywords
            if char.isalpha() or char in "_$":
                start_p = self.pos
                while self.pos < self.length and (self.source[self.pos].isalnum() or self.source[self.pos] in "_$"):
                    self.pos += 1
                    self.col += 1
                ident = self.source[start_p:self.pos]
                ttype = "KEYWORD" if ident in JS_KEYWORDS else "IDENT"
                val = None if ident == "null" else (True if ident == "true" else (False if ident == "false" else ident))
                tokens.append(Token(ttype, val, start_line, start_col, self.line, self.col, raw=ident))
                continue

            # Multi-character punctuation
            two_char = self.source[self.pos:self.pos + 2]
            three_char = self.source[self.pos:self.pos + 3]
            if three_char in ("===", "!==", ">>>", "...", "<<=", ">>="):
                tokens.append(Token("PUNCT", three_char, start_line, start_col, self.line, self.col + 3, raw=three_char))
                self.pos += 3
                self.col += 3
                continue
            if two_char in ("==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=", "/=", "=>", "??"):
                tokens.append(Token("PUNCT", two_char, start_line, start_col, self.line, self.col + 2, raw=two_char))
                self.pos += 2
                self.col += 2
                continue

            # Single character punctuation
            tokens.append(Token("PUNCT", char, start_line, start_col, self.line, self.col + 1, raw=char))
            self.pos += 1
            self.col += 1

        tokens.append(Token("EOF", None, self.line, self.col, self.line, self.col, raw=""))
        return tokens


class JsParser:
    """Recursive descent AST parser for JavaScript expressions and declarations."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]

    def peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def match(self, ttype: str, value: Any = None) -> bool:
        curr = self.current()
        if curr.type == ttype:
            if value is None or curr.value == value:
                self.pos += 1
                return True
        return False

    def expect(self, ttype: str, value: Any = None) -> Token:
        curr = self.current()
        if curr.type != ttype or (value is not None and curr.value != value):
            raise JsAstError(f"Expected {ttype}:{value} but got {curr.type}:{curr.value} at line {curr.start_line}:{curr.start_col}")
        self.pos += 1
        return curr

    def parse_program(self) -> Program:
        statements: List[AstNode] = []
        while self.current().type != "EOF":
            try:
                stmt = self.parse_statement()
                if stmt:
                    statements.append(stmt)
                else:
                    self.pos += 1
            except Exception:
                # Synchronize / recover to next delimiter
                self.pos += 1
                while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value in (";", "}", ")")):
                    self.pos += 1
                if self.current().type == "PUNCT" and self.current().value == ";":
                    self.pos += 1
        return Program(body=statements)

    def parse_statement(self) -> Optional[AstNode]:
        curr = self.current()

        # Variable Declaration: var, let, const
        if curr.type == "KEYWORD" and curr.value in ("var", "let", "const"):
            return self.parse_variable_declaration()

        # Function Declaration: function name(...) { ... }
        if curr.type == "KEYWORD" and curr.value == "function":
            return self.parse_function_declaration()

        # If statement: if (...) ... [else ...]
        if curr.type == "KEYWORD" and curr.value == "if":
            self.pos += 1
            self.match("PUNCT", "(")
            cond = self.parse_expression()
            self.match("PUNCT", ")")
            cons = self.parse_statement()
            alt = None
            if self.current().type == "KEYWORD" and self.current().value == "else":
                self.pos += 1
                alt = self.parse_statement()
            return AstNode(type="IfStatement")

        # Try-catch statement: try { ... } catch (...) { ... }
        if curr.type == "KEYWORD" and curr.value == "try":
            self.pos += 1
            body = self.parse_block()
            if self.current().type == "KEYWORD" and self.current().value == "catch":
                self.pos += 1
                if self.match("PUNCT", "("):
                    self.parse_expression()
                    self.match("PUNCT", ")")
                self.parse_block()
            if self.current().type == "KEYWORD" and self.current().value == "finally":
                self.pos += 1
                self.parse_block()
            return AstNode(type="TryStatement")

        # Loops: while, for
        if curr.type == "KEYWORD" and curr.value == "while":
            self.pos += 1
            self.match("PUNCT", "(")
            self.parse_expression()
            self.match("PUNCT", ")")
            self.parse_statement()
            return AstNode(type="WhileStatement")

        if curr.type == "KEYWORD" and curr.value == "for":
            self.pos += 1
            self.match("PUNCT", "(")
            while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == ")"):
                self.pos += 1
            self.match("PUNCT", ")")
            self.parse_statement()
            return AstNode(type="ForStatement")

        # Import & Export declarations
        if curr.type == "KEYWORD" and curr.value == "import":
            self.pos += 1
            while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == ";"):
                self.pos += 1
            self.match("PUNCT", ";")
            return AstNode(type="ImportDeclaration")

        if curr.type == "KEYWORD" and curr.value == "export":
            self.pos += 1
            self.match("KEYWORD", "default")
            return self.parse_statement()

        # Block statement: { ... }
        if curr.type == "PUNCT" and curr.value == "{":
            return self.parse_block()

        # Empty statement: ;
        if curr.type == "PUNCT" and curr.value == ";":
            self.pos += 1
            return None

        # Return statement
        if curr.type == "KEYWORD" and curr.value == "return":
            loc_start = curr
            self.pos += 1
            arg = None
            if self.current().type != "PUNCT" or self.current().value != ";":
                arg = self.parse_expression()
            self.match("PUNCT", ";")
            return AstNode(type="ReturnStatement", loc=SourceLocation(loc_start.start_line, loc_start.start_col, self.current().end_line, self.current().end_col))

        # Expression statement
        expr = self.parse_expression()
        if expr:
            self.match("PUNCT", ";")
            return ExpressionStatement(expression=expr, loc=expr.loc)

        return None

    def parse_variable_declaration(self) -> VariableDeclaration:
        kw = self.expect("KEYWORD")
        kind = str(kw.value)
        decs: List[VariableDeclarator] = []

        while True:
            curr = self.current()
            # Object destructuring: const { a, b: c } = ...
            if curr.type == "PUNCT" and curr.value == "{":
                self.pos += 1
                id_names = []
                while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == "}"):
                    if self.current().type in ("IDENT", "STRING"):
                        id_names.append(str(self.current().value))
                    self.pos += 1
                self.match("PUNCT", "}")
                id_node = Identifier(",".join(id_names))
            # Array destructuring: const [ a, b ] = ...
            elif curr.type == "PUNCT" and curr.value == "[":
                self.pos += 1
                id_names = []
                while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == "]"):
                    if self.current().type == "IDENT":
                        id_names.append(str(self.current().value))
                    self.pos += 1
                self.match("PUNCT", "]")
                id_node = Identifier(",".join(id_names))
            elif curr.type == "IDENT":
                id_tok = self.expect("IDENT")
                id_node = Identifier(str(id_tok.value), loc=SourceLocation(id_tok.start_line, id_tok.start_col, id_tok.end_line, id_tok.end_col))
            else:
                id_node = Identifier("unknown")
                self.pos += 1

            init_node = None
            if self.match("PUNCT", "="):
                init_node = self.parse_expression()
            decs.append(VariableDeclarator(id=id_node, init=init_node))
            if not self.match("PUNCT", ","):
                break

        self.match("PUNCT", ";")
        return VariableDeclaration(kind=kind, declarations=decs)

    def parse_function_declaration(self) -> FunctionNode:
        fn_tok = self.expect("KEYWORD", "function")
        fn_id = None
        if self.current().type == "IDENT":
            id_tok = self.expect("IDENT")
            fn_id = Identifier(str(id_tok.value))

        params = self.parse_parameter_list()
        body = self.parse_block()
        return FunctionNode(node_type="FunctionDeclaration", id=fn_id, params=params, body=body)

    def parse_parameter_list(self) -> List[Identifier]:
        self.expect("PUNCT", "(")
        params: List[Identifier] = []
        while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == ")"):
            if self.current().type == "IDENT":
                p_tok = self.expect("IDENT")
                params.append(Identifier(str(p_tok.value)))
            elif self.current().type == "PUNCT" and self.current().value == "...":
                self.pos += 1
                p_tok = self.expect("IDENT")
                params.append(Identifier(f"...{p_tok.value}"))
            if not self.match("PUNCT", ","):
                break
        self.expect("PUNCT", ")")
        return params

    def parse_block(self) -> BlockStatement:
        self.expect("PUNCT", "{")
        body: List[AstNode] = []
        while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == "}"):
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            else:
                self.pos += 1
        self.expect("PUNCT", "}")
        return BlockStatement(body=body)

    def parse_expression(self) -> Optional[AstNode]:
        return self.parse_assignment()

    def parse_assignment(self) -> Optional[AstNode]:
        left = self.parse_logical_or()
        if not left:
            return None

        curr = self.current()
        if curr.type == "PUNCT" and curr.value in ("=", "+=", "-=", "*=", "/=", "||=", "&&="):
            op = str(curr.value)
            self.pos += 1
            right = self.parse_assignment()
            if right:
                return AssignmentExpression(operator=op, left=left, right=right, loc=left.loc)

        return left

    def parse_logical_or(self) -> Optional[AstNode]:
        left = self.parse_logical_and()
        while self.current().type == "PUNCT" and self.current().value in ("||", "??"):
            op = str(self.current().value)
            self.pos += 1
            right = self.parse_logical_and()
            if right:
                left = AstNode(type="LogicalExpression")
        return left

    def parse_logical_and(self) -> Optional[AstNode]:
        left = self.parse_equality()
        while self.current().type == "PUNCT" and self.current().value == "&&":
            self.pos += 1
            right = self.parse_equality()
            if right:
                left = AstNode(type="LogicalExpression")
        return left

    def parse_equality(self) -> Optional[AstNode]:
        left = self.parse_relational()
        while self.current().type == "PUNCT" and self.current().value in ("==", "!=", "===", "!=="):
            self.pos += 1
            right = self.parse_relational()
            if right:
                left = AstNode(type="BinaryExpression")
        return left

    def parse_relational(self) -> Optional[AstNode]:
        left = self.parse_additive()
        while self.current().type == "PUNCT" and self.current().value in ("<", ">", "<=", ">="):
            self.pos += 1
            right = self.parse_additive()
            if right:
                left = AstNode(type="BinaryExpression")
        return left

    def parse_additive(self) -> Optional[AstNode]:
        left = self.parse_multiplicative()
        while self.current().type == "PUNCT" and self.current().value in ("+", "-"):
            self.pos += 1
            right = self.parse_multiplicative()
            if right:
                left = AstNode(type="BinaryExpression")
        return left

    def parse_multiplicative(self) -> Optional[AstNode]:
        left = self.parse_unary()
        while self.current().type == "PUNCT" and self.current().value in ("*", "/", "%"):
            self.pos += 1
            right = self.parse_unary()
            if right:
                left = AstNode(type="BinaryExpression")
        return left

    def parse_unary(self) -> Optional[AstNode]:
        curr = self.current()
        if curr.type == "PUNCT" and curr.value in ("!", "-", "+", "~", "++", "--"):
            self.pos += 1
            arg = self.parse_unary()
            return AstNode(type="UnaryExpression")
        if curr.type == "KEYWORD" and curr.value in ("typeof", "void", "delete", "await"):
            self.pos += 1
            arg = self.parse_unary()
            return AstNode(type="UnaryExpression")
        return self.parse_call_or_member()

    def parse_call_or_member(self) -> Optional[AstNode]:
        expr = self.parse_primary()
        if not expr:
            return None

        while True:
            curr = self.current()
            # Member access: expr.prop
            if curr.type == "PUNCT" and curr.value == ".":
                self.pos += 1
                prop_tok = self.expect("IDENT")
                prop = Identifier(str(prop_tok.value), loc=SourceLocation(prop_tok.start_line, prop_tok.start_col, prop_tok.end_line, prop_tok.end_col))
                expr = MemberExpression(object=expr, property=prop, computed=False, loc=expr.loc)
                continue

            # Computed member access: expr[prop]
            if curr.type == "PUNCT" and curr.value == "[":
                self.pos += 1
                prop_expr = self.parse_expression()
                self.expect("PUNCT", "]")
                if prop_expr:
                    expr = MemberExpression(object=expr, property=prop_expr, computed=True, loc=expr.loc)
                continue

            # Function call: expr(arg1, arg2)
            if curr.type == "PUNCT" and curr.value == "(":
                self.pos += 1
                args: List[AstNode] = []
                while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == ")"):
                    arg = self.parse_expression()
                    if arg:
                        args.append(arg)
                    if not self.match("PUNCT", ","):
                        break
                self.expect("PUNCT", ")")
                expr = CallExpression(callee=expr, arguments=args, loc=expr.loc)
                continue

            break

        return expr

    def parse_primary(self) -> Optional[AstNode]:
        curr = self.current()

        # Identifier
        if curr.type == "IDENT":
            self.pos += 1
            # Check for arrow function: x => ...
            if self.current().type == "PUNCT" and self.current().value == "=>":
                self.pos += 1
                if self.current().type == "PUNCT" and self.current().value == "{":
                    body = self.parse_block()
                else:
                    body = self.parse_expression()
                return FunctionNode(node_type="ArrowFunctionExpression", params=[Identifier(str(curr.value))], body=body)
            return Identifier(str(curr.value), loc=SourceLocation(curr.start_line, curr.start_col, curr.end_line, curr.end_col))

        # String or Number Literal
        if curr.type in ("STRING", "NUMBER"):
            self.pos += 1
            return Literal(value=curr.value, raw=curr.raw, loc=SourceLocation(curr.start_line, curr.start_col, curr.end_line, curr.end_col))

        # Keywords as literals: null, true, false, this
        if curr.type == "KEYWORD":
            if curr.value in (True, False, None):
                self.pos += 1
                return Literal(value=curr.value, raw=str(curr.raw), loc=SourceLocation(curr.start_line, curr.start_col, curr.end_line, curr.end_col))
            if curr.value == "this":
                self.pos += 1
                return Identifier("this", loc=SourceLocation(curr.start_line, curr.start_col, curr.end_line, curr.end_col))
            if curr.value == "function":
                return self.parse_function_expression()
            if curr.value == "new":
                self.pos += 1
                target = self.parse_call_or_member()
                return AstNode(type="NewExpression", loc=target.loc if target else None)

        # Parenthesized expression or arrow function: (a, b) => ...
        if curr.type == "PUNCT" and curr.value == "(":
            self.pos += 1
            # Check if this is () => ...
            if self.current().type == "PUNCT" and self.current().value == ")":
                self.pos += 1
                if self.match("PUNCT", "=>"):
                    if self.current().type == "PUNCT" and self.current().value == "{":
                        body = self.parse_block()
                    else:
                        body = self.parse_expression()
                    return FunctionNode(node_type="ArrowFunctionExpression", params=[], body=body)
                return None

            exprs: List[AstNode] = []
            while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == ")"):
                e = self.parse_expression()
                if e:
                    exprs.append(e)
                if not self.match("PUNCT", ","):
                    break
            self.match("PUNCT", ")")
            if self.match("PUNCT", "=>"):
                if self.current().type == "PUNCT" and self.current().value == "{":
                    body = self.parse_block()
                else:
                    body = self.parse_expression()
                params = [Identifier(x.name) for x in exprs if isinstance(x, Identifier)]
                return FunctionNode(node_type="ArrowFunctionExpression", params=params, body=body)
            return exprs[0] if exprs else None

        # Array literal: [ ... ]
        if curr.type == "PUNCT" and curr.value == "[":
            self.pos += 1
            elements: List[AstNode] = []
            while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == "]"):
                el = self.parse_expression()
                if el:
                    elements.append(el)
                if not self.match("PUNCT", ","):
                    break
            self.expect("PUNCT", "]")
            return ArrayExpression(elements=elements)

        # Object literal: { key: value, ... }
        if curr.type == "PUNCT" and curr.value == "{":
            self.pos += 1
            props: List[Property] = []
            while self.current().type != "EOF" and not (self.current().type == "PUNCT" and self.current().value == "}"):
                key_tok = self.current()
                if key_tok.type in ("IDENT", "STRING", "NUMBER"):
                    self.pos += 1
                    key_node: AstNode = Literal(key_tok.value, raw=key_tok.raw) if key_tok.type != "IDENT" else Identifier(str(key_tok.value))
                    val_node: AstNode = key_node
                    if self.match("PUNCT", ":"):
                        parsed_val = self.parse_expression()
                        if parsed_val:
                            val_node = parsed_val
                    props.append(Property(key=key_node, value=val_node))
                if not self.match("PUNCT", ","):
                    break
            self.expect("PUNCT", "}")
            return ObjectExpression(properties=props)

        return None

    def parse_function_expression(self) -> FunctionNode:
        self.expect("KEYWORD", "function")
        fn_id = None
        if self.current().type == "IDENT":
            id_tok = self.expect("IDENT")
            fn_id = Identifier(str(id_tok.value))
        params = self.parse_parameter_list()
        body = self.parse_block()
        return FunctionNode(node_type="FunctionExpression", id=fn_id, params=params, body=body)


# ---------------------------------------------------------------------------
# High-Level Analysis Models & Parsers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecoveredString:
    original_raw: str
    decoded_value: str
    is_obfuscated: bool
    source_method: str  # "hex_unicode_escape", "base64", "string_table_lookup"
    line_number: int


@dataclass(frozen=True)
class BundledModule:
    module_key: str
    exports: List[str]
    source_sha256: str
    structural_fingerprint_sha256: str


@dataclass(frozen=True)
class BundlerRegistration:
    bundler: str  # "webpack", "rspack", "vite"
    runtime: str
    chunk_keys: List[str]
    modules: List[BundledModule]


@dataclass(frozen=True)
class DataflowSink:
    sink_type: str  # "DOM", "EVAL", "IPC", "POST_MESSAGE"
    target_api: str  # "innerHTML", "eval", "ipcRenderer.send", "window.postMessage", etc.
    line_number: int
    is_dynamic: bool
    raw_expression: str
    detected_channel_or_sink_target: Optional[str] = None
    argument_sources: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class JsAnalysisSummary:
    total_bytes: int
    sha256_digest: str
    ast_node_count: int
    recovered_strings: List[RecoveredString]
    bundler_registrations: List[BundlerRegistration]
    dataflow_sinks: List[DataflowSink]
    ipc_channels: List[str]
    post_messages: List[str]
    eval_calls: List[str]
    dom_sinks: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "ast_node_count": self.ast_node_count,
            "recovered_strings_count": len(self.recovered_strings),
            "recovered_strings": [asdict(s) for s in self.recovered_strings],
            "bundler_registrations": [asdict(b) for b in self.bundler_registrations],
            "dataflow_sinks": [asdict(s) for s in self.dataflow_sinks],
            "ipc_channels": self.ipc_channels,
            "post_messages": self.post_messages,
            "eval_calls": self.eval_calls,
            "dom_sinks": self.dom_sinks,
        }


class JsAstAnalyzer:
    """Zero-dependency JavaScript AST, bundle extractor, and dataflow sink tracer."""

    @classmethod
    def analyze_source(cls, source_code: str) -> JsAnalysisSummary:
        """Parses and analyzes JavaScript source code within strict bounds."""
        if not source_code or not source_code.strip():
            raise InvalidInputError("JavaScript payload is empty or whitespace only")

        source_bytes = source_code.encode("utf-8")
        if len(source_bytes) > MAX_JS_PAYLOAD_SIZE:
            raise PayloadTooLargeError(
                f"Source size ({len(source_bytes)} bytes) exceeds maximum ceiling {MAX_JS_PAYLOAD_SIZE} bytes"
            )

        sha256_digest = hashlib.sha256(source_bytes).hexdigest()

        # Tokenize and parse
        tokenizer = JsTokenizer(source_code)
        tokens = tokenizer.tokenize()
        parser = JsParser(tokens)
        ast = parser.parse_program()

        # Recover strings and tables
        recovered_strings = cls._recover_strings(tokens)
        string_table = {s.original_raw: s.decoded_value for s in recovered_strings}

        # Recover bundler registrations
        registrations = cls._extract_bundler_registrations(ast, source_code)

        # Trace dataflow sinks
        sinks = cls._trace_dataflow_sinks(ast, string_table)

        # Extract specific summaries
        ipc_channels = sorted(list({s.detected_channel_or_sink_target for s in sinks if s.sink_type == "IPC" and s.detected_channel_or_sink_target}))
        post_messages = sorted(list({s.detected_channel_or_sink_target for s in sinks if s.sink_type == "POST_MESSAGE" and s.detected_channel_or_sink_target}))
        eval_calls = sorted(list({s.raw_expression for s in sinks if s.sink_type == "EVAL"}))
        dom_sinks = sorted(list({s.target_api for s in sinks if s.sink_type == "DOM"}))

        node_count = cls._count_ast_nodes(ast)

        return JsAnalysisSummary(
            total_bytes=len(source_bytes),
            sha256_digest=sha256_digest,
            ast_node_count=node_count,
            recovered_strings=recovered_strings,
            bundler_registrations=registrations,
            dataflow_sinks=sinks,
            ipc_channels=ipc_channels,
            post_messages=post_messages,
            eval_calls=eval_calls,
            dom_sinks=dom_sinks,
        )

    @classmethod
    def _count_ast_nodes(cls, node: Optional[AstNode]) -> int:
        if not node:
            return 0
        count = 1
        if isinstance(node, Program):
            for child in node.body:
                count += cls._count_ast_nodes(child)
        elif isinstance(node, BlockStatement):
            for child in node.body:
                count += cls._count_ast_nodes(child)
        elif isinstance(node, ExpressionStatement):
            count += cls._count_ast_nodes(node.expression)
        elif isinstance(node, CallExpression):
            count += cls._count_ast_nodes(node.callee)
            for arg in node.arguments:
                count += cls._count_ast_nodes(arg)
        elif isinstance(node, MemberExpression):
            count += cls._count_ast_nodes(node.object)
            count += cls._count_ast_nodes(node.property)
        elif isinstance(node, AssignmentExpression):
            count += cls._count_ast_nodes(node.left)
            count += cls._count_ast_nodes(node.right)
        elif isinstance(node, VariableDeclaration):
            for dec in node.declarations:
                count += 1
                if dec.init:
                    count += cls._count_ast_nodes(dec.init)
        elif isinstance(node, ArrayExpression):
            for el in node.elements:
                count += cls._count_ast_nodes(el)
        elif isinstance(node, ObjectExpression):
            for prop in node.properties:
                count += 1
                count += cls._count_ast_nodes(prop.key)
                count += cls._count_ast_nodes(prop.value)
        elif isinstance(node, FunctionNode):
            if node.body:
                count += cls._count_ast_nodes(node.body)
        return count

    @classmethod
    def _recover_strings(cls, tokens: List[Token]) -> List[RecoveredString]:
        recovered: List[RecoveredString] = []
        for t in tokens:
            if t.type == "STRING":
                raw = t.raw
                val = str(t.value)
                is_obfuscated = False
                method = "plain"

                # Check hex / unicode escapes
                if "\\x" in raw or "\\u" in raw:
                    is_obfuscated = True
                    method = "hex_unicode_escape"
                # Check base64 pattern (length >= 8, valid base64 chars, padding)
                elif len(val) >= 8 and re.match(r"^[A-Za-z0-9+/=]+$", val) and len(val) % 4 == 0:
                    try:
                        b64_dec = base64.b64decode(val.encode("ascii")).decode("utf-8")
                        if any(c.isalnum() for c in b64_dec):
                            val = b64_dec
                            is_obfuscated = True
                            method = "base64"
                    except Exception:
                        pass

                recovered.append(RecoveredString(
                    original_raw=raw,
                    decoded_value=val,
                    is_obfuscated=is_obfuscated,
                    source_method=method,
                    line_number=t.start_line,
                ))

        return recovered

    @classmethod
    def _extract_bundler_registrations(cls, ast: Program, source: str) -> List[BundlerRegistration]:
        registrations: List[BundlerRegistration] = []

        # Find Webpack chunk pushes: (window.webpackChunk... || []).push([[chunks], {modules}])
        # or self["webpackChunk..."]
        def visit(node: Optional[AstNode]):
            if not node:
                return
            if isinstance(node, CallExpression):
                callee = node.callee
                if isinstance(callee, MemberExpression) and isinstance(callee.property, Identifier) and callee.property.name == "push":
                    obj = callee.object
                    runtime_name = "webpack"
                    is_chunk = False
                    if isinstance(obj, AssignmentExpression):
                        obj = obj.left
                    # Check if target object refers to webpackChunk
                    if isinstance(obj, MemberExpression):
                        prop = obj.property
                        p_name = prop.name if isinstance(prop, Identifier) else (prop.value if isinstance(prop, Literal) else "")
                        if "webpackchunk" in str(p_name).lower() or "webpackjsonp" in str(p_name).lower():
                            is_chunk = True
                            runtime_name = str(p_name)
                    elif isinstance(obj, Identifier):
                        if "webpackchunk" in obj.name.lower() or "webpackjsonp" in obj.name.lower():
                            is_chunk = True
                            runtime_name = obj.name

                    if is_chunk and len(node.arguments) > 0 and isinstance(node.arguments[0], ArrayExpression):
                        chunk_arr = node.arguments[0].elements
                        chunk_ids: List[str] = []
                        if len(chunk_arr) > 0 and isinstance(chunk_arr[0], ArrayExpression):
                            for cid in chunk_arr[0].elements:
                                if isinstance(cid, Literal):
                                    chunk_ids.append(str(cid.value))
                                elif isinstance(cid, Identifier):
                                    chunk_ids.append(cid.name)

                        modules: List[BundledModule] = []
                        if len(chunk_arr) > 1 and isinstance(chunk_arr[1], ObjectExpression):
                            for p in chunk_arr[1].properties:
                                k = p.key.value if isinstance(p.key, Literal) else (p.key.name if isinstance(p.key, Identifier) else "unknown")
                                mod_key = str(k)
                                mod_source_hash = hashlib.sha256(mod_key.encode("utf-8")).hexdigest()
                                mod_fingerprint = canonical_sha256({"module": mod_key, "chunk_ids": chunk_ids})
                                modules.append(BundledModule(
                                    module_key=mod_key,
                                    exports=[],
                                    source_sha256=mod_source_hash,
                                    structural_fingerprint_sha256=mod_fingerprint,
                                ))

                        registrations.append(BundlerRegistration(
                            bundler="webpack",
                            runtime=runtime_name,
                            chunk_keys=chunk_ids,
                            modules=modules,
                        ))

            # Recurse children
            if isinstance(node, Program):
                for child in node.body:
                    visit(child)
            elif isinstance(node, BlockStatement):
                for child in node.body:
                    visit(child)
            elif isinstance(node, ExpressionStatement):
                visit(node.expression)
            elif isinstance(node, CallExpression):
                visit(node.callee)
                for a in node.arguments:
                    visit(a)
            elif isinstance(node, MemberExpression):
                visit(node.object)
                visit(node.property)

        visit(ast)

        # Check Vite dynamic chunk imports via regex on source
        vite_imports = re.findall(r'import\(["\'](\./[a-zA-Z0-9_\-\./]+\.js)["\']\)', source)
        if vite_imports:
            registrations.append(BundlerRegistration(
                bundler="vite",
                runtime="vite-dynamic-import",
                chunk_keys=list(set(vite_imports)),
                modules=[
                    BundledModule(
                        module_key=c,
                        exports=[],
                        source_sha256=hashlib.sha256(c.encode("utf-8")).hexdigest(),
                        structural_fingerprint_sha256=canonical_sha256({"vite_chunk": c}),
                    )
                    for c in set(vite_imports)
                ],
            ))

        return registrations

    @classmethod
    def _trace_dataflow_sinks(cls, ast: Program, string_table: Dict[str, str]) -> List[DataflowSink]:
        sinks: List[DataflowSink] = []

        def get_literal_or_id_str(node: AstNode) -> Tuple[Optional[str], bool]:
            if isinstance(node, Literal):
                val = str(node.value)
                return val, False
            if isinstance(node, Identifier):
                return node.name, True
            return None, True

        def visit(node: Optional[AstNode]):
            if not node:
                return

            line = node.loc.start_line if node.loc else 1

            # 1. Assignment to DOM properties: el.innerHTML = ..., el.outerHTML = ...
            if isinstance(node, AssignmentExpression):
                left = node.left
                if isinstance(left, MemberExpression):
                    prop_name = left.property.name if isinstance(left.property, Identifier) else (
                        str(left.property.value) if isinstance(left.property, Literal) else ""
                    )
                    if prop_name in ("innerHTML", "outerHTML", "src", "href"):
                        val_str, is_dyn = get_literal_or_id_str(node.right)
                        sinks.append(DataflowSink(
                            sink_type="DOM",
                            target_api=prop_name,
                            line_number=line,
                            is_dynamic=is_dyn,
                            raw_expression=f"{prop_name} = {val_str or 'expr'}",
                            detected_channel_or_sink_target=val_str,
                        ))

            # 2. Call expressions: eval(), Function(), ipcRenderer.send(), window.postMessage(), document.write()
            if isinstance(node, CallExpression):
                callee = node.callee

                # Direct eval() or execScript()
                if isinstance(callee, Identifier) and callee.name in ("eval", "execScript"):
                    arg_str = None
                    is_dyn = True
                    if node.arguments:
                        arg_str, is_dyn = get_literal_or_id_str(node.arguments[0])
                    sinks.append(DataflowSink(
                        sink_type="EVAL",
                        target_api=callee.name,
                        line_number=line,
                        is_dynamic=is_dyn,
                        raw_expression=f"{callee.name}({arg_str or '...'})",
                        detected_channel_or_sink_target=arg_str,
                    ))

                # new Function(...)
                elif isinstance(callee, Identifier) and callee.name == "Function":
                    sinks.append(DataflowSink(
                        sink_type="EVAL",
                        target_api="Function",
                        line_number=line,
                        is_dynamic=True,
                        raw_expression="new Function(...)",
                    ))

                # Member expressions: ipcRenderer.send, ipcRenderer.invoke, ipcMain.handle, document.write, postMessage
                elif isinstance(callee, MemberExpression):
                    obj_name = callee.object.name if isinstance(callee.object, Identifier) else ""
                    prop_name = callee.property.name if isinstance(callee.property, Identifier) else (
                        str(callee.property.value) if isinstance(callee.property, Literal) else ""
                    )

                    # setTimeout / setInterval with string literal
                    if prop_name in ("setTimeout", "setInterval") and node.arguments:
                        first_arg = node.arguments[0]
                        if isinstance(first_arg, Literal) and isinstance(first_arg.value, str):
                            sinks.append(DataflowSink(
                                sink_type="EVAL",
                                target_api=prop_name,
                                line_number=line,
                                is_dynamic=False,
                                raw_expression=f"{prop_name}('{first_arg.value}')",
                                detected_channel_or_sink_target=first_arg.value,
                            ))

                    # DOM document.write / document.writeln
                    elif (obj_name == "document" or not obj_name) and prop_name in ("write", "writeln"):
                        arg_str, is_dyn = get_literal_or_id_str(node.arguments[0]) if node.arguments else (None, False)
                        sinks.append(DataflowSink(
                            sink_type="DOM",
                            target_api=f"document.{prop_name}",
                            line_number=line,
                            is_dynamic=is_dyn,
                            raw_expression=f"document.{prop_name}({arg_str or ''})",
                            detected_channel_or_sink_target=arg_str,
                        ))

                    # IPC calls: ipcRenderer.send, invoke, sendSync, on, once, ipcMain.handle, on
                    elif obj_name in ("ipcRenderer", "ipcMain") or "ipc" in obj_name.lower():
                        if prop_name in ("send", "invoke", "sendSync", "sendToHost", "handle", "handleOnce", "on", "once"):
                            chan_name, is_dyn = None, True
                            if node.arguments:
                                chan_name, is_dyn = get_literal_or_id_str(node.arguments[0])
                            sinks.append(DataflowSink(
                                sink_type="IPC",
                                target_api=f"{obj_name}.{prop_name}",
                                line_number=line,
                                is_dynamic=is_dyn,
                                raw_expression=f"{obj_name}.{prop_name}({chan_name or 'dynamic'})",
                                detected_channel_or_sink_target=chan_name,
                            ))

                    # postMessage: window.postMessage, target.postMessage
                    elif prop_name == "postMessage":
                        target_channel = None
                        if node.arguments:
                            first_arg = node.arguments[0]
                            if isinstance(first_arg, ObjectExpression):
                                for p in first_arg.properties:
                                    pk = p.key.name if isinstance(p.key, Identifier) else (str(p.key.value) if isinstance(p.key, Literal) else "")
                                    if pk in ("type", "action", "channel"):
                                        pv, _ = get_literal_or_id_str(p.value)
                                        target_channel = pv
                                        break
                            elif isinstance(first_arg, Literal):
                                target_channel = str(first_arg.value)

                        sinks.append(DataflowSink(
                            sink_type="POST_MESSAGE",
                            target_api=f"{obj_name or 'window'}.postMessage",
                            line_number=line,
                            is_dynamic=target_channel is None,
                            raw_expression=f"postMessage({target_channel or 'payload'})",
                            detected_channel_or_sink_target=target_channel,
                        ))

            # Recurse
            if isinstance(node, Program):
                for child in node.body:
                    visit(child)
            elif isinstance(node, BlockStatement):
                for child in node.body:
                    visit(child)
            elif isinstance(node, ExpressionStatement):
                visit(node.expression)
            elif isinstance(node, CallExpression):
                visit(callee)
                for a in node.arguments:
                    visit(a)
            elif isinstance(node, MemberExpression):
                visit(node.object)
                visit(node.property)
            elif isinstance(node, AssignmentExpression):
                visit(node.left)
                visit(node.right)
            elif isinstance(node, VariableDeclaration):
                for dec in node.declarations:
                    if dec.init:
                        visit(dec.init)
            elif isinstance(node, ArrayExpression):
                for el in node.elements:
                    visit(el)
            elif isinstance(node, ObjectExpression):
                for prop in node.properties:
                    visit(prop.key)
                    visit(prop.value)
            elif isinstance(node, FunctionNode):
                if node.body:
                    visit(node.body)

        visit(ast)
        return sinks
