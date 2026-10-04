"""Parse CWE và tạo bảng tần suất.

Không loại class hiếm, gộp label multi-CWE hoặc chọn CWE đầu tiên.
Đó là quyết định nghiên cứu; các helper này chỉ mô tả dữ liệu.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

FREQUENCY_THRESHOLDS: tuple[int, ...] = (20, 50, 100, 200)
CWE_PATTERN = re.compile(r"CWE[-_ ]?(\d+)", re.IGNORECASE)
MISSING_TOKENS = {"", "none", "null", "nan", "n/a", "na", "unknown", "[]"}


def parse_cwe_labels(raw_value: object) -> list[str]:
    """Trả về mọi CWE unique theo thứ tự nguồn mà không chọn một label duy nhất."""
    if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
        return []
    if isinstance(raw_value, (list, tuple, set, np.ndarray, pd.Series)):
        values: Iterable[object] = raw_value
    elif isinstance(raw_value, str):
        text = raw_value.strip()
        if text.lower() in MISSING_TOKENS:
            return []
        values = [text]
        if text[:1] in "[{(" and text[-1:] in "]})":
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(text)
                    values = parsed.values() if isinstance(parsed, dict) else (
                        parsed if isinstance(parsed, (list, tuple, set)) else [parsed]
                    )
                    break
                except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                    continue
    else:
        values = [raw_value]
    labels: list[str] = []
    for value in values:
        for number in CWE_PATTERN.findall(str(value)):
            label = f"CWE-{int(number)}"
            if label not in labels:
                labels.append(label)
    return labels


def cwe_distribution(records: pd.DataFrame) -> pd.DataFrame:
    """Tạo bảng CWE gồm CWE, sample_count, percentage và project_count.

    Input chỉ được chứa vulnerable record và các cột audit chuẩn hóa.
    """
    labeled = records[records["cwe_list"].map(bool)].copy()
    exploded = labeled.explode("cwe_list").rename(columns={"cwe_list": "cwe"})
    grouped = exploded.groupby("cwe", dropna=False)
    result = grouped.agg(
        sample_count=("sample_id", "nunique"),
        project_count=("project", lambda values: values.dropna().nunique()),
        commit_count=("commit", lambda values: values.dropna().nunique()),
    ).reset_index()
    denominator = len(labeled)
    result["percentage_of_labeled_vulnerable"] = (
        result["sample_count"].div(denominator).mul(100) if denominator else 0.0
    )
    return result[["cwe", "sample_count", "percentage_of_labeled_vulnerable", "project_count", "commit_count"]].sort_values(
        ["sample_count", "cwe"], ascending=[False, True], ignore_index=True
    )


def threshold_summary(
    distribution: pd.DataFrame,
    labeled_records: pd.DataFrame,
    thresholds: Sequence[int] = FREQUENCY_THRESHOLDS,
) -> pd.DataFrame:
    """Với từng threshold, đếm số CWE, vulnerable function và tỷ lệ được giữ lại.

    Một sample multi-CWE chỉ được tính giữ lại một lần khi có CWE đạt threshold.
    """
    rows = []
    denominator = len(labeled_records)
    for threshold in thresholds:
        eligible = distribution.loc[distribution["sample_count"] >= threshold]
        eligible_cwe = set(eligible["cwe"])
        retained = int(labeled_records["cwe_list"].map(lambda labels: bool(set(labels) & eligible_cwe)).sum())
        rows.append({
            "threshold": threshold,
            "number_of_cwe": len(eligible),
            "number_of_samples": retained,
            "percentage_samples_retained": 100.0 * retained / denominator if denominator else 0.0,
            "minimum_class_size": int(eligible["sample_count"].min()) if len(eligible) else 0,
            "maximum_class_size": int(eligible["sample_count"].max()) if len(eligible) else 0,
        })
    return pd.DataFrame(rows)


def multi_cwe_summary(records: pd.DataFrame) -> pd.DataFrame:
    """Đếm sample có một CWE và sample có từ hai CWE trở lên.

    Do not reduce a multi-CWE sample to its first label.
    """
    counts = records["cwe_list"].map(len)
    total = len(records)
    result = pd.DataFrame([
        {"category": "zero_cwe", "sample_count": int((counts == 0).sum())},
        {"category": "exactly_one_cwe", "sample_count": int((counts == 1).sum())},
        {"category": "two_or_more_cwe", "sample_count": int((counts >= 2).sum())},
    ])
    result["percentage_of_vulnerable"] = result["sample_count"].div(total).mul(100) if total else 0.0
    return result
