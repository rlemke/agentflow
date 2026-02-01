# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AFL Parser using Lark."""

from pathlib import Path

from lark import Lark
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from .ast import Program
from .source import CompilerInput, SourceRegistry
from .transformer import AFLTransformer


class ParseError(Exception):
    """AFL parse error with location information."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        source_id: str | None = None,
    ):
        self.line = line
        self.column = column
        self.source_id = source_id
        location = ""
        if line is not None:
            location = f" at line {line}"
            if column is not None:
                location += f", column {column}"
        prefix = f"[{source_id}] " if source_id else ""
        super().__init__(f"{prefix}{message}{location}")


_GRAMMAR_PATH = Path(__file__).parent / "grammar" / "afl.lark"


class AFLParser:
    """AFL language parser.

    Uses Lark with LALR mode and propagate_positions for error reporting.
    The Lark instance is shared across all AFLParser instances since the
    grammar is immutable at runtime.
    """

    _lark: Lark | None = None

    @classmethod
    def _get_lark(cls) -> Lark:
        """Return the shared Lark parser, creating it on first use."""
        if cls._lark is None:
            with open(_GRAMMAR_PATH) as f:
                grammar = f.read()
            cls._lark = Lark(
                grammar,
                parser="lalr",
                propagate_positions=True,
                maybe_placeholders=False,
            )
        return cls._lark

    def __init__(self) -> None:
        self._parser = self._get_lark()

    def parse(
        self,
        source: str,
        filename: str = "<string>",
        source_id: str | None = None,
    ) -> Program:
        """Parse AFL source code and return an AST.

        Args:
            source: AFL source code string
            filename: Optional filename for error messages
            source_id: Optional source identifier for provenance tracking

        Returns:
            Program AST node

        Raises:
            ParseError: If the source contains syntax errors
        """
        effective_source_id = source_id if source_id is not None else filename
        transformer = AFLTransformer(source_id=effective_source_id)

        try:
            tree = self._parser.parse(source)
            return transformer.transform(tree)
        except UnexpectedCharacters as e:
            raise ParseError(
                f"Unexpected character '{e.char}'",
                line=e.line,
                column=e.column,
            ) from e
        except UnexpectedToken as e:
            expected = ", ".join(sorted(e.expected)) if e.expected else "unknown"
            raise ParseError(
                f"Unexpected token '{e.token}'. Expected one of: {expected}",
                line=e.line,
                column=e.column,
            ) from e
        except UnexpectedInput as e:
            raise ParseError(
                "Syntax error",
                line=getattr(e, "line", None),
                column=getattr(e, "column", None),
            ) from e

    def parse_file(self, filepath: str | Path) -> Program:
        """Parse an AFL file and return an AST.

        Args:
            filepath: Path to the AFL source file

        Returns:
            Program AST node

        Raises:
            ParseError: If the file contains syntax errors
            FileNotFoundError: If the file doesn't exist
        """
        path = Path(filepath)
        source = path.read_text()
        source_id = f"file://{path}"
        return self.parse(source, filename=str(path), source_id=source_id)

    def parse_sources(
        self,
        compiler_input: CompilerInput,
    ) -> tuple[Program, SourceRegistry]:
        """Parse multiple sources with provenance tracking.

        Args:
            compiler_input: CompilerInput with primary and library sources

        Returns:
            Tuple of (merged Program AST, SourceRegistry with metadata)

        Raises:
            ParseError: If any source contains syntax errors
        """
        registry = SourceRegistry.from_compiler_input(compiler_input)

        programs: list[Program] = []
        for entry in compiler_input.all_sources:
            source_id = entry.source_id
            try:
                program = self.parse(
                    entry.text,
                    filename=source_id,
                    source_id=source_id,
                )
                programs.append(program)
            except ParseError as e:
                raise ParseError(
                    str(e),
                    line=e.line,
                    column=e.column,
                    source_id=source_id,
                ) from e

        return Program.merge(programs), registry


# Module-level cached parser for the convenience function
_default_parser: AFLParser | None = None


def _get_default_parser() -> AFLParser:
    """Return a module-level cached parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = AFLParser()
    return _default_parser


def parse(source: str, filename: str = "<string>") -> Program:
    """Parse AFL source code and return an AST.

    This is a convenience function that uses a cached parser instance.
    """
    return _get_default_parser().parse(source, filename)
