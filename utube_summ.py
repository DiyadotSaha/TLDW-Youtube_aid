import streamlit as st
from pytubefix import YouTube
import whisper
from summarizer import Summarizer
from pysummarization.nlpbase.auto_abstractor import AutoAbstractor
from pysummarization.tokenizabledoc.simple_tokenizer import SimpleTokenizer
from pysummarization.abstractabledoc.top_n_rank_abstractor import TopNRankAbstractor
import os

def download_audio_from_youtube(url):
    yt = YouTube(url)
    stream = yt.streams.filter(only_audio=True).first()
    output_file = stream.download(filename='audio.mp4')
    return output_file

def transcribe_audio(file_path):
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    transcribed_text = result["text"]
    return transcribed_text

def abstraction_summary(body): 
    auto_abstractor = AutoAbstractor()
    auto_abstractor.tokenizable_doc = SimpleTokenizer()
    auto_abstractor.delimiter_list = [".", "\n"]
    abstractable_doc = TopNRankAbstractor()
    result_dict = auto_abstractor.summarize(body, abstractable_doc)
    summary = ''.join(result_dict["summarize_result"])
    return summary 

def extraction_summary(body): 
    bert_model = Summarizer()
    summary = ''.join(bert_model(body, min_length=60))
    return summary

# Streamlit UI setup
st.title("YouTube Video Summarizer")
url = st.text_input("Enter YouTube URL")
summary_type = st.selectbox("Select Summary Type", ["Extractive", "Abstractive"])

if st.button("Summarize"):
    if url:
        with st.spinner("Downloading audio..."):
            try:
                audio_file = download_audio_from_youtube(url)
                st.success("Download completed")
                st.write(f"Audio downloaded as {audio_file}")

                with st.spinner("Transcribing audio..."):
                    transcription = transcribe_audio(audio_file)
                    st.success("Transcription completed")

                # Generate the summary based on the selected type
                if summary_type == "Extractive":
                    with st.spinner("Generating extractive summary..."):
                        summary = extraction_summary(transcription)
                        st.success("Extractive summary completed")
                else:
                    with st.spinner("Generating abstractive summary..."):
                        summary = abstraction_summary(transcription)
                        st.success("Abstractive summary completed")

                # Display the summary regardless
                st.write("Summary:")
                st.write(summary)

                # Create an expander for the full transcript
                with st.expander("Show Full Transcript", expanded=False):
                    st.write("Full Transcript:")
                    st.write(transcription)

                os.remove(audio_file)  # Clean up by removing the audio file
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Please enter a valid YouTube URL")
