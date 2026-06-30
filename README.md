# MSLearn — Microsoft Learn 실습 모음

Azure OpenAI / Azure AI Agents(Foundry) 관련 MS Learn 랩 파일들을 모아둔 저장소입니다.

- `mslearn-openai/` — Azure OpenAI 실습
- `mslearn-ai-agents/` — Azure AI Agents / Foundry / A2A 실습

## 주제

- Azure Open AI
- Azure AI Search
- Azure Foundry
- Azure AI-Agent

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

---

## 트러블슈팅

**`ModuleNotFoundError: No module named 'a2a.server.apps'` (lab 09)**
설치된 `a2a-sdk`가 1.x 버전입니다. lab 09는 0.3.26이 필요합니다. 해당 랩 전용 venv에서:
```powershell
pip install "a2a-sdk==0.3.26"
```
agent-framework를 같은 venv에 설치하면 `a2a-sdk`가 1.x로 올라가 이 에러가 다시 발생하니, **lab 09는 별도 venv**로 두세요.
