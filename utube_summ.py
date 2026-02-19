import streamlit as st
from pytubefix import YouTube
import whisper
import os
import google.generativeai as genai
import re
import random
from googleapiclient.discovery import build
from gtts import gTTS

# --- Configure Gemini and Youtube build---
genai.configure(api_key=MY_KEY)
youtube = build("youtube", "v3", developerKey="AIzaSyD9tRfLCKPB-BZSKUI1VLIzOrskC7uIjfY")

# --- Session state defaults ---
if "transcription" not in st.session_state:
    st.session_state.transcription = ""
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []
if "quiz_answers" not in st.session_state:
    st.session_state.quiz_answers = {}
if "graded" not in st.session_state:
    st.session_state.graded = False
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "transcript"

# --- Function definitions ---
def generate_summary_audio(summary_text, filename="summary.mp3"):
    tts = gTTS(text=summary_text, lang='en')
    tts.save(filename)
    return filename

def download_audio_from_youtube(url):
    yt = YouTube(url)
    stream = yt.streams.filter(only_audio=True).first()
    output_file = stream.download(filename='audio.mp4')
    return output_file

def transcribe_audio(file_path):
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]

def generate_summary(transcript):
    prompt = """
        Summarize the following video transcript in a clear and concise way.
        The summary should capture the main ideas and flow of the content, and should not be a list of bullet points.
        Keep it natural and easy to read, as if explaining to a friend.
        Transcript:
        """
    model = genai.GenerativeModel("gemini-2.0-flash") 
    response = model.generate_content(prompt + transcript)
    return response.text.strip()


def generate_quiz(transcript):
    prompt = """Given the video transcript below, generate 10 multiple-choice questions with the correct answer.
    Format:
    Question: This should be the question  
    correct_answer: [option_a]  
    other_options: [option_b, option_c, option_d]
    The option_a, option_b, option_c, option_d need to be replaced with the actual text.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(f"{prompt}\n\nTranscript:\n{transcript}")
    questions = []
    current = {}
    lines = response.text.strip().splitlines()
    for line in lines:
        if line.startswith("Question:"):
            if all(k in current for k in ("question", "correct_option", "options")):
                options = current["options"]
                if current["correct_option"] not in options:
                    options.append(current["correct_option"])
                random.shuffle(options)
                questions.append({
                    "question": current["question"],
                    "correct_option": current["correct_option"],
                    "shuffled_options": options
                })
            current = {
                "question": line.replace("Question:", "").strip()
            }
        elif line.startswith("correct_answer:"):
            correct = re.findall(r"\[(.*?)\]", line)
            if correct:
                current["correct_option"] = correct[0].strip()
        elif line.startswith("other_options:"):
            others = re.findall(r"\[(.*?)\]", line)
            if others:
                current["options"] = [opt.strip() for opt in others[0].split(",")]
    if all(k in current for k in ("question", "correct_option", "options")):
        options = current["options"]
        if current["correct_option"] not in options:
            options.append(current["correct_option"])
        random.shuffle(options)
        questions.append({
            "question": current["question"],
            "correct_option": current["correct_option"],
            "shuffled_options": options
        })
    return questions

@st.cache_data()
def extract_main_topic_area(transcript):
    prompt = """Given the video transcript below, briefly state the general subject area or context it belongs to (e.g., machine learning, climate change, public health, etc). Return only the topic area, not a sentence.
    Transcript:
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt + transcript)
    return response.text.strip()



def get_top_related_videos(keyword, max_results=3):
    request = youtube.search().list(
        q=keyword,
        part="snippet",
        type="video",
        maxResults=max_results
    )
    response = request.execute()
    videos = []
    for item in response["items"]:
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        videos.append((title, url))
    return videos


