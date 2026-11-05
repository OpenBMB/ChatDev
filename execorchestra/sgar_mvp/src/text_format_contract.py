"""Task-anchored plaintext shape, independent of JSON response encoding."""
from collections.abc import Mapping
import re

from typing import Literal, Any
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class NumericTextFormat(BaseModel):
    """Presentation of one number; unit meaning is independent of its label."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    decimal_places: int = Field(ge=0)
    unit: str | None = None
    unit_position: Literal["none", "prefix", "suffix"] = "none"
    grouping: bool = False

    @field_validator("unit")
    @classmethod
    def _unit(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip() or "\n" in value):
            raise ValueError("numeric_format_unit_invalid")
        return value



class TextFormatContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement_quote: str = Field(min_length=1)
    fullmatch_pattern: str = Field(min_length=1)
    numeric_format: NumericTextFormat | None = None

    @model_serializer(mode="wrap")
    def _legacy_shape(self, handler: Any) -> dict[str, Any]:
        value = handler(self)
        if self.numeric_format is None:
            value.pop("numeric_format", None)
        return value

    @field_validator("requirement_quote")
    @classmethod
    def _nonempty_quote(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text_format_requirement_quote_empty")
        return value

    @field_validator("fullmatch_pattern")
    @classmethod
    def _pattern_syntax(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error:
            raise ValueError("text_format_pattern_invalid") from None
        return value



_EXACT_FINAL_RESPONSE_PATTERNS = (
    re.compile(
        r"(?P<quote>\b(?:return|respond(?:\s+with)?|reply(?:\s+with)?|output)"
        r"\s+exactly\s+"
        r"(?P<literal>`[^`\r\n]+`|\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,.;:]+)"
        r"\s+as\s+(?:the\s+)?final\s+(?:reply|response|answer)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<quote>\b(?:the\s+)?final\s+(?:reply|response|answer)\s+"
        r"(?:must|should)\s+be\s+exactly\s+"
        r"(?P<literal>`[^`\r\n]+`|\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,.;:]+))",
        re.IGNORECASE,
    ),
)
_MAX_EXACT_FINAL_RESPONSE_BYTES = 512


def exact_final_response_from_request(
    request_text: str,
) -> tuple[str, TextFormatContract] | None:
    """Extract one unambiguous exact final literal from the public request."""
    matches: dict[str, tuple[str, TextFormatContract]] = {}
    for pattern in _EXACT_FINAL_RESPONSE_PATTERNS:
        for match in pattern.finditer(request_text):
            encoded_literal = match.group("literal")
            if (
                len(encoded_literal) >= 2
                and encoded_literal[0] == encoded_literal[-1]
                and encoded_literal[0] in {"`", "\"", "'"}
            ):
                literal = encoded_literal[1:-1]
            else:
                literal = encoded_literal
            if (
                not literal
                or len(literal.encode("utf-8")) > _MAX_EXACT_FINAL_RESPONSE_BYTES
            ):
                continue
            requirement_quote = match.group("quote")
            matches[literal] = (
                literal,
                TextFormatContract(
                    requirement_quote=requirement_quote,
                    fullmatch_pattern=re.escape(literal),
                ),
            )
    if len(matches) != 1:
        return None
    return next(iter(matches.values()))


def authoritative_exact_final_literal(
    contract: Mapping, original_request: str,
) -> str | None:
    """Return bytes-authoritative text only when request and contract agree."""
    try:
        declared = text_format_from_contract(contract)
    except ValueError:
        return None
    if declared is None:
        return None
    extracted = exact_final_response_from_request(original_request)
    if extracted is None:
        return None
    literal, expected = extracted
    if declared != expected:
        return None
    return literal

def text_format_from_contract(contract: Mapping) -> TextFormatContract | None:
    interface = contract.get("interface_contract")
    raw = interface.get("text_format") if isinstance(interface, Mapping) else None
    if raw is None:
        return None
    if contract.get("artifact_type") != "plaintext" or contract.get("content_kind", "value") != "value":
        raise ValueError("text_format_requires_plaintext_value")
    return TextFormatContract.model_validate(raw)


def require_text_format_authority(contract: Mapping, original_request: str) -> None:
    text_format = text_format_from_contract(contract)
    if text_format is not None and text_format.requirement_quote not in original_request:
        raise ValueError("text_format_requirement_quote_not_in_original_request")
    if (text_format is not None and text_format.numeric_format is not None
            and text_format.numeric_format.unit is not None
            and text_format.numeric_format.unit not in text_format.requirement_quote):
        raise ValueError("numeric_format_unit_not_in_requirement_quote")


def normalize_declared_numeric_text(content: str, contract: Mapping, *, original_request: str | None = None):
    """Format a declared scalar without rounding, conversion or reference answers.

    Ambiguous prose, wrong units, multiple values and value-changing precision
    reduction are left untouched for the existing validator/repair path.
    """
    text_format = text_format_from_contract(contract)
    if text_format is None or text_format.numeric_format is None:
        return content, None
    if original_request is not None:
        require_text_format_authority(contract, original_request)
    spec = text_format.numeric_format
    candidate = content.strip()
    if spec.unit:
        prefix, suffix = candidate.startswith(spec.unit), candidate.endswith(spec.unit)
        if prefix and suffix:
            return content, None
        if prefix:
            candidate = candidate[len(spec.unit):].strip()
        elif suffix:
            candidate = candidate[:-len(spec.unit)].strip()
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", candidate):
        return content, None
    try:
        value = Decimal(candidate.replace(",", ""))
        with localcontext() as ctx:
            ctx.prec = max(32, len(candidate) + spec.decimal_places + 4)
            rounded = value.quantize(Decimal(1).scaleb(-spec.decimal_places))
            if rounded != value:
                return content, None
            formatted = format(rounded, ("," if spec.grouping else "") + f".{spec.decimal_places}f")
    except InvalidOperation:
        return content, None
    if spec.unit and spec.unit_position == "prefix":
        formatted = spec.unit + " " + formatted
    elif spec.unit and spec.unit_position == "suffix":
        formatted += " " + spec.unit
    if formatted == content:
        return content, None
    return formatted, {
        "protocol": "sgar-numeric-text-realization-v1",
        "requirement_quote": text_format.requirement_quote,
        "source_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "output_sha256": hashlib.sha256(formatted.encode("utf-8")).hexdigest(),
        "numeric_value_preserved": True,
        "reference_answer_used": False,
    }
