import streamlit as st
import json, os, datetime, math, pandas as pd
from io import StringIO

# --------------------------------------------------
# 0️⃣  Page Config (必须是首个 Streamlit 调用)
# --------------------------------------------------
st.set_page_config(
    page_title="精英网球巡回赛系统 Plus",
    layout="wide",
    initial_sidebar_state="expanded",
)

"""
精英网球巡回赛管理系统 Plus
=============================
★ 赛事全流程  ★ Fast4 比分录入  ★ 选手管理  ★ 数据导出  ★ 统计分析
"""

# --------------------------------------------------
# 1️⃣  常量与路径
# --------------------------------------------------
ICONS = {
    "home": "🏟️", "tournament": "🏆", "players": "👥", "rankings": "📊",
    "history": "📜", "stats": "📈", "rules": "⚖️", "settings": "🔧", "vs": "⚔️",
}
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
PLAYER_F, RANK_F, HIST_F, SET_F = [os.path.join(DATA_DIR, f) for f in (
    "players.json", "rankings.json", "history.json", "settings.json")]

DEFAULT = {
    "fast4": {"sets": 2, "games": 4},
    "points": {
        "4":  {"winner": 100, "finalist": 60, "semifinalist": 30},
        "8":  {"winner": 200, "finalist": 120, "semifinalist": 70, "quarterfinalist": 30},
        "16": {"winner": 400, "finalist": 240, "semifinalist": 140, "quarterfinalist": 80, "round_of_16": 40},
        "32": {"winner": 800, "finalist": 480, "semifinalist": 280, "quarterfinalist": 160, "round_of_16": 80, "round_of_32": 40},
    },
}

# --------------------------------------------------
# 2️⃣  JSON I/O
# --------------------------------------------------
load_json = lambda p, d: json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else d
save_json = lambda d, p: json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

players  = load_json(PLAYER_F, {})
rankings = load_json(RANK_F,   {})
history  = load_json(HIST_F,  [])
config   = load_json(SET_F,   DEFAULT)
FAST4    = config["fast4"]
POINTS   = {int(k): v for k, v in config["points"].items()}

ss = st.session_state
ss.setdefault("page", "home")
ss.setdefault("step", "setup")
ss.setdefault("tour", {})

# --------------------------------------------------
# 3️⃣  工具函数
# --------------------------------------------------

def next_power_of_two(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))


def build_bracket(seed_list):
    size = next_power_of_two(len(seed_list))
    byes = seed_list[: size - len(seed_list)]
    rest = seed_list[len(byes):]
    matches = [(rest[i], rest[~i]) for i in range(len(rest) // 2)]
    return matches, byes, size


def dot_graph(tour):
    if not tour:
        return "digraph G {}"
    rounds, size = tour["rounds"], tour["size"]
    champion = rounds.get("1", [None])[0]
    g = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box,style="rounded,filled",fillcolor=lightblue];',
        "edge [arrowhead=none];",
    ]
    if champion:
        g.append(f'"C" [label="🏆 {champion}",fillcolor=gold];')
    cur = size
    while cur >= 2:
        players_in_round = rounds.get(str(cur), [])
        for j in range(0, len(players_in_round), 2):
            p1 = players_in_round[j]
            p2 = players_in_round[j + 1] if j + 1 < len(players_in_round) else "BYE"
            nid = f"R{cur}_{j // 2}"
            g.append(f'"{nid}" [label="{p1} {ICONS["vs"]} {p2}"];')
            next_size = cur // 2
            if champion and next_size >= 1:
                target = "C" if next_size == 1 else f"R{next_size}_{(j // 2) // 2}"
                g.append(f'"{nid}" -> "{target}";')
        cur //= 2
    g.append("}")
    return "\n".join(g)


def points_for(draw_size, outcome_key):
    closest = min(POINTS, key=lambda k: abs(k - draw_size))
    return POINTS[closest].get(outcome_key, 0)

# --------------------------------------------------
# 4️⃣  页面函数
# --------------------------------------------------
# 首页

def home_page():
    st.title(f"{ICONS['home']} 精英网球巡回赛 Plus")
    c1, c2, c3 = st.columns(3)
    c1.metric("注册选手", len(players))
    c2.metric("比赛历史", len(history))
    c3.metric("排行榜人数", len(rankings))

# 选手管理

