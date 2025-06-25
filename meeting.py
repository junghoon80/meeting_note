import streamlit as st
import assemblyai as aai
import google.generativeai as genai
import tempfile
import datetime
import re
import os

# API 키 불러오기
ASSEMBLYAI_API_KEY = st.secrets["GOOGLE_API_KEY"]  # 기존 Google API 키 자리에 넣음
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# AssemblyAI, Gemini 설정
aai.settings.api_key = ASSEMBLYAI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# 오늘 날짜
current_date = datetime.date.today().strftime("%Y년 %m월 %d일")

st.set_page_config(page_title="AI 회의록 요약 도구", page_icon="📝", layout="wide")

st.title(f"🤖 AI 회의록 요약 도구 ({current_date})")
st.markdown("음성, 텍스트 파일, 직접 입력을 통합해 AI가 자동으로 요약해 드립니다.")

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

# AssemblyAI 음성 인식 함수
def process_audio(audio_file):
    with st.spinner("음성 파일 업로드 및 분석 중..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_file.read())
            tmp_path = tmp.name
        
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(tmp_path)
        
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        return transcript.text

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

# Gemini 요약 생성 함수
def generate_summary(text):
    prompt = f"""
    다음은 통합된 회의록 내용입니다:
    ---
    {text}
    ---
    
    아래 조건에 따라 회의록을 요약해 주세요:
    1. 회의 내용을 10개 항목으로 간결하게 정리
    2. 마지막에 액션 아이템을 별도로 정리
    3. 중복된 내용은 제거하고 [중복] 표시
    4. 한국어로 작성
    5. 전문적인 비즈니스 문체 사용
    """
    response = model.generate_content(prompt)
    return response.text

# UI - 파일 업로드 및 직접 입력
col1, col2 = st.columns(2)

with col1:
    st.subheader("음성 파일 업로드")
    audio_file = st.file_uploader("회의 녹음 파일 (MP3, WAV 등)", type=["mp3", "wav", "m4a"], key="audio_uploader")
    if audio_file:
        st.audio(audio_file)
        if st.button("음성 → 텍스트 변환", key="audio_btn"):
            st.session_state.transcript = process_audio(audio_file)
            st.success("음성 파일 분석 완료!")

with col2:
    st.subheader("텍스트 파일 업로드")
    text_file = st.file_uploader("텍스트 파일 (TXT)", type=["txt"], key="text_uploader")
    if text_file:
        st.session_state.text_content = text_file.getvalue().decode("utf-8")
        st.success("텍스트 파일 로드 완료!")

st.subheader("직접 입력")
st.session_state.direct_input = st.text_area("회의 내용을 직접 입력하세요", height=200, key="direct_input")

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
    
    st.session_state.summary = generate_summary(st.session_state.combined_text)

# 결과 표시 및 다운로드
if st.session_state.combined_text:
    st.divider()
    st.subheader("통합 회의 내용")
    with st.expander("전체 내용 보기"):
        st.write(st.session_state.combined_text)
    st.download_button(
        label="통합 회의록 다운로드",
        data=st.session_state.combined_text,
        file_name=f"통합_회의록_{current_date.replace(' ', '')}.txt",
        mime="text/plain"
    )

if st.session_state.summary:
    st.divider()
    st.subheader("AI 요약 결과")
    st.write(st.session_state.summary)
    st.download_button(
        label="요약본 다운로드",
        data=st.session_state.summary,
        file_name=f"회의_요약_{current_date.replace(' ', '')}.txt",
        mime="text/plain"
    )

if st.session_state.transcript:
    st.divider()
    st.download_button(
        label="음성 텍스트 다운로드",
        data=st.session_state.transcript,
        file_name=f"음성_텍스트_{current_date.replace(' ', '')}.txt",
        mime="text/plain"
    )

# 사이드바 안내
with st.sidebar:
    st.header("사용 방법")
    st.markdown("""
    1. 음성 파일/텍스트 파일 업로드 또는 직접 입력
    2. "회의록 통합 및 요약 생성" 버튼 클릭
    3. AI가 생성한 요약 결과 확인
    4. 필요한 내용 다운로드
    """)
    st.header("기능 특징")
    st.markdown("""
    - AssemblyAI 음성 인식 사용
    - Gemini 2.5 Flash 기반 회의록 요약
    - 중복 문장 자동 제거 및 표시
    - 10개 항목 요약 및 액션 아이템 별도 정리
    - 결과 파일 다운로드 지원
    """)
    if st.button("초기화"):
        st.session_state.clear()
        st.rerun()
