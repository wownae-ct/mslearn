import csv
import os
import re
import traceback
from datetime import datetime

import numpy as np
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentAnalysisFeature,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.storage.blob import ContainerClient
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값 읽어오기
endpoint = os.environ.get("YOUR_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("YOUR_FORM_RECOGNIZER_KEY")
sas_token = os.environ.get("AZURE_CONTAINER_SAS_TOKEN")
blob_endpoint = os.environ.get("AZURE_BLOB_CONTAINER_URL")

print("=" * 60)
print("[DEBUG] 환경변수 로드 상태")
print("=" * 60)
print("Document-Intelligence 엔드포인트:", endpoint)
print("키 로드 성공 여부:", bool(key))
print("SAS 토큰 로드 성공 여부:", bool(sas_token))
print("블롭 스토리지 URL 로드 성공 여부:", bool(blob_endpoint))

# 🌟 [추가] 필수 환경변수가 하나라도 비어있으면 여기서 바로 명확하게 죽여서
#     "왜 안 되는지 모르겠다"는 상황 자체를 방지
_missing = [
    name
    for name, val in [
        ("YOUR_FORM_RECOGNIZER_ENDPOINT", endpoint),
        ("YOUR_FORM_RECOGNIZER_KEY", key),
        ("AZURE_CONTAINER_SAS_TOKEN", sas_token),
        ("AZURE_BLOB_CONTAINER_URL", blob_endpoint),
    ]
    if not val
]
if _missing:
    raise SystemExit(
        f"[FATAL] .env에서 다음 값을 못 읽었습니다: {_missing}\n"
        f"  -> .env 파일 경로/이름, 실행 위치(cwd)를 확인하세요."
    )

# 🌟 [추가] SAS 토큰 만료 시각 미리 파싱해서 경고
#     SAS 토큰 쿼리스트링에는 보통 'se=' (signed expiry) 파라미터가 들어있습니다.
_se_match = re.search(r"se=([^&]+)", sas_token)
if _se_match:
    try:
        # URL 인코딩된 콜론(%3A) 등을 풀어서 파싱
        from urllib.parse import unquote

        expiry_str = unquote(_se_match.group(1))
        expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        now = datetime.now(expiry_dt.tzinfo)
        print(f"[DEBUG] SAS 토큰 만료 시각: {expiry_dt.isoformat()}")
        if now >= expiry_dt:
            print(
                f"⚠️  [경고] SAS 토큰이 이미 만료되었습니다! "
                f"(만료: {expiry_dt.isoformat()}, 현재: {now.isoformat()})\n"
                f"    -> Azure Portal에서 새 SAS 토큰을 발급받아 .env를 갱신하세요."
            )
        else:
            remaining = expiry_dt - now
            print(f"[DEBUG] SAS 토큰 남은 유효시간: {remaining}")
    except Exception as parse_err:
        print(f"[DEBUG] SAS 만료시각 파싱 실패(무시 가능): {parse_err!r}")
else:
    print("[DEBUG] SAS 토큰에서 만료시각(se=) 파라미터를 찾지 못함")

print("=" * 60)


def format_bounding_box(bounding_box):
    if not bounding_box:
        return "N/A"
    reshaped_bounding_box = np.array(bounding_box).reshape(-1, 2)
    return ", ".join(["[{}, {}]".format(x, y) for x, y in reshaped_bounding_box])


def save_to_individual_csv(file_name, fieldnames, rows_data):
    if not rows_data:
        print(f"[DEBUG] '{file_name}' 처리 결과 rows_data가 비어있어 CSV를 만들지 않음")
        return

    output_dir = "document-intelligence/data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[DEBUG] 출력 디렉토리 생성: {output_dir}")

    pure_name, _ = os.path.splitext(file_name)
    output_csv_path = os.path.join(output_dir, f"{pure_name}_result.csv")

    with open(output_csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_data)
    print(f"💾 [개별 저장 완료] '{output_csv_path}' 파일이 생성되었습니다. (행 개수: {len(rows_data)})")


