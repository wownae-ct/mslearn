import csv
import os
import re

import numpy as np
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentAnalysisFeature,
)
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import ContainerClient
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값 읽어오기
endpoint = os.environ.get("YOUR_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("YOUR_FORM_RECOGNIZER_KEY")
sas_token = os.environ.get("AZURE_CONTAINER_SAS_TOKEN")
blob_endpoint = os.environ.get("AZURE_BLOB_CONTAINER_URL")

print("Document-Intelligence 엔드포인트:", endpoint)
print("키 로드 성공 여부:", bool(key))
print("SAS 토큰 로드 성공 여부:", bool(sas_token))
print("블롭 스토리지 URL 로드 성공 여부:", bool(blob_endpoint))


def format_bounding_box(bounding_box):
    if not bounding_box:
        return "N/A"
    reshaped_bounding_box = np.array(bounding_box).reshape(-1, 2)
    return ", ".join(["[{}, {}]".format(x, y) for x, y in reshaped_bounding_box])


def save_to_individual_csv(file_name, fieldnames, rows_data):
    if not rows_data:
        return

    output_dir = "document-inteligence/data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pure_name, _ = os.path.splitext(file_name)
    output_csv_path = os.path.join(output_dir, f"{pure_name}_result.csv")

    with open(output_csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        # extrasaction="ignore": 쿼리필드 행이 섞여 들어와도 정의되지 않은 키는 무시
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_data)
    print(f"💾 [개별 저장 완료] '{output_csv_path}' 파일이 생성되었습니다.")


# ============================================================
# 🌟 공통 유틸: 모든 모델이 query_fields를 옵션으로 수락하기 위한 공통 인자 처리
# ============================================================
def sanitize_query_field_name(name):
    """Azure Query Fields 이름 규칙(^[\\p{L}\\p{M}\\p{N}_]{1,64}$)에 맞게 정규화한다.
    공백/특수문자가 섞인 자연어 질문("프로젝트 이름")을 그대로 넘기면
    'InvalidParameter: queryFields is invalid' 에러가 나므로,
    공백은 밑줄로 바꾸고 그 외 허용되지 않는 문자는 제거한다."""
    normalized = re.sub(r"\s+", "_", name.strip())
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
    return (normalized or "field")[:64]


def sanitize_query_fields(query_fields):
    if not query_fields:
        return query_fields
    return [sanitize_query_field_name(q) for q in query_fields]


def build_analyze_kwargs(model_id, form_url, query_fields=None):
    """model_id/body는 항상 동일한 형태로 구성하고,
    query_fields가 있을 때만 QUERY_FIELDS 기능과 query_fields kwarg를 추가한다."""
    kwargs = {
        "model_id": model_id,
        "body": AnalyzeDocumentRequest(url_source=form_url),
    }
    if query_fields:
        kwargs["features"] = [DocumentAnalysisFeature.QUERY_FIELDS]
        kwargs["query_fields"] = query_fields
    return kwargs


def extract_query_field_rows(result, query_fields, row_builder):
    """모든 prebuilt 모델 공통: result.documents[].fields 에서 질의응답 결과를 뽑아
    각 모델의 CSV 스키마에 맞는 dict로 변환해 반환한다.
    query_fields가 없거나, 해당 모델 결과에 documents/fields가 없으면 조용히 빈 리스트를 반환한다
    (예: prebuilt-read는 documents가 없으므로 자동으로 스킵됨)."""
    rows = []
    if not query_fields:
        return rows

    for doc in getattr(result, "documents", []) or []:
        fields_dict = getattr(doc, "fields", {}) or {}
        for q_field in query_fields:
            field_data = fields_dict.get(q_field)
            if field_data and getattr(field_data, "content", None):
                print(f"💬 질문: '{q_field}' -> 🎯 답변: '{field_data.content}'")
                rows.append(
                    row_builder(q_field, field_data.content, field_data.confidence)
                )
    return rows


# --- [모델 1] Prebuilt-Invoice 분석 및 CSV 저장 로직 ---
def analyze_invoice_model(client, form_url, file_name, query_fields=None):
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-invoice", form_url, query_fields)
    )
    invoices = poller.result()

    file_rows = []
    docs_list = getattr(invoices, "documents", [])
    for idx, invoice in enumerate(docs_list):
        print("--------Recognizing invoice #{}--------".format(idx + 1))

        for field_name, attr_type in [
            ("VendorName", "value_string"),
            ("VendorAddress", "value_address"),
            ("CustomerName", "value_string"),
            ("InvoiceId", "value_string"),
            ("InvoiceDate", "value_date"),
            ("DueDate", "value_date"),
        ]:
            field_obj = invoice.fields.get(field_name)
            if field_obj and getattr(field_obj, attr_type, None):
                val = getattr(field_obj, attr_type)
                print(f"{field_name}: {val}")
                file_rows.append(
                    {
                        "항목": field_name,
                        "데이터": str(val),
                        "신뢰도": field_obj.confidence,
                    }
                )

        invoice_total = invoice.fields.get("InvoiceTotal")
        if invoice_total:
            total_val = getattr(invoice_total, "value_currency", None)
            total_final = (
                total_val.amount
                if total_val
                else getattr(invoice_total, "value_string", "0")
            )
            print(f"InvoiceTotal: {total_final}")
            file_rows.append(
                {
                    "항목": "InvoiceTotal",
                    "데이터": str(total_final),
                    "신뢰도": invoice_total.confidence,
                }
            )

    # 🌟 공통 쿼리필드 결과 병합 (invoice 스키마 그대로 활용)
    file_rows.extend(
        extract_query_field_rows(
            invoices,
            query_fields,
            row_builder=lambda q, a, c: {
                "항목": f"[Query] {q}",
                "데이터": a,
                "신뢰도": c,
            },
        )
    )

    save_to_individual_csv(file_name, ["항목", "데이터", "신뢰도"], file_rows)


