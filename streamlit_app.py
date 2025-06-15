import streamlit as st
import json
import os
import datetime
import pandas as pd
import math
from collections import defaultdict
import itertools

# --- 1. 初始化与配置 ---
st.set_page_config(page_title="专业网球赛事管理系统", layout="wide", initial_sidebar_state="expanded")

# --- 2. 图标定义 ---
ICONS = {
    "home": "🏟️", "tournament": "🏆", "players": "👥", "history": "📜",
    "rules": "⚖️", "warning": "⚠️", "info": "ℹ️", "player": "👤",
    "vs": "⚔️", "save": "💾", "H2H": "📊"
}

# --- 3. 数据文件路径 (类数据库结构) ---
DATA_DIR = 'data'
PLAYERS_FILE = os.path.join(DATA_DIR, 'players.json')
TOURNAMENTS_FILE = os.path.join(DATA_DIR, 'tournaments.json')
MATCHES_FILE = os.path.join(DATA_DIR, 'matches.json')
os.makedirs(DATA_DIR, exist_ok=True)

# --- 4. 数据处理核心函数 ---
def load_data(filepath, default_value):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return default_value
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_value

def save_data(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 5. 状态管理初始化 ---
def initialize_state():
    if 'page' not in st.session_state:
        st.session_state.page = "home"

initialize_state()

# --- 6. 核心业务逻辑函数 ---

def get_player_name(player_id, players_data):
    """根据ID获取选手姓名"""
    return players_data.get(player_id, {}).get("name", "未知选手")

def get_h2h_stats(player1_id, player2_id, matches_data):
    """计算两位选手之间的H2H战绩"""
    p1_wins = 0
    p2_wins = 0
    records = []
    for match in matches_data.values():
        players = {match["player1_id"], match["player2_id"]}
        if players == {player1_id, player2_id}:
            winner_id = match.get("winner_id")
            if winner_id == player1_id:
                p1_wins += 1
            elif winner_id == player2_id:
                p2_wins += 1
            records.append(match)
    return p1_wins, p2_wins, records

def create_round_robin_schedule(player_ids):
    """为循环赛创建对阵日程"""
    if len(player_ids) % 2 != 0:
        player_ids.append(None) # 加入一个虚拟选手以保证偶数
    
    schedule = []
    num_players = len(player_ids)
    num_rounds = num_players - 1
    
    for r in range(num_rounds):
        round_matches = []
        for i in range(num_players // 2):
            p1 = player_ids[i]
            p2 = player_ids[num_players - 1 - i]
            if p1 is not None and p2 is not None:
                round_matches.append(tuple(sorted((p1, p2))))
        schedule.append(round_matches)
        
        # 轮换选手
        player_ids.insert(1, player_ids.pop())
        
    return list(itertools.chain.from_iterable(schedule))

def create_single_elimination_bracket(player_ids):
    """为单败淘汰赛创建对阵"""
    num_players = len(player_ids)
    bracket_size = 1 if num_players == 0 else 2**math.ceil(math.log2(num_players))
    num_byes = bracket_size - num_players
    
    byes = player_ids[:num_byes]
    players_in_first_round = player_ids[num_byes:]
    
    matches = []
    head, tail = 0, len(players_in_first_round) - 1
    while head < tail:
        matches.append(tuple(sorted((players_in_first_round[head], players_in_first_round[tail]))))
        head += 1
        tail -= 1
        
    return matches, byes

# --- 7. 页面渲染函数 ---

def page_home():
    st.title(f"{ICONS['home']} 专业网球赛事管理系统")
    st.markdown("### 欢迎使用全新升级的赛事管理系统！")
    st.info(f"""
    本系统现已支持多种赛制，并提供详细的选手数据统计功能。
    - **{ICONS['tournament']} 举办新比赛**: 创建并管理 **单败淘汰赛** 或 **循环赛**。
    - **{ICONS['players']} 选手数据库**: 查看所有选手资料、参赛历史和 **H2H (历史交手)** 记录。
    - **{ICONS['history']} 赛事档案馆**: 回顾所有已结束的赛事详情和完整对阵。
    """)
    
    players = load_data(PLAYERS_FILE, {})
    tournaments = load_data(TOURNAMENTS_FILE, {})
    col1, col2 = st.columns(2)
    col1.metric("注册选手总数", len(players))
    col2.metric("已举办赛事总数", len(tournaments))


def page_player_database():
    st.title(f"{ICONS['players']} 选手数据库与分析")
    players = load_data(PLAYERS_FILE, {})
    matches = load_data(MATCHES_FILE, {})
    tournaments = load_data(TOURNAMENTS_FILE, {})

    if not players:
        st.warning("尚未注册任何选手。")
        return

    all_player_names = {pid: pdata["name"] for pid, pdata in players.items()}
    
    st.sidebar.subheader("选手快速导航")
    selected_pid = st.sidebar.selectbox("选择查看选手", options=list(all_player_names.keys()), format_func=lambda pid: all_player_names[pid])

    if selected_pid:
        player_name = get_player_name(selected_pid, players)
        st.header(f"{ICONS['player']} {player_name} 的个人档案")

        player_matches = [m for m in matches.values() if selected_pid in [m["player1_id"], m["player2_id"]]]
        wins = sum(1 for m in player_matches if m.get("winner_id") == selected_pid)
        losses = len(player_matches) - wins

        col1, col2, col3 = st.columns(3)
        col1.metric("总参赛场次", len(player_matches))
        col2.metric("总胜场", wins)
        col3.metric("总负场", losses)

        # H2H 对比分析
        st.subheader(f"{ICONS['H2H']} 历史交手记录 (H2H)")
        other_players = {pid: name for pid, name in all_player_names.items() if pid != selected_pid}
        opponent_pid = st.selectbox("选择对比选手", options=list(other_players.keys()), format_func=lambda pid: other_players[pid], index=None, placeholder="请选择对手...")

        if opponent_pid:
            opponent_name = get_player_name(opponent_pid, players)
            p1_wins, p2_wins, h2h_records = get_h2h_stats(selected_pid, opponent_pid, matches)
            
            st.metric(f"对阵 **{opponent_name}** 总战绩", f"{p1_wins} - {p2_wins}")
            if h2h_records:
                h2h_df = pd.DataFrame([{
                    "赛事": tournaments.get(m["tournament_id"], {}).get("name", "N/A"),
                    "轮次": m["round_name"],
                    "胜者": get_player_name(m["winner_id"], players),
                    "比分": m.get("score", "N/A")
                } for m in sorted(h2h_records, key=lambda x: tournaments.get(x["tournament_id"], {}).get("date", ""), reverse=True)])
                st.dataframe(h2h_df, use_container_width=True, hide_index=True)

        # 完整比赛历史
        st.subheader("完整比赛历史")
        if player_matches:
            history_df = pd.DataFrame([{
                "日期": tournaments.get(m["tournament_id"], {}).get("date", "N/A"),
                "赛事": tournaments.get(m["tournament_id"], {}).get("name", "N/A"),
                "轮次": m["round_name"],
                "对手": get_player_name(m["player2_id"] if m["player1_id"] == selected_pid else m["player1_id"], players),
                "结果": "胜利" if m.get("winner_id") == selected_pid else "失利",
                "比分": m.get("score", "N/A")
            } for m in sorted(player_matches, key=lambda x: tournaments.get(x["tournament_id"], {}).get("date", ""), reverse=True)])
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.info("该选手暂无比赛记录。")


def page_tournament_creation():
    st.title(f"{ICONS['tournament']} 举办一场新比赛")
    
    players = load_data(PLAYERS_FILE, {})
    all_player_names = sorted(players.values(), key=lambda x: x["name"])
    
    st.subheader("步骤 1: 注册新选手")
    new_player_name = st.text_input("输入新选手姓名 (注册后才能参赛)", key="new_player_name")
    if st.button(f"注册选手 {new_player_name}", disabled=not new_player_name):
        if new_player_name in [p["name"] for p in players.values()]:
            st.warning("该选手已存在！")
        else:
            new_pid = "p_" + str(int(datetime.datetime.now().timestamp()))
            players[new_pid] = {"name": new_player_name, "registered_date": datetime.datetime.now().isoformat()}
            save_data(players, PLAYERS_FILE)
            st.success(f"选手 {new_player_name} 注册成功！")
            st.rerun()

    st.subheader("步骤 2: 设置比赛信息")
    with st.form("tournament_form"):
        tournament_name = st.text_input("比赛名称", f"{datetime.date.today().strftime('%Y-%m')} 挑战赛")
        tournament_format = st.selectbox("选择赛制", ["单败淘汰赛 (Single Elimination)", "循环赛 (Round Robin)"])
        
        participant_names = st.multiselect("选择参赛选手 (种子顺序)", options=[p["name"] for p in all_player_names])
        
        submitted = st.form_submit_button("创建比赛并生成对阵", type="primary")

        if submitted:
            if len(participant_names) < 2:
                st.error("至少需要2名选手才能创建比赛。")
            else:
                tournaments = load_data(TOURNAMENTS_FILE, {})
                matches_db = load_data(MATCHES_FILE, {})
                
                # 按选择顺序获取选手ID
                participant_ids = [pid for pid, pdata in players.items() if pdata["name"] in participant_names]
                id_map = {pdata["name"]: pid for pid, pdata in players.items()}
                sorted_participant_ids = [id_map[name] for name in participant_names]

                t_id = "t_" + str(int(datetime.datetime.now().timestamp()))
                
                new_tournament = {
                    "name": tournament_name,
                    "date": datetime.date.today().isoformat(),
                    "format": tournament_format,
                    "participants": sorted_participant_ids,
                    "status": "进行中"
                }

                if "单败淘汰赛" in tournament_format:
                    initial_matches, byes = create_single_elimination_bracket(sorted_participant_ids)
                    new_tournament["byes"] = byes
                    round_num = len(sorted_participant_ids) - len(byes)
                    round_name = f"{round_num}强" if round_num > 2 else "决赛"
                else: # 循环赛
                    initial_matches = create_round_robin_schedule(sorted_participant_ids)
                    round_name = "循环赛"

                # 创建比赛记录
                for p1_id, p2_id in initial_matches:
                    match_id = "m_" + str(len(matches_db) + 1).zfill(6)
                    matches_db[match_id] = {
                        "tournament_id": t_id,
                        "player1_id": p1_id,
                        "player2_id": p2_id,
                        "round_name": round_name,
                        "winner_id": None,
                        "score": ""
                    }
                
                tournaments[t_id] = new_tournament
                save_data(tournaments, TOURNAMENTS_FILE)
                save_data(matches_db, MATCHES_FILE)

                st.session_state.page = "赛事档案馆"
                st.success("比赛创建成功！正在跳转到赛事管理页面...")
                st.rerun()

def page_tournament_archive():
    st.title(f"{ICONS['history']} 赛事档案馆")
    
    tournaments = load_data(TOURNAMENTS_FILE, {})
    matches = load_data(MATCHES_FILE, {})
    players = load_data(PLAYERS_FILE, {})
    
    if not tournaments:
        st.info("还没有任何赛事记录。")
        return

    # 按状态分类
    active_tournaments = {tid: t for tid, t in tournaments.items() if t.get("status") == "进行中"}
    completed_tournaments = {tid: t for tid, t in tournaments.items() if t.get("status") == "已结束"}

    tab1, tab2 = st.tabs(["进行中的赛事", "已结束的赛事"])

    with tab1:
        if not active_tournaments:
            st.success("所有赛事均已完成！")
        else:
            for t_id, t_data in sorted(active_tournaments.items(), key=lambda item: item[1]['date'], reverse=True):
                with st.expander(f"**{t_data['name']}** ({t_data['format']}) - {t_data['date']}", expanded=True):
                    tournament_matches = {mid: m for mid, m in matches.items() if m["tournament_id"] == t_id}
                    
                    # 比赛录入区
                    for m_id, m_data in tournament_matches.items():
                        if m_data.get("winner_id"): continue # 跳过已完成的比赛

                        p1_name = get_player_name(m_data["player1_id"], players)
                        p2_name = get_player_name(m_data["player2_id"], players)

                        st.markdown(f"**{p1_name}** {ICONS['vs']} **{p2_name}** ({m_data['round_name']})")
                        cols = st.columns([2, 1, 1])
                        score = cols[0].text_input("输入比分", key=f"score_{m_id}", placeholder="例如: 6-4, 6-3")
                        
                        if cols[1].button(f"👈 {p1_name} 胜", key=f"win_{m_id}_{p1_name}"):
                            matches[m_id]["winner_id"] = m_data["player1_id"]
                            matches[m_id]["score"] = score
                            save_data(matches, MATCHES_FILE)
                            st.rerun()

                        if cols[2].button(f"{p2_name} 胜 👉", key=f"win_{m_id}_{p2_name}"):
                            matches[m_id]["winner_id"] = m_data["player2_id"]
                            matches[m_id]["score"] = score
                            save_data(matches, MATCHES_FILE)
                            st.rerun()
                        st.divider()

                    # 结束比赛按钮
                    if all(m.get("winner_id") for m in tournament_matches.values()):
                        if st.button(f"✅ 完成并归档赛事: {t_data['name']}", type="primary"):
                            tournaments[t_id]["status"] = "已结束"
                            save_data(tournaments, TOURNAMENTS_FILE)
                            st.rerun()
    with tab2:
        if not completed_tournaments:
            st.info("暂无已结束的赛事。")
        else:
            for t_id, t_data in sorted(completed_tournaments.items(), key=lambda item: item[1]['date'], reverse=True):
                 with st.expander(f"**{t_data['name']}** ({t_data['format']}) - {t_data['date']}"):
                    tournament_matches = [m for m in matches.values() if m["tournament_id"] == t_id]
                    
                    df_data = [{
                        "轮次": m["round_name"],
                        "选手1": get_player_name(m["player1_id"], players),
                        "选手2": get_player_name(m["player2_id"], players),
                        "比分": m.get("score", "N/A"),
                        "胜者": get_player_name(m.get("winner_id"), players)
                    } for m in tournament_matches]
                    
                    st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)


# --- 8. 主导航与页面渲染 ---
st.sidebar.title("导航")
PAGES_CONFIG = {
    "home": "系统主页",
    "tournament_creation": "举办新比赛",
    "players": "选手数据库",
    "history": "赛事档案馆"
}
PAGES_RENDER = {
    "home": page_home,
    "tournament_creation": page_tournament_creation,
    "players": page_player_database,
    "history": page_tournament_archive
}

for page_key, page_name in PAGES_CONFIG.items():
    if st.sidebar.button(f"{ICONS[page_key]} {page_name}", use_container_width=True):
        st.session_state.page = page_key
        st.rerun()

# 渲染当前页面
page_to_render = st.session_state.get("page", "home")
PAGES_RENDER[page_to_render]()
