from hospital_assistant.assistant import _ground_short_hospital_question
from hospital_assistant.assistant import HospitalAssistant
from langchain_core.documents import Document


def test_ground_short_address_question_to_hospital_a() -> None:
    assert _ground_short_hospital_question("Địa chỉ bệnh viện") == "Địa chỉ Bệnh viện A Thái Nguyên"


def test_ground_short_exam_price_question_to_hospital_a() -> None:
    assert _ground_short_hospital_question("Giá khám bệnh") == "Giá khám bệnh tại Bệnh viện A"


def test_ground_short_contact_question_to_hospital_a() -> None:
    assert _ground_short_hospital_question("Số điện thoại liên hệ") == "Số điện thoại liên hệ của Bệnh viện A Thái Nguyên"


def test_keep_department_question_unchanged() -> None:
    assert _ground_short_hospital_question("Khoa Nhi") == "Khoa Nhi"


def test_exam_price_answer_accepts_natural_short_grounded_phrase() -> None:
    assistant = HospitalAssistant.__new__(HospitalAssistant)
    assistant._pricing_page_docs = lambda: [
        Document(
            page_content="I Giá khám bệnh\n1 Bệnh viện A 50.600\n2 Bệnh viện C 50.600",
            metadata={
                "title": "Bảng giá viện phí",
                "source_url": "https://benhvienathainguyen.com.vn/page/11/bang-gia-vien-phi",
                "record_type": "web_document",
                "chunk_id": "pricing-1",
            },
        )
    ]

    result = assistant._structured_exam_price_answer("Giá khám bệnh tại Bệnh viện A")

    assert result is not None
    assert result.answer == "Giá khám bệnh tại Bệnh viện A là 50.600 VNĐ [Nguon 1]."