# --- [모델 2] Prebuilt-Read 분석 및 CSV 저장 로직 ---
def analyze_read_model(client, form_url, file_name, query_fields=None):
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-read", form_url, query_fields)
    )
    result = poller.result()

    file_rows = []
    for page in getattr(result, "pages", []):
        print("----Analyzing Read from page #{}----".format(page.page_number))
        for line_idx, line in enumerate(getattr(page, "lines", [])):
            text_content = getattr(line, "content", "")
            print(f"...Line # {line_idx}: {text_content}")
            file_rows.append(
                {
                    "페이지": page.page_number,
                    "라인번호": line_idx,
                    "텍스트": text_content,
                }
            )

    # 🌟 공통 쿼리필드 결과 병합
    # 참고: prebuilt-read는 Azure 측에서 QUERY_FIELDS add-on 자체를 지원하지 않아
    # result.documents가 비어 있으므로, 실제로는 아무 행도 추가되지 않고 조용히 넘어간다.
    file_rows.extend(
        extract_query_field_rows(
            result,
            query_fields,
            row_builder=lambda q, a, c: {"페이지": "Query", "라인번호": q, "텍스트": a},
        )
    )

    save_to_individual_csv(file_name, ["페이지", "라인번호", "텍스트"], file_rows)


# --- [모델 3] Prebuilt-Layout 분석 및 CSV 저장 로직 (텍스트+표 전수 추출 + 쿼리필드) ---
def analyze_document_model(client, form_url, file_name, query_fields=None):
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-layout", form_url, query_fields)
    )
    result = poller.result()

    file_rows = []

    print("----Paragraphs found in document----")
    paragraphs = getattr(result, "paragraphs", [])
    for p_idx, paragraph in enumerate(paragraphs):
        content = getattr(paragraph, "content", "")
        role = getattr(paragraph, "role", "Text")
        if content:
            print(f"[{role}] {content[:50]}...")
            file_rows.append(
                {
                    "구분": f"문단_{p_idx + 1}({role})",
                    "위치정보": f"줄바꿈순서_{p_idx}",
                    "상세데이터": content,
                }
            )

    print("----Tables found in document----")
    tables = getattr(result, "tables", [])
    if tables:
        for t_idx, table in enumerate(tables):
            print(f"  📊 Table #{t_idx + 1} ({table.row_count}x{table.column_count})")
            for cell in getattr(table, "cells", []):
                cell_text = getattr(cell, "content", "")
                file_rows.append(
                    {
                        "구분": f"표_{t_idx + 1}_데이터",
                        "위치정보": f"{cell.row_index}행 {cell.column_index}열",
                        "상세데이터": cell_text,
                    }
                )
    else:
        print("추출된 표가 없습니다.")

    # 🌟 공통 쿼리필드 결과 병합 (layout 스키마에 신뢰도 컬럼을 추가로 확장)
    file_rows.extend(
        extract_query_field_rows(
            result,
            query_fields,
            row_builder=lambda q, a, c: {
                "구분": "Query",
                "위치정보": q,
                "상세데이터": a,
                "신뢰도": c,
            },
        )
    )

    save_to_individual_csv(
        file_name, ["구분", "위치정보", "상세데이터", "신뢰도"], file_rows
    )


