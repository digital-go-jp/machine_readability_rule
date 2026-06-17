"""OOXML inspector のテスト。"""

from __future__ import annotations

import io
import zipfile

from harunobu.core.ooxml_inspector import (
    FormulaInspectionLimits,
    ObjectInspectionLimits,
    inspect_formula_artifacts,
    inspect_object_artifacts,
)


def _xlsx_bytes(sheet_xml: str) -> bytes:
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>"""

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return bio.getvalue()


def test_extracts_reference_sum_constant_and_shared_formulas():
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="2">
      <c r="B2"><f>A2</f><v>10</v></c>
      <c r="C2"><f>SUM(1,2)</f><v>3</v></c>
      <c r="D2"><f>1</f><v>1</v></c>
      <c r="E2"><f t="shared" si="0">A2*2</f><v>20</v></c>
      <c r="F2"><f t="shared" si="0"/><v>22</v></c>
    </row>
  </sheetData>
</worksheet>"""

    result = inspect_formula_artifacts(_xlsx_bytes(sheet_xml))

    assert result.error is None
    assert [ref.cell_ref for ref in result.formula_refs] == ["B2", "C2", "D2", "E2", "F2"]
    assert result.formula_refs[0].formula_text == "A2"
    assert result.formula_refs[-1].formula_type == "shared"
    assert result.formula_refs[-1].formula_text is None


def test_string_equals_value_without_formula_is_not_formula():
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="2"><c r="B2" t="inlineStr"><is><t>=A2</t></is></c></row>
  </sheetData>
</worksheet>"""

    result = inspect_formula_artifacts(_xlsx_bytes(sheet_xml))

    assert result.error is None
    assert result.formula_refs == []
    assert result.formula_error_refs == []


def test_extracts_ref_errors_from_error_cell_and_formula_cached_value():
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="2">
      <c r="B2" t="e"><v>#REF!</v></c>
      <c r="C2" t="e"><f>A2</f><v>#REF!</v></c>
    </row>
  </sheetData>
</worksheet>"""

    result = inspect_formula_artifacts(_xlsx_bytes(sheet_xml))

    assert result.error is None
    assert [ref.cell_ref for ref in result.formula_refs] == ["C2"]
    assert [ref.cell_ref for ref in result.formula_error_refs] == ["B2", "C2"]


def test_worksheet_xml_size_limit_returns_error():
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData><row r="1"><c r="A1"><f>1</f><v>1</v></c></row></sheetData>
</worksheet>"""

    result = inspect_formula_artifacts(
        _xlsx_bytes(sheet_xml),
        FormulaInspectionLimits(max_worksheet_xml_bytes=10),
    )

    assert result.error == "worksheet_xml_too_large"


def test_artifact_count_limit_returns_error():
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1"><f>1</f><v>1</v></c><c r="B1"><f>2</f><v>2</v></c></row>
  </sheetData>
</worksheet>"""

    result = inspect_formula_artifacts(
        _xlsx_bytes(sheet_xml),
        FormulaInspectionLimits(max_formula_refs=1),
    )

    assert result.error == "too_many_formula_artifacts"


# ─── object inspection テスト用ヘルパー ───


SHEET_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
</worksheet>"""

DRAWING_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
XDR_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"


def _xlsx_with_drawing(drawing_xml: str, extra_rels: str = "") -> bytes:
    """1 シートと 1 つの drawing パートを持つ最小限の xlsx を生成する。"""
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>"""
    sheet_rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="{DRAWING_REL_TYPE}"
    Target="../drawings/drawing1.xml"/>{extra_rels}
</Relationships>"""

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", SHEET_XML_EMPTY)
        zf.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels_xml)
        zf.writestr("xl/drawings/drawing1.xml", drawing_xml)
    return bio.getvalue()


def _xlsx_no_drawing() -> bytes:
    """1 シートを持ち worksheet rels ファイルを含まない最小限の xlsx を生成する。"""
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>"""

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", SHEET_XML_EMPTY)
        # worksheet rels を意図的に含めない
    return bio.getvalue()


