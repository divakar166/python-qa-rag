import os
from datetime import datetime

import requests
from tqdm import tqdm

API_URL = "http://localhost:8000/ask"
REPORT_PATH = "evaluation/evaluation_results.md"

NORMAL_QUERIES = [
    "How do I sort a list in Python?",
    "What is the difference between a list and a tuple?",
    "How do I read a CSV file in Python?",
    "How do I handle exceptions in Python?",
    "What is a decorator in Python?",
    "How do I use list comprehensions?",
    "What is the difference between deep copy and shallow copy?",
    "How do I work with JSON in Python?",
    "How do I use virtual environments in Python?",
]

EDGE_CASE_QUERIES = [
    "!!@@@$$$%%%",
    "",
    "a",
]


def sanitize_md(text, max_len=120):
    if not text:
        return "-"
    text = str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    if max_len and len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def evaluate_queries(queries, tag):
    results = []
    for q in tqdm(queries, desc=tag, unit="q"):
        row = {"question": q, "tag": tag, "status": None, "answer": "", "sources": [], "observation": ""}
        try:
            resp = requests.post(API_URL, json={"question": q}, timeout=60)
            row["status"] = resp.status_code
            if resp.status_code == 200:
                data = resp.json()
                row["answer"] = data.get("answer", "")
                row["sources"] = [s.get("title", "") for s in data.get("sources", [])]
            else:
                detail = resp.json().get("detail", "")
                row["answer"] = detail
                row["observation"] = "Non-200 response"
        except requests.exceptions.ConnectionError as e:
            row["status"] = 0
            row["answer"] = f"Connection refused: {e}"
            row["observation"] = "API not reachable"
        except Exception as e:
            row["status"] = 0
            row["answer"] = str(e)
            row["observation"] = "Exception during request"
        results.append(row)
    return results


def write_report(normal_results, edge_results):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)

    all_results = normal_results + edge_results
    successful = sum(1 for r in all_results if r["status"] == 200)
    failed = sum(1 for r in all_results if r["status"] != 200)
    total = len(all_results)

    with open(REPORT_PATH, "w") as f:
        f.write("# Evaluation Results\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**API Endpoint:** `{API_URL}`\n\n")
        f.write("---\n\n")

        for label, results in [("Normal Queries", normal_results), ("Edge Cases", edge_results)]:
            f.write(f"## {label}\n\n")
            f.write("| # | Query | Status | Answer | Sources | Observation |\n")
            f.write("|---|-------|--------|--------|---------|-------------|\n")
            for i, r in enumerate(results, 1):
                f.write(
                    f"| {i} "
                    f"| {sanitize_md(r['question'])} "
                    f"| {r['status']} "
                    f"| {sanitize_md(r['answer'])} "
                    f"| {sanitize_md('; '.join(r['sources'][:3]), max_len=80) or '-'} "
                    f"| {sanitize_md(r['observation'])} |\n"
                )
            f.write("\n")

        f.write("---\n\n")
        f.write("## Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total Queries | {total} |\n")
        f.write(f"| Successful (200) | {successful} |\n")
        f.write(f"| Failed | {failed} |\n")
        f.write(f"| Normal Queries | {len(normal_results)} |\n")
        f.write(f"| Edge Cases | {len(edge_results)} |\n")

    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    print(f"Evaluating {len(NORMAL_QUERIES)} normal queries and {len(EDGE_CASE_QUERIES)} edge cases...")
    print(f"Target: {API_URL}\n")

    normal_results = evaluate_queries(NORMAL_QUERIES, "Normal")
    edge_results = evaluate_queries(EDGE_CASE_QUERIES, "Edge Case")

    write_report(normal_results, edge_results)

    success = sum(1 for r in normal_results + edge_results if r["status"] == 200)
    total = len(normal_results) + len(edge_results)
    print(f"Done. {success}/{total} queries succeeded.")
