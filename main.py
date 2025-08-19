# streamlit_app.py
import streamlit as st
from travel_model import run_travel_model
from logistics_model import run_logistics_model

def main():
    st.title(" Multi-AI Assistant")

    choice = st.selectbox("Choose an assistant:", ["Travel Assistant", "Logistics Assistant"])

    if choice == "Travel Assistant":
        run_travel_model()
    elif choice == "Logistics Assistant":
        run_logistics_model()

if __name__ == "__main__":
    main()