def _two_cell_anchor(row: int, col: int, child_xml: str) -> str:
    """twoCellAnchor の XML 断片を生成する（row/col は 0-indexed）。"""
    from_xml = f"<xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff>"
    to_xml = (
        f"<xdr:col>{col + 1}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{row + 1}</xdr:row><xdr:rowOff>0</xdr:rowOff>"
    )
    return f"""<xdr:twoCellAnchor xmlns:xdr="{XDR_NS}">
  <xdr:from>{from_xml}</xdr:from>
  <xdr:to>{to_xml}</xdr:to>
  {child_xml}
  <xdr:clientData/>
</xdr:twoCellAnchor>"""


def _drawing_xml(*anchors: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="{XDR_NS}">
{"".join(anchors)}
</xdr:wsDr>"""


# ─── object inspection テスト ───


def test_no_drawing_rels_returns_empty_no_error():
    """worksheet rels ファイルが存在しない場合は空結果で error=None（正常系）。"""
    result = inspect_object_artifacts(_xlsx_no_drawing())
    assert result.error is None
    assert result.object_refs == []


def test_pic_anchor_detected_as_image():
    """pic アンカーは object_type=image で検出される。"""
    pic_xml = """<xdr:pic xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvPicPr><xdr:cNvPr id="2" name="logo.png"/><xdr:cNvPicPr/></xdr:nvPicPr>
  <xdr:blipFill/><xdr:spPr/>
</xdr:pic>"""
    drawing = _drawing_xml(_two_cell_anchor(1, 2, pic_xml))
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert len(result.object_refs) == 1
    ref = result.object_refs[0]
    assert ref.object_type == "image"
    assert ref.row == 2  # 0-indexed 1 → 1-indexed 2
    assert ref.col == 3  # 0-indexed 2 → 1-indexed 3
    assert ref.name == "logo.png"
    assert ref.sheet_name == "Sheet1"


def test_graphic_frame_anchor_detected_as_chart():
    """graphicFrame アンカーは object_type=chart で検出される。"""
    gf_xml = """<xdr:graphicFrame xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvGraphicFramePr><xdr:cNvPr id="3" name="Chart 1"/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>
  <xdr:xfrm/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>
</xdr:graphicFrame>"""
    drawing = _drawing_xml(_two_cell_anchor(0, 0, gf_xml))
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert len(result.object_refs) == 1
    ref = result.object_refs[0]
    assert ref.object_type == "chart"
    assert ref.row == 1
    assert ref.col == 1
    assert ref.name == "Chart 1"


def test_sp_anchor_detected_as_shape():
    """sp アンカーは object_type=shape で検出される。"""
    sp_xml = """<xdr:sp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvSpPr><xdr:cNvPr id="4" name="TextBox 1"/><xdr:cNvSpPr/></xdr:nvSpPr>
  <xdr:spPr/><xdr:txBody/>
</xdr:sp>"""
    drawing = _drawing_xml(_two_cell_anchor(2, 3, sp_xml))
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert len(result.object_refs) == 1
    ref = result.object_refs[0]
    assert ref.object_type == "shape"
    assert ref.row == 3
    assert ref.col == 4
    assert ref.name == "TextBox 1"


def test_cxn_sp_anchor_detected_as_connector():
    """cxnSp アンカーは object_type=connector で検出される。"""
    cxn_xml = """<xdr:cxnSp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvCxnSpPr><xdr:cNvPr id="5" name="Arrow 1"/><xdr:cNvCxnSpPr/></xdr:nvCxnSpPr>
  <xdr:spPr/>
</xdr:cxnSp>"""
    drawing = _drawing_xml(_two_cell_anchor(0, 0, cxn_xml))
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert len(result.object_refs) == 1
    assert result.object_refs[0].object_type == "connector"
    assert result.object_refs[0].name == "Arrow 1"


def test_grp_sp_only_anchor_skipped():
    """grpSp のみのアンカーはスキップされる。"""
    grp_xml = """<xdr:grpSp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvGrpSpPr><xdr:cNvPr id="6" name="Group 1"/></xdr:nvGrpSpPr>
</xdr:grpSp>"""
    drawing = _drawing_xml(_two_cell_anchor(0, 0, grp_xml))
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert result.object_refs == []


def test_absolute_anchor_skipped():
    """absoluteAnchor はセルアンカーがないためスキップされる。"""
    sp_xml = """<xdr:sp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvSpPr><xdr:cNvPr id="7" name="Shape 1"/><xdr:cNvSpPr/></xdr:nvSpPr>
  <xdr:spPr/>
</xdr:sp>"""
    drawing = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="{XDR_NS}">
  <xdr:absoluteAnchor>
    <xdr:pos x="0" y="0"/>
    <xdr:ext cx="100" cy="100"/>
    {sp_xml}
    <xdr:clientData/>
  </xdr:absoluteAnchor>
</xdr:wsDr>"""
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert result.object_refs == []


def test_non_drawing_rel_type_ignored():
    """drawing 以外の rel type（oleObject 等）は無視される。"""
    ole_rel = """
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject"
    Target="../embeddings/ole1.bin"/>"""
    sp_xml = """<xdr:sp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvSpPr><xdr:cNvPr id="8" name="Shape"/><xdr:cNvSpPr/></xdr:nvSpPr><xdr:spPr/>
</xdr:sp>"""
    drawing = _drawing_xml(_two_cell_anchor(0, 0, sp_xml))
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing, extra_rels=ole_rel))

    assert result.error is None
    # drawing rel は存在するため shape が1件検出されるが、oleObject は無視される
    assert len(result.object_refs) == 1
    assert result.object_refs[0].object_type == "shape"


