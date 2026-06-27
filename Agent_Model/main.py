import streamlit as st
from travel_model import run_travel_model
from logistics_model import run_logistics_model

st.set_page_config(
    page_title="Multi-AI Assistant",
    page_icon="🌐",
    layout="centered",
)

def main():
    st.title("🌐 Multi-AI Assistant")

    with st.sidebar:
        st.header("Navigation")
        choice = st.radio(
            "Choose an assistant:",
            ["✈️ Travel Assistant", "🚚 Logistics Assistant"],
            label_visibility="collapsed"
        )
        st.divider()

        if choice == "✈️ Travel Assistant":
            st.markdown(
                "**Travel Assistant** can help you with:\n"
                "- 🗺️ Day-by-day itineraries\n"
                "- 🕐 Local times & distances\n"
                "- 🧳 Packing lists\n"
                "- 🛂 Visa requirements\n"
                "- 💱 Currency conversion\n"
            )
        else:
            st.markdown(
                "**Logistics Assistant** can help you with:\n"
                "- 🚚 Road freight cost estimates\n"
                "- ✈️ Air freight cost estimates\n"
                "- 📦 Shipping mode comparisons\n"
                "- 🌡️ Storage recommendations\n"
                "- 🛃 Customs duty estimates\n"
            )

    if "✈️" in choice:
        run_travel_model()
    else:
        run_logistics_model()


if __name__ == "__main__":
    main()
