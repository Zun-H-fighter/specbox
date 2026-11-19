# 스펙박스 B 담당 가이드: 서류 금고 · 체크리스트 · 알림

> 레포의 `docs/ROLE_B.md`에 두고 같이 고쳐 가며 쓰는 문서.
> 데이터 양식의 기준은 팀 문서 "스펙박스 역할 분담과 데이터 양식"이고, 이 문서와 다르면 팀 문서를 따른다.

## 1. B가 맡는 범위 한눈에

| 구분 | 내용 |
|---|---|
| 기능 | 서류 금고, 제출서류 체크리스트 대조, 마감·재발급·재응시 알림 |
| 만드는 화면 | 서류 금고(목록·업로드), 공고 상세의 체크리스트 영역, 알림 예정 영역 |
| 맡는 AWS | S3 원본 버킷 + 버킷 정책 + VPC Endpoint, KMS 암호화, SNS 이메일, SQS DLQ, 알림 중복 방지 |
| 시연 담당 | ① 처리 실패 시 DLQ 격리 ② 웹 서버 침해 가정 시 원본 읽기·DB 접속 차단 |
| A와 만나는 지점 | A가 저장하는 `postings.required_docs` (B는 읽기만 한다) |

## 2. 로컬 개발 시작하기 (처음 한 번)

```bash
gh repo clone <준혁 아이디>/specbox && cd specbox
cp .env.example .env              # 고용24 키는 본인 것으로 따로 발급해서 채움
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
docker compose exec db mysql -uspecbox -pspecbox-local specbox -e "SHOW TABLES;"   # 7개
git switch -c feat/vault          # B 작업 브랜치, main에는 PR로만
```

- WSL에서 `python3 -m venv`가 안 되면 `sudo apt install -y python3-venv`.
- `docker`가 안 잡히면 Docker Desktop → Settings → Resources → WSL integration에서 쓰는 배포판을 켜고 `wsl --shutdown`.
- 로컬에선 `STORAGE_MODE=local`로 파일을 `./.storage/`에 저장한다. AWS로 갈 때 `s3`로만 바꾸면 되게 저장 함수를 한 곳에 모아 둔다.

## 3. B가 쓰는 테이블

| 테이블 | B가 하는 일 |
|---|---|
| `postings` | **읽기만**. `required_docs`, `deadline`, `url` 사용 |
| `documents` | 서류 금고. 업로드·수정·삭제 |
| `applications` | "지원 건으로 등록" 시 생성 |
| `checklist_items` | 지원 건 생성 시 `required_docs`로 만들고, 대조 결과를 `state`에 저장 |
| `notifications` | 알림 예약과 발송 기록, `dedup_key`로 중복 방지 |

### `required_docs` 예시 (A가 만들어 주는 값)

```json
[
  {"doc_type": "graduation_expected", "rule": {"issued_within_months": 3}},
  {"doc_type": "english_score", "rule": {"any_of": [{"test": "TOEIC", "min": 700}]}},
  {"doc_type": "english_speaking", "rule": {"any_of": [{"test": "OPIc", "min": "IM2"}, {"test": "TOEIC_SPEAKING", "min": "IM3"}]}},
  {"doc_type": "certificate", "rule": {"name": "정보처리기사 자격증 사본"}},
  {"doc_type": "other", "rule": {"text": "건강검진서"}}
]
```

- 고용24 원문이 자유 텍스트라 A의 파서가 못 알아본 항목은 `other` + `rule.text`로 온다.
- 개발 초기엔 A 작업을 기다리지 말고 `postings`에 `source='sample'`로 샘플 공고를 직접 넣어서 쓴다.

## 4. 체크리스트 대조 규칙 (핵심 로직)

기준일은 공고 마감일(`deadline`), 마감일이 없으면 오늘이다.

