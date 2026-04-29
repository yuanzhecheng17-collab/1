#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科研文献 / 专利调研 Agent

功能：
1. 输入一个研究主题，例如："GH4169 alloy additive manufacturing thermal simulation"
2. 自动扩展检索关键词
3. 检索论文：OpenAlex + Crossref
4. 检索专利：PatentsView API（偏美国专利数据）
5. 去重、相关性打分、排序
6. 输出：Markdown 综述报告 + CSV 数据表

特点：
- 不依赖 OpenAI API Key，也能运行
- 如配置 OPENAI_API_KEY，可使用 LLM 生成更自然的关键词和综述
- 单文件即可运行，便于你后续改造成 Web 应用或多 Agent 系统

安装：
    pip install requests pandas python-dotenv tqdm

可选安装：
    pip install openai

运行示例：
    python research_patent_survey_agent.py \
        --topic "GH4169 alloy additive manufacturing thermal simulation" \
        --max-papers 30 \
        --max-patents 20 \
        --out ./output

如果要启用 OpenAI 辅助：
    export OPENAI_API_KEY="你的 key"
    python research_patent_survey_agent.py --topic "nickel-based superalloy additive manufacturing" --use-llm
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
import requests
from tqdm import tqdm

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


# =========================
# 基础配置
# =========================

USER_AGENT = "ResearchPatentSurveyAgent/1.0 (mailto:example@example.com)"
REQUEST_TIMEOUT = 20


# =========================
# 数据结构
# =========================

@dataclass
class Paper:
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    abstract: str = ""
    doi: str = ""
    url: str = ""
    source: str = ""
    venue: str = ""
    citation_count: Optional[int] = None
    keywords: List[str] = field(default_factory=list)
    relevance_score: float = 0.0

    def key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower().strip()}"
        return "title:" + normalize_text(self.title)


@dataclass
class Patent:
    title: str
    abstract: str = ""
    patent_number: str = ""
    publication_date: str = ""
    assignees: List[str] = field(default_factory=list)
    inventors: List[str] = field(default_factory=list)
    url: str = ""
    source: str = ""
    relevance_score: float = 0.0

    def key(self) -> str:
        if self.patent_number:
            return f"patent:{self.patent_number.lower().strip()}"
        return "title:" + normalize_text(self.title)


@dataclass
class SurveyResult:
    topic: str
    queries: List[str]
    papers: List[Paper]
    patents: List[Patent]
    generated_at: str


# =========================
# 通用工具函数
# =========================


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text



def safe_get(d: Dict[str, Any], path: Iterable[Any], default=None):
    cur = d
    for p in path:
        try:
            if isinstance(cur, dict):
                cur = cur[p]
            elif isinstance(cur, list) and isinstance(p, int):
                cur = cur[p]
            else:
                return default
        except (KeyError, IndexError, TypeError):
            return default
    return cur



