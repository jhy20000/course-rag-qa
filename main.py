import re
from pathlib import Path


# 项目根目录、资料目录、旧版 course.txt 路径和问答历史路径。
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
COURSE_FILE = PROJECT_DIR / "course.txt"
HISTORY_FILE = PROJECT_DIR / "history.txt"
SUPPORTED_SUFFIXES = {".txt", ".md"}

# 停用词经常出现在问题里，但通常不能代表真正的检索主题。
STOP_WORDS = {
    "什么",
    "为什么",
    "怎么",
    "如何",
    "这个",
    "那个",
    "一个",
    "一下",
    "请问",
    "可以",
    "能不能",
    "不能",
    "能",
    "不",
    "的是",
    "了吗",
    "吗",
    "呢",
    "啊",
    "了",
    "的",
    "是",
    "在",
    "和",
    "与",
    "或",
}
KEEP_ENGLISH_KEYWORDS = {"rag", "ai", "pdf", "python"}


def split_segments(text):
    """按句号、问号、感叹号和换行切分资料片段。"""
    raw_segments = re.split(r"[。！？?!\r\n]+", text)
    return [segment.strip() for segment in raw_segments if segment.strip()]


def load_documents():
    """读取资料文件。

    v4.0 优先读取 data 文件夹下的所有 .txt 和 .md 文件；如果 data 中没有资料，
    再回退读取旧版 course.txt，保留第一版功能。
    """
    documents = []

    if DATA_DIR.exists():
        data_files = [
            file_path
            for file_path in DATA_DIR.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_SUFFIXES
        ]
        for file_path in sorted(data_files):
            text = file_path.read_text(encoding="utf-8")
            documents.append({"source": file_path.name, "text": text})

    if not documents and COURSE_FILE.exists():
        text = COURSE_FILE.read_text(encoding="utf-8")
        documents.append({"source": COURSE_FILE.name, "text": text})

    return documents


def build_segments(documents):
    """把多个资料文件切分成片段，并记录每个片段的来源文件。"""
    segments = []

    for document in documents:
        for segment in split_segments(document["text"]):
            segments.append(
                {
                    "source": document["source"],
                    "content": segment,
                }
            )

    return segments


def extract_keywords(question):
    """从问题中提取英文、数字和中文关键词。

    英文和数字按连续词提取；中文没有第三方分词库，所以用连续字符和
    2 到 6 字短语片段做简单检索，并过滤停用词和无意义短词。
    """
    keywords = set()

    # 保留 RAG、AI、PDF、Python 这类英文关键词。
    for word in re.findall(r"[A-Za-z0-9]+", question):
        normalized = word.lower()
        if len(normalized) >= 2 or normalized in KEEP_ENGLISH_KEYWORDS:
            keywords.add(normalized)

    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", question)
    for chunk in chinese_chunks:
        cleaned_chunk = chunk
        for stop_word in STOP_WORDS:
            cleaned_chunk = cleaned_chunk.replace(stop_word, "")

        if len(cleaned_chunk) >= 2 and cleaned_chunk not in STOP_WORDS:
            keywords.add(cleaned_chunk)

        for size in range(2, 7):
            for start in range(0, len(cleaned_chunk) - size + 1):
                keyword = cleaned_chunk[start : start + size]
                if len(keyword) >= 2 and keyword not in STOP_WORDS:
                    keywords.add(keyword)

    return keywords


def score_segments(question, segments):
    """计算每个资料片段的匹配分数，并按分数从高到低排序。

    分数由三部分组成：命中关键词数量、关键词在片段中的出现次数、
    关键词在来源文件名中的命中加分。
    """
    keywords = extract_keywords(question)
    scored = []

    for segment in segments:
        content_lower = segment["content"].lower()
        source_lower = segment["source"].lower()
        hit_keywords = []
        occurrence_count = 0
        filename_bonus = 0

        for keyword in keywords:
            content_hits = content_lower.count(keyword)
            source_hits = source_lower.count(keyword)
            if content_hits or source_hits:
                hit_keywords.append(keyword)
                occurrence_count += content_hits
                filename_bonus += source_hits

        if hit_keywords:
            score = len(hit_keywords) * 2 + occurrence_count + filename_bonus
            scored.append(
                {
                    "source": segment["source"],
                    "content": segment["content"],
                    "score": score,
                    "hits": sorted(hit_keywords),
                }
            )

    return sorted(scored, key=lambda item: item["score"], reverse=True)


def save_history(question, top_results, answer):
    """把每次问答记录追加保存到 history.txt。"""
    if top_results:
        sources = "、".join(sorted({item["source"] for item in top_results}))
        hit_keywords = "、".join(sorted({keyword for item in top_results for keyword in item["hits"]}))
        scores = "、".join(f"{item['source']}={item['score']}" for item in top_results)
        has_match = "是"
    else:
        sources = "无命中资料"
        hit_keywords = "无"
        scores = "无"
        has_match = "否"

    lines = [
        f"用户问题：{question}",
        f"是否命中资料：{has_match}",
        f"命中来源文件：{sources}",
        f"命中关键词：{hit_keywords}",
        f"匹配分数：{scores}",
        f"最终回答：{answer}",
        "----------------------------------------",
        "",
    ]
    with HISTORY_FILE.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines))


def print_no_match_suggestions():
    """资料不足时输出改问建议。"""
    print("你可以尝试：")
    print("- 换一个更具体的问题")
    print("- 把相关资料放进 data 文件夹")
    print("- 检查资料文件是否包含这个知识点")


def answer_question(question, segments):
    """根据命中的资料片段生成模板化回答，并保存问答记录。"""
    results = score_segments(question, segments)

    if not results:
        answer = "资料不足，不能根据当前资料回答，避免胡说。"
        print(answer)
        print()
        print_no_match_suggestions()
        save_history(question, [], answer)
        return

    top_results = results[:3]
    source_text = "、".join(sorted({item["source"] for item in top_results}))
    answer = (
        f"根据已检索到的资料，当前问题可以这样理解：{top_results[0]['content']}。"
        f"依据主要来自：{source_text} 文件。"
    )

    print("命中的资料片段：")
    for index, item in enumerate(top_results, start=1):
        hits = "、".join(item["hits"])
        print(f"{index}. 排名：{index}")
        print(f"   来源文件：{item['source']}")
        print(f"   匹配分数：{item['score']}")
        print(f"   命中关键词：{hits}")
        print(f"   资料片段内容：{item['content']}")

    print()
    print(answer)
    save_history(question, top_results, answer)


def main():
    """程序入口：加载资料，然后循环接收用户问题。"""
    documents = load_documents()
    segments = build_segments(documents)

    print("课程资料防胡说问答助手 v4.0")
    print(f"已加载资料文件数量：{len(documents)}")
    print(f"已切分资料片段数量：{len(segments)}")
    print("请输入问题；直接回车或输入 q 退出。")

    if not segments:
        print("未找到可用资料，请在 data 文件夹中放入 .txt 或 .md 文件。")
        return

    while True:
        question = input("\n问题：").strip()
        if not question or question.lower() == "q":
            print("已退出。")
            break

        answer_question(question, segments)


if __name__ == "__main__":
    main()
