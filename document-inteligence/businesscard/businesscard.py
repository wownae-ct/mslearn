"""
This code sample shows Prebuilt Business Card operations with the Azure Form Recognizer client library.
The async versions of the samples require Python 3.6 or later.

To learn more, please visit the documentation - Quickstart: Form Recognizer Python client library SDKs
https://learn.microsoft.com/azure/applied-ai-services/form-recognizer/quickstarts/get-started-v3-sdk-rest-api?view=doc-intel-3.1.0&pivots=programming-language-python
"""

from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값 읽어오기
endpoint = os.environ.get("YOUR_FORM_RECOGNIZER_ENDPOINT")
key = os.environ.get("YOUR_FORM_RECOGNIZER_KEY")

print("엔드포인트:", endpoint)
print("키 로드 성공 여부:", bool(key))

# sample document
formUrl = "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/business-card-english.jpg"

document_analysis_client = DocumentAnalysisClient(
    endpoint=endpoint, credential=AzureKeyCredential(key)
)

poller = document_analysis_client.begin_analyze_document_from_url(
    "prebuilt-businessCard", formUrl
)
business_cards = poller.result()

for idx, business_card in enumerate(business_cards.documents):
    print("--------Analyzing business card #{}--------".format(idx + 1))
    contact_names = business_card.fields.get("ContactNames")
    if contact_names:
        for contact_name in contact_names.value:
            print(
                "Contact First Name: {} has confidence: {}".format(
                    contact_name.value["FirstName"].value,
                    contact_name.value["FirstName"].confidence,
                )
            )
            print(
                "Contact Last Name: {} has confidence: {}".format(
                    contact_name.value["LastName"].value,
                    contact_name.value["LastName"].confidence,
                )
            )
    company_names = business_card.fields.get("CompanyNames")
    if company_names:
        for company_name in company_names.value:
            print(
                "Company Name: {} has confidence: {}".format(
                    company_name.value, company_name.confidence
                )
            )
    departments = business_card.fields.get("Departments")
    if departments:
        for department in departments.value:
            print(
                "Department: {} has confidence: {}".format(
                    department.value, department.confidence
                )
            )
    job_titles = business_card.fields.get("JobTitles")
    if job_titles:
        for job_title in job_titles.value:
            print(
                "Job Title: {} has confidence: {}".format(
                    job_title.value, job_title.confidence
                )
            )
    emails = business_card.fields.get("Emails")
    if emails:
        for email in emails.value:
            print("Email: {} has confidence: {}".format(email.value, email.confidence))
    websites = business_card.fields.get("Websites")
    if websites:
        for website in websites.value:
            print(
                "Website: {} has confidence: {}".format(
                    website.value, website.confidence
                )
            )
    addresses = business_card.fields.get("Addresses")
    if addresses:
        for address in addresses.value:
            print(
                "Address: {} has confidence: {}".format(
                    address.value, address.confidence
                )
            )
    mobile_phones = business_card.fields.get("MobilePhones")
    if mobile_phones:
        for phone in mobile_phones.value:
            print(
                "Mobile phone number: {} has confidence: {}".format(
                    phone.content, phone.confidence
                )
            )
    faxes = business_card.fields.get("Faxes")
    if faxes:
        for fax in faxes.value:
            print(
                "Fax number: {} has confidence: {}".format(fax.content, fax.confidence)
            )
    work_phones = business_card.fields.get("WorkPhones")
    if work_phones:
        for work_phone in work_phones.value:
            print(
                "Work phone number: {} has confidence: {}".format(
                    work_phone.content, work_phone.confidence
                )
            )
    other_phones = business_card.fields.get("OtherPhones")
    if other_phones:
        for other_phone in other_phones.value:
            print(
                "Other phone number: {} has confidence: {}".format(
                    other_phone.value, other_phone.confidence
                )
            )
    print("----------------------------------------")