def request_json(url: str, params: Optional[Dict[str, Any]] = None, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        if method.upper() == "GET":
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        else:
            resp = requests.post(url, params=params, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 429:
            time.sleep(2)
            return request_json(url, params=params, method=method, payload=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"[WARN] 请求失败: {url} | {exc}")
        return None



def truncate(text: str, max_len: int = 500) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."



def unique_by_key(items: List[Any]) -> List[Any]:
    seen = set()
    result = []
    for item in items:
        k = item.key()
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


# =========================
# Agent 1：查询规划 Agent
# =========================

class QueryPlannerAgent:
    """将用户主题拆解成多个检索 query。"""

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm and bool(os.getenv("OPENAI_API_KEY"))

    def plan(self, topic: str) -> List[str]:
        if self.use_llm:
            queries = self._plan_with_llm(topic)
            if queries:
                return queries
        return self._plan_rule_based(topic)

    def _plan_rule_based(self, topic: str) -> List[str]:
        base = topic.strip()
        normalized = normalize_text(base)

        # 常见科研/专利扩展词，可按你的专业继续扩充
        expansions = [
            base,
            f"{base} review",
            f"{base} mechanism",
            f"{base} modeling simulation",
            f"{base} process optimization",
            f"{base} patent",
        ]

        # 针对增材制造 / 合金 / 热模拟的简单扩展
        domain_terms = []
        if any(t in normalized for t in ["additive manufacturing", "3d printing", "laser", "增材", "激光"]):
            domain_terms.extend([
                f"{base} laser powder bed fusion",
                f"{base} directed energy deposition",
                f"{base} residual stress thermal history",
            ])
        if any(t in normalized for t in ["gh4169", "in718", "inconel", "nickel", "superalloy", "高温合金"]):
            domain_terms.extend([
                f"{base} nickel-based superalloy",
                f"{base} Inconel 718",
                f"{base} microstructure evolution",
            ])

        queries = expansions + domain_terms
        # 去重并限制数量，避免请求过多
        deduped = []
        for q in queries:
            q = q.strip()
            if q and q.lower() not in {x.lower() for x in deduped}:
                deduped.append(q)
        return deduped[:10]

    def _plan_with_llm(self, topic: str) -> List[str]:
        try:
            from openai import OpenAI

            client = OpenAI()
            prompt = f"""
你是科研检索专家。请根据研究主题生成 8 个英文检索式。
要求：
1. 覆盖论文检索、专利检索、综述、方法、应用、挑战。
2. 每个检索式不超过 12 个英文单词。
3. 只输出 JSON 数组，不要解释。

研究主题：{topic}
""".strip()
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = resp.choices[0].message.content or "[]"
            content = content.strip().strip("`")
            match = re.search(r"\[.*\]", content, flags=re.S)
            if match:
                data = json.loads(match.group(0))
                return [str(x).strip() for x in data if str(x).strip()][:10]
        except Exception as exc:
            print(f"[WARN] LLM 关键词规划失败，改用规则方法: {exc}")
        return []


# =========================
# Agent 2：论文检索 Agent
# =========================

class LiteratureSearchAgent:
    """从 OpenAlex 和 Crossref 检索论文。"""

    def __init__(self, max_results: int = 30):
        self.max_results = max_results

    def search(self, queries: List[str]) -> List[Paper]:
        papers: List[Paper] = []
        per_query = max(3, self.max_results // max(1, len(queries)))
        for q in tqdm(queries, desc="检索论文"):
            papers.extend(self._search_openalex(q, per_page=per_query))
            papers.extend(self._search_crossref(q, rows=per_query))
            time.sleep(0.2)
        papers = unique_by_key(papers)
        return papers[: self.max_results * 2]

    def _search_openalex(self, query: str, per_page: int = 10) -> List[Paper]:
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "per-page": per_page,
            "sort": "cited_by_count:desc",
        }
        data = request_json(url, params=params)
        if not data:
            return []
        results = []
        for item in data.get("results", []):
            title = item.get("title") or ""
            if not title:
                continue
            authorships = item.get("authorships", []) or []
            authors = []
            for a in authorships[:8]:
                name = safe_get(a, ["author", "display_name"], "")
                if name:
                    authors.append(name)
            abstract = self._openalex_abstract(item.get("abstract_inverted_index"))
            doi = item.get("doi") or ""
            if doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")
            venue = safe_get(item, ["primary_location", "source", "display_name"], "") or ""
            url_ = item.get("id") or item.get("doi") or ""
            concepts = [c.get("display_name", "") for c in item.get("concepts", [])[:8] if c.get("display_name")]
            results.append(
                Paper(
                    title=title,
                    authors=authors,
                    year=item.get("publication_year"),
                    abstract=abstract,
                    doi=doi,
                    url=url_,
                    source="OpenAlex",
                    venue=venue,
                    citation_count=item.get("cited_by_count"),
                    keywords=concepts,
                )
            )
        return results

    @staticmethod
    def _openalex_abstract(inv_index: Optional[Dict[str, List[int]]]) -> str:
        if not inv_index:
            return ""
        words = []
        for word, positions in inv_index.items():
            for pos in positions:
                words.append((pos, word))
        words.sort(key=lambda x: x[0])
        return " ".join(w for _, w in words)

    def _search_crossref(self, query: str, rows: int = 10) -> List[Paper]:
        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": rows,
            "sort": "is-referenced-by-count",
            "order": "desc",
        }
        data = request_json(url, params=params)
        if not data:
            return []
        items = safe_get(data, ["message", "items"], []) or []
        results = []
        for item in items:
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            if not title:
                continue
            authors = []
            for a in item.get("author", [])[:8]:
                given = a.get("given", "")
                family = a.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)
            year = None
            parts = safe_get(item, ["published-print", "date-parts"], None) or safe_get(item, ["published-online", "date-parts"], None)
            if parts and parts[0]:
                year = parts[0][0]
            abstract = item.get("abstract") or ""
            venue = ""
            if item.get("container-title"):
                venue = item["container-title"][0]
            results.append(
                Paper(
                    title=title,
                    authors=authors,
                    year=year,
                    abstract=re.sub(r"<[^>]+>", " ", abstract),
                    doi=item.get("DOI", ""),
                    url=item.get("URL", ""),
                    source="Crossref",
                    venue=venue,
                    citation_count=item.get("is-referenced-by-count"),
                )
            )
        return results