# ============================================================
# 🌟 공통 유틸: 모든 모델이 query_fields를 옵션으로 수락하기 위한 공통 인자 처리
# ============================================================
def sanitize_query_field_name(name):
    normalized = re.sub(r"\s+", "_", name.strip())
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
    return (normalized or "field")[:64]


def sanitize_query_fields(query_fields):
    if not query_fields:
        return query_fields
    return [sanitize_query_field_name(q) for q in query_fields]


def build_analyze_kwargs(model_id, form_url, query_fields=None):
    kwargs = {
        "model_id": model_id,
        "body": AnalyzeDocumentRequest(url_source=form_url),
    }
    if query_fields:
        kwargs["features"] = [DocumentAnalysisFeature.QUERY_FIELDS]
        kwargs["query_fields"] = query_fields
    print(f"[DEBUG] build_analyze_kwargs: model_id={model_id}, query_fields={query_fields}")
    return kwargs


def extract_query_field_rows(result, query_fields, row_builder):
    rows = []
    if not query_fields:
        return rows

    docs = getattr(result, "documents", []) or []
    print(f"[DEBUG] extract_query_field_rows: documents 개수={len(docs)}")

    for doc in docs:
        fields_dict = getattr(doc, "fields", {}) or {}
        for q_field in query_fields:
            field_data = fields_dict.get(q_field)
            if field_data and getattr(field_data, "content", None):
                print(f"💬 질문: '{q_field}' -> 🎯 답변: '{field_data.content}'")
                rows.append(
                    row_builder(q_field, field_data.content, field_data.confidence)
                )
            else:
                # 🌟 [추가] 왜 이 필드가 안 뽑혔는지 원인 추적용
                print(f"[DEBUG] 쿼리필드 '{q_field}' 응답 없음 (field_data={field_data})")
    return rows


# --- [모델 1] Prebuilt-Invoice 분석 및 CSV 저장 로직 ---
def analyze_invoice_model(client, form_url, file_name, query_fields=None):
    print(f"[DEBUG] analyze_invoice_model 시작: {file_name}")
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-invoice", form_url, query_fields)
    )
    invoices = poller.result()

    file_rows = []
    docs_list = getattr(invoices, "documents", [])
    print(f"[DEBUG] invoice documents 개수: {len(docs_list)}")
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
    print(f"[DEBUG] analyze_read_model 시작: {file_name}")
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-read", form_url, query_fields)
    )
    result = poller.result()

    file_rows = []
    pages = getattr(result, "pages", [])
    print(f"[DEBUG] read pages 개수: {len(pages)}")
    for page in pages:
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
    print(f"[DEBUG] analyze_document_model(layout) 시작: {file_name}")
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-layout", form_url, query_fields)
    )
    result = poller.result()

    file_rows = []

    print("----Paragraphs found in document----")
    paragraphs = getattr(result, "paragraphs", [])
    print(f"[DEBUG] paragraphs 개수: {len(paragraphs)}")
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
    print(f"[DEBUG] tables 개수: {len(tables)}")
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
    print(f"[DEBUG] analyze_receipt_model 시작: {file_name}")
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-receipt", form_url, query_fields)
    )
    receipts = poller.result()

    file_rows = []
    docs = getattr(receipts, "documents", [])
    print(f"[DEBUG] receipt documents 개수: {len(docs)}")
    for idx, receipt in enumerate(docs):
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
    print(f"[DEBUG] analyze_id_model 시작: {file_name}")
    poller = client.begin_analyze_document(
        **build_analyze_kwargs("prebuilt-idDocument", form_url, query_fields)
    )
    id_documents = poller.result()

    file_rows = []
    docs = getattr(id_documents, "documents", [])
    print(f"[DEBUG] id documents 개수: {len(docs)}")
    for idx, id_document in enumerate(docs):
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
    return "[모델 2] Read(일반 텍스트/OCR)", analyze_read_model


def _mask_sas(url):
    """SAS 토큰이 포함된 URL을 로그에 찍을 때 시크릿을 일부 가려서 출력"""
    if "?" in url:
        base, qs = url.split("?", 1)
        return f"{base}?{qs[:12]}...(마스킹됨)"
    return url


