import streamlit as st
import pandas as pd
import json, os

LOG_PATH = "./data/evaluations.jsonl"
st.set_page_config("RAG Quality Dashboard", layout="wide")
st.title(" Dashboard de Calidad RAG")

if not os.path.exists(LOG_PATH):
    st.warning("No hay evaluaciones todavía")
    st.stop()

rows = [json.loads(l) for l in open(LOG_PATH)]
df = pd.DataFrame(rows)

users = df['username'].unique()
selected_user = st.selectbox("Filtrar por usuario", options=["Todos"] + list(users))
view = df if selected_user=="Todos" else df[df["username"]==selected_user]

c1,c2,c3,c4 = st.columns(4)
c1.metric("Preguntas", len(view))
c2.metric("Pass Rate", f"{view['pass'].mean()*100:.1f}%")
c3.metric("Similaridad Media", f"{view['context_similarity'].mean():.2f}")
c4.metric("Longitud Media", int(view['answer_length'].mean()))

st.divider()
st.subheader("Detalle por Pregunta")
only_fail = st.checkbox("Solo fallos")
view_detail = view if not only_fail else view[view["pass"]==False]

for _, r in view_detail.iterrows():
    with st.expander(r["question"]):
        st.write(r["answer"])
        st.write("Fuentes:", ", ".join(r.get("sources", [])))
        st.json({"similarity": r["context_similarity"],"length":r["answer_length"],"pass":r["pass"]})
