from hospital_assistant.assistant import HospitalAssistant
from hospital_assistant.assistant import _ground_short_hospital_question


def _assistant_with_chunks(chunks: list[dict]) -> HospitalAssistant:
    assistant = HospitalAssistant.__new__(HospitalAssistant)
    assistant.chunk_manifest = chunks
    assistant.manifest_docs = [assistant._build_manifest_doc(item) for item in chunks]
    assistant.pricing_service_docs = []
    return assistant


def _chunk(chunk_id: str, title: str, source_url: str, content: str, page_type: str = "page") -> dict:
    return {
        "chunk_id": chunk_id,
        "title": title,
        "record_type": "web_document",
        "source_url": source_url,
        "origin_path": "",
        "page_number": None,
        "content": content,
        "metadata": {
            "title": title,
            "source_url": source_url,
            "page_type": page_type,
            "topic_group": "generic",
        },
    }


def test_keep_vaccine_booking_location_question_unchanged() -> None:
    assert _ground_short_hospital_question("Đặt tiêm vaccine ở đâu?") == "Đặt tiêm vaccine ở đâu?"


def test_keep_department_contact_question_unchanged() -> None:
    question = "Phòng Quản lý chất lượng bệnh viện có thông tin liên hệ không?"

    assert _ground_short_hospital_question(question) == question


def test_keep_appointment_validity_question_unchanged() -> None:
    question = "Giấy hẹn khám lại có giá trị sử dụng mấy lần?"

    assert _ground_short_hospital_question(question) == question


def test_keep_specific_price_service_question_unchanged() -> None:
    question = "giá khám Siêu âm màng phổi cấp cứu"

    assert _ground_short_hospital_question(question) == question


def test_price_intent_ignores_document_validity_phrase() -> None:
    assistant = HospitalAssistant.__new__(HospitalAssistant)

    assert not assistant._is_price_query("Giấy hẹn khám lại có giá trị sử dụng mấy lần?")


def test_priority_topic_docs_routes_health_check_process() -> None:
    assistant = _assistant_with_chunks(
        [
            _chunk(
                "process-general",
                "Quy Trình Khám Bệnh",
                "https://benhvienathainguyen.com.vn/page/15/quy-trinh-kham-benh",
                "Quy trình khám bệnh thông thường.",
            ),
            _chunk(
                "process-health",
                "Quy Trình Khám Sức Khỏe",
                "https://benhvienathainguyen.com.vn/page/16/quy-trinh-kham-suc-khoe",
                "Quy trình khám sức khỏe.",
            ),
        ]
    )

    docs = assistant._priority_topic_docs("Khám sức khỏe làm theo quy trình nào?", limit=4)

    assert docs
    assert docs[0].metadata["source_url"].endswith("/page/16/quy-trinh-kham-suc-khoe")


def test_priority_topic_docs_routes_bhyt_follow_up_terms() -> None:
    assistant = _assistant_with_chunks(
        [
            _chunk(
                "faq-noise",
                "Faq",
                "https://benhvienathainguyen.com.vn/faqs/faq/117/",
                "Số điện thoại liên hệ trong hỏi đáp.",
                page_type="faq_detail",
            ),
            _chunk(
                "bhyt-appointment",
                "Hướng Dẫn Cơ Sở Khám Bệnh, Chữa Bệnh Đủ Điều Kiện Khám Bệnh, Chữa Bệnh Bhyt Năm 2024",
                "https://benhvienathainguyen.com.vn/article/1080/huong-dan-co-so-kham-benh-chua-benh-du-dieu-kien-kham-benh-chua-benh-bhyt-nam-2024",
                "Giấy hẹn khám lại chỉ có giá trị sử dụng một lần.",
                page_type="article",
            ),
        ]
    )

    docs = assistant._priority_topic_docs("Giấy hẹn khám lại có giá trị sử dụng mấy lần?", limit=4)

    assert docs
    assert docs[0].metadata["source_url"].startswith("https://benhvienathainguyen.com.vn/article/1080/")