# --- [모델 5] Prebuilt-Receipt 분석 및 CSV 저장 로직 (영수증 전용) ---
def analyze_receipt_model(client, form_url, file_name, query_fields=None):
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-receipt", form_url, query_fields)
    )
    receipts = poller.result()

    file_rows = []
    for idx, receipt in enumerate(getattr(receipts, "documents", [])):
        print("--------Recognizing receipt #{}--------".format(idx + 1))
        for field_name, attr_type in [
            ("MerchantName", "value_string"),
            ("MerchantAddress", "value_address"),
            ("MerchantPhoneNumber", "value_phone_number"),
            ("TransactionDate", "value_date"),
            ("TransactionTime", "value_time"),
            ("Subtotal", "value_currency"),
            ("TotalTax", "value_currency"),
            ("Total", "value_currency"),
        ]:
            field_obj = receipt.fields.get(field_name)
            if field_obj and getattr(field_obj, attr_type, None):
                val = getattr(field_obj, attr_type)
                # 통화 필드(value_currency)는 amount만 뽑아서 사람이 읽기 좋게 정리
                if attr_type == "value_currency":
                    val = getattr(val, "amount", val)
                print(f"{field_name}: {val}")
                file_rows.append(
                    {
                        "항목": field_name,
                        "데이터": str(val),
                        "신뢰도": field_obj.confidence,
                    }
                )

    # 🌟 공통 쿼리필드 결과 병합 (invoice와 동일한 3컬럼 스키마 재사용)
    file_rows.extend(
        extract_query_field_rows(
            receipts,
            query_fields,
            row_builder=lambda q, a, c: {
                "항목": f"[Query] {q}",
                "데이터": a,
                "신뢰도": c,
            },
        )
    )

    save_to_individual_csv(file_name, ["항목", "데이터", "신뢰도"], file_rows)


# --- [모델 4] Prebuilt-IdDocument 분석 및 CSV 저장 로직 ---
def analyze_id_model(client, form_url, file_name, query_fields=None):
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-idDocument", form_url, query_fields)
    )
    id_documents = poller.result()

    file_rows = []
    for idx, id_document in enumerate(getattr(id_documents, "documents", [])):
        print("--------Recognizing ID document #{}--------".format(idx + 1))
        for id_key, id_attr in [
            ("FirstName", "value_string"),
            ("LastName", "value_string"),
            ("DocumentNumber", "value_string"),
            ("DateOfBirth", "value_date"),
        ]:
            id_obj = id_document.fields.get(id_key)
            if id_obj and getattr(id_obj, id_attr, None):
                val = getattr(id_obj, id_attr)
                print(f"{id_key}: {val}")
                file_rows.append(
                    {
                        "신분증필드": id_key,
                        "추출데이터": str(val),
                        "신뢰도": id_obj.confidence,
                    }
                )

    # 🌟 공통 쿼리필드 결과 병합
    file_rows.extend(
        extract_query_field_rows(
            id_documents,
            query_fields,
            row_builder=lambda q, a, c: {
                "신분증필드": f"[Query] {q}",
                "추출데이터": a,
                "신뢰도": c,
            },
        )
    )

    save_to_individual_csv(file_name, ["신분증필드", "추출데이터", "신뢰도"], file_rows)


# --- 모델 라우팅 테이블: (모델 판별 함수) -> 실행 함수 매핑 ---
# 🌟 [리팩토링 핵심] 더 이상 "질문 유무"로 갈라지는 별도의 모델(query-fields 전용 분기)이 없다.
#     invoice/receipt/id/read/layout 5개 함수 모두 query_fields를 공통 kwarg로 받으므로,
#     파일 종류에 따라 어떤 모델을 쓸지만 결정하면 되고, query_fields는 그 위에 항상 얹어서 전달한다.
#
# 🌟 [버그 수정] 예전 로직은 "확장자가 이미지면 무조건 ID 모델"이었다.
#     그래서 receipt1.jpg / receipt2.jpg 같은 영수증 사진까지 전부 신분증 모델로 잘못 들어갔다.
#     신분증 키워드를 먼저 명시적으로 좁혀서 검사하고, 영수증은 별도의 prebuilt-receipt 모델로 분리한다.
ID_KEYWORDS = (
    "license",
    "passport",
    "id_",
    "id-",
    "신분증",
    "주민등록증",
    "여권",
    "운전면허",
)
RECEIPT_KEYWORDS = ("receipt", "영수증")
INVOICE_KEYWORDS = ("invoice", "bill", "인보이스", "청구서", "거래명세서")