def players_page():
    st.title(f"{ICONS['players']} 选手管理")
    tab_add, tab_batch, tab_list = st.tabs(["单个添加", "批量导入", "列表"])

    # --- 单个添加 ---
    with tab_add:
        with st.form("add_player_form"):
            name = st.text_input("姓名")
            age = st.number_input("年龄", 5, 80, 18)
            level = st.selectbox("水平", ["Rookie", "Challenger", "Pro"])
            submitted = st.form_submit_button("保存")
        if submitted:
            if not name or name in players:
                st.warning("姓名不能为空或已存在！")
            else:
                players[name] = {"age": int(age), "level": level}
                save_json(players, PLAYER_F)
                st.success("已添加！")
                st.experimental_rerun()

    # --- 批量导入 ---
    with tab_batch:
        csv_file = st.file_uploader("CSV 格式 name,age,level", type="csv")
        if csv_file and st.button("导入"):
            df = pd.read_csv(StringIO(csv_file.getvalue().decode()), header=None)
            added = 0
            for _, row in df.iterrows():
                n, a, l = row[0], row[1], row[2]
                if n not in players:
                    players[n] = {"age": int(a), "level": l}
                    added += 1
            save_json(players, PLAYER_F)
            st.success(f"成功导入 {added} 人")
            st.experimental_rerun()

    # --- 列表 & 删除 ---
    with tab_list:
        if not players:
            st.info("暂无选手记录")
        else:
            df = pd.DataFrame(players).T.reset_index().rename(columns={"index": "姓名"})
            st.dataframe(df, use_container_width=True)
            sel = st.multiselect("选择要删除的选手", list(players))
            if sel and st.button("确认删除"):
                for n in sel:
                    players.pop(n, None)
                    rankings.pop(n, None)
                save_json(players, PLAYER_F)
                save_json(rankings, RANK_F)
                st.success("已删除")
                st.experimental_rerun()

# 举办比赛

def tournament_page():
    st.title(f"{ICONS['tournament']} 举办比赛")
    if ss.step != "setup" and st.sidebar.button("❌ 取消当前比赛"):
        ss.step, ss.tour = "setup", {}
        st.experimental_rerun()

    # ---------- Step 1: 参赛列表 ----------
    if ss.step == "setup":
        seeds_text = st.text_area("参赛选手 (每行一名，按种子顺序)")
        if st.button("全部插入选手库") and players:
            seeds_text = "\n".join(players)
            st.session_state["seeds_text"] = seeds_text
            st.experimental_rerun()
        seeds = [n.strip() for n in seeds_text.strip().split("\n") if n.strip()] if seeds_text else []
        if st.button("生成对阵", disabled=len(seeds) < 2):
            matches, byes, size = build_bracket(seeds)
            ss.tour = {
                "size": size,
                "rounds": {str(size): seeds},
                "current": byes + [p for m in matches for p in m],
            }
            ss.step = "play"
            st.experimental_rerun()

    # ---------- Step 2: 比赛进行 ----------
    elif ss.step == "play":
        tour = ss.tour
        current_players = tour["current"]
        st.subheader(f"当前轮次：{len(current_players)} 强")
        st.graphviz_chart(dot_graph(tour))

        winners = []
        for i in range(0, len(current_players), 2):
            p1 = current_players[i]
            p2 = current_players[i + 1]
            if p2 == "BYE":
                winners.append(p1)
                continue
            col1, col2 = st.columns(2)
            s1 = col1.number_input(f"{p1} 赢盘数", 0, FAST4["sets"], key=f"w_{i}")
            s2 = col2.number_input(f"{p2} 赢盘数", 0, FAST4["sets"], key=f"l_{i}")
            if s1 == FAST4["sets"]:
                winners.append(p1)
            elif s2 == FAST4["sets"]:
                winners.append(p2)

        if len(winners) == len(current_players) // 2 and st.button("确认本轮结果"):
            tour["rounds"][str(len(winners))] = winners
            tour["current"] = winners
            if len(winners) == 1:
                ss.step = "finish"
            st.experimental_rerun()

    # ---------- Step 3: 结束 ----------
    elif ss.step == "finish":
        tour = ss.tour
        champion = tour["current"][0]
        st.balloons()
        st.success(f"🏆 冠军：{champion}")
        st.graphviz_chart(dot_graph(tour))
        st.write("(此处可调用积分结算函数，略)")
        if st.button("新比赛"):
            ss.step, ss.tour = "setup", {}
            st.experimental_rerun()
# --------------------------------------------------
# 5️⃣  侧边栏导航 & 路由   ★★ 必不可少 ★★
# --------------------------------------------------
PAGES = {
    "home":        home_page,
    "players":     players_page,
    "tournament":  tournament_page,
    # 其余 page_rankings / page_history / page_stats / page_rules / settings_page
}

st.sidebar.header("导航")
for key, label in [
    ("home", "主页"),
    ("players", "选手管理"),
    ("tournament", "举办比赛"),
]:
    if st.sidebar.button(label):
        ss.page = key

# 默认调用
PAGES.get(ss.page, home_page)()
