from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


APP_TITLE = "\u7528\u6237\u6d41\u5931\u5206\u6790\u5e94\u7528"
REPORT_TITLE = "\u7528\u6237\u6d41\u5931\u5206\u6790\u62a5\u544a"
HIGH = "\u9ad8\u98ce\u9669"
MEDIUM = "\u4e2d\u98ce\u9669"
LOW = "\u4f4e\u98ce\u9669"
DAY_1_3 = "1-3\u5929"
DAY_3_7 = "3-7\u5929"
DAY_7_14 = "7-14\u5929"
DAY_14_PLUS = "14\u5929\u4ee5\u4e0a"


FIELD_LABELS = {
    "user_id": "\u7528\u6237ID",
    "login_days_7d": "\u8fd17\u65e5\u767b\u5f55\u5929\u6570",
    "last_active_days": "\u8ddd\u4e0a\u6b21\u6d3b\u8dc3\u5929\u6570",
    "payment_amount_30d": "\u8fd130\u65e5\u4ed8\u8d39\u91d1\u989d",
    "level": "\u7b49\u7ea7",
    "fail_count_3d": "\u8fd13\u65e5\u5931\u8d25\u6b21\u6570",
    "social_interactions_7d": "\u8fd17\u65e5\u793e\u4ea4\u4e92\u52a8\u6b21\u6570",
}

FIELD_ALIASES = {
    "user_id": [
        "user_id", "userid", "uid", "user", "player_id", "playerid", "role_id", "account_id",
        "用户id", "用户编号", "玩家id", "玩家编号", "角色id", "账号id",
    ],
    "login_days_7d": [
        "login_days_7d", "login7", "7d_login", "7dlogindays", "weekly_login_days",
        "最近7日登录天数", "近7日登录天数", "7日登录天数", "登录天数7日", "周登录天数",
    ],
    "last_active_days": [
        "last_active_days", "inactive_days", "days_since_last_active", "days_since_active",
        "最近活跃间隔", "距离上次活跃天数", "上次活跃距今天数", "未活跃天数", "不活跃天数", "流失间隔",
        "最近活跃日期", "上次活跃日期", "最后活跃日期", "上次活跃时间", "最后活跃时间",
    ],
    "payment_amount_30d": [
        "payment_amount_30d", "pay30", "30d_payment", "revenue30d", "amount30d",
        "最近30日付费金额", "近30日付费金额", "30日付费", "30日充值金额", "月付费金额",
    ],
    "level": [
        "level", "lv", "lvl", "player_level", "user_level",
        "等级", "玩家等级", "当前等级", "角色等级",
    ],
    "fail_count_3d": [
        "fail_count_3d", "fail3", "loss3", "recent_fail_count",
        "近3日失败次数", "最近3日失败次数", "失败次数3日", "近期失败次数", "挫败次数",
    ],
    "social_interactions_7d": [
        "social_interactions_7d", "social7", "7d_social", "interaction7d", "chat_count_7d",
        "近7日社交互动次数", "最近7日社交互动次数", "社交互动7日", "近7日互动次数", "社交次数",
    ],
}

TEXT_NULLS = {"", "-", "--", "—", "null", "none", "nan", "n/a", "na", "未知", "空", "无"}
FIELD_LIMITS = {
    "login_days_7d": (0, 7),
    "last_active_days": (0, 3650),
    "payment_amount_30d": (0, 100000000),
    "level": (0, 9999),
    "fail_count_3d": (0, 500),
    "social_interactions_7d": (0, 100000),
}


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

SESSION_DEFAULTS = {
    "uploaded_name": None,
    "uploaded_bytes": None,
    "upload_signature": None,
    "raw_original_df": None,
    "raw_df": None,
    "analysis_df": None,
    "summary": None,
    "html_report": None,
    "analysis_ready": False,
    "export_message": None,
    "cleaning_notes": [],
    "cleaning_summary_table": None,
    "base_cleaning_detail_table": None,
    "cleaning_detail_table": None,
    "assumption_notes": [],
}

for _key, _value in SESSION_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value