| doc_type | 판정 |
|---|---|
| `resume`, `portfolio` | 금고에 있으면 `ready`, 없으면 `missing` |
| `graduation`, `graduation_expected`, `enrollment`, `transcript` | 없으면 `missing`. `rule.issued_within_months`가 있고 `issued_on`이 기준일보다 그 개월 수 이전이면 `reissue_needed`, 아니면 `ready` |
| `english_score`, `english_speaking` | `rule.any_of` 중 하나라도 만족하는 성적이 있으면 `ready`. 성적은 있는데 `expires_on`이 기준일 전이거나 점수가 `min` 미달이면 `retest_needed`. 해당 시험 성적이 아예 없으면 `missing` |
| `certificate` | `rule.name`과 서류 `title`을 비교(부분 일치)해서 있으면 `ready`, 없으면 `missing` |
| `other` | 자동 판정 안 함. 기본 `missing`, 사용자가 직접 `ready`로 바꿀 수 있게 |

등급형 점수 비교 순서(낮음 → 높음). **공식 등급표로 한 번 확인할 것.**
- OPIc: `NL < NM < NH < IL < IM1 < IM2 < IM3 < IH < AL`
- TOEIC Speaking: `NL < NM < NH < IL < IM1 < IM2 < IM3 < IH < AL < AM < AH`

### 구현 뼈대 (직접 채우기)

```python
# app/checklist.py
from datetime import date

def months_before(base: date, months: int) -> date:
    # TODO B-1: base에서 months개월 전 날짜 (말일 처리 주의: 5/31의 3개월 전)
    ...

def judge_item(item: dict, docs: list[dict], base: date) -> tuple[str, int | None]:
    """item: required_docs의 원소, docs: 이 사용자의 documents 행들
    반환: (state, 매칭된 document_id 또는 None)"""
    # TODO B-2: doc_type이 같은 서류만 고르기 (certificate는 rule.name 부분 일치)
    # TODO B-3: 증명서류 — issued_within_months 규칙으로 ready / reissue_needed
    # TODO B-4: 어학 — any_of 순회, 만료일·최소 점수 비교 (등급형은 순서 리스트의 index로)
    # TODO B-5: 여러 장이 맞으면 가장 최근 것(issued_on 또는 expires_on 기준) 선택
    ...

def build_checklist(application_id: int) -> None:
    # TODO B-6: application → posting.required_docs 읽기
    # TODO B-7: 항목마다 judge_item 호출, checklist_items에 INSERT (재계산 시 기존 행 갱신)
    ...
```

`judge_item`은 DB 없이 돌아가는 순수 함수로 두고 `tests/test_checklist.py`에 경우별 테스트를 먼저 쓰면 편하다(프로토타입 화면의 5가지 상태가 그대로 테스트 케이스).

## 5. 알림 규칙

| kind | 언제 | 조건 |
|---|---|---|
| `deadline_d3` | 마감 3일 전 09:00 (KST) | 지원 건 `active` |
| `deadline_d1` | 마감 1일 전 09:00 | 지원 건 `active` |
| `reissue_reminder` | `reissue_needed`가 생긴 다음 날 09:00 | 마감 전일 때만 |
| `retest_reminder` | `retest_needed`가 생긴 다음 날 09:00 | 마감 전일 때만 |

- DB엔 UTC로 저장하므로 09:00 KST = 00:00 UTC.
- `dedup_key = "{application_id}:{kind}:{send_on}"` — UNIQUE라서 같은 알림을 두 번 INSERT하면 DB가 막아 준다. **INSERT 실패를 "이미 예약됨"으로 처리**하는 게 멱등성 패턴의 핵심.
- 발송은 매일 정해진 시각에 `send_notifications` 작업이 SQS로 들어오면 Worker가 `send_on = 오늘`이고 `sent_at IS NULL`인 행을 보내고 `sent_at`을 채운다.
- 로컬에선 SNS 대신 콘솔 출력(또는 파일 기록)으로 발송을 흉내 낸다.

