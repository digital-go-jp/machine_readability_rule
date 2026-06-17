"""OOXML パートを読み取る軽量インスペクタ。

Excel の OOXML パートの一部を ZIP パッケージから直接読み取る。
他のルールがパッケージ走査を再利用できるよう、workbook/sheet の
relationship 処理を formula 抽出から意図的に分離している。
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree as ET

from harunobu.core.models import FormulaErrorRef, FormulaRef, ObjectRef

MAX_FORMULA_REFS = 50_000
MAX_FORMULA_ERROR_REFS = 50_000
MAX_WORKSHEET_XML_BYTES = 100 * 1024 * 1024

MAX_OBJECT_REFS = 50_000
MAX_DRAWING_XML_BYTES = 50 * 1024 * 1024

WORKBOOK_PART = "xl/workbook.xml"
WORKBOOK_RELS_PART = "xl/_rels/workbook.xml.rels"

DRAWING_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"


@dataclass(frozen=True)
class FormulaInspectionLimits:
    """OOXML 数式インスペクションの安全上限値。"""

    max_formula_refs: int = MAX_FORMULA_REFS
    max_formula_error_refs: int = MAX_FORMULA_ERROR_REFS
    max_worksheet_xml_bytes: int = MAX_WORKSHEET_XML_BYTES


@dataclass
class FormulaInspectionResult:
    """OOXML ワークブックから検出した数式関連のアーティファクト。"""

    formula_refs: list[FormulaRef] = field(default_factory=list)
    formula_error_refs: list[FormulaErrorRef] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class OOXMLSheetPart:
    """解決済みのワークシートパートのメタデータ。"""

    sheet_name: str
    rel_id: str
    path: str


@dataclass(frozen=True)
class OOXMLRelationship:
    """ターゲットパスを解決済みの OOXML relationship エントリ 1 件。"""

    rel_id: str
    rel_type: str
    target: str


@dataclass(frozen=True)
class ObjectInspectionLimits:
    """OOXML オブジェクトインスペクションの安全上限値。"""

    max_object_refs: int = MAX_OBJECT_REFS
    max_drawing_xml_bytes: int = MAX_DRAWING_XML_BYTES


@dataclass
class ObjectInspectionResult:
    """OOXML ワークブックから検出したオブジェクト関連のアーティファクト。"""

    object_refs: list[ObjectRef] = field(default_factory=list)
    error: str | None = None


def inspect_formula_artifacts(
    source: bytes | Path | str,
    limits: FormulaInspectionLimits | None = None,
) -> FormulaInspectionResult:
    """xlsx/xlsm パッケージを走査し、数式セルと #REF! エラーを抽出する。

    Args:
        source (bytes | Path | str): 対象の xlsx/xlsm ファイル（バイト列またはパス）
        limits (FormulaInspectionLimits | None): 走査時の安全上限値。None の場合はデフォルト値を使う

    Returns:
        FormulaInspectionResult: 数式 ref・#REF! エラー ref のリスト。失敗時は error フィールドに理由を設定する
    """
    limits = limits or FormulaInspectionLimits()
    result = FormulaInspectionResult()

    try:
        with _open_zip(source) as zf:
            sheet_parts = list_workbook_sheet_parts(zf)
            for sheet_part in sheet_parts:
                info = zf.getinfo(sheet_part.path)
                if info.file_size > limits.max_worksheet_xml_bytes:
                    result.error = "worksheet_xml_too_large"
                    return result

                with zf.open(info) as stream:
                    _inspect_worksheet_formula_artifacts(stream, sheet_part.sheet_name, result, limits)
                if result.error is not None:
                    return result
    except Exception as exc:
        result.error = f"inspect_failed:{type(exc).__name__}"

    return result


def list_workbook_sheet_parts(zf: zipfile.ZipFile) -> list[OOXMLSheetPart]:
    """ワークブック内の各シートを、解決済みのワークシート XML パッケージパス付きで返す。"""
    rel_targets = _read_relationship_targets(zf, WORKBOOK_RELS_PART, WORKBOOK_PART)
    sheets: list[OOXMLSheetPart] = []

    with zf.open(WORKBOOK_PART) as workbook_xml:
        root = ET.parse(workbook_xml).getroot()

    for elem in root.iter():
        if _local_name(elem.tag) != "sheet":
            continue

        name = elem.attrib.get("name")
        rel_id = _relationship_id(elem.attrib)
        if not name or not rel_id:
            continue

        target = rel_targets.get(rel_id)
        if target is None:
            continue

        sheets.append(OOXMLSheetPart(sheet_name=name, rel_id=rel_id, path=target))

    return sheets


def _open_zip(source: bytes | Path | str) -> zipfile.ZipFile:
    if isinstance(source, bytes):
        return zipfile.ZipFile(io.BytesIO(source))
    return zipfile.ZipFile(source)


def read_relationships(
    zf: zipfile.ZipFile,
    rels_part: str,
    source_part: str,
) -> list[OOXMLRelationship]:
    """rels パートからすべての relationship を返す。

    rels ファイルが ZIP 内に存在しない場合は空リストを返す
    （drawing を持たないシートにはワークシート rels ファイルが存在せず、これは正常）。

    Args:
        zf (zipfile.ZipFile): 対象の OOXML パッケージ
        rels_part (str): rels パートのパッケージパス
        source_part (str): relationship のターゲット解決の基点となるパートのパス

    Returns:
        list[OOXMLRelationship]: ターゲットパス解決済みの relationship のリスト
    """
    if rels_part not in zf.namelist():
        return []

    with zf.open(rels_part) as rels_xml:
        root = ET.parse(rels_xml).getroot()

    rels: list[OOXMLRelationship] = []
    for rel in root:
        if _local_name(rel.tag) != "Relationship":
            continue
        rel_id = rel.attrib.get("Id")
        rel_type = rel.attrib.get("Type", "")
        target = rel.attrib.get("Target")
        if not rel_id or not target:
            continue
        rels.append(
            OOXMLRelationship(
                rel_id=rel_id,
                rel_type=rel_type,
                target=resolve_package_target(source_part, target),
            )
        )
    return rels


def _read_relationship_targets(
    zf: zipfile.ZipFile,
    rels_part: str,
    source_part: str,
) -> dict[str, str]:
    return {r.rel_id: r.target for r in read_relationships(zf, rels_part, source_part)}


def inspect_object_artifacts(
    source: bytes | Path | str,
    limits: ObjectInspectionLimits | None = None,
) -> ObjectInspectionResult:
    """xlsx/xlsm パッケージを走査し、埋め込み drawing オブジェクトを抽出する。

    xl/drawings/drawing*.xml の twoCellAnchor / oneCellAnchor 要素を走査し、
    pic / graphicFrame / sp / cxnSp を anchor の行/列とともに抽出する。
    absoluteAnchor はセル anchor を持たないためスキップする。

    Args:
        source (bytes | Path | str): 対象の xlsx/xlsm ファイル（バイト列またはパス）
        limits (ObjectInspectionLimits | None): 走査時の安全上限値。None の場合はデフォルト値を使う

    Returns:
        ObjectInspectionResult: 検出したオブジェクト ref のリスト。失敗時は error フィールドに理由を設定する
    """
    limits = limits or ObjectInspectionLimits()
    result = ObjectInspectionResult()

    try:
        with _open_zip(source) as zf:
            sheet_parts = list_workbook_sheet_parts(zf)
            for sheet_part in sheet_parts:
                sheet_rels_part = _worksheet_rels_path(sheet_part.path)
                rels = read_relationships(zf, sheet_rels_part, sheet_part.path)
                drawing_targets = [r.target for r in rels if r.rel_type == DRAWING_REL_TYPE]

                for drawing_path in drawing_targets:
                    if drawing_path not in zf.namelist():
                        continue
                    info = zf.getinfo(drawing_path)
                    if info.file_size > limits.max_drawing_xml_bytes:
                        result.error = "drawing_xml_too_large"
                        return result

                    with zf.open(info) as stream:
                        _inspect_drawing_artifacts(
                            stream,
                            sheet_part.sheet_name,
                            drawing_path,
                            result,
                            limits,
                        )
                    if result.error is not None:
                        return result
    except Exception as exc:
        result.error = f"inspect_failed:{type(exc).__name__}"

    return result


def _worksheet_rels_path(worksheet_path: str) -> str:
    """ワークシート XML のパスからワークシート rels のパスを導出する。

    例: "xl/worksheets/sheet1.xml" -> "xl/worksheets/_rels/sheet1.xml.rels"
    """
    dirname = posixpath.dirname(worksheet_path)
    basename = posixpath.basename(worksheet_path)
    return posixpath.join(dirname, "_rels", basename + ".rels")


# xdr:* 要素で使われる DrawingML 名前空間プレフィックスの anchor 要素名
_XDR_ANCHOR_NAMES = {"twoCellAnchor", "oneCellAnchor"}

# 子要素のローカル名 -> ObjectRef の object_type 対応表
_OBJECT_TYPE_MAP = {
    "pic": "image",
    "graphicFrame": "chart",
    "sp": "shape",
    "cxnSp": "connector",
}

# 名前抽出用の object_type -> nvXxxPr 要素のローカル名 対応表
_NV_PROP_NAMES = {
    "image": "nvPicPr",
    "chart": "nvGraphicFramePr",
    "shape": "nvSpPr",
    "connector": "nvCxnSpPr",
}


def _inspect_drawing_artifacts(
    stream: BinaryIO,
    sheet_name: str,
    drawing_part: str,
    result: ObjectInspectionResult,
    limits: ObjectInspectionLimits,
) -> None:
    """1 つの drawing XML ストリームを解析し、ObjectRef エントリを result に追加する。"""
    current_anchor: dict | None = None

    for event, elem in ET.iterparse(stream, events=("start", "end")):
        local = _local_name(elem.tag)

        if event == "start":
            if local in _XDR_ANCHOR_NAMES:
                current_anchor = {"anchor_tag": local}
            continue

        # ここからは event == "end"
        if local not in _XDR_ANCHOR_NAMES:
            continue

        if current_anchor is None:
            elem.clear()
            continue

        # 最初にマッチした子要素（優先順位順）で object_type を判定する
        object_type: str | None = None
        for child_local, otype in _OBJECT_TYPE_MAP.items():
            if _first_child(elem, child_local) is not None:
                object_type = otype
                break

        if object_type is None:
            # grpSp のみ、または認識できない anchor はスキップ
            current_anchor = None
            elem.clear()
            continue

        # xdr:from から anchor の行/列を抽出する（0 始まり -> +1）
        from_elem = _first_child(elem, "from")
        if from_elem is None:
            # absoluteAnchor には xdr:from が無い。oneCellAnchor の安全のためにもスキップ
            current_anchor = None
            elem.clear()
            continue

        row_elem = _first_child(from_elem, "row")
        col_elem = _first_child(from_elem, "col")
        if row_elem is None or col_elem is None:
            current_anchor = None
            elem.clear()
            continue

        try:
            row = int(row_elem.text or "0") + 1
            col = int(col_elem.text or "0") + 1
        except (TypeError, ValueError):
            current_anchor = None
            elem.clear()
            continue

        # nvXxxPr/cNvPr@name から名前を抽出する
        # child_local_name は object_type にマッチした要素タグ
        name: str | None = None
        nv_tag = _NV_PROP_NAMES.get(object_type)
        child_local_name = next(k for k, v in _OBJECT_TYPE_MAP.items() if v == object_type)
        if nv_tag:
            child_shape_elem = _first_child(elem, child_local_name)
            if child_shape_elem is not None:
                nv_elem = _first_child(child_shape_elem, nv_tag)
                if nv_elem is not None:
                    cnv_elem = _first_child(nv_elem, "cNvPr")
                    if cnv_elem is not None:
                        name = cnv_elem.attrib.get("name") or None

        result.object_refs.append(
            ObjectRef(
                sheet_name=sheet_name,
                object_type=object_type,  # type: ignore[arg-type]
                row=row,
                col=col,
                name=name,
                drawing_part=drawing_part,
            )
        )

        if len(result.object_refs) > limits.max_object_refs:
            result.error = "too_many_object_artifacts"
            elem.clear()
            return

        current_anchor = None
        elem.clear()


def resolve_package_target(source_part: str, target: str) -> str:
    """OOXML relationship のターゲットを、パッケージ内の POSIX パスとして解決する。"""
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _inspect_worksheet_formula_artifacts(
    stream: BinaryIO,
    sheet_name: str,
    result: FormulaInspectionResult,
    limits: FormulaInspectionLimits,
) -> None:
    for _event, elem in ET.iterparse(stream, events=("end",)):
        local_name = _local_name(elem.tag)
        if local_name == "row":
            elem.clear()
            continue
        if local_name != "c":
            continue

        cell_ref = elem.attrib.get("r")
        if cell_ref:
            row, col = _cell_ref_to_row_col(cell_ref)
        else:
            row, col = 0, 0

        formula_elem = _first_child(elem, "f")
        value_elem = _first_child(elem, "v")
        has_formula = formula_elem is not None
        value_text = value_elem.text if value_elem is not None else None

        if has_formula and cell_ref:
            result.formula_refs.append(
                FormulaRef(
                    sheet_name=sheet_name,
                    cell_ref=cell_ref,
                    row=row,
                    col=col,
                    formula_type=formula_elem.attrib.get("t"),
                    formula_text=formula_elem.text,
                )
            )
            if len(result.formula_refs) > limits.max_formula_refs:
                result.error = "too_many_formula_artifacts"
                elem.clear()
                return

        if cell_ref and value_text == "#REF!" and (has_formula or elem.attrib.get("t") == "e"):
            result.formula_error_refs.append(
                FormulaErrorRef(
                    sheet_name=sheet_name,
                    cell_ref=cell_ref,
                    row=row,
                    col=col,
                    error_text=value_text,
                )
            )
            if len(result.formula_error_refs) > limits.max_formula_error_refs:
                result.error = "too_many_formula_artifacts"
                elem.clear()
                return

        elem.clear()


def _first_child(elem: ET.Element, local_name: str) -> ET.Element | None:
    for child in elem:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _relationship_id(attrib: dict[str, str]) -> str | None:
    for key, value in attrib.items():
        if key == "id" or _local_name(key) == "id":
            return value
    return None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _cell_ref_to_row_col(cell_ref: str) -> tuple[int, int]:
    col = 0
    row_text = ""
    for char in cell_ref:
        if char.isalpha():
            col = col * 26 + (ord(char.upper()) - ord("A") + 1)
        elif char.isdigit():
            row_text += char
    return int(row_text or "0"), col
