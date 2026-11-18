"""고용24 채용정보 상세(callTp=D)를 받아 스펙박스 postings 양식(JSON)으로 바꾼다.

사용법:
    python fetch_posting.py <구인인증번호>            # API 호출
    python fetch_posting.py --file sample.xml       # 저장해 둔 XML로 테스트
인증키는 환경변수 WORK24_KEY_RECRUIT(.env)에서 읽는다.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

DETAIL_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210D01.do"
SOURCE_URL = ("https://www.work24.go.kr/wk/a/b/1500/empDetailAuthView.do"
              "?wantedAuthNo={no}&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet")

# 제출서류 자유 텍스트 → doc_type (위에서부터 먼저 맞는 것 하나)
DOC_RULES = [
    ("graduation_expected", r"졸업\s*\(?\s*예정"),
    ("graduation", r"졸업\S*\s*증명"),
    ("enrollment", r"재학\s*증명"),
    ("transcript", r"성적\s*증명"),
    ("english_speaking", r"OPIc|오픽|토익\s*스피킹|TOEIC\s*Speaking|토스"),
    ("english_score", r"TOEIC|토익|TOEFL|토플|TEPS|텝스|어학"),
    ("certificate", r"자격증|자격\s*면허"),
    ("portfolio", r"포트폴리오|portfolio"),
    ("resume", r"이력서|자기\s*소개서|자소서"),
]


def text(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


def parse_deadline(raw):
    """'2026-11-30', '20261130', '2026.11.30' 등을 YYYY-MM-DD로. '채용시까지' 등은 None."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 8:
        try:
            return datetime.strptime(digits[:8], "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def parse_required_docs(submit_doc):
    """제출서류 원문을 쉼표·줄바꿈 등으로 나눠 doc_type 목록으로 바꾼다."""
    if not submit_doc:
        return []
    global_months = re.search(r"(\d+)\s*개월", submit_doc)
    items, seen = [], set()
    for part in re.split(r"[,\n/·ㆍ;]+", submit_doc):
        part = part.strip()
        if not part:
            continue
        doc_type = next((t for t, p in DOC_RULES if re.search(p, part, re.I)), "other")
        rule = {}
        months = re.search(r"(\d+)\s*개월", part) or global_months
        if doc_type in ("graduation", "graduation_expected", "enrollment", "transcript") and months:
            rule["issued_within_months"] = int(months.group(1))
        if doc_type == "certificate":
            rule["name"] = part
        if doc_type == "other":
            rule["text"] = part
        key = (doc_type, json.dumps(rule, ensure_ascii=False))
        if key not in seen:
            seen.add(key)
            items.append({"doc_type": doc_type, "rule": rule})
    return items


def join(*parts):
    vals = [p for p in parts if p]
    return "\n".join(vals) if vals else None


def to_posting(xml_text):
    root = ET.fromstring(xml_text)
    dtl = root if root.tag == "wantedDtl" else root.find(".//wantedDtl")
    if dtl is None:
        raise ValueError("wantedDtl 요소가 없음: " + xml_text[:300])
    w = dtl.find("wantedInfo")
    no = text(dtl, "wantedAuthNo")
    submit_doc = text(w, "submitDoc")
    return {
        "source": "worknet",
        "source_id": no,
        "company": text(dtl, "corpInfo/corpNm"),
        "title": text(w, "wantedTitle"),
        "deadline": parse_deadline(text(w, "receiptCloseDt")),
        "deadline_raw": text(w, "receiptCloseDt"),
        "jobs_cd": text(w, "jobsCd"),
        "enter_tp_cd": text(w, "enterTpCd"),
        "requirements_text": join(
            text(w, "jobCont"), text(w, "eduNm"), text(w, "major"),
            text(w, "forLang"), text(w, "certificate"), text(w, "compAbl")),
        "preferred_text": join(text(w, "pfCond"), text(w, "etcPfCond")),
        "submit_doc_raw": submit_doc,
        "required_docs": parse_required_docs(submit_doc),
        "keywords": [k.text.strip() for k in w.findall("keywordList/srchKeywordNm")
                     if k.text and k.text.strip()],
        "url": SOURCE_URL.format(no=no),
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def fetch(wanted_auth_no):
    key = os.environ.get("WORK24_KEY_RECRUIT")
    if not key:
        sys.exit("WORK24_KEY_RECRUIT 환경변수가 없음 (.env 확인)")
    params = {"authKey": key, "callTp": "D", "returnType": "XML",
              "wantedAuthNo": wanted_auth_no, "infoSvc": "VALIDATION"}
    r = requests.get(DETAIL_URL, params=params, timeout=15)
    r.raise_for_status()
    return r.text


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if len(sys.argv) == 3 and sys.argv[1] == "--file":
        xml_text = open(sys.argv[2], encoding="utf-8").read()
    elif len(sys.argv) == 2:
        xml_text = fetch(sys.argv[1])
    else:
        sys.exit(__doc__)
    print(json.dumps(to_posting(xml_text), ensure_ascii=False, indent=2))