# =========================
# Agent 3：专利检索 Agent
# =========================

class PatentSearchAgent:
    """从 PatentsView 检索专利。"""

    def __init__(self, max_results: int = 20):
        self.max_results = max_results

    def search(self, queries: List[str]) -> List[Patent]:
        patents: List[Patent] = []
        per_query = max(3, self.max_results // max(1, len(queries)))
        for q in tqdm(queries, desc="检索专利"):
            patents.extend(self._search_patentsview(q, per_page=per_query))
            time.sleep(0.3)
        patents = unique_by_key(patents)
        return patents[: self.max_results * 2]

    def _search_patentsview(self, query: str, per_page: int = 10) -> List[Patent]:
        """
        PatentsView API 版本可能会调整。如果请求失败，可替换为你单位可用的商业专利库 API。
        当前实现使用 v1 patents/query 风格。
        """
        url = "https://api.patentsview.org/patents/query"
        payload = {
            "q": {
                "_or": [
                    {"_text_any": {"patent_title": query}},
                    {"_text_any": {"patent_abstract": query}},
                ]
            },
            "f": [
                "patent_number",
                "patent_title",
                "patent_abstract",
                "patent_date",
                "assignee_organization",
                "inventor_first_name",
                "inventor_last_name",
            ],
            "o": {"per_page": per_page, "page": 1},
        }
        data = request_json(url, method="POST", payload=payload)
        if not data:
            return []
        items = data.get("patents", []) or []
        results = []
        for item in items:
            title = item.get("patent_title") or ""
            if not title:
                continue
            assignees = []
            for a in item.get("assignees", []) or []:
                org = a.get("assignee_organization")
                if org:
                    assignees.append(org)
            inventors = []
            for inv in item.get("inventors", []) or []:
                name = f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip()
                if name:
                    inventors.append(name)
            number = item.get("patent_number") or ""
            results.append(
                Patent(
                    title=title,
                    abstract=item.get("patent_abstract") or "",
                    patent_number=number,
                    publication_date=item.get("patent_date") or "",
                    assignees=list(dict.fromkeys(assignees)),
                    inventors=list(dict.fromkeys(inventors)),
                    url=f"https://patents.google.com/patent/US{number}" if number else "",
                    source="PatentsView",
                )
            )
        return results


# =========================
# Agent 4：相关性评估 / 排序 Agent
# =========================

class RelevanceRankerAgent:
    """不依赖模型的轻量相关性排序。"""

    def __init__(self, topic: str, queries: List[str]):
        self.topic = topic
        self.queries = queries
        self.topic_terms = self._extract_terms(" ".join([topic] + queries))

    def rank_papers(self, papers: List[Paper]) -> List[Paper]:
        for p in papers:
            text = " ".join([p.title, p.abstract, p.venue, " ".join(p.keywords)])
            score = self._score_text(text)
            if p.citation_count:
                score += min(10.0, p.citation_count / 50.0)
            if p.year:
                current_year = dt.datetime.now().year
                if p.year >= current_year - 5:
                    score += 2.0
            p.relevance_score = round(score, 3)
        return sorted(papers, key=lambda x: x.relevance_score, reverse=True)

    def rank_patents(self, patents: List[Patent]) -> List[Patent]:
        for p in patents:
            text = " ".join([p.title, p.abstract, " ".join(p.assignees), " ".join(p.inventors)])
            score = self._score_text(text)
            if p.publication_date:
                try:
                    year = int(p.publication_date[:4])
                    current_year = dt.datetime.now().year
                    if year >= current_year - 5:
                        score += 2.0
                except Exception:
                    pass
            p.relevance_score = round(score, 3)
        return sorted(patents, key=lambda x: x.relevance_score, reverse=True)

    def _extract_terms(self, text: str) -> List[str]:
        stopwords = {
            "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with", "by", "from",
            "review", "study", "research", "method", "methods", "based", "using", "use",
            "模拟", "研究", "方法", "综述", "基于", "利用", "一种", "及其",
        }
        norm = normalize_text(text)
        tokens = [t for t in norm.split() if len(t) > 2 and t not in stopwords]
        # 保留高频词和原始顺序
        seen = set()
        terms = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                terms.append(t)
        return terms[:40]

    def _score_text(self, text: str) -> float:
        norm = normalize_text(text)
        if not norm:
            return 0.0
        score = 0.0
        for term in self.topic_terms:
            if term in norm:
                score += 1.0
        # 标题命中更重要
        title_part = normalize_text(text[:250])
        for term in self.topic_terms[:20]:
            if term in title_part:
                score += 0.8
        return score


# =========================
# Agent 5：洞察生成 / 报告 Agent
# =========================

class ReportWriterAgent:
    def __init__(self, topic: str, use_llm: bool = False):
        self.topic = topic
        self.use_llm = use_llm and bool(os.getenv("OPENAI_API_KEY"))

    def write(self, result: SurveyResult, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "survey_report.md"

        if self.use_llm:
            report = self._write_with_llm(result)
        else:
            report = self._write_rule_based(result)

        report_path.write_text(report, encoding="utf-8")
        return report_path

    def _write_rule_based(self, result: SurveyResult) -> str:
        top_papers = result.papers[:10]
        top_patents = result.patents[:10]

        years = [p.year for p in result.papers if p.year]
        year_summary = ""
        if years:
            year_summary = f"论文年份范围主要覆盖 {min(years)}–{max(years)}。"

        assignee_counter: Dict[str, int] = {}
        for pat in result.patents:
            for a in pat.assignees:
                assignee_counter[a] = assignee_counter.get(a, 0) + 1
        top_assignees = sorted(assignee_counter.items(), key=lambda x: x[1], reverse=True)[:8]

        keywords = self._collect_keywords(result.papers, result.patents)

        lines = []
        lines.append(f"# 科研文献 / 专利调研报告")
        lines.append("")
        lines.append(f"**主题：** {result.topic}")
        lines.append(f"**生成时间：** {result.generated_at}")
        lines.append("")

        lines.append("## 1. 检索策略")
        lines.append("")
        lines.append("本报告使用多 Agent 流程生成：查询规划 Agent 先扩展关键词，论文检索 Agent 调用 OpenAlex 与 Crossref，专利检索 Agent 调用 PatentsView，排序 Agent 根据主题词命中、引用量、时间新近性等因素综合排序。")
        lines.append("")
        lines.append("检索式：")
        for q in result.queries:
            lines.append(f"- {q}")
        lines.append("")

        lines.append("## 2. 总体发现")
        lines.append("")
        lines.append(f"共检索并去重得到 **{len(result.papers)} 篇论文** 和 **{len(result.patents)} 件专利**。{year_summary}")
        if keywords:
            lines.append(f"高频技术关键词包括：{', '.join(keywords[:15])}。")
        if top_assignees:
            lines.append("主要专利申请人/权利人包括：" + ", ".join([f"{a}（{n}）" for a, n in top_assignees]) + "。")
        lines.append("")

        lines.append("## 3. 重点论文")
        lines.append("")
        for i, p in enumerate(top_papers, 1):
            authors = ", ".join(p.authors[:5])
            if len(p.authors) > 5:
                authors += " et al."
            lines.append(f"### {i}. {p.title}")
            lines.append(f"- 年份：{p.year or 'N/A'}")
            lines.append(f"- 作者：{authors or 'N/A'}")
            lines.append(f"- 来源：{p.venue or p.source or 'N/A'}")
            lines.append(f"- 引用量：{p.citation_count if p.citation_count is not None else 'N/A'}")
            lines.append(f"- 相关性评分：{p.relevance_score}")
            if p.doi:
                lines.append(f"- DOI：{p.doi}")
            if p.url:
                lines.append(f"- 链接：{p.url}")
            if p.abstract:
                lines.append(f"- 摘要：{truncate(p.abstract, 450)}")
            lines.append("")

        lines.append("## 4. 重点专利")
        lines.append("")
        for i, pat in enumerate(top_patents, 1):
            lines.append(f"### {i}. {pat.title}")
            lines.append(f"- 专利号：{pat.patent_number or 'N/A'}")
            lines.append(f"- 公开/授权日期：{pat.publication_date or 'N/A'}")
            lines.append(f"- 权利人：{', '.join(pat.assignees[:5]) or 'N/A'}")
            lines.append(f"- 发明人：{', '.join(pat.inventors[:5]) or 'N/A'}")
            lines.append(f"- 相关性评分：{pat.relevance_score}")
            if pat.url:
                lines.append(f"- 链接：{pat.url}")
            if pat.abstract:
                lines.append(f"- 摘要：{truncate(pat.abstract, 450)}")
            lines.append("")

        lines.append("## 5. 初步技术趋势判断")
        lines.append("")
        lines.append("根据论文与专利标题、摘要和关键词的交叉结果，可以从以下角度继续深入：")
        lines.append("1. **核心方法路线**：关注高频出现的建模、工艺优化、材料组织演化、性能预测等方向。")
        lines.append("2. **工程落地场景**：专利中高频申请人和应用场景可用于判断产业化重点。")
        lines.append("3. **研究空白**：如果论文多而专利少，可能说明技术尚处研究阶段；如果专利多而高被引论文少，可能说明工程应用快于基础机制研究。")
        lines.append("4. **后续建议**：对 Top 10 论文阅读全文，并对 Top 10 专利查看权利要求书，以识别真正的技术保护点。")
        lines.append("")

        lines.append("## 6. 局限性")
        lines.append("")
        lines.append("本脚本默认使用公开免费数据源，可能存在数据库覆盖不足、专利字段缺失、摘要不完整等问题。正式科研立项或专利布局分析建议结合 Web of Science、Scopus、Derwent、Lens、智慧芽、Incopat 或企业内部专利库进行复核。")
        lines.append("")

        return "\n".join(lines)

    def _write_with_llm(self, result: SurveyResult) -> str:
        try:
            from openai import OpenAI

            client = OpenAI()
            compact = {
                "topic": result.topic,
                "queries": result.queries,
                "top_papers": [dataclasses.asdict(p) for p in result.papers[:15]],
                "top_patents": [dataclasses.asdict(p) for p in result.patents[:15]],
            }
            prompt = f"""
请基于以下论文和专利检索结果，写一份中文科研/专利调研报告。
报告结构：
1. 检索策略
2. 总体发现
3. 重点论文解读
4. 重点专利解读
5. 技术趋势
6. 潜在研究空白
7. 后续建议
要求：
- 不要编造没有给出的数据。
- 每篇论文和专利都要尽量保留标题、年份/日期、链接或 DOI。
- 输出 Markdown。

数据：
{json.dumps(compact, ensure_ascii=False, indent=2)}
""".strip()
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return resp.choices[0].message.content or self._write_rule_based(result)
        except Exception as exc:
            print(f"[WARN] LLM 报告生成失败，改用规则报告: {exc}")
            return self._write_rule_based(result)

    def _collect_keywords(self, papers: List[Paper], patents: List[Patent]) -> List[str]:
        freq: Dict[str, int] = {}
        stop = {"the", "and", "for", "with", "from", "method", "system", "apparatus", "using", "based"}
        text = " ".join(
            [p.title + " " + " ".join(p.keywords) for p in papers]
            + [p.title for p in patents]
        )
        for token in normalize_text(text).split():
            if len(token) < 4 or token in stop:
                continue
            freq[token] = freq.get(token, 0) + 1
        return [k for k, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)]


# =========================
# Agent 6：导出 Agent
# =========================

class ExportAgent:
    def export(self, result: SurveyResult, out_dir: Path) -> Tuple[Path, Path, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        papers_csv = out_dir / "papers.csv"
        patents_csv = out_dir / "patents.csv"
        raw_json = out_dir / "raw_result.json"

        pd.DataFrame([dataclasses.asdict(p) for p in result.papers]).to_csv(papers_csv, index=False, encoding="utf-8-sig")
        pd.DataFrame([dataclasses.asdict(p) for p in result.patents]).to_csv(patents_csv, index=False, encoding="utf-8-sig")

        raw_json.write_text(
            json.dumps(
                {
                    "topic": result.topic,
                    "queries": result.queries,
                    "generated_at": result.generated_at,
                    "papers": [dataclasses.asdict(p) for p in result.papers],
                    "patents": [dataclasses.asdict(p) for p in result.patents],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return papers_csv, patents_csv, raw_json


# =========================
# 总控：多 Agent 编排器
# =========================

class ResearchPatentSurveyOrchestrator:
    def __init__(self, topic: str, max_papers: int, max_patents: int, out_dir: str, use_llm: bool = False):
        self.topic = topic
        self.max_papers = max_papers
        self.max_patents = max_patents
        self.out_dir = Path(out_dir)
        self.use_llm = use_llm

        self.query_agent = QueryPlannerAgent(use_llm=use_llm)
        self.literature_agent = LiteratureSearchAgent(max_results=max_papers)
        self.patent_agent = PatentSearchAgent(max_results=max_patents)
        self.export_agent = ExportAgent()

    def run(self) -> SurveyResult:
        print(f"\n[1/6] 研究主题：{self.topic}")

        print("[2/6] 生成检索式...")
        queries = self.query_agent.plan(self.topic)
        for q in queries:
            print(f"  - {q}")

        print("[3/6] 检索论文...")
        papers = self.literature_agent.search(queries)
        print(f"  论文候选数：{len(papers)}")

        print("[4/6] 检索专利...")
        patents = self.patent_agent.search(queries)
        print(f"  专利候选数：{len(patents)}")

        print("[5/6] 相关性排序...")
        ranker = RelevanceRankerAgent(self.topic, queries)
        papers = ranker.rank_papers(papers)[: self.max_papers]
        patents = ranker.rank_patents(patents)[: self.max_patents]

        result = SurveyResult(
            topic=self.topic,
            queries=queries,
            papers=papers,
            patents=patents,
            generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        print("[6/6] 导出结果...")
        papers_csv, patents_csv, raw_json = self.export_agent.export(result, self.out_dir)
        report_writer = ReportWriterAgent(self.topic, use_llm=self.use_llm)
        report_path = report_writer.write(result, self.out_dir)

        print("\n完成！输出文件：")
        print(f"  - {report_path}")
        print(f"  - {papers_csv}")
        print(f"  - {patents_csv}")
        print(f"  - {raw_json}")

        return result


# =========================
# CLI 入口
# =========================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="科研文献 / 专利调研 Agent")
    parser.add_argument("--topic", required=True, help="研究主题，例如：GH4169 alloy additive manufacturing thermal simulation")
    parser.add_argument("--max-papers", type=int, default=30, help="最多输出论文数量")
    parser.add_argument("--max-patents", type=int, default=20, help="最多输出专利数量")
    parser.add_argument("--out", default="./survey_output", help="输出目录")
    parser.add_argument("--use-llm", action="store_true", help="启用 OpenAI 辅助生成关键词和报告，需要 OPENAI_API_KEY")
    return parser.parse_args()



def main():
    if load_dotenv:
        load_dotenv()

    args = parse_args()
    orchestrator = ResearchPatentSurveyOrchestrator(
        topic=args.topic,
        max_papers=args.max_papers,
        max_patents=args.max_patents,
        out_dir=args.out,
        use_llm=args.use_llm,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
