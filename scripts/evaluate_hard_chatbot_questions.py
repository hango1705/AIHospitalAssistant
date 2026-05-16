from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hospital_assistant.assistant import HospitalAssistant, _normalize_match


FALLBACK_TEXT = "Tôi chưa tìm thấy thông tin phù hợp trong cơ sở tri thức hiện có."


@dataclass(frozen=True)
class EvalQuestion:
    category: str
    question: str
    expected_terms: tuple[str, ...] = ()


QUESTIONS: list[EvalQuestion] = [
    # Short hospital-profile queries.
    EvalQuestion("hospital_profile_short", "Địa chỉ bệnh viện", ("quang trung",)),
    EvalQuestion("hospital_profile_short", "Số điện thoại liên hệ", ("0280", "0208")),
    EvalQuestion("hospital_profile_short", "Email bệnh viện", ("gmail",)),
    EvalQuestion("hospital_profile_short", "Bệnh viện nằm ở phường nào?", ("thinh dan",)),
    EvalQuestion("hospital_profile_short", "Thông tin liên hệ bệnh viện A", ("dien thoai", "email")),

    # Process pages.
    EvalQuestion("process", "Quy trình khám bệnh gồm những bước nào?", ("buoc",)),
    EvalQuestion("process", "Khám sức khỏe làm theo quy trình nào?", ("kham suc khoe",)),
    EvalQuestion("process", "Quy trình khám nội trú tại bệnh viện ra sao?", ("noi tru",)),
    EvalQuestion("process", "Người bệnh trước khi khám cần làm thủ tục gì?", ("kham",)),

    # Department and unit queries, including less common units.
    EvalQuestion("department", "Khoa Giải phẫu bệnh làm nhiệm vụ gì?", ("giai phau benh",)),
    EvalQuestion("department", "Khoa Kiểm soát nhiễm khuẩn có thông tin gì?", ("kiem soat nhiem khuan",)),
    EvalQuestion("department", "Phòng Vật tư TBYT phụ trách gì?", ("vat tu",)),
    EvalQuestion("department", "Phòng Quản lý chất lượng bệnh viện có thông tin liên hệ không?", ("quan ly chat luong",)),
    EvalQuestion("department", "Đơn nguyên nội soi ở bệnh viện có thông tin gì?", ("noi soi",)),
    EvalQuestion("department", "Trung tâm sàng lọc chẩn đoán trước sinh và sơ sinh", ("sang loc",)),
    EvalQuestion("department", "Khoa Hỗ trợ sinh sản có chức năng gì?", ("ho tro sinh san",)),
    EvalQuestion("department", "Khoa Huyết học truyền máu", ("huyet hoc",)),
    EvalQuestion("department", "Khoa Sinh hóa vi sinh", ("sinh hoa", "vi sinh")),
    EvalQuestion("department", "Khoa Dinh dưỡng", ("dinh duong",)),
    EvalQuestion("department", "Phòng Công tác xã hội", ("cong tac xa hoi",)),

    # Follow-up-like but standalone terse queries that should still be grounded.
    EvalQuestion("terse_domain", "Khoa Nhi", ("khoa nhi",)),
    EvalQuestion("terse_domain", "Khoa Phụ", ("khoa phu",)),
    EvalQuestion("terse_domain", "Răng hàm mặt", ("rang ham mat",)),
    EvalQuestion("terse_domain", "Da liễu", ("da lieu",)),
    EvalQuestion("terse_domain", "Mắt", ("khoa mat",)),

    # Service/vaccine pages.
    EvalQuestion("service", "Dịch vụ tiêm chủng có những thông tin gì?", ("tiem",)),
    EvalQuestion("service", "Đặt tiêm vaccine ở đâu?", ("tiem",)),
    EvalQuestion("service", "Điều trị theo yêu cầu là gì?", ("yeu cau",)),
    EvalQuestion("service", "Có thông tin về Gardasil không?", ("gardasil",)),
    EvalQuestion("service", "Rotarix có trong cơ sở tri thức không?", ("rotarix",)),
    EvalQuestion("service", "Vaxigrip tetra là vaccine gì?", ("vaxigrip",)),

    # Pricing, including specific and less-common services.
    EvalQuestion("pricing", "Giá khám bệnh", ("50.600",)),
    EvalQuestion("pricing", "Giá hội chẩn ca bệnh khó", ("200.000",)),
    EvalQuestion("pricing", "Giá siêu âm tuyến giáp", ("58.600",)),
    EvalQuestion("pricing", "Siêu âm tim thai qua đường âm đạo giá bao nhiêu?", ("195.600",)),
    EvalQuestion("pricing", "Giá siêu âm tiền liệt tuyến qua trực tràng", ("195.600",)),
    EvalQuestion("pricing", "Chụp OCT bán phần sau nhãn cầu giá bao nhiêu?", ("222.300",)),
    EvalQuestion("pricing", "Chụp X-quang răng cận chóp Periapical giá?", ("16.100",)),
    EvalQuestion("pricing", "Ngày giường điều trị ban ngày Bệnh viện A bao nhiêu?", ("ban ngay",)),
    EvalQuestion("pricing", "Ngày giường hồi sức cấp cứu ở Bệnh viện A", ("hoi suc",)),

    # BHYT and document/article content.
    EvalQuestion("bhyt", "Hướng dẫn tích hợp thẻ bảo hiểm y tế trên VNeID gồm bước nào?", ("vneid",)),
    EvalQuestion("bhyt", "Điều kiện cần để tích hợp thẻ BHYT là gì?", ("dinh danh",)),
    EvalQuestion("bhyt", "Người trên 80 tuổi có liên quan gì tới đăng ký KCB ban đầu tại Bệnh viện A?", ("80",)),
    EvalQuestion("bhyt", "Trẻ em dưới 6 tuổi có được đăng ký KCB ban đầu tại Bệnh viện A không?", ("6 tuoi",)),
    EvalQuestion("bhyt", "Người có HIV/AIDS điều trị ngoại trú tại Bệnh viện A được nhắc ở đâu?", ("hiv")),
    EvalQuestion("bhyt", "Các trường hợp cấp cứu BHYT được xác định như thế nào?", ("cap cuu")),
    EvalQuestion("bhyt", "Giấy hẹn khám lại có giá trị sử dụng mấy lần?", ("mot lan",)),
    EvalQuestion("bhyt", "Mẫu giấy chuyển tuyến khám bệnh BHYT có nội dung gì?", ("giay chuyen tuyen")),
]


