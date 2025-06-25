import streamlit as st
import assemblyai as aai
import google.generativeai as genai
import tempfile
import datetime
import re
import os

# API 키 설정
ASSEMBLYAI_API_KEY = st.secrets["ASSEMBLYAI_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

aai.settings.api_key = ASSEMBLYAI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

current_date = datetime.date.today().strftime("%Y년 %m월 %d일")

st.set_page_config(page_title="AI 회의록 요약 도구", page_icon="📝", layout="wide")
st.title(f"🤖 회의록 요약 ({current_date})")
st.markdown("음성, 텍스트 파일, 직접 입력 통합 | STT 최적화 적용")

# 세션 상태 초기화
if 'transcript' not in st.session_state:
    st.session_state.transcript = ""
if 'text_content' not in st.session_state:
    st.session_state.text_content = ""
if 'direct_input' not in st.session_state:
    st.session_state.direct_input = ""
if 'combined_text' not in st.session_state:
    st.session_state.combined_text = ""
if 'summary' not in st.session_state:
    st.session_state.summary = ""
if 'audio_processed' not in st.session_state:
    st.session_state.audio_processed = False
if 'md_head' not in st.session_state:
    st.session_state.md_head = ""
if 'md_body' not in st.session_state:
    st.session_state.md_body = ""
if 'md_action' not in st.session_state:
    st.session_state.md_action = ""

# STT 처리 함수
def process_audio(audio_file):
    with st.spinner("음성 인식 중..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_file.read())
            tmp_path = tmp.name
        
        transcriber = aai.Transcriber()
        config = aai.TranscriptionConfig(
            language_code="ko",
            speaker_labels=True,
            audio_start_from=500
        )
        transcript = transcriber.transcribe(tmp_path, config=config)
        
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if transcript.status == aai.TranscriptStatus.error:
            return f"오류 발생: {transcript.error}"
        
        if transcript.utterances:
            return "\n\n".join([f"화자 {u.speaker}: {u.text}" for u in transcript.utterances])
        return transcript.text

# STT 결과 사후교정
def correct_transcript(transcript):
    prompt = f"""
    [한국어 전문가 시스템]
    다음은 회의 녹음의 STT(음성 인식) 결과입니다. 이 결과에는 오류가 있을 수 있습니다.
    아래 지침에 따라 원본 내용을 손상시키지 않으면서 정확하고 자연스러운 한국어로 교정해 주세요:
    1. 잘못 인식된 단어, 특히 기술 용어, 고유 명사, 숫자 등을 정정하세요.
    2. 표준 한국어 문법과 띄어쓰기를 준수하도록 수정하세요.
    3. 원본의 의미를 변경하지 마세요. 원본에 없는 내용을 추가하지 마세요.
    4. 회의 내용의 전문성을 유지하되, 비문이나 오류를 자연스럽게 고치세요.
    
    STT 텍스트:
    {transcript}
    
    교정된 텍스트:
    """
    with st.spinner("AI가 STT 결과 교정 중..."):
        response = model.generate_content(prompt)
    return response.text

# 중복 제거 함수
def remove_duplicates(text_list):
    seen = set()
    unique_texts = []
    duplicates = []
    for text in text_list:
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
        for sentence in sentences:
            clean_sentence = sentence.strip()
            if clean_sentence:
                if clean_sentence not in seen:
                    unique_texts.append(clean_sentence)
                    seen.add(clean_sentence)
                else:
                    duplicates.append(clean_sentence)
    return "\n".join(unique_texts), duplicates

# Gemini 요약 생성 함수 (Head/Body/Action 분리)
def generate_summary_and_md(text):
    prompt = f"""
    다음은 통합된 회의록 내용입니다:
    ---
    {text}
    ---
    아래 조건에 따라 회의록을 요약해 주세요:
    1. 회의 제목, 일시, 참석자 등 헤드라인 정보를 먼저 정리 (헤드)
    2. 회의 주요 논의 내용과 결정사항을 10개 항목 이내로 간결하게 정리 (본문)
    3. 마지막에 액션 아이템을 별도로 정리 (액션 아이템)
    4. 각 부분을 아래와 같이 구분해서 출력하세요.

    [헤드]
    (헤드라인 정보)

    [본문]
    (주요 논의 내용/결정사항)

    [액션 아이템]
    (액션 아이템 리스트)
    """
    with st.spinner("AI가 회의록 요약 중..."):
        response = model.generate_content(prompt)
    # 결과 파싱
    head, body, action = "", "", ""
    result = response.text
    head_match = re.search(r"\[헤드\](.*?)(\[본문\]|\Z)", result, re.DOTALL)
    body_match = re.search(r"\[본문\](.*?)(\[액션 아이템\]|\Z)", result, re.DOTALL)
    action_match = re.search(r"\[액션 아이템\](.*)", result, re.DOTALL)
    if head_match:
        head = head_match.group(1).strip()
    if body_match:
        body = body_match.group(1).strip()
    if action_match:
        action = action_match.group(1).strip()
    return head, body, action

# 마크다운 문서 생성 함수
def format_markdown_document(head: str, body: str, action_items: str) -> str:
    md = f"""
# 회의록 요약 문서

---

## 헤드

{head}

---

## 본문

{body}

---

## 액션 아이템

{action_items}

---
"""
    return md

# 파일 업로드 및 직접 입력 UI
col1, col2 = st.columns(2)

with col1:
    st.subheader("음성 파일 업로드")
    audio_file = st.file_uploader("회의 녹음 파일 (MP3, WAV 등)", type=["mp3", "wav", "m4a"], key="audio_uploader")
    
    if audio_file:
        st.audio(audio_file)
        if st.button("음성 → 텍스트 변환", key="audio_btn"):
            raw_transcript = process_audio(audio_file)
            st.session_state.transcript = correct_transcript(raw_transcript)
            st.session_state.audio_processed = True
            st.success("음성 파일 분석 완료!")

with col2:
    st.subheader("텍스트 파일 업로드")
    text_file = st.file_uploader("텍스트 파일 (TXT)", type=["txt"], key="text_uploader")
    if text_file:
        st.session_state.text_content = text_file.getvalue().decode("utf-8")
        st.success("텍스트 파일 로드 완료!")

# 직접 입력
st.subheader("직접 입력")
st.text_area(
    "회의 내용을 직접 입력하세요",
    value=st.session_state.direct_input,
    height=200,
    key="direct_input"
)

# 통합 및 요약 생성
if st.button("회의록 통합 및 요약 생성", type="primary", use_container_width=True):
    inputs = []
    if st.session_state.transcript:
        inputs.append(st.session_state.transcript)
    if st.session_state.text_content:
        inputs.append(st.session_state.text_content)
    if st.session_state.direct_input:
        inputs.append(st.session_state.direct_input)

    if not inputs:
        st.warning("입력된 내용이 없습니다!")
        st.stop()

    combined_text, duplicates = remove_duplicates(inputs)
    st.session_state.combined_text = combined_text

    if duplicates:
        st.session_state.combined_text += "\n\n[중복 제거된 내용: " + ", ".join(set(duplicates)) + "]"

    # Head/Body/Action 분리 요약
    head, body, action = generate_summary_and_md(st.session_state.combined_text)
    st.session_state.md_head = head
    st.session_state.md_body = body
    st.session_state.md_action = action
    st.session_state.summary = format_markdown_document(head, body, action)

# 결과 및 다운로드
if st.session_state.summary:
    st.divider()
    st.subheader("AI 요약 결과 (마크다운)")
    st.markdown(st.session_state.summary)
    st.download_button(
        label="마크다운 회의록 다운로드",
        data=st.session_state.summary,
        file_name=f"회의록_{current_date.replace(' ', '')}.md",
        mime="text/markdown"
    )

if st.session_state.transcript and st.session_state.audio_processed:
    st.divider()
    st.download_button(
        label="음성 텍스트 다운로드 (교정됨)",
        data=st.session_state.transcript,
        file_name=f"음성_텍스트_{current_date.replace(' ', '')}.txt",
        mime="text/plain"
    )

# 사이드바 안내
with st.sidebar:
    st.header("고급 처리 기능")
    st.markdown("""
    - **AssemblyAI 음성 인식**: 한국어 최적화
    - **Gemini 사후교정**: STT 결과 정확도 향상
    - **중복 문장 자동 제거**: 문장 단위 중복 처리
    - **AI 요약**: 헤드/본문/액션 아이템 구분, 마크다운 문서로 다운로드
    """)
    
    st.header("사용 방법")
    st.markdown("""
    1. 음성/텍스트 파일 업로드 또는 직접 입력
    2. "회의록 통합 및 요약 생성" 버튼 클릭
    3. AI가 생성한 요약 결과 확인
    4. 마크다운 파일로 다운로드
    """)
    
    if st.button("초기화"):
        st.session_state.clear()
        st.rerun()