def main():
    # 🌟 [추가] 컨테이너/클라이언트 생성 및 최초 접속 자체를 별도로 감싸서
    #     "리스트업조차 안 되는" 상황(인증/네트워크 문제)을 명확히 구분
    print("\n[DEBUG] ContainerClient 생성 시도...")
    try:
        container_client = ContainerClient.from_container_url(
            f"{blob_endpoint}?{sas_token}"
        )
        print("[DEBUG] ContainerClient 생성 성공")
    except Exception:
        print("[FATAL] ContainerClient 생성 실패. blob_endpoint/sas_token 형식을 확인하세요.")
        traceback.print_exc()
        raise

    print("[DEBUG] DocumentIntelligenceClient 생성 시도...")
    try:
        document_intelligence_client = DocumentIntelligenceClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )
        print("[DEBUG] DocumentIntelligenceClient 생성 성공")
    except Exception:
        print("[FATAL] DocumentIntelligenceClient 생성 실패. endpoint/key를 확인하세요.")
        traceback.print_exc()
        raise

    TARGET_QUERIES = {
        "계획": ["프로젝트_이름", "시작_날짜", "담당자", "최종_목적"],
        "target": ["문서_제목", "발행일", "수신자"],
    }
    MANUAL_OVERRIDE_QUERIES = None

    print("\n📂 특정 컨테이너 내부 전수 조사를 시작합니다...")

    # 🌟 [추가] list_blobs() 자체가 SAS 만료/권한 문제로 실패하는 경우를 명확히 잡아냄
    try:
        blob_list = list(container_client.list_blobs())
        print(f"[DEBUG] 컨테이너에서 조회된 blob 개수: {len(blob_list)}")
        if not blob_list:
            print(
                "⚠️  [경고] 컨테이너에서 파일이 하나도 조회되지 않았습니다. "
                "컨테이너 경로/이름이 맞는지, 실제로 파일이 있는지 확인하세요."
            )
    except ClientAuthenticationError:
        print("[FATAL] 인증 실패 (SAS 토큰이 유효하지 않거나 만료됨)")
        traceback.print_exc()
        return
    except HttpResponseError as e:
        print(f"[FATAL] Blob 목록 조회 중 HTTP 에러: status_code={getattr(e, 'status_code', None)}")
        traceback.print_exc()
        return
    except Exception:
        print("[FATAL] Blob 목록 조회 중 예상치 못한 에러")
        traceback.print_exc()
        return

    total_files_processed = 0
    total_files_failed = 0

    for blob in blob_list:
        if blob.name.endswith("/"):
            continue

        total_files_processed += 1
        print("\n==================================================")
        print(f"📄 대상 파일 인지: {blob.name} (누적 처리: {total_files_processed}개)")
        print("==================================================")

        form_url = f"{blob_endpoint}/{blob.name}?{sas_token}"
        print(f"[DEBUG] 요청 URL: {_mask_sas(form_url)}")
        lower_name = blob.name.lower()
        _, ext = os.path.splitext(lower_name)

        active_questions = None
        for keyword, q_list in TARGET_QUERIES.items():
            if keyword in lower_name:
                active_questions = q_list
                break

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
        except HttpResponseError as e:
            # 🌟 [추가] Azure 쪽에서 명시적으로 던지는 HTTP 에러는 상태코드/에러코드까지 출력
            total_files_failed += 1
            print(
                f"❌ [HttpResponseError] 파일 [{blob.name}] 분석 실패: "
                f"status_code={getattr(e, 'status_code', None)}, "
                f"error_code={getattr(getattr(e, 'error', None), 'code', None)}"
            )
            traceback.print_exc()
        except Exception:
            # 🌟 [수정] 기존엔 str(e)만 찍어서 원인을 알 수 없었음 -> 전체 스택트레이스 출력
            total_files_failed += 1
            print(f"❌ 파일 [{blob.name}] 분석 중 예상치 못한 에러 발생 (스킵)")
            traceback.print_exc()

    print("\n==================================================")
    print(
        f"🎉 [SUCCESS] 모든 파일 처리가 끝났습니다. "
        f"총 {total_files_processed}개 시도, 실패 {total_files_failed}개."
    )
    print("==================================================")


if __name__ == "__main__":
    main()