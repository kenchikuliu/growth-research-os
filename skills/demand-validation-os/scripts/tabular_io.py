#!/usr/bin/env python3
"""Small standard-library tabular IO helpers for csv/tsv/xlsx."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def extension(path: str) -> str:
    return Path(path).suffix.lower()


def normalize_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def read_delimited_rows(path: str, delimiter: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        return [{key: (value or "").strip() for key, value in row.items() if key} for row in reader]


def write_delimited_rows(path: str, rows: list[dict[str, Any]], delimiter: str) -> None:
    headers = ordered_headers(rows)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, delimiter=delimiter)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: normalize_scalar(row.get(header, "")) for header in headers})


def ordered_headers(rows: list[dict[str, Any]]) -> list[str]:
    headers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            headers.append(key)
    return headers


def col_letters(index: int) -> str:
    result = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def col_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    result = 0
    for ch in letters:
        result = result * 26 + (ord(ch) - 64)
    return result


def xml_t(value: Any) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_xlsx_rows(path: str) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path, "r") as zf:
        worksheet_names = sorted(
            name for name in zf.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not worksheet_names:
            return []
        shared_strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for item in shared_root.findall(f"{{{XML_NS}}}si"):
                texts = [node.text or "" for node in item.findall(f".//{{{XML_NS}}}t")]
                shared_strings.append("".join(texts))

        sheet_root = ET.fromstring(zf.read(worksheet_names[0]))
        rows: list[list[str]] = []
        for row_node in sheet_root.findall(f".//{{{XML_NS}}}row"):
            values: dict[int, str] = {}
            max_col = 0
            for cell in row_node.findall(f"{{{XML_NS}}}c"):
                ref = cell.attrib.get("r", "")
                idx = col_index(ref)
                max_col = max(max_col, idx)
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    text = "".join(node.text or "" for node in cell.findall(f".//{{{XML_NS}}}t"))
                else:
                    raw_value = cell.findtext(f"{{{XML_NS}}}v", default="")
                    if cell_type == "s" and raw_value.isdigit():
                        shared_index = int(raw_value)
                        text = shared_strings[shared_index] if shared_index < len(shared_strings) else ""
                    else:
                        text = raw_value or ""
                values[idx] = text
            if max_col <= 0:
                continue
            rows.append([values.get(col, "") for col in range(1, max_col + 1)])

    if not rows:
        return []
    headers = [str(value).strip() for value in rows[0]]
    result: list[dict[str, Any]] = []
    for row in rows[1:]:
        item = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            item[header] = row[idx].strip() if idx < len(row) else ""
        if any(value != "" for value in item.values()):
            result.append(item)
    return result


def write_xlsx_rows(path: str, rows: list[dict[str, Any]], sheet_name: str = "Sheet1") -> None:
    headers = ordered_headers(rows)
    table_rows: list[list[Any]] = [headers]
    for row in rows:
        table_rows.append([normalize_scalar(row.get(header, "")) for header in headers])

    sheet_xml_rows = []
    for row_idx, row in enumerate(table_rows, start=1):
        cells = []
        for col_idx, value in enumerate(row, start=1):
            ref = f"{col_letters(col_idx)}{row_idx}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_t(value)}</t></is></c>')
        sheet_xml_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{XML_NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{xml_t(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{XML_NS}"><sheetData>{"".join(sheet_xml_rows)}</sheetData></worksheet>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
    Path(path).write_bytes(buffer.getvalue())


def read_rows(path: str) -> list[dict[str, Any]]:
    ext = extension(path)
    if ext == ".json":
        payload = json.loads(Path(path).read_text())
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            return [row for row in payload["jobs"] if isinstance(row, dict)]
        raise ValueError("JSON input must be an array or an object with a 'jobs' array.")
    if ext == ".csv":
        return read_delimited_rows(path, ",")
    if ext == ".tsv":
        return read_delimited_rows(path, "\t")
    if ext == ".xlsx":
        return read_xlsx_rows(path)
    raise ValueError(f"Unsupported input format: {ext}")


def write_rows(path: str, rows: list[dict[str, Any]], sheet_name: str = "Sheet1") -> None:
    ext = extension(path)
    if ext == ".json":
        Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if ext == ".csv":
        write_delimited_rows(path, rows, ",")
        return
    if ext == ".tsv":
        write_delimited_rows(path, rows, "\t")
        return
    if ext == ".xlsx":
        write_xlsx_rows(path, rows, sheet_name=sheet_name)
        return
    raise ValueError(f"Unsupported output format: {ext}")


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return ""
    if text[0] in "[{":
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        clean_key = str(key).strip()
        if not clean_key:
            continue
        parsed = parse_jsonish(value)
        if isinstance(parsed, str):
            parsed = parsed.strip()
        if parsed in ("", None):
            continue
        normalized[clean_key] = parsed
    return normalized