```python
# worker/notify.py
# TODO B-8: 지원 건 하나에 대한 알림 행 만들기 (dedup_key 충돌은 무시)
# TODO B-9: 오늘 보낼 알림 조회 → 발송 함수 호출 → sent_at 갱신
# TODO B-10: 발송 함수는 NOTIFY_MODE=console|sns 로 나눠 두기
```

## 6. 서류 금고

- 업로드 시 입력: 서류 종류(`doc_type`), 제목, 발급일 또는 유효기간 만료일, 어학이면 점수(`score_value`), 포트폴리오는 파일 대신 링크(`link_url`)도 허용.
- 파일 저장 경로: `{user_id}/{document_id}.{확장자}` (S3에선 `specbox-originals-*` 버킷).
- **주민등록번호는 어떤 필드에도 저장하지 않는다.** 시연은 가짜 서류로만.
- 서류가 추가·수정되면 그 사용자의 `active` 지원 건 체크리스트를 다시 계산한다(`build_checklist` 재호출).

```python
# app/storage.py
# TODO B-11: save_file(user_id, document_id, fileobj, ext) — local이면 .storage/, s3면 boto3 put_object
# TODO B-12: 원본 다운로드 함수는 만들지 않는다 (Service에서 원본 읽기는 버킷 정책으로 막힘). 미리보기가 필요하면 별도로 상의
```

## 7. 화면에 꼭 들어가야 하는 것

- 공고 상세에 **"채용정보 제공사이트로 이동"** 버튼 (`postings.url`로 연결) — 고용24 이용 조건
- 공고 상세 하단에 출처 문구: "본 자료는 고용노동부 고용24(www.work24.go.kr)에서 제공된 정보이며, 무단복제 및 배포를 금지합니다."
- 체크리스트: 진행률("7개 중 4개 준비됨"), 상태 배지 4종, 행동 버튼(재발급 일정 등록 / 금고에 업로드 / 시험 일정 보기)
- 알림 예정 목록

## 8. AWS 단계에서 B가 할 일 (로컬 기능이 돌아간 뒤)

| 순서 | 할 일 | 완료 기준 |
|---|---|---|
| 1 | 원본 버킷 정책 적용(구축 가이드 5단계) | Web에서 업로드 OK, 다운로드 `AccessDenied` |
| 2 | Processing의 S3 Gateway Endpoint로 원본 읽기 | Processing 인스턴스에서 다운로드 OK |
| 3 | SSE-KMS(AWS 관리형 키) 테스트 | 업로드 후 객체 암호화 표시 확인, 안 되면 SSE-S3 유지하고 기록 |
| 4 | SNS 토픽 + 이메일 구독 | 테스트 메일 수신 |
| 5 | DLQ 시연 준비 | 일부러 실패하는 작업을 넣어 3회 후 DLQ로 이동 |
| 6 | 침해 가정 테스트 1·2·4번 | 결과 스크린샷과 명령어 기록 |

## 9. 1주 단위 목표

| 주 | 목표 |
|---|---|
| 1주 | 서류 금고 CRUD(로컬 저장), `judge_item` 테스트 통과 |
| 2주 | 지원 건 등록 → 체크리스트 생성·재계산, 화면 연결 |
| 3주 | 알림 예약·발송(콘솔), AWS 버킷 정책·SNS·DLQ 적용 |
| 4주 | 침해 가정·DLQ 시연 리허설, 화면 다듬기 |

## 10. 막히면 정할 것 / 열린 질문

- 등급형 점수 순서표 공식 확인 (OPIc, TOEIC Speaking)
- `other` 항목을 사용자가 직접 체크하는 UI를 MVP에 넣을지
- 체크리스트 기준일을 "마감일"로 할지 "사용자가 정한 제출 예정일"로 할지 (지금은 마감일)
- 공유 자원(VPC, 보안 그룹, RDS 스키마) 변경은 준혁이 담당 — 바꿀 일이 생기면 요청