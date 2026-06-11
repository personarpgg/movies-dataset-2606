import re

import altair as alt
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Movies dataset", page_icon="🎬", layout="wide")

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ 설정")
    st.session_state.dark_mode = st.toggle("🌙 다크 모드", value=st.session_state.dark_mode)

    st.divider()

    metric_labels = {
        "gross": "흥행 수익 ($)",
        "imdb_score": "IMDB 점수",
        "popularity": "인기도",
        "vote_average": "평균 평점",
    }
    selected_metric = st.selectbox(
        "📊 지표 선택",
        list(metric_labels.keys()),
        format_func=lambda x: metric_labels[x],
    )

    chart_type = st.selectbox("📈 차트 타입", ["라인", "바", "영역"])
    top_n = st.slider("🏆 TOP N 장르 순위", 3, 10, 5)

# --- Theme ---
if st.session_state.dark_mode:
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #1a1c23; }
    [data-testid="stMetric"] { background-color: #1e2129; border-radius: 8px; padding: 12px; }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #f0f2f6; }
    [data-testid="stMetric"] { background-color: #f8f9fa; border-radius: 8px; padding: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- Title ---
st.title("🎬 Movies dataset")
st.write("TMDB 영화 데이터를 기반으로 장르별 성과를 탐색하세요.")

# --- Data ---
@st.cache_data
def load_data():
    return pd.read_csv("data/movies_genres_summary.csv")

@st.cache_data
def load_famous_movies():
    return pd.read_csv("data/famous_movies.csv")

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_poster(wiki_title: str) -> str:
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title.replace(' ', '_')}"
        r = requests.get(url, timeout=5, headers={"User-Agent": "MovieDashboard/1.0"})
        if r.status_code == 200:
            src = r.json().get("thumbnail", {}).get("source", "")
            if src:
                return re.sub(r"/\d+px-", "/400px-", src)
    except Exception:
        pass
    return ""

df = load_data()
famous_df = load_famous_movies()

# --- Filters ---
col_genre, col_year = st.columns([2, 1])
with col_genre:
    genres = st.multiselect(
        "장르",
        df.genre.unique(),
        ["Action", "Adventure", "Biography", "Comedy", "Drama", "Horror"],
    )
with col_year:
    years = st.slider("연도", int(df.year.min()), int(df.year.max()), (2000, 2010))

df_filtered = df[(df["genre"].isin(genres)) & (df["year"].between(years[0], years[1]))]

if df_filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# --- Summary Cards ---
st.subheader("요약 통계")
y_title = metric_labels[selected_metric]
total = df_filtered[selected_metric].sum()
best_genre = df_filtered.groupby("genre")[selected_metric].sum().idxmax()
best_year = df_filtered.groupby("year")[selected_metric].sum().idxmax()
avg_val = df_filtered[selected_metric].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("합계", f"{total:,.0f}" if selected_metric == "gross" else f"{total:,.2f}")
c2.metric("최고 장르", best_genre)
c3.metric("최고 연도", str(best_year))
c4.metric("평균", f"{avg_val:,.0f}" if selected_metric == "gross" else f"{avg_val:,.2f}")

st.divider()

# --- Pivot Table ---
df_reshaped = df_filtered.pivot_table(
    index="year", columns="genre", values=selected_metric, aggfunc="sum", fill_value=0
)
df_reshaped = df_reshaped.sort_values(by="year", ascending=False)
st.dataframe(df_reshaped, use_container_width=True)

# --- Chart ---
df_chart = pd.melt(
    df_reshaped.reset_index(), id_vars="year", var_name="genre", value_name=selected_metric
)
encode_args = dict(
    x=alt.X("year:N", title="연도"),
    y=alt.Y(f"{selected_metric}:Q", title=y_title),
    color="genre:N",
    tooltip=["year:N", "genre:N", f"{selected_metric}:Q"],
)
if chart_type == "라인":
    chart = alt.Chart(df_chart).mark_line(point=True).encode(**encode_args)
elif chart_type == "바":
    chart = alt.Chart(df_chart).mark_bar().encode(**encode_args)
else:
    chart = alt.Chart(df_chart).mark_area(opacity=0.5, line=True).encode(**encode_args)
st.altair_chart(chart.properties(height=360), use_container_width=True)

st.divider()

# --- Genre Ranking ---
st.subheader(f"🏆 장르별 TOP {top_n} 순위 ({years[0]}–{years[1]})")
genre_rank = (
    df_filtered.groupby("genre")[selected_metric]
    .sum()
    .sort_values(ascending=False)
    .head(top_n)
    .reset_index()
)
genre_rank.columns = ["장르", y_title]
genre_rank.index = genre_rank.index + 1
st.dataframe(genre_rank, use_container_width=True)

# --- Download ---
csv = df_filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 필터링된 데이터 CSV 다운로드",
    data=csv,
    file_name=f"movies_filtered_{years[0]}_{years[1]}.csv",
    mime="text/csv",
)

st.divider()

# --- Representative Movies by Genre ---
def render_movie_grid(movies: pd.DataFrame, cols_count: int = 4):
    cols = st.columns(cols_count)
    for i, (_, movie) in enumerate(movies.iterrows()):
        with cols[i % cols_count]:
            poster = fetch_poster(movie["wiki_title"])
            if poster:
                st.image(poster, use_container_width=True)
            else:
                st.markdown("🎬")
            st.markdown(f"**{movie['title']}** ({movie['year']})")
            st.caption(f"⭐ {movie['imdb_score']}점  ·  {movie['genre']}")
            st.caption(movie["description"])

st.subheader("🎬 장르별 대표 영화")
genre_movies = famous_df[famous_df["genre"].isin(genres)].head(8)
if genre_movies.empty:
    st.info("선택한 장르에 해당하는 대표 영화가 없습니다.")
else:
    with st.spinner("포스터 이미지 불러오는 중..."):
        render_movie_grid(genre_movies)

st.divider()

# --- Global Top Movies ---
st.subheader("🌍 전 세계 흥행 TOP 영화")
top_global = famous_df.sort_values("gross", ascending=False).head(8)
with st.spinner("포스터 이미지 불러오는 중..."):
    render_movie_grid(top_global)