def normalize_key(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[\s_\-/()（）]+", "", text)
    return text


def make_unique_columns(columns: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for raw in columns:
        base = str(raw).strip() or "unnamed"
        count = seen.get(base, 0)
        if count:
            result.append(f"{base}_{count + 1}")
        else:
            result.append(base)
        seen[base] = count + 1
    return result


def infer_mapping(columns: List[str]) -> Dict[str, str | None]:
    normalized = {col: normalize_key(col) for col in columns}
    mapping: Dict[str, str | None] = {}
    for field, candidates in FIELD_ALIASES.items():
        normalized_candidates = [normalize_key(item) for item in candidates]
        match = None
        for col, norm in normalized.items():
            if norm in normalized_candidates:
                match = col
                break
        if match is None:
            for col, norm in normalized.items():
                if any(token in norm or norm in token for token in normalized_candidates):
                    match = col
                    break
        mapping[field] = match
    return mapping


def load_data(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(uploaded_file)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(uploaded_file)
    raise ValueError("Only CSV / XLSX / XLS files are supported.")


def load_data_from_bytes(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    buffer = BytesIO(file_bytes)
    buffer.name = file_name
    return load_data(buffer)


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, List[str], pd.DataFrame, pd.DataFrame]:
    notes: List[str] = []
    detail_rows: List[dict] = []
    work = df.copy()

    original_rows, original_cols = len(work), len(work.columns)
    work.columns = make_unique_columns([str(col).strip() for col in work.columns])

    for col in work.columns:
        if work[col].dtype == object:
            work[col] = work[col].map(lambda v: v.strip() if isinstance(v, str) else v)
            work[col] = work[col].replace(list(TEXT_NULLS), pd.NA)

    work = work.dropna(axis=0, how="all").dropna(axis=1, how="all")

    if len(work) != original_rows:
        notes.append(f"已删除 {original_rows - len(work)} 行全空记录。")
        detail_rows.append({"阶段": "结构清洗", "字段": "整表", "处理": "删除全空行", "影响记录数": original_rows - len(work)})
    if len(work.columns) != original_cols:
        notes.append(f"已删除 {original_cols - len(work.columns)} 列全空字段。")
        detail_rows.append({"阶段": "结构清洗", "字段": "整表", "处理": "删除全空列", "影响记录数": original_cols - len(work.columns)})

    duplicate_rows = int(work.duplicated().sum())
    if duplicate_rows:
        work = work.drop_duplicates().reset_index(drop=True)
        notes.append(f"已移除 {duplicate_rows} 行完全重复记录。")
        detail_rows.append({"阶段": "结构清洗", "字段": "整表", "处理": "删除重复行", "影响记录数": duplicate_rows})

    summary_table = pd.DataFrame(
        [
            {"指标": "原始行数", "值": original_rows},
            {"指标": "清洗后行数", "值": len(work)},
            {"指标": "原始列数", "值": original_cols},
            {"指标": "清洗后列数", "值": len(work.columns)},
        ]
    )
    detail_table = pd.DataFrame(detail_rows, columns=["阶段", "字段", "处理", "影响记录数"])

    if not notes:
        notes.append("未发现需要自动清理的空行、空列或重复记录。")
    return work, notes, summary_table, detail_table


def to_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(default)

    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace("¥", "", regex=False)
        .str.replace("%", "", regex=False)
        .replace(list(TEXT_NULLS), pd.NA)
    )
    is_negative_paren = cleaned.str.match(r"^\(.*\)$", na=False)
    unit_multiplier = pd.Series(1.0, index=cleaned.index)
    unit_multiplier = unit_multiplier.where(~cleaned.str.contains("亿", na=False), 100000000.0)
    unit_multiplier = unit_multiplier.where(~cleaned.str.contains("万", na=False), 10000.0)
    unit_multiplier = unit_multiplier.where(~cleaned.str.contains("千", na=False), 1000.0)
    cleaned = (
        cleaned
        .str.replace("亿", "", regex=False)
        .str.replace("万", "", regex=False)
        .str.replace("千", "", regex=False)
        .str.replace(r"[()]", "", regex=True)
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    numeric = numeric * unit_multiplier
    numeric = numeric.where(~is_negative_paren, -numeric)
    return numeric.fillna(default)


def maybe_convert_date_gap(series: pd.Series) -> tuple[pd.Series, bool]:
    if pd.api.types.is_datetime64_any_dtype(series):
        parsed = pd.to_datetime(series, errors="coerce")
        today = pd.Timestamp(datetime.now().date())
        converted = (today - parsed.dt.normalize()).dt.days.clip(lower=0)
        return converted.fillna(0), True

    # If the field is already numeric-like, treat it as a day-gap metric and do not
    # reinterpret it as a date. This avoids converting values like "7" into 1970-based timestamps.
    numeric_probe = pd.to_numeric(series, errors="coerce")
    if numeric_probe.notna().sum() / max(len(series), 1) >= 0.8:
        return series, False

    text_series = series.astype(str).str.strip()
    date_like_mask = text_series.str.contains(r"[-/年月日:]", regex=True, na=False)
    if date_like_mask.sum() / max(len(series), 1) < 0.5:
        return series, False

    parsed = pd.to_datetime(text_series.where(date_like_mask), errors="coerce")
    valid_count = int(parsed.notna().sum())
    if valid_count == 0:
        return series, False
    if valid_count / max(len(series), 1) < 0.6:
        return series, False
    today = pd.Timestamp(datetime.now().date())
    converted = (today - parsed.dt.normalize()).dt.days.clip(lower=0)
    return converted.fillna(0), True


def sanitize_metric_field(field: str, series: pd.Series) -> tuple[pd.Series, List[dict]]:
    actions: List[dict] = []
    low, high = FIELD_LIMITS[field]
    cleaned = series.copy()
    below_count = int((cleaned < low).sum())
    above_count = int((cleaned > high).sum())
    if below_count:
        cleaned = cleaned.mask(cleaned < low, low)
        actions.append({"阶段": "异常值修正", "字段": FIELD_LABELS[field], "处理": f"低于最小值 {low} 的记录已截断", "影响记录数": below_count})
    if above_count:
        cleaned = cleaned.mask(cleaned > high, high)
        actions.append({"阶段": "异常值修正", "字段": FIELD_LABELS[field], "处理": f"高于最大值 {high} 的记录已截断", "影响记录数": above_count})

    if field in {"login_days_7d", "last_active_days", "level", "fail_count_3d", "social_interactions_7d"}:
        decimal_count = int(((cleaned % 1) != 0).sum())
        cleaned = cleaned.round(0)
        if decimal_count:
            actions.append({"阶段": "格式修正", "字段": FIELD_LABELS[field], "处理": "小数值已四舍五入为整数", "影响记录数": decimal_count})
    else:
        cleaned = cleaned.round(2)
    return cleaned, actions


def analyze_data(df: pd.DataFrame, mapping: Dict[str, str | None]) -> tuple[pd.DataFrame, List[str], pd.DataFrame]:
    work = df.copy()
    assumptions: List[str] = []
    cleaning_actions: List[dict] = []

    if mapping.get("user_id") is None:
        work["_generated_user_id"] = [f"user_{idx + 1}" for idx in range(len(work))]
        mapping = {**mapping, "user_id": "_generated_user_id"}
        assumptions.append("缺少用户ID字段，已自动生成 user_序号 作为用户标识。")

    for field in FIELD_LABELS:
        col = mapping.get(field)
        if col is None or col not in work.columns:
            if field == "user_id":
                continue
            work[field] = 0
            assumptions.append(f"缺少“{FIELD_LABELS[field]}”，已按保守默认值 0 处理。")
        else:
            work[field] = work[col]

    work["user_id"] = work[mapping["user_id"]].astype(str)
    for field in FIELD_LABELS:
        if field != "user_id":
            if field == "last_active_days":
                converted, converted_from_date = maybe_convert_date_gap(work[field])
                if converted_from_date:
                    work[field] = converted
                    assumptions.append("检测到“距上次活跃天数”字段为日期格式，已自动换算为距今天数。")
                    cleaning_actions.append({"阶段": "语义换算", "字段": FIELD_LABELS[field], "处理": "日期自动换算为距今天数", "影响记录数": int(len(work[field]))})
            work[field] = to_numeric(work[field])
            work[field], field_actions = sanitize_metric_field(field, work[field])
            cleaning_actions.extend(field_actions)

    rows: List[dict] = []
    for row in work.itertuples(index=False):
        login = float(row.login_days_7d)
        inactive = float(row.last_active_days)
        pay = float(row.payment_amount_30d)
        level = float(row.level)
        fail = float(row.fail_count_3d)
        social = float(row.social_interactions_7d)

        prob = 0.05
        drivers: List[str] = []
        details: List[str] = []

        if login <= 1:
            prob += 0.32
            drivers.append("Engagement Drop")
            details.append(f"\u8fd17\u65e5\u767b\u5f55\u4ec5 {login:.0f} \u5929\uff0c\u6d3b\u8dc3\u8282\u594f\u660e\u663e\u4e0b\u6ed1")
        elif login <= 3:
            prob += 0.20
            drivers.append("Engagement Drop")
            details.append(f"\u8fd17\u65e5\u767b\u5f55 {login:.0f} \u5929\uff0c\u5468\u6d3b\u8dc3\u4e60\u60ef\u504f\u5f31")
        elif login <= 5:
            prob += 0.08

        if inactive >= 14:
            prob += 0.32
            if "Engagement Drop" not in drivers:
                drivers.append("Engagement Drop")
            details.append(f"\u5df2 {inactive:.0f} \u5929\u672a\u6d3b\u8dc3\uff0c\u5904\u4e8e\u5373\u65f6\u6d41\u5931\u7a97\u53e3")
        elif inactive >= 7:
            prob += 0.22
            if "Engagement Drop" not in drivers:
                drivers.append("Engagement Drop")
            details.append(f"\u8ddd\u4e0a\u6b21\u6d3b\u8dc3 {inactive:.0f} \u5929\uff0c\u56de\u6d41\u98ce\u9669\u660e\u663e\u5347\u9ad8")
        elif inactive >= 3:
            prob += 0.10

        if fail >= 4:
            prob += 0.18
            drivers.append("Frustration")
            details.append(f"\u8fd13\u65e5\u5931\u8d25 {fail:.0f} \u6b21\uff0c\u632b\u8d25\u611f\u8f83\u91cd")
        elif fail >= 2:
            prob += 0.11
            drivers.append("Frustration")
            details.append(f"\u8fd13\u65e5\u5931\u8d25 {fail:.0f} \u6b21\uff0c\u5b58\u5728\u8fde\u7eed\u53d7\u632b\u98ce\u9669")
        elif fail >= 1:
            prob += 0.05

        if social <= 1:
            prob += 0.15
            drivers.append("Social Isolation")
            details.append(f"\u8fd17\u65e5\u793e\u4ea4\u4e92\u52a8\u4ec5 {social:.0f} \u6b21\uff0c\u5173\u7cfb\u94fe\u7275\u5f15\u504f\u5f31")
        elif social <= 3:
            prob += 0.08
            drivers.append("Social Isolation")
            details.append(f"\u8fd17\u65e5\u793e\u4ea4\u4e92\u52a8 {social:.0f} \u6b21\uff0c\u793e\u4ea4\u9ecf\u6027\u4e0d\u8db3")

        if pay <= 0:
            prob += 0.10
            drivers.append("Motivation Loss")
            details.append("\u8fd130\u65e5\u65e0\u4ed8\u8d39\uff0c\u6210\u957f\u4e0e\u5956\u52b1\u8ffd\u6c42\u52a8\u529b\u504f\u5f31")
        elif pay < 5:
            prob += 0.04

        if level < 15:
            prob += 0.06
            if "Motivation Loss" not in drivers:
                drivers.append("Motivation Loss")
            details.append(f"\u5f53\u524d\u7b49\u7ea7 {level:.0f}\uff0c\u4ecd\u5904\u4e8e\u6210\u957f\u52a8\u673a\u8f83\u8106\u5f31\u9636\u6bb5")
        elif level < 30:
            prob += 0.03

        if inactive >= 14 and login <= 1:
            prob += 0.05
        if fail >= 2 and social <= 1:
            prob += 0.04

        prob = min(0.98, round(prob, 2))

        if prob > 0.7:
            risk = HIGH
            window = DAY_1_3
        elif prob >= 0.4:
            risk = MEDIUM
            window = DAY_3_7 if inactive >= 7 else DAY_7_14
        else:
            risk = LOW
            window = DAY_14_PLUS

        uniq = []
        for item in drivers:
            if item not in uniq:
                uniq.append(item)

        if not details:
            details = ["\u8fd1\u671f\u884c\u4e3a\u76f8\u5bf9\u7a33\u5b9a\uff0c\u672a\u89c2\u5bdf\u5230\u663e\u8457\u6d41\u5931\u4fe1\u53f7"]

        summary = (
            f"\u8be5\u7528\u6237\u5f53\u524d\u6d41\u5931\u6982\u7387\u4e3a {prob:.2f}\uff0c\u5224\u5b9a\u4e3a{risk}\u3002"
            f"\u4e3b\u8981\u98ce\u9669\u6765\u81ea{'/'.join(uniq[:3]) if uniq else '\u884c\u4e3a\u8282\u594f\u53d8\u5316'}\uff0c"
            f"\u5efa\u8bae\u56f4\u7ed5 {window} \u7a97\u53e3\u8fdb\u884c\u8fd0\u8425\u89e6\u8fbe\u3002"
        )

        rows.append(
            {
                "user_id": row.user_id,
                "churn_probability": prob,
                "risk_level": risk,
                "estimated_churn_time": window,
                "login_days_7d": login,
                "last_active_days": inactive,
                "payment_amount_30d": pay,
                "level": level,
                "fail_count_3d": fail,
                "social_interactions_7d": social,
                "drivers": uniq,
                "reason_analysis": "\uff1b".join(details[:3]),
                "summary": summary,
            }
        )

    cleaning_action_table = pd.DataFrame(cleaning_actions, columns=["阶段", "字段", "处理", "影响记录数"])
    return pd.DataFrame(rows), assumptions, cleaning_action_table


def build_summary(
    analysis_df: pd.DataFrame,
    assumptions: List[str] | None = None,
    cleaning_notes: List[str] | None = None,
    cleaning_detail_table: pd.DataFrame | None = None,
) -> dict:
    total = len(analysis_df)
    risk_order = [HIGH, MEDIUM, LOW]
    risk_counts = analysis_df["risk_level"].value_counts().reindex(risk_order, fill_value=0).to_dict()

    engagement_signal_count = int(analysis_df["drivers"].apply(lambda items: "Engagement Drop" in items).sum())
    driver_order = ["Social Isolation", "Frustration", "Motivation Loss"]
    driver_counts = {key: 0 for key in driver_order}
    for items in analysis_df["drivers"]:
        for item in items:
            if item in driver_counts:
                driver_counts[item] += 1

    risk_table = pd.DataFrame(
        [
            {
                "\u98ce\u9669\u7b49\u7ea7": risk,
                "\u7528\u6237\u6570": risk_counts[risk],
                "\u5360\u6bd4": round(risk_counts[risk] / total * 100, 2) if total else 0,
            }
            for risk in risk_order
        ]
    )

    metric_table = pd.DataFrame(
        [
            {"\u6307\u6807": "Avg Login Days (7d)", "\u503c": round(float(analysis_df["login_days_7d"].mean()), 2)},
            {"\u6307\u6807": "Avg Last Active Gap", "\u503c": round(float(analysis_df["last_active_days"].mean()), 2)},
            {"\u6307\u6807": "Avg Fail Count (3d)", "\u503c": round(float(analysis_df["fail_count_3d"].mean()), 2)},
            {"\u6307\u6807": "Avg Social Interactions (7d)", "\u503c": round(float(analysis_df["social_interactions_7d"].mean()), 2)},
            {"\u6307\u6807": "Avg Payment Amount (30d)", "\u503c": round(float(analysis_df["payment_amount_30d"].mean()), 2)},
            {"\u6307\u6807": "Avg Level", "\u503c": round(float(analysis_df["level"].mean()), 2)},
        ]
    )

    driver_map = {
        "Engagement Drop": "\u6d3b\u8dc3\u4e0b\u964d",
        "Social Isolation": "\u793e\u4ea4\u5b64\u7acb",
        "Frustration": "\u632b\u8d25\u611f",
        "Motivation Loss": "\u52a8\u673a\u6d41\u5931",
    }
    driver_table = pd.DataFrame(
        [
            {
                "\u6d41\u5931\u9a71\u52a8": driver_map[key],
                "\u9891\u6b21": driver_counts[key],
                "\u5360\u7528\u6237\u6bd4": round(driver_counts[key] / total * 100, 2) if total else 0,
            }
            for key in driver_order
        ]
    )

    samples = (
        analysis_df.sort_values(
            by=["churn_probability", "last_active_days", "login_days_7d"],
            ascending=[False, False, True],
        )
        .to_dict("records")
    )

    dominant_driver_label = driver_table.sort_values("频次", ascending=False).iloc[0]["流失驱动"] if not driver_table.empty else "社交孤立"
    driver_focus_map = {
        "社交孤立": "补强关系链留存与组队牵引",
        "挫败感": "优先修复失败反馈与难度断层",
        "动机流失": "重建成长奖励与阶段目标感",
    }
    operational_recommendations = {
        HIGH: [
            f"围绕 {DAY_1_3} 窗口做强召回，优先触达近7日登录 0-1 天且长时间未活跃的玩家，使用限时回归礼包、定向资源补偿和一键回流入口。",
            f"召回文案先聚焦“马上回来能拿到什么”，再结合主导问题“{dominant_driver_label}”给出明确修复承诺，例如降低失败成本、补发社交奖励或恢复成长节奏。",
            "高风险池建议由运营做名单化管理，按沉默时长和历史价值分层，避免泛发触达造成资源浪费。",
        ],
        MEDIUM: [
            f"把中风险用户作为“可修复盘”，优先做 {DAY_3_7} 的活跃回拉，通过任务减负、阶段奖励补强和轻社交目标避免继续滑入高风险池。",
            f"结合当前主导根因“{dominant_driver_label}”，重点推进{driver_focus_map.get(dominant_driver_label, '机制修复与内容补强')}，让用户在下一次登录时立刻感知改善。",
            "建议对中风险用户做分群实验，例如任务奖励加码、好友召回任务、失败保护机制，对比哪类干预更能把用户拉回稳定周循环。",
        ],
        LOW: [
            f"低风险用户重点不是强刺激召回，而是维持稳定周循环，围绕 {DAY_7_14} 与 {DAY_14_PLUS} 的长期留存节奏持续提供轻量目标和常规奖励。",
            "可通过签到、进度里程碑、轻社交互动和版本内容预告来巩固习惯，防止安全盘用户因内容空窗逐步转入中风险。",
            "建议把低风险人群作为留存基盘观察对象，持续监控其登录频次和互动变化，一旦出现活跃预警就提前干预。",
        ],
    }

    return {
        "total_users": total,
        "risk_counts": risk_counts,
        "risk_table": risk_table,
        "metric_table": metric_table,
        "driver_table": driver_table,
        "driver_counts": driver_counts,
        "engagement_signal_count": engagement_signal_count,
        "engagement_signal_pct": round(engagement_signal_count / total * 100, 2) if total else 0,
        "operational_recommendations": operational_recommendations,
        "samples": samples,
        "assumptions": assumptions or [],
        "cleaning_notes": cleaning_notes or [],
        "cleaning_detail_table": cleaning_detail_table if cleaning_detail_table is not None else pd.DataFrame(columns=["阶段", "字段", "处理", "影响记录数"]),
    }


def next_report_path(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    existing = list(folder.glob("user_churn_analysis_report_版本*.html"))
    nums: List[int] = []
    for path in existing:
        suffix = path.stem.split("版本")[-1]
        if suffix.isdigit():
            nums.append(int(suffix))
    return folder / f"user_churn_analysis_report_版本{max(nums, default=0) + 1}.html"


def risk_hex(risk: str) -> str:
    return {HIGH: "#c2410c", MEDIUM: "#b7791f", LOW: "#2f855a"}[risk]


def generate_html(summary: dict, source_name: str, report_title: str, top_n_samples: int) -> str:
    driver_display_map = {
        "Engagement Drop": "活跃下降",
        "Social Isolation": "社交孤立",
        "Frustration": "挫败感",
        "Motivation Loss": "动机流失",
    }
    metric_explanations = {
        "Avg Login Days (7d)": "周活跃习惯明显不足",
        "Avg Last Active Gap": "不活跃间隔已进入危险区",
        "Avg Fail Count (3d)": "挫败感在大盘中普遍存在",
        "Avg Social Interactions (7d)": "社交关系链牵引偏弱",
        "Avg Payment Amount (30d)": "近期付费贡献可用于判断动机稳定度",
        "Avg Level": "等级位置可帮助区分新手流失与中后期断裂",
    }
    risk_interpretations = {
        HIGH: "优先级最高的召回池",
        MEDIUM: "最适合做机制修复与分层运营",
        LOW: "安全盘较小，需要防止继续流失",
    }

    risk_values = [summary["risk_counts"][HIGH], summary["risk_counts"][MEDIUM], summary["risk_counts"][LOW]]
    risk_pct = [row["占比"] for _, row in summary["risk_table"].iterrows()]

    driver_table = summary["driver_table"]
    driver_values = driver_table["频次"].tolist()
    driver_pct = driver_table["占用户比"].tolist()
    engagement_signal_pct = summary.get("engagement_signal_pct", 0.0)
    engagement_signal_count = summary.get("engagement_signal_count", 0)

    metrics = summary["metric_table"]["值"].tolist()

    high_plus_medium_pct = round(risk_pct[0] + risk_pct[1], 2)
    dominant_risk = summary["risk_table"].sort_values("用户数", ascending=False).iloc[0]
    dominant_driver = summary["driver_table"].sort_values("频次", ascending=False).iloc[0]
    second_driver = summary["driver_table"].sort_values("频次", ascending=False).iloc[1]
    assumptions = summary.get("assumptions", [])
    cleaning_notes = summary.get("cleaning_notes", [])
    cleaning_detail_table = summary.get("cleaning_detail_table", pd.DataFrame(columns=["阶段", "字段", "处理", "影响记录数"]))
    operational_recommendations = summary.get("operational_recommendations", {})

    core_findings = [
        f"中高风险用户合计占比达到 {high_plus_medium_pct:.2f}%，说明流失风险已经不是边缘问题，而是需要系统性治理的大盘问题。",
        f"当前最关键风险分群是“{dominant_risk['风险等级']}”，共 {int(dominant_risk['用户数'])} 人，占总样本 {dominant_risk['占比']:.2f}%。",
        f"根因层面上，当前最主要的流失原因是“{dominant_driver['流失驱动']}”({dominant_driver['占用户比']:.2f}%)，其次是“{second_driver['流失驱动']}”({second_driver['占用户比']:.2f}%)。",
        f"表现层面上，已有 {engagement_signal_count} 名用户出现活跃下降预警，占总样本 {engagement_signal_pct:.2f}%，说明大量用户已经脱离稳定周循环。",
    ]

    most_critical_segment = (
        f"近7日登录 0-1 天、距上次活跃 14 天及以上，且伴随低社交互动与近期失败记录的玩家，"
        f"是最需要优先触达的高危召回对象。"
    )
    recommendation_cards = "".join(
        f"""
        <article class="kpi-card">
          <div class="eyebrow">{risk} 用户</div>
          <h3>{risk}运营建议</h3>
          <ul class="summary-list">{"".join(f"<li>{item}</li>" for item in operational_recommendations.get(risk, []))}</ul>
        </article>
        """
        for risk in [HIGH, MEDIUM, LOW]
    )

    risk_rows = "".join(
        f"<tr><td>{row['风险等级']}</td><td>{int(row['用户数'])}</td><td>{row['占比']:.2f}%</td></tr>"
        for _, row in summary["risk_table"].iterrows()
    )
    metric_rows = "".join(
        f"<tr><td>{row['指标']}</td><td>{row['值']}</td></tr>"
        for _, row in summary["metric_table"].iterrows()
    )
    driver_rows = "".join(
        f"<tr><td>{row['流失驱动']}</td><td>{int(row['频次'])}</td><td>{row['占用户比']:.2f}%</td></tr>"
        for _, row in summary["driver_table"].iterrows()
    )
    decision_rows = "".join(
        (
            f"<tr><td>风险分布</td><td>{row['风险等级']}</td><td>{int(row['用户数'])}（{row['占比']:.2f}%）</td>"
            f"<td>{risk_interpretations[row['风险等级']]}</td></tr>"
        )
        for _, row in summary["risk_table"].iterrows()
    )
    decision_rows += "".join(
        (
            f"<tr><td>行为均值</td><td>{row['指标']}</td><td>{row['值']}</td>"
            f"<td>{metric_explanations.get(row['指标'], '用于辅助判断流失强度')}</td></tr>"
        )
        for _, row in summary["metric_table"].iterrows()
    )
    decision_rows += "".join(
        (
            f"<tr><td>Top 驱动</td><td>{row['流失驱动']}</td><td>{int(row['频次'])}（{row['占用户比']:.2f}%）</td>"
            f"<td>{'需要优先修复关系链留存' if row['流失驱动'] == '社交孤立' else '失败受挫是重要促退因子' if row['流失驱动'] == '挫败感' else '成长与奖励动机相对次级但不可忽视'}</td></tr>"
        )
        for _, row in summary["driver_table"].iterrows()
    )
    decision_rows += (
        f"<tr><td>活跃预警</td><td>活跃下降</td><td>{engagement_signal_count}（{engagement_signal_pct:.2f}%）</td>"
        f"<td>这是表现层预警信号，不与根因并列，建议结合社交、挫败和动机问题一起解释。</td></tr>"
    )

    risk_progress_rows = "".join(
        f"""
        <div class="bar-row">
          <div class="bar-head"><span>{row['风险等级']}</span><strong>{int(row['用户数'])} / {row['占比']:.2f}%</strong></div>
          <div class="bar-track"><div class="bar-fill {('high-fill' if row['风险等级'] == HIGH else 'medium-fill' if row['风险等级'] == MEDIUM else 'low-fill')}" style="width:{row['占比']:.2f}%;"></div></div>
        </div>
        """
        for _, row in summary["risk_table"].iterrows()
    )
    driver_fill_class = {
        "社交孤立": "blue-fill",
        "挫败感": "medium-fill",
        "动机流失": "low-fill",
    }
    driver_progress_rows = "".join(
        f"""
        <div class="bar-row">
          <div class="bar-head"><span>{row['流失驱动']}</span><strong>{int(row['频次'])} / {row['占用户比']:.2f}%</strong></div>
          <div class="bar-track"><div class="bar-fill {driver_fill_class.get(row['流失驱动'], 'blue-fill')}" style="width:{row['占用户比']:.2f}%;"></div></div>
        </div>
        """
        for _, row in summary["driver_table"].iterrows()
    )

    findings_html = "".join(f"<li>{item}</li>" for item in core_findings)
    assumption_html = "".join(f"<li>{item}</li>" for item in assumptions) or "<li>本次分析未使用额外缺失字段假设。</li>"
    cleaning_html = "".join(f"<li>{item}</li>" for item in cleaning_notes) or "<li>本次数据未触发额外自动清洗动作。</li>"
    cleaning_detail_rows = "".join(
        f"<tr><td>{row['阶段']}</td><td>{row['字段']}</td><td>{row['处理']}</td><td>{int(row['影响记录数'])}</td></tr>"
        for _, row in cleaning_detail_table.iterrows()
    ) or "<tr><td colspan='4'>本次未记录到额外字段级清洗动作。</td></tr>"

    cards = []
    for item in summary["samples"][:top_n_samples]:
        driver_text = "/".join(driver_display_map.get(driver, driver) for driver in item["drivers"][:3]) or "行为节奏变化"
        bullets = [
            f"近7日登录 {item['login_days_7d']:.0f} 天，距上次活跃 {item['last_active_days']:.0f} 天，活跃节奏明显转弱。",
            f"近3日失败 {item['fail_count_3d']:.0f} 次，近7日社交互动 {item['social_interactions_7d']:.0f} 次，当前主要风险来自 {driver_text}。",
            f"近30日付费 {item['payment_amount_30d']:.2f}，当前等级 {item['level']:.0f}，建议围绕 {item['estimated_churn_time']} 窗口优先触达。",
        ]
        bullet_html = "".join(f"<li>{bullet}</li>" for bullet in bullets)
        cards.append(
            f"""
            <article class="sample-card">
              <header>
                <div>
                  <h3>{item['user_id']}</h3>
                  <div class="sample-meta">预计流失时间：{item['estimated_churn_time']}</div>
                </div>
                <span class="risk-pill" style="background:{risk_hex(item['risk_level'])};">{item['risk_level']} {item['churn_probability']:.2f}</span>
              </header>
              <ul>{bullet_html}</ul>
              <p><strong>原因分析：</strong>{item['reason_analysis']}</p>
              <p class="footer-note">{item['summary']}</p>
            </article>
            """
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{report_title}</title>
  <style>
    :root {{
      --bg:#f6efe5; --bg-deep:#eadbc5; --panel:rgba(255,250,242,0.94); --ink:#1f2937; --muted:#6b7280;
      --line:#e6dac6; --high:#c2410c; --medium:#b7791f; --low:#2f855a; --blue:#2563eb; --shadow:0 20px 44px rgba(84,61,27,.08); --radius:24px;
    }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font:16px/1.65 "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink);
      background:radial-gradient(circle at 10% 20%, rgba(194,65,12,.08), transparent 26%), radial-gradient(circle at 90% 10%, rgba(37,99,235,.08), transparent 24%), linear-gradient(180deg,var(--bg) 0%,var(--bg-deep) 100%); }}
    .wrap {{ max-width:1260px; margin:0 auto; padding:34px 22px 72px; }}
    .hero,.panel,.sample-card {{ background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); padding:22px; }}
    .section {{ margin-top:18px; }} .hero-grid,.kpi-grid,.chart-grid,.sample-grid,.summary-grid {{ display:grid; gap:16px; }}
    .hero-grid {{ grid-template-columns:1.4fr .8fr; }} .kpi-grid {{ grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); }} .chart-grid {{ grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); }} .sample-grid {{ grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); }}
    .summary-grid {{ grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); }}
    .tag-row,.toggle-row,.legend {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }}
    .tag,.toggle-btn {{ padding:7px 12px; border-radius:999px; border:1px solid var(--line); background:#f5ebdc; color:#7a5b35; font-size:13px; }}
    .toggle-btn.active {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
    .kpi-card {{ padding:20px; border:1px solid var(--line); border-radius:20px; background:rgba(255,255,255,.55); }}
    .kpi-number {{ font-size:36px; font-weight:700; margin:10px 0 8px; }} .muted,.footer-note,.sample-meta {{ color:var(--muted); font-size:13px; }}
    .chart-shell {{ margin-top:14px; padding:14px; border-radius:18px; border:1px solid var(--line); background:rgba(255,255,255,.58); }}
    canvas {{ width:100%; height:auto; display:block; }} .legend-item {{ display:inline-flex; align-items:center; gap:8px; }}
    .legend-dot {{ width:10px; height:10px; border-radius:999px; }} .tooltip {{ position:fixed; z-index:20; pointer-events:none; padding:10px 12px; min-width:120px; border-radius:14px; background:rgba(31,41,55,.94); color:#fff; font-size:12px; opacity:0; transition:opacity .14s ease; }}
    .tooltip.show {{ opacity:1; }} .table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; font-size:14px; }} th,td {{ text-align:left; padding:12px 10px; border-bottom:1px solid var(--line); vertical-align:top; }} th {{ color:#6b4e2e; background:rgba(243,234,219,.72); font-weight:600; }}
    .sample-card header {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }} .risk-pill {{ display:inline-flex; align-items:center; border-radius:999px; padding:6px 10px; color:#fff; font-size:12px; font-weight:700; }}
    .eyebrow {{ color:#8b6b44; font-size:12px; letter-spacing:.08em; text-transform:uppercase; }} .summary-list {{ margin:0; padding-left:18px; }}
    .note-box {{ background:rgba(255,255,255,.45); border:1px dashed var(--line); border-radius:18px; padding:16px 18px; }}
    .bars {{ display:grid; gap:14px; margin-top:8px; }} .bar-row {{ display:grid; gap:8px; }} .bar-head {{ display:flex; justify-content:space-between; gap:12px; font-size:14px; }}
    .bar-track {{ width:100%; height:14px; border-radius:999px; background:rgba(214,194,165,.45); overflow:hidden; }} .bar-fill {{ height:100%; border-radius:999px; }}
    .high-fill {{ background:linear-gradient(90deg,#c2410c,#fb923c); }} .medium-fill {{ background:linear-gradient(90deg,#b7791f,#f6ad55); }} .low-fill {{ background:linear-gradient(90deg,#2f855a,#68d391); }} .blue-fill {{ background:linear-gradient(90deg,#2563eb,#60a5fa); }}
    .sample-card ul {{ margin:14px 0 0; padding-left:18px; }}
    @media (max-width:960px) {{ .hero-grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="muted">User Churn Dashboard</div>
          <h1>{report_title}</h1>
          <p>基于 <code>{source_name}</code> 生成的用户流失分析网页报告。本报告使用启发式规则进行流失风险估算，适合运营分层、召回优先级和趋势诊断。</p>
          <div class="tag-row"><span class="tag">简体中文</span><span class="tag">单文件 HTML</span><span class="tag">交互式图表</span><span class="tag">自动导出</span></div>
        </div>
        <div><h3>分析说明</h3><p class="muted">生成时间：{generated_at}</p><p class="muted">样本量：{summary['total_users']} 用户</p><p class="muted">方法：启发式流失评分</p></div>
      </div>
    </section>
    <section class="section kpi-grid">
      <article class="kpi-card"><div>高风险用户</div><div class="kpi-number" style="color:#c2410c;">{risk_values[0]}</div><p class="muted">占比 {risk_pct[0]:.2f}%</p></article>
      <article class="kpi-card"><div>中风险用户</div><div class="kpi-number" style="color:#b7791f;">{risk_values[1]}</div><p class="muted">占比 {risk_pct[1]:.2f}%</p></article>
      <article class="kpi-card"><div>低风险用户</div><div class="kpi-number" style="color:#2f855a;">{risk_values[2]}</div><p class="muted">占比 {risk_pct[2]:.2f}%</p></article>
      <article class="kpi-card"><div>活跃预警覆盖</div><div class="kpi-number">{engagement_signal_pct:.2f}%</div><p class="muted">{engagement_signal_count} 名用户已出现登录/活跃节奏走弱</p></article>
    </section>
    <section class="section summary-grid">
      <article class="panel">
        <div class="eyebrow">核心结论</div>
        <h2>本期流失风险不再是尾部现象</h2>
        <ul class="summary-list">{findings_html}</ul>
      </article>
      <article class="panel">
        <div class="eyebrow">最关键风险分群</div>
        <h2>优先触达高危沉默用户</h2>
        <p>{most_critical_segment}</p>
      </article>
    </section>
    <section class="section panel">
      <div class="eyebrow">运营建议</div>
      <h2>按风险等级分层制定动作</h2>
      <div class="kpi-grid">{recommendation_cards}</div>
    </section>
    <section class="section chart-grid">
      <article class="panel note-box"><h2>数据清洗记录</h2><ul class="summary-list">{cleaning_html}</ul></article>
      <article class="panel note-box"><h2>分析假设说明</h2><ul class="summary-list">{assumption_html}</ul></article>
    </section>
    <section class="section panel"><h2>清洗动作明细</h2><div class="table-wrap"><table><thead><tr><th>阶段</th><th>字段</th><th>处理</th><th>影响记录数</th></tr></thead><tbody>{cleaning_detail_rows}</tbody></table></div></section>
    <section class="section chart-grid">
      <article class="panel"><h2>风险分布饼图</h2><div class="toggle-row" data-toggle-group="risk"><button class="toggle-btn active" data-mode="count">看人数</button><button class="toggle-btn" data-mode="percent">看占比</button></div><div class="chart-shell"><canvas id="riskPie" width="520" height="330"></canvas></div><div class="legend"><span class="legend-item"><span class="legend-dot" style="background:#c2410c;"></span>高风险</span><span class="legend-item"><span class="legend-dot" style="background:#b7791f;"></span>中风险</span><span class="legend-item"><span class="legend-dot" style="background:#2f855a;"></span>低风险</span></div><p class="footer-note">洞察：中高风险用户合计占比很高，说明留存问题已经具备系统性特征。</p></article>
      <article class="panel"><h2>流失根因柱状图</h2><div class="toggle-row" data-toggle-group="driver"><button class="toggle-btn active" data-mode="count">看人数</button><button class="toggle-btn" data-mode="percent">看占比</button></div><div class="chart-shell"><canvas id="driverBar" width="520" height="330"></canvas></div><p class="footer-note">洞察：这里展示的是根因层问题，活跃下降已被单独归为表现层预警，不再和根因并列。</p></article>
      <article class="panel"><h2>关键行为均值柱状图</h2><div class="chart-shell"><canvas id="metricBar" width="520" height="330"></canvas></div><p class="footer-note">洞察：不活跃天数偏高，而登录天数偏低，说明大量用户已脱离稳定回流节奏。</p></article>
    </section>
    <section class="section chart-grid">
      <article class="panel"><h2>风险分布进度条</h2><div class="bars">{risk_progress_rows}</div></article>
      <article class="panel"><h2>流失根因进度条</h2><div class="bars">{driver_progress_rows}</div><div class="note-box" style="margin-top:16px;"><strong>活跃预警：</strong> {engagement_signal_count} 名用户 / {engagement_signal_pct:.2f}% 已出现活跃下降表现，建议结合根因标签一起判断。</div></article>
    </section>
    <section class="section panel"><h2>聚合统计表</h2><div class="table-wrap"><table><thead><tr><th>表格</th><th>指标</th><th>值</th><th>解释</th></tr></thead><tbody>{decision_rows}</tbody></table></div></section>
    <section class="section"><h2>高风险样本用户</h2><div class="sample-grid">{''.join(cards)}</div></section>
  </div>
  <div id="chartTooltip" class="tooltip"></div>
  <script>
    const state = {{ riskMode: "count", driverMode: "count", hitAreas: {{}} }};
    const riskData = [{{ label: "High", count: {risk_values[0]}, percent: {risk_pct[0]:.2f}, color: "#c2410c" }}, {{ label: "Medium", count: {risk_values[1]}, percent: {risk_pct[1]:.2f}, color: "#b7791f" }}, {{ label: "Low", count: {risk_values[2]}, percent: {risk_pct[2]:.2f}, color: "#2f855a" }}];
    const driverData = [{{ label: "Social Isolation", count: {driver_values[0]}, percent: {driver_pct[0]:.2f}, color: "#2563eb", color2: "#60a5fa" }}, {{ label: "Frustration", count: {driver_values[1]}, percent: {driver_pct[1]:.2f}, color: "#b7791f", color2: "#f6ad55" }}, {{ label: "Motivation Loss", count: {driver_values[2]}, percent: {driver_pct[2]:.2f}, color: "#2f855a", color2: "#68d391" }}];
    const metricData = [{{ label: "Login Days", value: {metrics[0]:.2f}, color: "#2563eb", color2: "#60a5fa" }}, {{ label: "Inactive Gap", value: {metrics[1]:.2f}, color: "#c2410c", color2: "#fb923c" }}, {{ label: "Fail Count", value: {metrics[2]:.2f}, color: "#7c3aed", color2: "#a78bfa" }}, {{ label: "Social Interactions", value: {metrics[3]:.2f}, color: "#0f766e", color2: "#5eead4" }}];
    function fitCanvas(canvas) {{ const r = window.devicePixelRatio || 1; const rect = canvas.getBoundingClientRect(); const w = rect.width || canvas.width; const h = rect.height || canvas.height; canvas.width = Math.round(w * r); canvas.height = Math.round(h * r); const ctx = canvas.getContext("2d"); ctx.setTransform(r, 0, 0, r, 0, 0); return {{ ctx, width: w, height: h }}; }}
    function setTooltip(content, x, y) {{ const tip = document.getElementById("chartTooltip"); tip.innerHTML = content; tip.style.left = (x + 14) + "px"; tip.style.top = (y + 14) + "px"; tip.classList.add("show"); }}
    function hideTooltip() {{ document.getElementById("chartTooltip").classList.remove("show"); }}
    function drawRiskPie() {{ const canvas = document.getElementById("riskPie"); const {{ ctx, width, height }} = fitCanvas(canvas); ctx.clearRect(0, 0, width, height); const total = riskData.reduce((s, i) => s + i.count, 0); const cx = width * 0.35; const cy = height * 0.54; const radius = Math.min(width, height) * 0.28; let startAngle = -Math.PI / 2; const areas = []; riskData.forEach((item) => {{ const angle = (item.count / total) * Math.PI * 2; const endAngle = startAngle + angle; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, radius, startAngle, endAngle); ctx.closePath(); ctx.fillStyle = item.color; ctx.fill(); const mid = startAngle + angle / 2; const lx = cx + Math.cos(mid) * radius * 0.65; const ly = cy + Math.sin(mid) * radius * 0.65; ctx.fillStyle = "#fff"; ctx.font = "bold 13px Segoe UI"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(item.label, lx, ly - 8); ctx.fillText(state.riskMode === "count" ? item.count.toString() : item.percent.toFixed(1) + "%%", lx, ly + 10); areas.push({{ type: "arc", cx, cy, radius, start: startAngle, end: endAngle, item }}); startAngle = endAngle; }}); state.hitAreas.riskPie = areas; }}
    function drawBar(canvasId, data, mode, max, step, fieldKey) {{ const canvas = document.getElementById(canvasId); const {{ ctx, width, height }} = fitCanvas(canvas); ctx.clearRect(0, 0, width, height); const pad = {{ top: 24, right: 20, bottom: 64, left: 54 }}; const chartWidth = width - pad.left - pad.right; const chartHeight = height - pad.top - pad.bottom; const gap = 18; const barWidth = (chartWidth - gap * (data.length - 1)) / data.length; const areas = []; ctx.strokeStyle = "#e6dac6"; ctx.lineWidth = 1; ctx.fillStyle = "#6b7280"; ctx.font = "12px Segoe UI"; ctx.textAlign = "right"; ctx.textBaseline = "middle"; for (let v = 0; v <= max; v += step) {{ const y = pad.top + chartHeight - (v / max) * chartHeight; ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke(); ctx.fillText(String(Math.round(v * 100) / 100), pad.left - 8, y); }} data.forEach((item, index) => {{ const value = item[fieldKey]; const x = pad.left + index * (barWidth + gap); const barHeight = (value / max) * chartHeight; const y = pad.top + chartHeight - barHeight; const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight); gradient.addColorStop(0, item.color); gradient.addColorStop(1, item.color2 || item.color); ctx.fillStyle = gradient; ctx.fillRect(x, y, barWidth, barHeight); ctx.fillStyle = "#1f2937"; ctx.textAlign = "center"; ctx.font = "bold 12px Segoe UI"; const topText = mode === "percent" ? value.toFixed(2) + "%%" : value.toLocaleString(); ctx.fillText(topText, x + barWidth / 2, y - 10); ctx.fillStyle = "#6b7280"; ctx.font = "12px Segoe UI"; ctx.fillText(item.label, x + barWidth / 2, height - 26); areas.push({{ type: "rect", x, y, width: barWidth, height: barHeight, item }}); }}); state.hitAreas[canvasId] = areas; }}
    function drawDriverBar() {{ const field = state.driverMode === "percent" ? "percent" : "count"; const countMax = Math.max(...driverData.map((item) => item.count), 1); const max = state.driverMode === "percent" ? 100 : countMax * 1.1; const step = state.driverMode === "percent" ? 25 : Math.max(1, Math.ceil(countMax / 4 / 100) * 100); drawBar("driverBar", driverData, state.driverMode, max, step, field); }}
    function drawMetricBar() {{ const metricMax = Math.max(...metricData.map((item) => item.value), 1); const step = Math.max(1, Math.ceil(metricMax / 4)); drawBar("metricBar", metricData, "value", metricMax * 1.15, step, "value"); }}
    function pointInArc(px, py, area) {{ const dx = px - area.cx; const dy = py - area.cy; const dist = Math.sqrt(dx * dx + dy * dy); if (dist > area.radius) return false; let angle = Math.atan2(dy, dx); if (angle < -Math.PI / 2) angle += Math.PI * 2; let startAngle = area.start; let endAngle = area.end; if (startAngle < -Math.PI / 2) startAngle += Math.PI * 2; if (endAngle < startAngle) endAngle += Math.PI * 2; if (angle < startAngle) angle += Math.PI * 2; return angle >= startAngle && angle <= endAngle; }}
    function bindTooltip(canvasId, formatter) {{ const canvas = document.getElementById(canvasId); canvas.addEventListener("mousemove", (event) => {{ const rect = canvas.getBoundingClientRect(); const x = event.clientX - rect.left; const y = event.clientY - rect.top; const areas = state.hitAreas[canvasId] || []; let match = null; for (const area of areas) {{ if (area.type === "arc" && pointInArc(x, y, area)) {{ match = area; break; }} if (area.type === "rect" && x >= area.x && x <= area.x + area.width && y >= area.y && y <= area.y + area.height) {{ match = area; break; }} }} if (!match) {{ hideTooltip(); return; }} setTooltip(formatter(match), event.clientX, event.clientY); }}); canvas.addEventListener("mouseleave", hideTooltip); }}
    function syncToggle(groupName, activeMode) {{ document.querySelectorAll('[data-toggle-group="' + groupName + '"] .toggle-btn').forEach((btn) => btn.classList.toggle("active", btn.dataset.mode === activeMode)); }}
    function initToggles() {{ document.querySelectorAll('[data-toggle-group="risk"] .toggle-btn').forEach((btn) => btn.addEventListener("click", () => {{ state.riskMode = btn.dataset.mode; syncToggle("risk", state.riskMode); drawRiskPie(); }})); document.querySelectorAll('[data-toggle-group="driver"] .toggle-btn').forEach((btn) => btn.addEventListener("click", () => {{ state.driverMode = btn.dataset.mode; syncToggle("driver", state.driverMode); drawDriverBar(); }})); }}
    function renderCharts() {{ drawRiskPie(); drawDriverBar(); drawMetricBar(); }}
    window.addEventListener("load", () => {{ renderCharts(); initToggles(); bindTooltip("riskPie", (area) => "<strong>" + area.item.label + "</strong><br>Count: " + area.item.count.toLocaleString() + "<br>Percent: " + area.item.percent.toFixed(2) + "%%"); bindTooltip("driverBar", (area) => "<strong>" + area.item.label + "</strong><br>Count: " + area.item.count.toLocaleString() + "<br>Percent: " + area.item.percent.toFixed(2) + "%%"); bindTooltip("metricBar", (area) => "<strong>" + area.item.label + "</strong><br>Average: " + area.item.value.toFixed(2)); }});
    window.addEventListener("resize", renderCharts);
  </script>
</body>
</html>
"""


st.title(APP_TITLE)
st.caption("\u62d6\u62fd\u4e0a\u4f20 CSV / Excel\uff0c\u81ea\u52a8\u5b8c\u6210\u6d41\u5931\u5206\u6790\u3001\u56fe\u8868\u5c55\u793a\u548c HTML \u62a5\u544a\u5bfc\u51fa\u3002")

with st.sidebar:
    st.header("\u5206\u6790\u914d\u7f6e")
    output_dir = st.text_input(
        "\u62a5\u544a\u8f93\u51fa\u76ee\u5f55",
        value=str(Path(__file__).parent),
        help="\u70b9\u51fb\u5bfc\u51fa\u65f6\uff0c\u4f1a\u81ea\u52a8\u751f\u6210\u4e0b\u4e00\u4e2a\u7248\u672c\u53f7\u7684 HTML \u62a5\u544a\u3002",
    )
    report_title = st.text_input("\u62a5\u544a\u6807\u9898", value=REPORT_TITLE)
    top_n_samples = st.slider("\u9ad8\u98ce\u9669\u6837\u672c\u5c55\u793a\u6570", 3, 10, 6)


uploaded_file = st.file_uploader(
    "\u62d6\u62fd\u6216\u9009\u62e9\u6570\u636e\u6587\u4ef6",
    type=["csv", "xlsx", "xls"],
    help="\u652f\u6301 CSV / Excel \u6587\u4ef6\u3002",
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    signature = (uploaded_file.name, len(file_bytes))
    if st.session_state.upload_signature != signature:
        try:
            loaded_df = load_data_from_bytes(uploaded_file.name, file_bytes)
            cleaned_df, cleaning_notes, cleaning_summary_table, cleaning_detail_table = clean_dataframe(loaded_df)
            st.session_state.raw_original_df = loaded_df
            st.session_state.raw_df = cleaned_df
            st.session_state.cleaning_notes = cleaning_notes
            st.session_state.cleaning_summary_table = cleaning_summary_table
            st.session_state.base_cleaning_detail_table = cleaning_detail_table
            st.session_state.cleaning_detail_table = cleaning_detail_table
        except Exception as exc:
            st.error(f"\u8bfb\u53d6\u6587\u4ef6\u5931\u8d25\uff1a{exc}")
            st.stop()
        st.session_state.uploaded_name = uploaded_file.name
        st.session_state.uploaded_bytes = file_bytes
        st.session_state.upload_signature = signature
        st.session_state.analysis_df = None
        st.session_state.summary = None
        st.session_state.html_report = None
        st.session_state.analysis_ready = False
        st.session_state.export_message = None
        st.session_state.assumption_notes = []

raw_df = st.session_state.raw_df

if raw_df is None:
    st.info("\u4e0a\u4f20\u4e00\u4efd\u884c\u4e3a\u6570\u636e\u8868\u540e\uff0c\u5e94\u7528\u4f1a\u81ea\u52a8\u8fdb\u5165\u5b57\u6bb5\u8bc6\u522b\u548c\u5206\u6790\u6d41\u7a0b\u3002")
    st.stop()

source_name = st.session_state.uploaded_name or "\u672a\u547d\u540d\u6587\u4ef6"
st.success(f"\u5df2\u8bfb\u53d6\u6587\u4ef6\uff1a`{source_name}`\uff0c\u5171 {len(raw_df)} \u884c\uff0c{len(raw_df.columns)} \u5217\u3002")

with st.expander("\u6570\u636e\u6e05\u6d17\u8bb0\u5f55", expanded=False):
    for note in st.session_state.cleaning_notes:
        st.write(f"- {note}")
    if st.session_state.cleaning_summary_table is not None:
        st.dataframe(st.session_state.cleaning_summary_table, use_container_width=True, hide_index=True)
    if st.session_state.cleaning_detail_table is not None and not st.session_state.cleaning_detail_table.empty:
        st.markdown("**清洗动作明细**")
        st.dataframe(st.session_state.cleaning_detail_table, use_container_width=True, hide_index=True)

with st.expander("\u67e5\u770b\u6e05\u6d17\u524d\u540e\u5bf9\u6bd4", expanded=True):
    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("**清洗前预览**")
        if st.session_state.raw_original_df is not None:
            st.dataframe(st.session_state.raw_original_df.head(20), use_container_width=True)
    with after_col:
        st.markdown("**清洗后预览**")
        st.dataframe(raw_df.head(20), use_container_width=True)

mapping_defaults = infer_mapping(list(raw_df.columns))
mapping: Dict[str, str | None] = {}

with st.expander("\u5b57\u6bb5\u6620\u5c04", expanded=True):
    st.write("\u5982\u679c\u81ea\u52a8\u8bc6\u522b\u4e0d\u51c6\u786e\uff0c\u53ef\u4ee5\u624b\u52a8\u4fee\u6539\u3002")
    options = ["<empty>"] + list(raw_df.columns)
    cols = st.columns(2)
    for idx, (field, label) in enumerate(FIELD_LABELS.items()):
        default_col = mapping_defaults.get(field)
        default_index = options.index(default_col) if default_col in options else 0
        selected = cols[idx % 2].selectbox(label, options=options, index=default_index, key=f"map_{field}")
        mapping[field] = None if selected == "<empty>" else selected

if st.button("\u5f00\u59cb\u5206\u6790", type="primary", use_container_width=True):
    analysis_df, assumption_notes, analysis_cleaning_table = analyze_data(raw_df, mapping)
    existing_cleaning_table = (
        st.session_state.base_cleaning_detail_table
        if st.session_state.base_cleaning_detail_table is not None
        else pd.DataFrame(columns=["阶段", "字段", "处理", "影响记录数"])
    )
    combined_cleaning_table = pd.concat(
        [existing_cleaning_table, analysis_cleaning_table],
        ignore_index=True,
    )
    summary = build_summary(
        analysis_df,
        assumption_notes,
        st.session_state.cleaning_notes,
        combined_cleaning_table,
    )
    st.session_state.analysis_df = analysis_df
    st.session_state.summary = summary
    st.session_state.html_report = generate_html(summary, source_name, report_title, top_n_samples)
    st.session_state.analysis_ready = True
    st.session_state.export_message = None
    st.session_state.assumption_notes = assumption_notes
    st.session_state.cleaning_detail_table = combined_cleaning_table

if not st.session_state.analysis_ready:
    st.stop()

analysis_df = st.session_state.analysis_df
summary = st.session_state.summary

if st.session_state.assumption_notes:
    with st.expander("\u5206\u6790\u5047\u8bbe\u8bf4\u660e", expanded=True):
        for note in st.session_state.assumption_notes:
            st.write(f"- {note}")

st.subheader(report_title)

metrics = st.columns(4)
metrics[0].metric("\u9ad8\u98ce\u9669\u7528\u6237", summary["risk_counts"][HIGH], f"{summary['risk_table'].iloc[0]['占比']:.2f}%")
metrics[1].metric("\u4e2d\u98ce\u9669\u7528\u6237", summary["risk_counts"][MEDIUM], f"{summary['risk_table'].iloc[1]['占比']:.2f}%")
metrics[2].metric("\u4f4e\u98ce\u9669\u7528\u6237", summary["risk_counts"][LOW], f"{summary['risk_table'].iloc[2]['占比']:.2f}%")
metrics[3].metric("\u6d3b\u8dc3\u9884\u8b66\u8986\u76d6", f"{summary['engagement_signal_pct']:.2f}%", f"{summary['engagement_signal_count']} \u4eba")

chart_cols = st.columns(3)
with chart_cols[0]:
    st.markdown("#### \u98ce\u9669\u5206\u5e03")
    risk_chart_df = pd.DataFrame(
        {"风险等级": [HIGH, MEDIUM, LOW], "用户数": [summary["risk_counts"][HIGH], summary["risk_counts"][MEDIUM], summary["risk_counts"][LOW]]}
    )
    st.vega_lite_chart(
        risk_chart_df,
        {
            "mark": {"type": "arc", "innerRadius": 40},
            "encoding": {
                "theta": {"field": "用户数", "type": "quantitative"},
                "color": {"field": "风险等级", "type": "nominal"},
                "tooltip": [{"field": "风险等级"}, {"field": "用户数"}],
            },
        },
        use_container_width=True,
    )
    st.caption("\u6d1e\u5bdf\uff1a\u4e2d\u9ad8\u98ce\u9669\u7528\u6237\u5408\u8ba1\u5360\u6bd4\u5f88\u9ad8\uff0c\u8bf4\u660e\u7559\u5b58\u95ee\u9898\u5df2\u5177\u5907\u7cfb\u7edf\u6027\u7279\u5f81\u3002")

with chart_cols[1]:
    st.markdown("#### \u6d41\u5931\u6839\u56e0")
    st.bar_chart(summary["driver_table"].set_index("流失驱动")["频次"], use_container_width=True)
    st.caption("\u6d1e\u5bdf\uff1a\u8fd9\u91cc\u5c55\u793a\u7684\u662f\u6839\u56e0\u5c42\u95ee\u9898\uff0c\u6d3b\u8dc3\u4e0b\u964d\u5df2\u5355\u72ec\u5f52\u4e3a\u8868\u73b0\u5c42\u9884\u8b66\u3002")

with chart_cols[2]:
    st.markdown("#### \u5173\u952e\u884c\u4e3a\u5747\u503c")
    behavior_df = pd.DataFrame(
        {
            "指标": ["登录天数", "不活跃天数", "失败次数", "社交互动"],
            "值": summary["metric_table"]["值"].tolist()[:4],
        }
    )
    st.bar_chart(behavior_df.set_index("指标")["值"], use_container_width=True)
    st.caption("\u6d1e\u5bdf\uff1a\u4e0d\u6d3b\u8dc3\u5929\u6570\u504f\u9ad8\uff0c\u800c\u767b\u5f55\u5929\u6570\u504f\u4f4e\uff0c\u8bf4\u660e\u5927\u91cf\u7528\u6237\u5df2\u8131\u79bb\u7a33\u5b9a\u56de\u6d41\u8282\u594f\u3002")

left, right = st.columns(2)
with left:
    st.markdown("#### \u98ce\u9669\u5206\u5e03\u8868")
    st.dataframe(summary["risk_table"], use_container_width=True, hide_index=True)
    st.markdown("#### \u6d41\u5931\u6839\u56e0\u8868")
    st.dataframe(summary["driver_table"], use_container_width=True, hide_index=True)
with right:
    st.markdown("#### \u5173\u952e\u884c\u4e3a\u5747\u503c\u8868")
    st.dataframe(summary["metric_table"], use_container_width=True, hide_index=True)
    st.markdown("#### \u9ad8\u98ce\u9669\u6837\u672c")
    st.dataframe(
        analysis_df.sort_values(
            by=["churn_probability", "last_active_days", "login_days_7d"],
            ascending=[False, False, True],
        )[["user_id", "churn_probability", "risk_level", "estimated_churn_time", "reason_analysis"]].head(top_n_samples),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("#### \u8fd0\u8425\u5efa\u8bae")
recommendation_cols = st.columns(3)
for idx, risk in enumerate([HIGH, MEDIUM, LOW]):
    with recommendation_cols[idx]:
        st.markdown(f"**{risk}\u7528\u6237**")
        for item in summary["operational_recommendations"].get(risk, []):
            st.write(f"- {item}")

html_report = generate_html(summary, source_name, report_title, top_n_samples)
st.session_state.html_report = html_report

st.markdown("#### HTML \u62a5\u544a\u9884\u89c8")
components.html(html_report, height=760, scrolling=True)

st.download_button(
    "\u4e0b\u8f7d HTML \u62a5\u544a",
    data=html_report,
    file_name=f"{report_title}.html".replace(" ", "_"),
    mime="text/html",
    use_container_width=True,
    on_click="ignore",
)

if st.button("\u5bfc\u51fa\u5230\u8f93\u51fa\u76ee\u5f55", use_container_width=True):
    try:
        output_path = next_report_path(Path(output_dir).expanduser())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_report, encoding="utf-8")
        st.session_state.export_message = f"\u5bfc\u51fa\u6210\u529f\uff1a`{output_path}`"
    except Exception as exc:
        st.session_state.export_message = f"\u5bfc\u51fa\u5931\u8d25\uff1a{exc}"

if st.session_state.export_message:
    if st.session_state.export_message.startswith("\u5bfc\u51fa\u6210\u529f"):
        st.success(st.session_state.export_message)
    else:
        st.error(st.session_state.export_message)
