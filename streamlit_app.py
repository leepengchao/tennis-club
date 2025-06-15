import streamlit as st
import json, os, datetime, math
import pandas as pd
from io import StringIO

# --------------------------------------------------
# 0️⃣  Page Config (⚠️ 必须是首个 Streamlit 调用)
# --------------------------------------------------
st.set_page_config(
    page_title="精英网球巡回赛系统 Plus",
    layout="wide",
    initial_sidebar_state="expanded",
)

"""
精英网球巡回赛管理系统 Plus
=============================
✓ 赛事全流程   ✓ Fast4 比分录入   ✓ 选手管理   ✓ 积分榜 / 历史 / 统计   ✓ 数据导出
"""

# --------------------------------------------------
# 1️⃣  常量与路径
# --------------------------------------------------
ICONS = {
    "home": "🏟️", "tournament": "🏆", "players": "👥", "rankings": "📊",
    "history": "📜", "stats": "📈", "rules": "⚖️", "settings": "🔧", "vs": "⚔️",
}
DATA_DIR = "data"; os.makedirs(DATA_DIR, exist_ok=True)
PLAYER_F, RANK_F, HIST_F, SET_F = [os.path.join(DATA_DIR, f) for f in (
    "players.json", "rankings.json", "history.json", "settings.json")]

DEFAULT = {
    "fast4": {"sets": 2, "games": 4},
    "points": {
        "4" : {"winner":100,"finalist":60,"semifinalist":30},
        "8" : {"winner":200,"finalist":120,"semifinalist":70,"quarterfinalist":30},
        "16": {"winner":400,"finalist":240,"semifinalist":140,"quarterfinalist":80,"round_of_16":40},
        "32": {"winner":800,"finalist":480,"semifinalist":280,"quarterfinalist":160,"round_of_16":80,"round_of_32":40},
    },
}

# --------------------------------------------------
# 2️⃣  JSON I/O
# --------------------------------------------------
load_json = lambda p, d: json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else d
save_json = lambda d, p: json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

players   = load_json(PLAYER_F, {})          # {name:{age,level}}
rankings  = load_json(RANK_F,   {})          # {name: points}
history   = load_json(HIST_F,  [])           # list[dict]
config    = load_json(SET_F,    DEFAULT)
FAST4     = config["fast4"]                      # dict
POINTS    = {int(k): v for k, v in config["points"].items()}

ss = st.session_state
ss.setdefault("page", "home")
ss.setdefault("step", "setup")   # setup / play / finish
ss.setdefault("tour", {})         # 当前赛事数据

# --------------------------------------------------
# 3️⃣  算法工具
# --------------------------------------------------

def next_pow2(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))


def build_bracket(seed_list):
    size = next_pow2(len(seed_list))
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
        'node [shape=box,style="rounded,filled",fillcolor=lightblue,fontname=sans-serif];',
        "edge [arrowhead=none];",
    ]
    if champion:
        g.append(f'"C" [label="🏆 {champion}",fillcolor=gold];')
    cur = size
    while cur >= 2:
        players_round = rounds.get(str(cur), [])
        for j in range(0, len(players_round), 2):
            p1 = players_round[j]
            p2 = players_round[j + 1] if j + 1 < len(players_round) else "BYE"
            nid = f"R{cur}_{j // 2}"
            g.append(f'"{nid}" [label="{p1} {ICONS["vs"]} {p2}"];')
            if champion:
                nxt = cur // 2; target = "C" if nxt == 1 else f"R{nxt}_{(j // 2) // 2}"
                g.append(f'"{nid}" -> "{target}";')
        cur //= 2
    g.append("}")
    return "\n".join(g)


def outcome_and_points(draw_size, player, rounds):
    ladder = {
        1: ("winner", "冠军"), 2: ("finalist", "亚军"), 4: ("semifinalist", "四强"),
        8: ("quarterfinalist", "八强"), 16: ("round_of_16", "十六强"), 32: ("round_of_32", "三十二强"),
    }
    for rs, (key, name) in ladder.items():
        if player in rounds.get(str(rs), []):
            pts = POINTS[min(POINTS, key=lambda k: abs(k - draw_size))].get(key, 0)
            return name, pts
    return "参与", 0

# --------------------------------------------------
# 4️⃣  结算积分 & 保存历史
# --------------------------------------------------

def settle_points(tour):
    size = tour["size"]
    rounds = tour["rounds"]
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    record = {"time": ts, "name": f"{ts} ({size}签)", "players": []}

    for p in rounds[str(size)]:
        outcome, pts = outcome_and_points(size, p, rounds)
        rankings[p] = rankings.get(p, 0) + pts
        wins = sum(1 for rps in rounds.values() if p in rps and len(rps) < size)
        record["players"].append({"name": p, "outcome": outcome, "wins": wins, "points": pts})
    history.append(record)
    save_json(rankings, RANK_F)
    save_json(history, HIST_F)

# --------------------------------------------------
# 5️⃣  页面函数
# --------------------------------------------------

## 5.1 主页

