import re
from pathlib import Path


# 课程资料文件固定放在当前项目目录下。
COURSE_FILE = Path(__file__).with_name("course.txt")

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
    "吗",
    "是",
}


def load_course_text():
    """读取课程资料文本。"""
    return COURSE_FILE.read_text(encoding="utf-8")


def split_segments(text):
    """按句号、问号、感叹号和换行切分资料片段。"""
    raw_segments = re.split(r"[。！？?!\r\n]+", text)
    return [segment.strip() for segment in raw_segments if segment.strip()]


def extract_keywords(question):
    """从问题中提取英文、数字、中文关键词。

    英文和数字按连续单词提取；中文没有分词库，所以使用 2 到 4 个字的
    连续片段做简单关键词匹配，并过滤常见泛化词。
    """
    keywords = set()

    # 提取英文和数字组成的连续词，例如 RAG、Python3。
    for word in re.findall(r"[A-Za-z0-9]+", question):
        keywords.add(word.lower())

    # 提取中文连续文本，再切成短片段。
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", question)
    for chunk in chinese_chunks:
        for size in range(2, 5):
            for start in range(0, len(chunk) - size + 1):
                keyword = chunk[start : start + size]
                if keyword not in STOP_WORDS:
                    keywords.add(keyword)

    return keywords


def score_segments(question, segments):
    """统计每个资料片段命中的关键词数量，并按命中数量排序。"""
    keywords = extract_keywords(question)
    scored = []

    for segment in segments:
        segment_lower = segment.lower()
        hit_keywords = [keyword for keyword in keywords if keyword in segment_lower]
        if hit_keywords:
            scored.append(
                {
                    "segment": segment,
                    "score": len(hit_keywords),
                    "hits": sorted(hit_keywords),
                }
            )

    return sorted(scored, key=lambda item: item["score"], reverse=True)


def answer_question(question, segments):
    """根据命中的资料片段生成模板化回答。"""
    results = score_segments(question, segments)

    if not results:
        print("资料不足，不能根据当前资料回答，避免胡说。")
        return

    top_results = results[:3]
    evidence_segments = [item["segment"] for item in top_results]

    print("命中的资料片段：")
    for index, item in enumerate(top_results, start=1):
        hits = "、".join(item["hits"])
        print(f"{index}. {item['segment']}（命中关键词：{hits}）")

    evidence_text = "；".join(evidence_segments)
    print()
    print(f"基于资料的简短回答：根据资料，{evidence_segments[0]}。相关依据包括：{evidence_text}。")


def main():
    """程序入口：加载资料，然后循环接收用户问题。"""
    course_text = load_course_text()
    segments = split_segments(course_text)

    print("课程资料防胡说问答助手")
    print("请输入问题；直接回车或输入 q 退出。")

    while True:
        question = input("\n问题：").strip()
        if not question or question.lower() == "q":
            print("已退出。")
            break

        answer_question(question, segments)


if __name__ == "__main__":
    main()
