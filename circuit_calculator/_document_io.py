"""Internal bounded JSON and atomic-file primitives shared by both formats."""

from decimal import Decimal, DecimalException
import json
import os
from pathlib import Path
import tempfile


def string_field(value, field, limit, error_type):
    if not isinstance(value, str):
        raise error_type(f'{field} must be a string')
    if len(value) > limit:
        raise error_type(f'{field} exceeds {limit} characters')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise error_type(f'{field} must contain valid Unicode') from error
    return value


def object_fields(value, expected, field, error_type):
    if not isinstance(value, dict):
        raise error_type(f'{field} must be an object')
    missing, unknown = set(expected) - value.keys(), value.keys() - set(expected)
    if missing or unknown:
        raise error_type(f'{field}: missing fields {sorted(missing)}; unknown fields {sorted(unknown)}')


def check_text(text, max_bytes, max_depth, error_type):
    if not isinstance(text, str):
        raise TypeError('document text must be a string')
    if len(text) > max_bytes:
        raise error_type(f'document exceeds {max_bytes} UTF-8 bytes')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeEncodeError as error:
        raise error_type('document must contain valid Unicode') from error
    if size > max_bytes:
        raise error_type(f'document exceeds {max_bytes} UTF-8 bytes')
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > max_depth:
                raise error_type(f'JSON nesting exceeds {max_depth}')
        elif char in ']}':
            depth -= 1


def loads_json(text, max_bytes, max_depth, error_type):
    check_text(text, max_bytes, max_depth, error_type)

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise error_type(f'duplicate JSON object key: {key!r}')
            result[key] = value
        return result

    def reject_constant(value):
        raise error_type(f'non-finite JSON number is not supported: {value}')

    try:
        return json.loads(text, object_pairs_hook=unique_object,
                          parse_float=Decimal, parse_constant=reject_constant)
    except json.JSONDecodeError as error:
        raise error_type(f'invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}') from error
    except (ValueError, RecursionError, DecimalException) as error:
        if isinstance(error, error_type):
            raise
        raise error_type(f'invalid JSON: {error}') from error


def dumps_json(data, max_bytes, max_depth, error_type):
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + '\n'
    check_text(text, max_bytes, max_depth, error_type)
    return text


def read_utf8(path, max_bytes, error_type):
    with Path(path).open('rb') as stream:
        content = stream.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise error_type(f'document exceeds {max_bytes} UTF-8 bytes')
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError as error:
        raise error_type('document file must be UTF-8') from error


def atomic_write(content, path, *, overwrite=False):
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be a bool')
    destination, temporary = Path(path), None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.circuit-',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
