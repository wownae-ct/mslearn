# MSLearn — Microsoft Learn 실습 모음

Azure OpenAI / AI Agents(Foundry) / Document Intelligence / AI Speech 관련 MS Learn 랩 파일들을 모아둔 저장소입니다.

- `mslearn-openai/` — Azure OpenAI 실습
- `mslearn-ai-agents/` — Azure AI Agents / Foundry / A2A 실습
- `document-intelligence/` — Azure Document Intelligence 실습 (OCR / 영수증 / 명함 / 신분증 / 송장 / 레이아웃)
- `mslearn-ai-speech/` — Azure AI Speech 실습 (STT / TTS / 번역)

## 주제

- Azure Open AI
- Azure AI Search
- Azure Foundry
- Azure AI-Agent
- Azure Document Intelligence
- Azure AI Speech

---

## ⚠️ 먼저 알아둘 것

- **가상환경(venv)은 저장소에 포함되지 않습니다.** `labenv/`, `.venv/` 등은 `.gitignore`로 제외됩니다. 클론 후 **직접 환경을 새로 만들어야** 합니다.
- **하나의 venv로 모든 랩을 돌릴 수 없습니다.** 랩마다 의존성 버전이 충돌하기 때문입니다. 특히:
  - `09-build-remote-agents-with-a2a` → **`a2a-sdk==0.3.26`** 필요
  - `07-agent-framework`, `08-agent-orchestration` (agent-framework) → **`a2a-sdk>=1.0`** 필요
  - 둘은 같은 venv에서 공존 불가 → **랩(또는 폴더)별로 venv를 분리**하세요.
- **각 랩 폴더의 `requirements.txt`가 정답(source of truth)입니다.** (버전이 올바르게 고정되어 있음)
- **비밀정보는 `.env`에 넣고 커밋하지 마세요.** 각 랩에 `.env.example`이 있으니 복사해서 채우면 됩니다. (`.env`는 `.gitignore`로 제외됨)

---

## 셋업 (클론 후)

### 0) 루트 uv 환경 (신규 랩: `document-intelligence`, `mslearn-ai-speech`)

루트에 `pyproject.toml` + `uv.lock`이 있어 [uv](https://docs.astral.sh/uv/)로 한 번에 설치됩니다.

```powershell
uv sync
# 사내 프록시 등으로 TLS 인증서 오류가 나면:
uv sync --native-tls
```

> 이 환경은 `document-intelligence` / `mslearn-ai-speech` 및 일반 스크립트용입니다.
> **agent 랩(07·08·09 등)은 의존성 충돌**(아래 참고) 때문에 이 환경으로 돌리지 말고, 해당 랩의 `requirements.txt`로 **랩별 venv**를 따로 만드세요.
> 패키지를 추가할 땐 `uv add <패키지명>` 한 번이면 `pyproject.toml`·`uv.lock`·`.venv`가 함께 갱신됩니다.

### 1) Azure OpenAI 실습 (`mslearn-openai`)

openai 랩들은 의존성이 동일해서 **하나의 venv**로 충분합니다.

```powershell
cd mslearn-openai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 각 랩의 .env 설정
copy Labfiles\<랩폴더>\Python\.env.example Labfiles\<랩폴더>\Python\.env
# .env 안의 값(엔드포인트/키 등)을 채운 뒤 실행
```

### 2) Azure AI Agents 실습 (`mslearn-ai-agents`)

랩마다 의존성이 다르므로 **랩별로 venv를 만드는 것을 권장**합니다.

```powershell
cd mslearn-ai-agents\Labfiles\<랩폴더>\Python   # 일부 랩은 python\ (소문자)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# .env 설정
copy .env.example .env
# .env 값 채운 뒤 실행 (예: python run_all.py)
```

> 예) lab 09 실행:
> ```powershell
> cd mslearn-ai-agents\Labfiles\09-build-remote-agents-with-a2a\python
> python -m venv .venv; .venv\Scripts\activate
> pip install -r requirements.txt    # a2a-sdk 0.3.26 설치됨
> python run_all.py
> ```

### 3) Azure Document Intelligence 실습 (`document-intelligence`)

문서 종류별로 폴더가 나뉘어 있고, 각 폴더가 Document Intelligence의 `prebuilt-*` 모델을 호출합니다. **루트 uv 환경(0번)** 으로 실행합니다.

```powershell
cd document-intelligence\ocr
copy .env.example .env
#   YOUR_FORM_RECOGNIZER_ENDPOINT / _KEY 채우기
#   total*.py(Blob 컨테이너 일괄 분석)는 AZURE_BLOB_CONTAINER_URL / AZURE_CONTAINER_SAS_TOKEN 도 필요
uv run ocr-local.py          # uv가 루트 pyproject를 찾아 실행 (결과 CSV는 ..\data\ 에 저장)
```

| 폴더 | 모델 | 내용 |
|---|---|---|
| `ocr/` | `prebuilt-read` | 이미지·문서 OCR (`ocr-local.py` 로컬 / `ocr-url.py` URL / `sample.ipynb` Gradio UI) |
| `receipts/` | `prebuilt-receipt` | 영수증 |
| `invoice/` | `prebuilt-invoice` | 송장 |
| `businesscard/` | `prebuilt-businessCard` | 명함 |
| `Identity/` | `prebuilt-idDocument` | 신분증 |
| `creditcard/` | `prebuilt-creditCard` | 신용카드 |
| `layout/` | `prebuilt-layout` | 레이아웃(표·구조 추출) |
| `general/` | `prebuilt-document` / `prebuilt-invoice` | 일반 문서 |
| `total*.py` | 여러 모델 | Blob 컨테이너 문서 일괄 분석(SAS 토큰 필요) |

> 각 폴더의 `test-data/`에 샘플 이미지가 들어 있습니다. `ocr/sample.ipynb`의 키도 `.env`에서 읽어오도록 되어 있습니다(하드코딩 아님).

### 4) Azure AI Speech 실습 (`mslearn-ai-speech`)

`azure-cognitiveservices-speech` 기반 음성 실습입니다. **루트 uv 환경(0번)** 으로 실행합니다.

```powershell
cd mslearn-ai-speech
copy .env.example .env
#   SPEECH_KEY / ENDPOINT 채우기
uv run tts.py
```

| 파일 | 내용 |
|---|---|
| `stt.py`, `stt2.py` | STT (음성 → 텍스트) |
| `batch-stt.py` | 오디오 파일 배치 STT |
| `tts.py`, `tts2.py`, `speech_synthesis*.py` | TTS (텍스트 → 음성) |
| `translate.py`, `translate2.py` | 음성 번역 |
| `to-way.py`, `to-way2.py` | 실시간 양방향 통역 (ko↔en, 인식 → 번역 → TTS) |

> `batch-stt.py`는 입력으로 `record.m4a`를 참조하지만, 이 오디오는 개인 파일이라 저장소에 포함되지 않습니다(`.gitignore`). 본인 오디오 파일 경로로 바꿔 실행하세요. 결과는 `mslearn-ai-speech\data\` 에 저장됩니다.

---

## 트러블슈팅

**`ModuleNotFoundError: No module named 'a2a.server.apps'` (lab 09)**
설치된 `a2a-sdk`가 1.x 버전입니다. lab 09는 0.3.26이 필요합니다. 해당 랩 전용 venv에서:
```powershell
pip install "a2a-sdk==0.3.26"
```
agent-framework를 같은 venv에 설치하면 `a2a-sdk`가 1.x로 올라가 이 에러가 다시 발생하니, **lab 09는 별도 venv**로 두세요.