@st.cache_data(show_spinner="Generating explanation...")
def explain_answer(question, correct_answer):
    prompt = f"""Given the question below and its correct answer, explain why the answer is correct in 2-3 concise sentences.
    Question: {question}
    Correct Answer: {correct_answer}
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

# --- UI: App Layout ---
st.markdown("""
<h1 style='text-align: center;'>TL;DW</h1>
<p style='text-align: center; font-size: 16px; font-style: italic; color: gray;'>Too Long; Didn't Watch</p>
""", unsafe_allow_html=True)

url = st.text_input("Enter Your YouTube URL")
if url:
    st.video(url)

# --- Tab selection ---
st.markdown("### Choose an Action")
cols = st.columns(5)
with cols[0]:
    if st.button("Summarize"):
        st.session_state.active_tab = "summarize"
with cols[1]:
    if st.button("Key Topics"):
        st.session_state.active_tab = "topics"
with cols[2]:
    if st.button("Take Quiz"):
        st.session_state.active_tab = "quiz"
with cols[3]:
    if st.button("Full Transcript"):
        st.session_state.active_tab = "Transcript"
with cols[4]:
    if st.button("Related Videos"):
        st.session_state.active_tab = "related"


# processing video url 
if url and not st.session_state.transcription:
    with st.spinner("Processing video..."):
        try:
            audio_file = download_audio_from_youtube(url)
            st.session_state.transcription = transcribe_audio(audio_file)
            os.remove(audio_file)
            st.success("Video processed!")
        except Exception as e:
            st.error(f"Error processing video: {e}")

# --- Summary Tab ---
if st.session_state.active_tab == "summarize":
    st.header("Video Summary")
    if st.session_state.transcription:
        with st.spinner("Summarizing transcript..."):
            st.session_state.summary = generate_summary(st.session_state.transcription)
        if st.session_state.summary:
            st.write(st.session_state.summary)
            with st.spinner("Generating voiceover..."):
                st.subheader("Listen to the Video Summary")
                audio_file = generate_summary_audio(st.session_state.summary)
                st.audio(audio_file)
    else:
        st.info("Please enter a YouTube URL above to generate the summary.")

## --- Topics Tab ---
elif st.session_state.active_tab == "topics":
    st.header("Key Topics")
    if "topics" not in st.session_state:
        st.session_state.topics = ""

    if st.session_state.transcription:
        if not st.session_state.topics:
            with st.spinner("Generating key topics..."):
                try:
                    prompt = "Given the video transcript below, give me the highlights of the topics discussed in the video."
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    response = model.generate_content(f"{prompt}\n\nTranscript:\n{st.session_state.transcription}")
                    st.session_state.topics = response.text.strip()
                except Exception as e:
                    st.error(f"Error generating topics: {e}")
        if st.session_state.topics:
            st.markdown(st.session_state.topics)
    else:
        st.info("Please enter a YouTube URL above to generate the summary")

# --- Quiz Tab ---
elif st.session_state.active_tab == "quiz":
    st.header("Test your Knowledge")
    if "quiz_generated" not in st.session_state:
        st.session_state.quiz_generated = False
    if st.session_state.transcription:
        if st.button("Generate Quiz"):
            with st.spinner("Generating quiz from transcript..."):
                st.session_state.quiz_data = generate_quiz(st.session_state.transcription)
                st.session_state.quiz_answers = {}
                st.session_state.graded = False
                st.session_state.quiz_generated = True 

    else:
        st.info("Please enter a YouTube URL to generate the transcript first.")
    if st.session_state.quiz_generated and st.session_state.quiz_data:
        for idx, q in enumerate(st.session_state.quiz_data, start=1):
            st.markdown(f"### {idx}. {q['question']}")
            options = q["shuffled_options"]
            prev_answer = st.session_state.quiz_answers.get(idx)
            selected = st.radio(
                label="Choose your answer:",
                options=options,
                index=options.index(prev_answer) if prev_answer in options else None,
                key=f"quiz_q{idx}",
                label_visibility="collapsed"
            )
            if selected and selected != st.session_state.quiz_answers.get(idx):
                st.session_state.quiz_answers[idx] = selected
            if st.session_state.graded:
                if selected == q["correct_option"]:
                    st.success("Correct!")
                else:
                    st.error(f"Wrong! Correct answer: {q['correct_option']}")
                with st.expander("Explain Why"):
                    explanation = explain_answer(q['question'], q['correct_option'])
                    st.markdown(f"**Explanation:** {explanation}")
            st.markdown("---")
        if not st.session_state.graded:
            if st.button("Grade Quiz"):
                st.session_state.graded = True
                st.rerun()
        if st.session_state.graded:
            total = len(st.session_state.quiz_data)
            correct = sum(
                1 for idx, q in enumerate(st.session_state.quiz_data, start=1)
                if st.session_state.quiz_answers.get(idx) == q["correct_option"]
            )
            st.subheader(f"Final Score: {correct} / {total}")

# --- Related Content Tab ---
elif st.session_state.active_tab == "related":
    st.header("Related YouTube Content")
    search_query = st.text_input("Enter a keyword to search within the video's topic")
    if search_query:
        if st.session_state.transcription:
            with st.spinner("Extracting topic context from video..."):
                try:
                    topic_area = extract_main_topic_area(st.session_state.transcription)
                    refined_query = f"{search_query} in the context of {topic_area}"
                    st.caption(f" Searching: `{refined_query}`")
                    related_videos = get_top_related_videos(refined_query)
                    if related_videos:
                        for title, url in related_videos:
                            st.markdown(f"- [{title}]({url})")
                    else:
                        st.warning("No related videos found for your query.")
                except Exception as e:
                    st.error(f"Error during search: {e}")
        else:
            st.warning("Please enter a YouTube URL above to generate the related content.")
    
# --- Transcript Tab ---
elif st.session_state.active_tab == "Transcript":
    st.header("Video Transcript")
    if st.session_state.transcription:
        st.text_area("Transcript", st.session_state.transcription, height=400)
    else:
        st.info("Transcript not available. Please enter a YouTube URL above to generate it.")
