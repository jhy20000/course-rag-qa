import re
from pathlib import Path


# 项目根目录、资料目录和旧版 course.txt 路径。
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
COURSE_FILE = PROJECT_DIR / "course.txt"
HISTORY_FILE = PROJECT_DIR / "history.txt"
SUPPORTED_SUFFIXES = {".txt", ".md"}

# 这些词经常出现在问题里，但不能代表真正的课程主题。
STOP_WORDS = {
    "什么",
    "怎么",
    "这个",
    "那个",
    "一个",
    "一种",
    "哪些",
    "是否",
    "可以",
    "应该",
    "的是",
    "为什么",
    "原因",
    "吗",
    "是",
}


def split_segments(text):
    """按句号、问号、感叹号和换行切分资料片段。"""
    raw_segments = re.split(r"[。！？?!\r\n]+", text)
    return [segment.strip() for segment in raw_segments if segment.strip()]


def load_documents():
    """读取资料文件。

    v3.0 优先读取 data 文件夹下的所有 .txt 和 .md 文件；如果 data 中没有资料，
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

    英文和数字按连续单词提取；中文没有第三方分词库，所以使用 2 到 6 个字
    的连续片段做简单关键词匹配，并过滤常见泛化词。
    """
    keywords = set()

    # 先去掉常见疑问词，避免把“为什么会”“这个”等泛化表达当成关键词。
    cleaned_question = re.sub(r"为什么|什么|怎么|这个|那个|是否|哪些|请问|会|吗|呢", "", question)

    # 提取英文和数字组成的连续词，例如 RAG、AI、Python3。
    for word in re.findall(r"[A-Za-z0-9]+", cleaned_question):
        keywords.add(word.lower())

    # 提取中文连续文本，再切成短片段。
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", cleaned_question)
    for chunk in chinese_chunks:
        for size in range(2, 7):
            for start in range(0, len(chunk) - size + 1):
                keyword = chunk[start : start + size]
                if keyword not in STOP_WORDS:
                    keywords.add(keyword)

    return keywords


def score_segments(question, segments):
    """统计每个资料片段命中的关键词数量，并按命中数量从高到低排序。"""
    keywords = extract_keywords(question)
    scored = []

    for segment in segments:
        content_lower = segment["content"].lower()
        hit_keywords = [keyword for keyword in keywords if keyword in content_lower]
        if hit_keywords:
            scored.append(
                {
                    "source": segment["source"],
                    "content": segment["content"],
                    "score": len(hit_keywords),
                    "hits": sorted(hit_keywords),
                }
            )

    return sorted(scored, key=lambda item: item["score"], reverse=True)


def save_history(question, top_results, answer):
    """把每次问答记录追加保存到 history.txt。"""
    if top_results:
        sources = "、".join(sorted({item["source"] for item in top_results}))
    else:
        sources = "无命中资料"

    lines = [
        "----------------------------------------",
        f"问题：{question}",
        f"命中的资料来源：{sources}",
        f"回答结果：{answer}",
        "",
    ]
    HISTORY_FILE.write_text("", encoding="utf-8") if not HISTORY_FILE.exists() else None
    with HISTORY_FILE.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines))


def answer_question(question, segments):
    """根据命中的资料片段生成模板化回答，并保存问答记录。"""
    results = score_segments(question, segments)

    if not results:
        answer = "资料不足，不能根据当前资料回答，避免胡说。"
        print(answer)
        save_history(question, [], answer)
        return

    top_results = results[:3]
    evidence_text = "；".join(item["content"] for item in top_results)
    answer = f"根据资料，{top_results[0]['content']}。相关依据包括：{evidence_text}。"

    print("命中的资料片段：")
    for index, item in enumerate(top_results, start=1):
        hits = "、".join(item["hits"])
        print(f"{index}. 来源文件：{item['source']}")
        print(f"   命中关键词：{hits}")
        print(f"   资料内容：{item['content']}")

    print()
    print(f"基于资料的简短回答：{answer}")
    save_history(question, top_results, answer)


def main():
    """程序入口：加载资料，然后循环接收用户问题。"""
    documents = load_documents()
    segments = build_segments(documents)

    print("课程资料防胡说问答助手 v3.0")
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
