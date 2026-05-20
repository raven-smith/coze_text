import os
import re
import math
from collections import Counter
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


PLUGIN_API_KEY = os.getenv("PLUGIN_API_KEY", "").strip()

app = FastAPI(
    title="Coze Text Toolbox Plugin",
    description="A simple local text-processing toolbox plugin for Coze. No external API key is required.",
    version="1.0.0",
)


def verify_api_key(x_api_key: Optional[str]) -> None:
    """Optional API key verification. If PLUGIN_API_KEY is empty, auth is disabled."""
    if PLUGIN_API_KEY and x_api_key != PLUGIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


class TextInput(BaseModel):
    text: str = Field(..., description="The text to process.", min_length=1)


class CleanTextInput(BaseModel):
    text: str = Field(..., description="The text to clean.", min_length=1)
    normalize_spaces: bool = Field(True, description="Collapse repeated spaces and tabs.")
    normalize_newlines: bool = Field(True, description="Collapse repeated blank lines.")
    remove_urls: bool = Field(False, description="Remove URLs from the text.")
    remove_emails: bool = Field(False, description="Remove email addresses from the text.")


class KeywordInput(BaseModel):
    text: str = Field(..., description="The text to analyze.", min_length=1)
    top_k: int = Field(10, description="Maximum number of keywords to return.", ge=1, le=50)
    min_length: int = Field(2, description="Minimum token length.", ge=1, le=10)


class AcademicCheckInput(BaseModel):
    text: str = Field(..., description="Chinese academic text to check.", min_length=1)


CHINESE_STOPWORDS = {
    "一个", "一种", "一些", "以及", "因此", "由于", "其中", "通过", "进行", "对于", "基于", "本文", "研究",
    "可以", "能够", "具有", "相关", "影响", "作用", "机制", "分析", "结果", "表明", "发现", "进一步",
    "同时", "然而", "此外", "并且", "还是", "这个", "这些", "那种", "这种", "主要", "不同", "整体", "方面",
    "问题", "过程", "内容", "方法", "模型", "数据", "变量", "指标", "水平", "程度", "可能", "需要",
}

ENGLISH_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "are", "was", "were", "has", "have", "had", "but",
    "not", "can", "may", "its", "their", "into", "over", "under", "between", "among", "such", "more", "than",
    "then", "also", "there", "these", "those", "using", "used", "based", "study", "research", "analysis",
}

ORAL_EXPRESSIONS = [
    "我觉得", "我认为", "其实", "就是说", "然后", "这个", "那个", "挺", "蛮", "比较来说", "大概", "差不多", "有点", "很明显",
    "总的来说", "简单来说", "说白了", "大家都知道", "我们可以看到",
]

WEAK_EXPRESSIONS = [
    "可能", "也许", "大概", "或许", "似乎", "一定程度上", "某种程度上", "较为", "比较", "相对", "基本上",
]

