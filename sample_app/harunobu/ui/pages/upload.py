"""ファイルアップロードページ"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import streamlit as st

from harunobu.ui.safe_html import escape_html
from harunobu.ui.styles import page_header

MAX_UPLOAD_FILES = 20
MAX_UPLOAD_MB = 10
MAX_TOTAL_UPLOAD_MB = 50

_BYTES_PER_MB = 1024 * 1024
_ALLOWED_UPLOAD_TYPES = ("xlsx", "csv", "tsv")


def render() -> None:
    """ファイルアップロードページを描画する。"""
    page_header(
        "📁",
        "ファイルアップロード",
        "機械可読性をチェックしたいファイルをアップロードしてください。複数ファイルを選択すると年版間の比較も行います。",
    )

    # 対応フォーマット
    st.markdown(
        '<div class="format-badges">'
        '<span class="format-badge">📗 .xlsx</span>'
        '<span class="format-badge">📄 .csv</span>'
        '<span class="format-badge">📄 .tsv</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "ファイルを選択（複数選択可）",
        type=list(_ALLOWED_UPLOAD_TYPES),
        help=(
            f"1ファイル {MAX_UPLOAD_MB}MB 以下、合計 {MAX_TOTAL_UPLOAD_MB}MB 以下、"
            f"最大 {MAX_UPLOAD_FILES} ファイルまでアップロードできます。"
        ),
        label_visibility="collapsed",
        accept_multiple_files=True,
    )

    if uploaded:
        files = uploaded if isinstance(uploaded, list) else [uploaded]
        file_sizes = _uploaded_file_sizes(files)
        total_size_mb = sum(size for _, size in file_sizes) / _BYTES_PER_MB

        _sync_upload_error_state(files)
        limit_errors = _get_upload_limit_errors(files)
        state_errors = st.session_state.get("upload_validation_errors") or []
        all_errors = limit_errors + state_errors

        # ファイル情報サマリー
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f'<div class="info-card">'
                f'<div class="info-card-label">ファイル数</div>'
                f'<div class="info-card-value">{len(files)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with col2:
            extensions = {f.name.rsplit(".", 1)[-1].upper() for f in files}
            st.markdown(
                f'<div class="info-card">'
                f'<div class="info-card-label">フォーマット</div>'
                f'<div class="info-card-value">{escape_html(", ".join(sorted(extensions)))}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f'<div class="info-card">'
                f'<div class="info-card-label">合計サイズ</div>'
                f'<div class="info-card-value">{total_size_mb:.2f} MB</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        if all_errors:
            _render_upload_errors(all_errors)

        # 個別ファイル一覧
        with st.expander(f"📂 アップロードされたファイル ({len(files)}件)", expanded=len(files) <= 5):
            for i, (f, size) in enumerate(file_sizes):
                size_mb = size / _BYTES_PER_MB
                st.markdown(f"- **{i + 1}.** {f.name} ({size_mb:.2f} MB)")

        if len(files) == 1:
            button_label = "次へ: データプレビュー →"
        else:
            button_label = f"次へ: チェック実行 → ({len(files)}ファイル一括)"
        if all_errors:
            st.button(button_label, type="primary", width="stretch", disabled=True)
        else:
            st.button(
                button_label,
                type="primary",
                width="stretch",
                on_click=_go_next,
                args=(files,),
            )
    else:
        st.session_state.upload_validation_errors = []
        st.session_state.upload_validation_signature = None


def _go_next(files: list) -> None:
    errors = _get_upload_limit_errors(files)
    if not errors:
        errors = _get_upload_readability_errors(files)

    if errors:
        st.session_state.upload_validation_errors = errors
        st.session_state.upload_validation_signature = _upload_signature(files)
        st.session_state.workflow_step = "UPLOAD"
        return

    st.session_state.upload_validation_errors = []
    st.session_state.upload_validation_signature = _upload_signature(files)
    st.session_state.uploaded_files = files
    st.session_state.uploaded_file = files[0] if files else None
    st.session_state.active_file_index = 0
    if len(files) == 1:
        st.session_state.workflow_step = "PREVIEW"
    else:
        # 複数ファイルはプレビューをスキップして採点に直接遷移
        st.session_state.workflow_step = "SCORING"


def _uploaded_file_sizes(files: list) -> list[tuple[object, int]]:
    return [(f, len(f.getvalue())) for f in files]


def _upload_signature(files: list) -> tuple[tuple[str, int], ...]:
    return tuple((f.name, size) for f, size in _uploaded_file_sizes(files))


def _sync_upload_error_state(files: list) -> None:
    signature = _upload_signature(files)
    if st.session_state.get("upload_validation_signature") != signature:
        st.session_state.upload_validation_errors = []
        st.session_state.upload_validation_signature = signature


def _get_upload_limit_errors(files: list) -> list[str]:
    errors: list[str] = []
    file_sizes = _uploaded_file_sizes(files)

    if len(files) > MAX_UPLOAD_FILES:
        errors.append(
            f"アップロードできるファイル数は最大 {MAX_UPLOAD_FILES} 件です。選択されたファイル数: {len(files)} 件"
        )

    max_file_bytes = MAX_UPLOAD_MB * _BYTES_PER_MB
    for f, size in file_sizes:
        if size > max_file_bytes:
            errors.append(
                f"'{f.name}' は {size / _BYTES_PER_MB:.2f} MB です。1ファイルあたりの上限は {MAX_UPLOAD_MB} MB です。"
            )

    total_size = sum(size for _, size in file_sizes)
    max_total_bytes = MAX_TOTAL_UPLOAD_MB * _BYTES_PER_MB
    if total_size > max_total_bytes:
        errors.append(
            f"合計サイズは {total_size / _BYTES_PER_MB:.2f} MB です。"
            f"アップロード全体の上限は {MAX_TOTAL_UPLOAD_MB} MB です。"
        )

    return errors


def _get_upload_readability_errors(files: list) -> list[str]:
    from harunobu.core.reader import CorruptedFileError, UnsupportedFormatError, read_workbook

    errors: list[str] = []
    allowed_suffixes = {f".{suffix}" for suffix in _ALLOWED_UPLOAD_TYPES}
    for f in files:
        suffix = Path(f.name).suffix.lower()
        if suffix not in allowed_suffixes:
            errors.append(f"'{f.name}' は対応していないファイル形式です。.xlsx、.csv、.tsv を選択してください。")
            continue

        try:
            read_workbook(f.name, BytesIO(f.getvalue()), max_rows=1, max_cols=1)
        except UnsupportedFormatError as exc:
            errors.append(f"'{f.name}' を読み込めません: {exc}")
        except CorruptedFileError:
            errors.append(
                f"'{f.name}' を開けません。ファイルが破損している可能性があります。"
                "ExcelまたはCSV/TSVとして開けるファイルをアップロードしてください。"
            )
        except UnicodeDecodeError:
            errors.append(
                f"'{f.name}' の文字コードを判定できません。"
                "UTF-8 または CP932 で保存してから再度アップロードしてください。"
            )
        except Exception as exc:
            errors.append(f"'{f.name}' を読み込めません: {type(exc).__name__}: {exc}")

    return errors


def _render_upload_errors(errors: list[str]) -> None:
    st.error("アップロード内容を確認してください。")
    for error in errors:
        st.error(error)