def test_department_contact_answer_uses_department_contact_doc() -> None:
    assistant = _assistant_with_chunks(
        [
            _chunk(
                "department-body",
                "Phòng Quản Lý Chất Lượng Bệnh Viện",
                "https://benhvienathainguyen.com.vn/his/department/29/phong-quan-ly-chat-luong-benh-vien",
                "Phòng Quản Lý Chất Lượng Bệnh Viện giới thiệu cải tiến chất lượng.",
                page_type="department",
            ),
            _chunk(
                "department-contact",
                "Phòng Quản Lý Chất Lượng Bệnh Viện",
                "https://benhvienathainguyen.com.vn/his/contact/29/phong-quan-ly-chat-luong-benh-vien",
                "Liên hệ PHÒNG QUẢN LÝ CHẤT LƯỢNG BỆNH VIỆN (0208)3846112",
                page_type="department_contact",
            ),
        ]
    )

    result = assistant._structured_department_contact_answer(
        "Phòng Quản lý chất lượng bệnh viện có thông tin liên hệ không?"
    )

    assert result is not None
    assert "Phòng Quản Lý Chất Lượng Bệnh Viện" in result.answer
    assert "02083846112" in result.answer
    assert "/his/contact/29/" in (result.sources[0].source_url or "")


def test_price_amount_question_maps_known_exam_price() -> None:
    assistant = _assistant_with_chunks([])
    assistant._pricing_page_docs = lambda: [
        assistant._build_manifest_doc(
            _chunk(
                "pricing-page",
                "Bảng Giá Viện Phí",
                "https://benhvienathainguyen.com.vn/page/11/bang-gia-vien-phi",
                "I Giá khám bệnh\n1 Bệnh viện A 50.600\n2 Bệnh viện C 50.600",
            )
        )
    ]

    result = assistant._structured_price_amount_answer("đó là khám bệnh gì mà 50.600đ nhỉ")

    assert result is not None
    assert "giá khám bệnh tại Bệnh viện A" in result.answer
    assert "50.600 VNĐ" in result.answer


def test_price_fallback_mentions_related_non_pricing_docs() -> None:
    assistant = _assistant_with_chunks(
        [
            _chunk(
                "bhyt-lao",
                "Hướng Dẫn KCB BHYT",
                "https://benhvienathainguyen.com.vn/article/1080/huong-dan-co-so-kham-benh-chua-benh-du-dieu-kien-kham-benh-chua-benh-bhyt-nam-2024",
                "Thông tin liên quan đến khám bệnh, chữa bệnh lao phổi và bảo hiểm y tế.",
                page_type="article",
            )
        ]
    )

    result = assistant._related_price_fallback_answer("giá khám lao phổi")

    assert result is not None
    assert "chưa tìm thấy giá" in result.answer
    assert "thông tin liên quan" in result.answer
    assert result.sources[0].title == "Hướng Dẫn KCB BHYT"


def test_department_list_question_uses_organization_structure_doc() -> None:
    assistant = _assistant_with_chunks(
        [
            _chunk(
                "org-structure",
                "Cơ Cấu Tổ Chức",
                "https://benhvienathainguyen.com.vn/page/5/co-cau-to-chuc",
                (
                    "Cơ cấu tổ chức các khoa phòng hiện tại gồm: 33 khoa phòng gồm: "
                    "phòng Tổ chức - Hành chính, phòng Tài chính - Kế toán. "
                    "Các khoa trong Bệnh viện gồm : khoa Khám bệnh, khoa Hồi sức cấp cứu, "
                    "khoa Nội tổng hợp, Khoa Sản, Khoa Nhi, khoa Mắt, khoa Răng - Hàm - Mặt"
                ),
            )
        ]
    )

    result = assistant._structured_department_list_answer("Bệnh viện A có những khoa nào")

    assert result is not None
    assert "khoa Khám bệnh" in result.answer
    assert "Khoa Nhi" in result.answer
    assert result.sources[0].title == "Cơ Cấu Tổ Chức"