# "ID1.jpg", "id_2.png" 처럼 파일명 전체가 "id + 숫자"로만 구성된 경우까지 잡아내기 위한 헬퍼.
# (밑줄/하이픈으로 나눈 토큰 단위 검사라 "invoice", "video" 같은 단어는 걸리지 않는다)
def looks_like_id_filename(pure_name):
    tokens = re.split(r"[_\-]", pure_name)
    return any(
        tok.startswith("id") and (tok == "id" or tok[2:].isdigit()) for tok in tokens
    )


def select_model_func(lower_name, ext):
    pure_name, _ = os.path.splitext(lower_name)

    if any(k in lower_name for k in RECEIPT_KEYWORDS):
        return "[모델 5] Receipt(영수증)", analyze_receipt_model
    if any(k in lower_name for k in INVOICE_KEYWORDS):
        return "[모델 1] Invoice(인보이스)", analyze_invoice_model
    if any(k in lower_name for k in ID_KEYWORDS) or looks_like_id_filename(pure_name):
        return "[모델 4] ID Document(신분증)", analyze_id_model
    if ext == ".pdf" or "form" in lower_name or "layout" in lower_name:
        return "[모델 3] Layout(표/문단 구조 분석)", analyze_document_model
    # 🌟 키워드로 특정할 수 없는 이미지/기타 파일은 더 이상 무조건 ID 모델로 보내지 않고,
    #    가장 안전한 범용 텍스트 추출(Read)로 우회한다.
    return "[모델 2] Read(일반 텍스트/OCR)", analyze_read_model


# --- 메인 컨트롤러 ---
def main():
    container_client = ContainerClient.from_container_url(
        f"{blob_endpoint}?{sas_token}"
    )
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # 파일명 키워드로 자동 매칭되는 쿼리필드 프리셋
    # 🌟 Azure Query Fields는 이름에 공백을 허용하지 않으므로(정규식 ^[\p{L}\p{M}\p{N}_]{1,64}$),
    #    사람이 읽기 편하게 밑줄(_)로 이어 쓴다. (sanitize_query_fields가 한 번 더 안전하게 정규화해준다)
    TARGET_QUERIES = {
        "계획": ["프로젝트_이름", "시작_날짜", "담당자", "최종_목적"],
        "target": ["문서_제목", "발행일", "수신자"],
    }

    # 🌟 필요할 때만 수동으로 채워서 자동 매칭보다 우선 적용 (예: ["프로젝트_이름", "담당자"])
    MANUAL_OVERRIDE_QUERIES = None

    print("\n📂 특정 컨테이너 내부 전수 조사를 시작합니다...")
    total_files_processed = 0

    for blob in container_client.list_blobs():
        if blob.name.endswith("/"):
            continue

        total_files_processed += 1
        print("\n==================================================")
        print(f"📄 대상 파일 인지: {blob.name} (누적 처리: {total_files_processed}개)")
        print("==================================================")

        form_url = f"{blob_endpoint}/{blob.name}?{sas_token}"
        lower_name = blob.name.lower()
        _, ext = os.path.splitext(lower_name)

        active_questions = None
        for keyword, q_list in TARGET_QUERIES.items():
            if keyword in lower_name:
                active_questions = q_list
                break

        # 🌟 [리팩토링] query_fields는 모델 선택과 완전히 분리된 공통 인자다.
        #     어떤 모델이 선택되든 동일하게 얹어서 전달하면 되므로, 별도의 분기(elif)가 필요 없다.
        # 🌟 API로 넘기기 직전에 딱 한 곳에서 정규화 → build_analyze_kwargs(전송)와
        #     extract_query_field_rows(결과 조회)가 항상 같은 이름을 참조하게 된다.
        query_fields = sanitize_query_fields(
            MANUAL_OVERRIDE_QUERIES or active_questions
        )

        try:
            model_label, model_func = select_model_func(lower_name, ext)
            print(f"▶ [자동 인식] {model_label} 모델을 가동합니다.")
            if query_fields:
                print(f"   ㄴ 🌟 쿼리필드 옵션 활성화: {query_fields}")

            model_func(
                document_intelligence_client,
                form_url,
                blob.name,
                query_fields=query_fields,
            )

            print("\n----------------------------------------")
        except Exception as e:
            print(
                f"❌ 파일 [{blob.name}] 분석 중 예상치 못한 포맷 거부 에러 발생 (스킵): {e}"
            )

    print("\n==================================================")
    print(
        f"🎉 [SUCCESS] 모든 파일 처리가 끝났습니다. 총 {total_files_processed}개의 파일을 분석했습니다."
    )
    print("==================================================")


if __name__ == "__main__":
    main()