def test_max_object_refs_limit_returns_error():
    """max_object_refs 超過時に too_many_object_artifacts エラーになる。"""
    sp_xml = """<xdr:sp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvSpPr><xdr:cNvPr id="1" name="s"/><xdr:cNvSpPr/></xdr:nvSpPr><xdr:spPr/>
</xdr:sp>"""
    anchors = _two_cell_anchor(0, 0, sp_xml) + _two_cell_anchor(1, 0, sp_xml)
    drawing = _drawing_xml(anchors)
    result = inspect_object_artifacts(
        _xlsx_with_drawing(drawing),
        ObjectInspectionLimits(max_object_refs=1),
    )

    assert result.error == "too_many_object_artifacts"


def test_max_drawing_xml_bytes_limit_returns_error():
    """drawing XML サイズが max_drawing_xml_bytes を超えたらエラーになる。"""
    sp_xml = """<xdr:sp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvSpPr><xdr:cNvPr id="1" name="s"/><xdr:cNvSpPr/></xdr:nvSpPr><xdr:spPr/>
</xdr:sp>"""
    drawing = _drawing_xml(_two_cell_anchor(0, 0, sp_xml))
    result = inspect_object_artifacts(
        _xlsx_with_drawing(drawing),
        ObjectInspectionLimits(max_drawing_xml_bytes=10),
    )

    assert result.error == "drawing_xml_too_large"


def test_multiple_objects_in_one_drawing():
    """同一 drawing 内の複数アンカーがすべて検出される。"""
    pic_xml = """<xdr:pic xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvPicPr><xdr:cNvPr id="2" name="img"/><xdr:cNvPicPr/></xdr:nvPicPr>
  <xdr:blipFill/><xdr:spPr/>
</xdr:pic>"""
    sp_xml = """<xdr:sp xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:nvSpPr><xdr:cNvPr id="3" name="box"/><xdr:cNvSpPr/></xdr:nvSpPr><xdr:spPr/>
</xdr:sp>"""
    drawing = _drawing_xml(
        _two_cell_anchor(0, 0, pic_xml),
        _two_cell_anchor(3, 2, sp_xml),
    )
    result = inspect_object_artifacts(_xlsx_with_drawing(drawing))

    assert result.error is None
    assert len(result.object_refs) == 2
    types = {r.object_type for r in result.object_refs}
    assert types == {"image", "shape"}