def _contains_expected_terms(answer: str, expected_terms: tuple[str, ...]) -> bool:
    if not expected_terms:
        return True
    normalized_answer = _normalize_match(answer)
    return any(_normalize_match(term) in normalized_answer for term in expected_terms)


def evaluate() -> list[dict]:
    assistant = HospitalAssistant()
    results: list[dict] = []

    for index, item in enumerate(QUESTIONS, start=1):
        started = time.perf_counter()
        try:
            answer_result = assistant.answer(item.question)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            answer = answer_result.answer
            has_answer = FALLBACK_TEXT not in answer
            has_sources = bool(answer_result.sources)
            has_expected_terms = _contains_expected_terms(answer, item.expected_terms)
            passed = has_answer and has_sources and has_expected_terms
            results.append(
                {
                    **asdict(item),
                    "index": index,
                    "passed": passed,
                    "has_answer": has_answer,
                    "has_sources": has_sources,
                    "has_expected_terms": has_expected_terms,
                    "elapsed_ms": elapsed_ms,
                    "answer": answer,
                    "sources": [source.model_dump() for source in answer_result.sources],
                }
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            results.append(
                {
                    **asdict(item),
                    "index": index,
                    "passed": False,
                    "has_answer": False,
                    "has_sources": False,
                    "has_expected_terms": False,
                    "elapsed_ms": elapsed_ms,
                    "answer": "",
                    "sources": [],
                    "error": repr(exc),
                }
            )
        print(f"[{index:02d}/{len(QUESTIONS)}] {'PASS' if results[-1]['passed'] else 'FAIL'} {item.category}: {item.question}")

    return results


def write_reports(results: list[dict]) -> None:
    output_dir = ROOT / "data" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hard_questions_results.json"
    md_path = output_dir / "hard_questions_report.md"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    passed = sum(1 for item in results if item["passed"])
    lines = [
        "# Hard Chatbot Question Evaluation",
        "",
        f"- Total: {len(results)}",
        f"- Passed: {passed}",
        f"- Failed: {len(results) - passed}",
        "",
        "## Failed Questions",
        "",
    ]
    failures = [item for item in results if not item["passed"]]
    if not failures:
        lines.append("No failures.")
    else:
        for item in failures:
            lines.extend(
                [
                    f"### {item['index']}. {item['question']}",
                    "",
                    f"- Category: `{item['category']}`",
                    f"- Has answer: `{item['has_answer']}`",
                    f"- Has sources: `{item['has_sources']}`",
                    f"- Has expected terms: `{item['has_expected_terms']}`",
                    f"- Expected terms: `{', '.join(item['expected_terms'])}`",
                    f"- Answer: {item['answer'] or item.get('error', '')}",
                    "",
                ]
            )

    lines.extend(["", "## All Questions", ""])
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(f"- `{status}` [{item['category']}] {item['question']}")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


def main() -> None:
    results = evaluate()
    write_reports(results)
    failed = [item for item in results if not item["passed"]]
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
