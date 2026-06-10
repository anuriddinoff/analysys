import streamlit as st
import json, pandas as pd
from io import BytesIO
import google.generativeai as genai

st.set_page_config(page_title="Texnik Ko'rik Tahlili", page_icon="🚂")
st.title(" Texnik Ko'rik AI Tahlili")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

uploaded = st.file_uploader("JSON fayl yuklang", type="json")

if uploaded:
    data = json.load(uploaded)
    df = pd.json_normalize(data)

    df["created_time"]   = pd.to_datetime(df["created_time"])
    df["is_closed_time"] = pd.to_datetime(df["is_closed_time"])
    df["vaqt_soat"]      = (df["is_closed_time"] - df["created_time"]).dt.total_seconds() / 3600
    df["vaqt_soat"]      = df["vaqt_soat"].round(2)
    df = df[df["vaqt_soat"] > 0]

    df["median_soat"]   = df.groupby("locomotive.name")["vaqt_soat"].transform("median")
    df["ortiqcha_soat"] = (df["vaqt_soat"] - df["median_soat"]).round(2)
    df["ortiqcha_soat"] = df["ortiqcha_soat"].apply(lambda x: x if x > 0 else 0)
    df["holat"]         = df["ortiqcha_soat"].apply(
        lambda x: "Normal" if x == 0 else f"+{x} soat oshgan"
    )

    result = df[[
        "id", "locomotive.name", "locomotive.locomotive_model.name",
        "branch.name", "created_time", "is_closed_time",
        "vaqt_soat", "median_soat", "ortiqcha_soat", "holat",
        "delay_reason", "section",
    ]].copy()

    result.columns = [
        "Ko'rik ID", "Lokomotiv", "Model", "Depo",
        "Boshlangan vaqt", "Yopilgan vaqt",
        "Sarflangan vaqt (soat)", "Normal vaqt / Median (soat)",
        "Ortiqcha sarflangan (soat)", "Holat",
        "Kechikish sababi", "Sekciya",
    ]

    result["Boshlangan vaqt"] = result["Boshlangan vaqt"].dt.tz_localize(None)
    result["Yopilgan vaqt"]   = result["Yopilgan vaqt"].dt.tz_localize(None)
    result = result.sort_values("Ortiqcha sarflangan (soat)", ascending=False)

    # Statistika
    col1, col2, col3 = st.columns(3)
    col1.metric("Jami ko'riklar", len(result))
    col2.metric(" Normal", len(result[result["Holat"] == "Normal"]))
    col3.metric(" Oshganlar", len(result[result["Holat"] != "Normal"]))

    st.dataframe(result, use_container_width=True)

    # Excel yuklab olish
    buffer = BytesIO()
    result.to_excel(buffer, index=False)
    st.download_button("📥 Excel yuklab olish", buffer.getvalue(),
                       "korik_tahlil.xlsx", "application/vnd.ms-excel")

    st.divider()
    st.subheader("🤖 AI Tahlil")

    top_oshgan = result[result["Holat"] != "Normal"].head(5)[
        ["Lokomotiv", "Model", "Depo",
         "Sarflangan vaqt (soat)", "Normal vaqt / Median (soat)",
         "Ortiqcha sarflangan (soat)"]
    ].to_string(index=False)

    depo_stat = result.groupby("Depo")["Sarflangan vaqt (soat)"].agg(
        count="count", mean="mean"
    ).round(2).to_string()

    summary = f"""
Jami ko'riklar: {len(result)}
Normal: {len(result[result['Holat'] == 'Normal'])}
Normadan oshgan: {len(result[result['Holat'] != 'Normal'])}

Eng ko'p vaqt sarflagan top 5 ko'rik:
{top_oshgan}

Depo bo'yicha statistika:
{depo_stat}
"""

    user_question = st.text_input(
        "AI ga savol bering (ixtiyoriy):",
        placeholder="Masalan: qaysi depo muammoli?"
    )

    if st.button("🔍 AI Tahlil qilsin"):
        with st.spinner("AI tahlil qilmoqda..."):
            prompt = f"""
Sen O'zbekiston temir yo'li lokomotiv texnik ko'rigi mutaxassisisan.
Quyidagi statistika asosida o'zbek tilida professional tahlil qil.

{summary}

{"Savol: " + user_question if user_question else "Umumiy tahlil va tavsiyalar ber."}

Quyidagilarni yoz:
1. Umumiy holat xulosasi
2. Muammoli lokomotivlar yoki depolar
3. Sabablari va tavsiyalar
"""
            response = model.generate_content(prompt)
            st.markdown(response.text)