REPEATED_CONNECTORS = [
    "因此", "同时", "此外", "然而", "并且", "进一步", "由此", "因此", "其次", "最后", "然后", "另外", "综上",
]


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_english_words(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z]+(?:[-'][A-Za-z]+)?\b", text))


def split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", text.strip()) if p.strip()]


def split_sentences(text: str) -> List[str]:
    # Simple Chinese/English sentence splitter.
    parts = re.split(r"(?<=[。！？!?；;\.])\s*", text.strip())
    return [s.strip() for s in parts if s.strip()]


def simple_clean(text: str, normalize_spaces: bool, normalize_newlines: bool, remove_urls: bool, remove_emails: bool) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    if remove_urls:
        cleaned = re.sub(r"https?://\S+|www\.\S+", "", cleaned)
    if remove_emails:
        cleaned = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "", cleaned)
    if normalize_spaces:
        cleaned = re.sub(r"[\t\u3000]+", " ", cleaned)
        cleaned = re.sub(r" {2,}", " ", cleaned)
        cleaned = re.sub(r" *\n *", "\n", cleaned)
    if normalize_newlines:
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_tokens(text: str, min_length: int) -> List[str]:
    # English tokens.
    english = [w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]*\b", text)]
    english = [w for w in english if len(w) >= min_length and w not in ENGLISH_STOPWORDS]

    # Continuous Chinese chunks.
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", text)
    chinese_tokens: List[str] = []
    for chunk in chinese_chunks:
        # Add 2-4 char n-grams. This is a lightweight fallback, not full Chinese word segmentation.
        max_n = min(4, len(chunk))
        for n in range(max(min_length, 2), max_n + 1):
            for i in range(0, len(chunk) - n + 1):
                token = chunk[i:i+n]
                if token not in CHINESE_STOPWORDS:
                    chinese_tokens.append(token)
    return english + chinese_tokens


def find_terms(text: str, terms: List[str]) -> Dict[str, int]:
    return {term: text.count(term) for term in terms if text.count(term) > 0}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/text_count")
def text_count(payload: TextInput, x_api_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    verify_api_key(x_api_key)
    text = payload.text
    paragraphs = split_paragraphs(text)
    sentences = split_sentences(text)
    chinese_chars = count_chinese_chars(text)
    english_words = count_english_words(text)
    total_chars = len(text)
    chars_no_spaces = len(re.sub(r"\s", "", text))
    return {
        "total_characters": total_chars,
        "characters_without_spaces": chars_no_spaces,
        "chinese_characters": chinese_chars,
        "english_words": english_words,
        "estimated_word_count": chinese_chars + english_words,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "average_sentence_length": round((chinese_chars + english_words) / max(len(sentences), 1), 2),
    }


@app.post("/clean_text")
def clean_text(payload: CleanTextInput, x_api_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    verify_api_key(x_api_key)
    cleaned = simple_clean(
        payload.text,
        normalize_spaces=payload.normalize_spaces,
        normalize_newlines=payload.normalize_newlines,
        remove_urls=payload.remove_urls,
        remove_emails=payload.remove_emails,
    )
    return {
        "cleaned_text": cleaned,
        "original_length": len(payload.text),
        "cleaned_length": len(cleaned),
        "removed_characters": len(payload.text) - len(cleaned),
    }


@app.post("/extract_keywords_simple")
def extract_keywords_simple(payload: KeywordInput, x_api_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    verify_api_key(x_api_key)
    tokens = extract_tokens(payload.text, payload.min_length)
    counts = Counter(tokens)
    keywords = [
        {"keyword": token, "frequency": freq}
        for token, freq in counts.most_common(payload.top_k)
    ]
    return {
        "keywords": keywords,
        "method_note": "Lightweight frequency-based extraction. Chinese tokens use 2-4 character n-grams, so results are best used as rough cues rather than formal segmentation.",
    }


@app.post("/academic_check")
def academic_check(payload: AcademicCheckInput, x_api_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    verify_api_key(x_api_key)
    text = payload.text
    sentences = split_sentences(text)
    oral_hits = find_terms(text, ORAL_EXPRESSIONS)
    weak_hits = find_terms(text, WEAK_EXPRESSIONS)
    connector_hits = find_terms(text, REPEATED_CONNECTORS)

    long_sentences = [s for s in sentences if count_chinese_chars(s) + count_english_words(s) > 80]
    very_short_paragraphs = [p for p in split_paragraphs(text) if count_chinese_chars(p) + count_english_words(p) < 30]

    suggestions: List[str] = []
    if oral_hits:
        suggestions.append("存在偏口语化表达，建议替换为更正式、客观的学术表述。")
    if weak_hits:
        suggestions.append("存在较多弱化表达，建议检查是否需要更明确的因果、机制或边界条件说明。")
    if long_sentences:
        suggestions.append("存在过长句，建议拆分为两到三句，提高论文表达的清晰度。")
    if very_short_paragraphs:
        suggestions.append("存在较短段落，建议检查是否需要合并或补充论证。")
    if connector_hits and max(connector_hits.values()) >= 3:
        suggestions.append("部分连接词重复较多，建议替换为更具体的逻辑衔接方式。")
    if not suggestions:
        suggestions.append("未发现明显的口语化、冗长句或连接词重复问题。")

    return {
        "sentence_count": len(sentences),
        "paragraph_count": len(split_paragraphs(text)),
        "oral_expression_hits": oral_hits,
        "weak_expression_hits": weak_hits,
        "connector_hits": connector_hits,
        "long_sentence_count": len(long_sentences),
        "very_short_paragraph_count": len(very_short_paragraphs),
        "suggestions": suggestions,
    }


@app.post("/formula_template")
def formula_template(payload: TextInput, x_api_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    verify_api_key(x_api_key)
    text = payload.text.strip()
    # Rule-based template for academic formula explanation. It does not infer math reliably; it structures user-provided content.
    return {
        "template": (
            "指标定义：" + text + "\n"
            "建议写法：设 i 表示企业，p 表示省份，t 表示年份。若该指标需要由企业层面汇总至省份—年份层面，"
            "可先对省份 p 在年份 t 内的相关企业观测值进行求和或加权平均，再根据研究设计进行标准化处理。\n"
            "注意：请根据你的真实变量含义补充分子、分母、权重和样本范围，避免公式与数据口径不一致。"
        )
    }
