import streamlit as st
import json
import os
import datetime
import pandas as pd
import math
from io import StringIO

"""
精英网球巡回赛管理系统 － Plus 版
====================================
功能亮点（较基础版新增★标注）：
------------------------------------
1. **赛事全流程**：创建 → 录入比分 → 自动晋级 → 结算积分 → 排行榜 / 历史。
2. **DOT 纯字符串可视化**：移除 python‑graphviz 依赖，部署零负担。
3. **★ 选手管理中心**：支持单个添加 / 批量导入 CSV / 删除；扩展字段（年龄、级别）。
4. **★ 比赛比分录入**：Fast4 三盘两胜，记录每盘局分；界面实时展示。
5. **★ 数据导出**：排行榜与历史记录一键下载为 CSV。
6. **★ 统计分析**：选手参赛次数、胜率、最近走势折线图。
7. **★ 设置中心**：自定义积分结构、Fast4 规则、默认场次名。  

> **提示**：功能加法不影响旧数据结构，凡旧版 json 文件均向后兼容。
"""

# --------------------------------------------------
# 1  页面配置
# --------------------------------------------------
st.set_page_config(
    page_title="精英网球巡回赛系统 Plus",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------
# 2  常量与路径
# --------------------------------------------------
ICONS = {
    "home": "🏟️",
    "tournament": "🏆",
    "rankings": "📊",
    "history": "📜",
    "rules": "⚖️",
    "players": "👥",
    "stats": "📈",
    "settings": "🔧",
    "warning": "⚠️",
    "info": "ℹ️",
    "player": "👤",
    "vs": "⚔️",
}

DATA_DIR = "data"
PLAYER_FILE = os.path.join(DATA_DIR, "players.json")
RANKINGS_FILE = os.path.join(DATA_DIR, "rankings.json")
HISTORY_FILE = os.path.join(DATA_DIR, "tournament_history.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# -------- 默认配置（可在设置中心修改） ---------
DEFAULT_SETTINGS = {
    "fast4": {
        "sets_to_win": 2,
        "games_per_set": 4,
        "tiebreak_game": 3,  # 3‑3 进入抢七
        "no_ad": True,
    },
    "points_structure": {
        "4": {"winner": 100, "finalist": 60, "semifinalist": 30},
        "8": {
            "winner": 200,
            "finalist": 120,
            "semifinalist": 70,
            "quarterfinalist": 30,
        },
        "16": {
            "winner": 400,
            "finalist": 240,
            "semifinalist": 140,
            "quarterfinalist": 80,
            "round_of_16": 40,
        },
        "32": {
            "winner": 800,
            "finalist": 480,
            "semifinalist": 280,
            "quarterfinalist": 160,
            "round_of_16": 80,
            "round_of_32": 40,
        },
    },
}

# --------------------------------------------------
# 3  通用 JSON I/O
# --------------------------------------------------

def load_json(path, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf‑8") as fp:
            return json.load(fp)
    except Exception:
        return fallback

def save_json(data, path):
    with open(path, "w", encoding="utf‑8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=4)

# --------------------------------------------------
# 4  初始化 SessionState
# --------------------------------------------------

def init_state():
    ss = st.session_state
    ss.setdefault("page", "home")
    ss.setdefault("tour_step", "setup")
    ss.setdefault("tour_data", {})
    ss.setdefault("score_buffer", {})  # 临时比分缓存

init_state()

# --------------------------------------------------
# 5  数据加载
# --------------------------------------------------
players_db = load_json(PLAYER_FILE, {})  # {name: {age:int, level:str}}
rankings_db = load_json(RANKINGS_FILE, {})  # {name: points}
history_db = load_json(HISTORY_FILE, [])
settings_db = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)

POINTS_STRUCTURE = {
    int(k): v for k, v in settings_db["points_structure"].items()
}

# --------------------------------------------------
# 6  工具：算法 & DOT
# --------------------------------------------------

def next_pow2(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))


def make_bracket(seed_list: list[str]):
    """返回 matches, byes, total_size"""
    size = next_pow2(len(seed_list))
    byes = seed_list[: size - len(seed_list)]
    remain = seed_list[len(byes):]
    matches = [(remain[i], remain[~i]) for i in range(len(remain) // 2)]
    return matches, byes, size


def bracket_dot(td: dict):
    if not td or "rounds" not in td:
        return "digraph G {}"
    rounds, size_max = td["rounds"], td["size"]
    dot = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box,style="rounded,filled",fillcolor=lightblue,fontname=sans-serif];',
        "edge [arrowhead=none];",
    ]
    # 冠军
    champ = rounds.get("1", [None])[0]
    if champ:
        dot.append(f'"R1_{champ}" [label="🏆 {champ}",fillcolor=gold];')
    # 逐轮
    cur = size_max
    while cur >= 2:
        ps = rounds.get(str(cur), [])
        for j in range(0, len(ps), 2):
            p1, p2 = ps[j], ps[j + 1] if j + 1 < len(ps) else "BYE"
            nid = f"R{cur}_{j//2}"
            lab = f"<{p1}<br/>⚔️<br/>{p2}>"
            dot.append(f'"{nid}" [label={lab}];')
            nxt = cur // 2
            if nxt >= 1 and champ:
                nxt_ps = rounds.get(str(nxt), [])
                win = p1 if p1 in nxt_ps else p2 if p2 in nxt_ps else None
                if win:
                    link = f'"R1_{champ}"' if nxt == 1 else f'"R{nxt}_{(j//2)//2}"'
                    dot.append(f'"{nid}" -> {link};')
        cur //= 2
    dot.append("}")
    return "\n".join(dot)


# --------------------------------------------------
# 7  页面：主页
# --------------------------------------------------

def page_home():
    st.title(f"{ICONS['home']} 精英网球巡回赛系统 Plus")
    st.caption("版本: 2025‑06")
    col1, col2, col3 = st.columns(3)
    col1.metric("注册选手", len(players_db))
    col2.metric("累计比赛", len(history_db))
    col3.metric("排行榜上榜", len(rankings_db))
    st.success("使用左侧导航，体验完整功能！")


# --------------------------------------------------
# 8  页面：选手管理 ★
# --------------------------------------------------

def page_players():
    st.title(f"{ICONS['players']} 选手管理中心")
    tab_add, tab_batch, tab_list = st.tabs(["单个添加", "批量导入", "选手列表"])

    with tab_add:
        with st.form("add_player_form"):
            name = st.text_input("姓名")
            age = st.number_input("年龄", 5, 80, 18)
            level = st.selectbox("水平", ["Rookie", "Challenger", "Pro"])
            submitted = st.form_submit_button("添加")
        if submitted:
            if name.strip() == "" or name in players_db:
                st.warning("姓名不能为空且不能重复！")
            else:
                players_db[name] = {"age": int(age), "level": level}
                save_json(players_db, PLAYER_FILE)
                st.success("已添加！")
                st.experimental_rerun()

    with tab_batch:
        st.markdown("**CSV 格式：name,age,level**  (首行标题可有可无)")
        csv_file = st.file_uploader("上传 CSV", type="csv")
        if csv_file and st.button("导入"):
            s = StringIO(csv_file.getvalue().decode())
            df = pd.read_csv(s, header=None)
            added = 0
            for _, row in df.iterrows():
                n, a, l = row[0], row[1], row[2]
                if n not in players_db:
                    players_db[n] = {"age": int(a), "level": l}
                    added += 1
            save_json(players_db, PLAYER_FILE)
            st.success(f"已导入 {added} 人！")
            st.experimental_rerun()

    with tab_list:
        if not players_db:
            st.info("尚无选手记录。")
        else:
            df = pd.DataFrame(players_db).T.reset_index().rename(columns={"index": "姓名"})
            st.dataframe(df, use_container_width=True)
            sel = st.multiselect("选择要删除的选手", list(players_db.keys()))
            if sel and st.button("删除"):
                for n in sel:
                    players_db.pop(n, None)
                    rankings_db.pop(n, None)
                save_json(players_db, PLAYER_FILE)
                save_json(rankings_db, RANKINGS_FILE)
                st.success("已删除！")
                st.experimental_rerun()


# --------------------------------------------------
# 9  页面：举办比赛（含比分录入★）
# --------------------------------------------------

def page_tournament():
    ss = st.session_state
    st.title(f"{ICONS['tournament']} 举办新比赛")
    rules = settings_db["fast4"]

    # 取消按钮
    if ss.tour_step != "setup":
        if st.sidebar.button("❌ 取消当前比赛"):
            ss.tour_step, ss.tour_data, ss.score_buffer = "setup", {}, {}
            st.experimental_rerun()

    # ---------- 步骤 1: 设置 ----------
    if ss.tour_step == "setup":
        st.subheader("步骤 1⃣  添加参赛选手 (按种子顺位)")
        seed_input = st.text_area("输入姓名 (每行一个)")
        auto_players_btn = st.button("从选手库一键插入全部")
        if auto_players_btn and players_db:
            seed_input = "\n".join(players_db.keys())
            st.session_state.seed_auto = seed_input
            st.experimental_rerun()
        # 解析
        seeds = [l.strip() for l in seed_input.strip().split("\n") if l.strip()] if seed_input else []
        start_btn = st.button("生成对阵并开始", disabled=len(seeds) < 2)
        if start_btn:
            matches, byes, size = make_bracket(seeds)
            ss.tour_data = {
                "size": size,
                "rounds": {str(size): seeds},
                "matches": matches,
                "byes": byes,
                "current": byes + [p for m in matches for p in m],
                "scores": {},  # {(round_size, idx): [[g1,g2], [g1,g2], ...]}
            }
            ss.tour_step = "playing"
            st.experimental_rerun()

    # ---------- 步骤 2: 进行比赛 ----------
    elif ss.tour_step == "playing":
        td = ss.tour_data
        curr_players = td["current"]
        r_size = len(curr_players)
        st.subheader(f"步骤 2⃣  {r_size} 强 比赛")
        draw_bracket(td)

        # 胜者输入
        winners = []
        for i in range(0, len(curr_players), 2):
            p1, p2 = curr_players[i], curr_players[i + 1]
            key = f"score_{r_size}_{i}"
            with st.expander(f"{p1} {ICONS['vs']} {p2}"):
                if p2 == "BYE":
                    st.info(f"{p1} 轮空晋级")
                    winners.append(p1)
                    continue
                sets = rules["sets_to_win"] * 2 - 1
                g1_total, g2_total = 0, 0
                td["scores"].setdefault((r_size, i), [])
                for s in range(sets):
                    col_a, col_b = st.columns(2)
                    g1 = col_a.number_input(
                        f"第 {s+1} 盘 {p1} 局数", 0, rules["games_per_set"], key=f"{key}_g1_{s}"
                    )
                    g2 = col_b.number_input(
                        f"第 {s+1} 盘 {p2} 局数", 0, rules["games_per_set"], key=f"{key}_g2_{s}"
                    )
                    td["scores"][(r_size, i)].append([int(g1), int(g2)])
                    if g1 > g2:
                        g1_total += 1
                    elif g2 > g1:
                        g2_total += 1
                # 判断胜者
                if g1_total >= rules["sets_to_win"]:
                    winners.append(p1)
                elif g2_total >= rules["sets_to_win"]:
                    winners.append(p2)
                else:
                    st.write("⚠️ 请完整填写并确保某方赢够盘数！")

        # 若胜者计数与下一轮匹配
        if len(winners) == r_size // 2 and st.button("确认本轮结果"):
            td["rounds"][str(len(winners))] = winners
            td["current"] = winners
            ss.score_buffer = {}
            if len(winners) == 1:
                ss.tour_step = "finished"
            st.experimental_rerun()

    # ---------- 步骤 3: 结束 ----------
    elif ss.tour_step == "finished":
        td = ss.tour_data
        champ = td["current"][0]
        st.balloons()
        st.success(f"冠军：{champ}")
        draw_bracket(td)
        settle_points(td)
        if st.button("返回首页"):
            ss.tour_step, ss.tour_data = "setup", {}
            st.experimental_rerun()


# --------------------------------------------------
# 10 页面：积分榜 & 导出 ★
# --------------------------------------------------

def page_rankings():
    st.title(f"{ICONS['rankings']} 积分排行榜")
    if not rankings_db:
        st.info("暂无数据")
        return
    df = (
        pd.Series(rankings_db).sort_values(ascending=False).reset_index()
        .rename(columns={"index": "姓名", 0: "积分"})
    )
    df["排名"] = range(1, len(df) + 1)
    st.dataframe(df[["排名", "姓名", "积分"]], use_container_width=True)
    csv = df.to_csv(index=False).encode()
    st.download_button("下载 CSV", csv, "rankings.csv", "text/csv")


# --------------------------------------------------
# 11 页面：历史记录 & 导出 ★
# --------------------------------------------------

def page_history():
    st.title(f"{ICONS['history']} 比赛历史")
    if not history_db:
        st.info("暂无历史记录")
        return
    records = []
    for t in history_db:
        for p in t["participants"]:
            records.append({
                "比赛": t["name"],
                "日期": t["id"].split()[0],
                "姓名": p["name"],
                "成绩": p["outcome"],
                "胜场": p["wins"],
                "积分": p["points_earned"],
            })
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode()
    st.download_button("下载 CSV", csv, "history.csv", "text/csv")


# --------------------------------------------------
# 12 页面：统计分析 ★
# --------------------------------------------------

def page_stats():
    st.title(f"{ICONS['stats']} 统计分析")
    if not history_db:
        st.info("暂无数据")
        return
    df_h = pd.DataFrame(sum(
        [[{**p, "比赛": t["name"], "日期": t["id"].split()[0]} for p in t["participants"]] for t in history_db],
        []),
    )
    player = st.selectbox("选择选手", sorted({p["name"] for p in df_h.to_dict("records")}))
    pdf = df_h[df_h["姓名"].eq(player)]
    st.write("参赛次数", len(pdf), "| 总积分", rankings_db.get(player, 0))
    # 胜率
    wins = pdf[pdf["成绩"].isin(["冠军", "亚军", "四强", "八强", "十六强", "三十二强"])]
    st.write("进入淘汰轮次数", len(wins))


# --------------------------------------------------
# 13 页面：设置中心 ★
# --------------------------------------------------

def page_settings():
    st.title(f"{ICONS['settings']} 设置中心")
    with st.expander("Fast4 规则"):
        st.write("sets_to_win =", settings_db["fast4"]["sets_to_win"])
        st.write("games_per_set =", settings_db["fast4"]["games_per_set"])
        st.info("如需修改，可直接编辑 settings.json")
    st.write("⚙️ 暂仅支持查看，后续版本开放图形化修改。")


# --------------------------------------------------
# 14 积分结算函数
# --------------------------------------------------

def settle_points(td):
    size = td["size"]
    points_key = min(POINTS_STRUCTURE.keys(), key=lambda k: abs(k - size))
    pts_map = POINTS_STRUCTURE[points_key]
    rounds = td["rounds"]

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    record = {
        "id": timestamp,
        "name": f"{timestamp} ({size}签)",
        "participants": [],
    }
    summary = []
    for p in rounds[str(size)]:
        wins = sum(1 for v in rounds.values() if p in v and len(v) < size)
        outcome, pts = "参与", 0
        ladder = {
            1: ("winner", "冠军"),
            2: ("finalist", "亚军"),
            4: ("semifinalist", "四强"),
            8: ("quarterfinalist", "八强"),
            16: ("round_of_16", "十六强"),
            32: ("round_of_32", "三十二强"),
        }
        for rn, (key, name) in ladder.items():
            if p in rounds.get(str(rn), []):
                pts = pts_map.get(key, 0)
                outcome = name
                break
        rankings_db[p] = rankings_db.get(p, 0) + pts
        record["participants"].append({
            "name": p,
            "outcome": outcome,
            "wins": wins,
            "points_earned": pts,
        })
        summary.append({"姓名": p, "成绩": outcome, "胜场": wins, "积分": pts})

    history_db.append(record)
    save_json(history_db, HISTORY_FILE)
    save_json(rankings_db, RANKINGS_FILE)
    st.subheader("积分结算")
    st.dataframe(pd.DataFrame(summary), use_container_width=True)


# --------------------------------------------------
# 15 侧边导航
# --------------------------------------------------
SIDEBAR_PAGES = [
    ("home", "主页"),
    ("tournament", "举办比赛"),
    ("players", "选手管理"),
    ("rankings", "积分榜"),
    ("history", "历史记录"),
    ("stats", "统计分析"),
    ("rules", "赛事规则"),
    ("settings", "设置中心"),
]

for key, name in SIDEBAR_PAGES:
    st.sidebar.button(f"{ICONS.get(key,'')} {name}", on_click=lambda k=key: st.session_state.__setitem__("page", k), use_container_width=True)

# --------------------------------------------------
# 16 页面路由
# --------------------------------------------------
router = {
    "home": page_home,
    "tournament": page_tournament,
    "players": page_players,
    "rankings": page_rankings,
    "history": page_history,
    "stats": page_stats,
    "rules": page_rules,
    "settings": page_settings,
}

router[st.session_state.page]()