def home_page():
    st.title(f"{ICONS['home']} 精英网球巡回赛 Plus")
    c1, c2, c3 = st.columns(3)
    c1.metric("注册选手", len(players))
    c2.metric("比赛历史", len(history))
    c3.metric("排行榜人数", len(rankings))

## 5.2 选手管理

def players_page():
    st.title(f"{ICONS['players']} 选手管理")
    tab_add, tab_batch, tab_list = st.tabs(["添加", "批量导入", "列表"])

    with tab_add:
        with st.form("add_player"):
            name = st.text_input("姓名")
            age = st.number_input("年龄", 5, 80, 18)
            level = st.selectbox("水平", ["Rookie", "Challenger", "Pro"])
            if st.form_submit_button("保存"):
                if not name or name in players:
                    st.warning("姓名为空或已存在")
                else:
                    players[name] = {"age": int(age), "level": level}
                    save_json(players, PLAYER_F)
                    st.success("已添加")
                    st.experimental_rerun()

    with tab_batch:
        up = st.file_uploader("CSV name,age,level", type="csv")
        if up and st.button("导入"):
            df = pd.read_csv(StringIO(up.getvalue().decode()), header=None)
            added = 0
            for _, r in df.iterrows():
                if r[0] not in players:
                    players[r[0]] = {"age": int(r[1]), "level": r[2]}
                    added += 1
            save_json(players, PLAYER_F)
            st.success(f"导入 {added} 人")
            st.experimental_rerun()

    with tab_list:
        if players:
            df = pd.DataFrame(players).T.reset_index().rename(columns={"index": "姓名"})
            st.dataframe(df, use_container_width=True)
            sel = st.multiselect("删除选手", list(players))
            if sel and st.button("确认删除"):
                for n in sel:
                    players.pop(n, None); rankings.pop(n, None)
                save_json(players, PLAYER_F); save_json(rankings, RANK_F)
                st.experimental_rerun()
        else:
            st.info("暂无选手")

## 5.3 举办比赛

def tournament_page():
    st.title(f"{ICONS['tournament']} 举办比赛")
    if ss.step != "setup" and st.sidebar.button("取消比赛"):
        ss.step, ss.tour = "setup", {}; st.experimental_rerun()

    # ----- Step1 ------
    if ss.step == "setup":
        seeds_txt = st.text_area("输入选手 (一行一名，按种子)")
        if st.button("用选手库填充"):
            seeds_txt = "\n".join(players)
            st.session_state["tmp_seeds"] = seeds_txt; st.experimental_rerun()
        seeds = [s.strip() for s in seeds_txt.strip().split("\n") if s.strip()] if seeds_txt else []
        if st.button("生成对阵", disabled=len(seeds) < 2):
            m, byes, sz = build_bracket(seeds)
            ss.tour = {"size": sz, "rounds": {str(sz): seeds}, "current": byes + [p for a in m for p in a]}
            ss.step = "play"; st.experimental_rerun()

    # ----- Step2 ------
    elif ss.step == "play":
        tour = ss.tour; cur = tour["current"]
        st.subheader(f"{len(cur)} 强")
        st.graphviz_chart(dot_graph(tour))
        winners = []
        for i in range(0, len(cur), 2):
            p1, p2 = cur[i], cur[i + 1]
            if p2 == "BYE": winners.append(p1); continue
            c1, c2 = st.columns(2)
            win1 = c1.checkbox(f"{p1} 胜", key=f"chk_{i}_1")
            win2 = c2.checkbox(f"{p2} 胜", key=f"chk_{i}_2")
            if win1 and not win2: winners.append(p1)
            elif win2 and not win1: winners.append(p2)
        if len(winners) == len(cur) // 2 and st.button("确认本轮结果"):
            tour["rounds"][str(len(winners))] = winners; tour["current"] = winners
            ss.step = "finish" if len(winners) == 1 else "play"
            st.experimental_rerun()

    # ----- Step3 ------
    elif ss.step == "finish":
        tour = ss.tour; champ = tour["current"][0]
        st.balloons(); st.success(f"冠军 {champ}")
        st.graphviz_chart(dot_graph(tour))
        settle_points(tour)
        st.write("积分已更新，排行榜 & 历史记录可查看")
        if st.button("新比赛"):
            ss.step, ss.tour = "setup", {}; st.experimental_rerun()

## 5.4 积分榜

def rankings_page():
    st.title(f"{ICONS['rankings']} 积分榜")
    if not rankings:
        st.info("暂无数据"); return
    df = pd.Series(rankings).sort_values(ascending=False).reset_index(); df.columns = ["姓名", "积分"]
    df["排名"] = range(1, len(df) + 1)
    st.dataframe(df[["排名", "姓名", "积分"]], use_container_width=True)
    st.download_button("下载 CSV", df.to_csv(index=False).encode(), "rankings.csv")

## 5.5 历史记录

def history_page():
    st.title(f"{ICONS['history']} 历史记录")
    if not history:
        st.info("暂无记录"); return
    rec = [{**p, "比赛": h["name"], "日期": h["time"]} for h in history for p in h["players"]]
    df = pd.DataFrame(rec)
    st.dataframe(df, use_container_width=True)
    st.download_button("下载 CSV", df.to_csv(index=False).encode(), "history.csv")

## 5
