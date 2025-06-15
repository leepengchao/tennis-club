import streamlit as st
import json
import os
import collections
import datetime
import pandas as pd

# --- 初始化与配置 ---
st.set_page_config(page_title="网球俱乐部赛事系统", layout="wide")

# --- 数据文件路径 ---
DATA_DIR = 'data'
RANKINGS_FILE = os.path.join(DATA_DIR, 'rankings.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'tournament_history.json')

# 确保数据文件夹存在
os.makedirs(DATA_DIR, exist_ok=True)


# --- 积分规则 (与之前相同) ---
POINTS_STRUCTURE = {
    4: {"winner": 100, "finalist": 60, "semifinalist": 30},
    8: {"winner": 200, "finalist": 120, "semifinalist": 70, "quarterfinalist": 30},
    16: {"winner": 400, "finalist": 240, "semifinalist": 140, "quarterfinalist": 80, "round_of_16": 40}
}

# --- 数据处理函数 (与之前基本相同) ---
def load_data(filepath, default_value):
    if not os.path.exists(filepath):
        return default_value
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_value

def save_data(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 核心逻辑：状态管理初始化 ---
# 使用 Streamlit 的 session_state 来跟踪应用状态
if 'page' not in st.session_state:
    st.session_state.page = "home"
if 'tournament_step' not in st.session_state:
    st.session_state.tournament_step = "setup"
if 'tournament_data' not in st.session_state:
    st.session_state.tournament_data = {}

# --- 页面渲染函数 ---

def page_home():
    st.title("🎾 网球俱乐部赛事管理系统")
    st.markdown("---")
    st.header("欢迎使用！")
    st.info("请使用左侧的导航栏来切换功能页面：举办比赛、查看排名、查询历史或阅读赛制。")
    
    col1, col2 = st.columns(2)
    with col1:
        rankings = load_data(RANKINGS_FILE, {})
        st.metric("注册选手总数", len(rankings))
    with col2:
        history = load_data(HISTORY_FILE, [])
        st.metric("已举办比赛场次", len(history))


def page_rules():
    st.title("📜 赛事章程与规则")
    try:
        with open("rules.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except FileNotFoundError:
        st.error("错误：`rules.md` 文件未找到！")

def page_rankings():
    st.title("📈 学员总积分排行榜")
    rankings = load_data(RANKINGS_FILE, {})
    if not rankings:
        st.warning("目前没有排名数据，请先举办一场比赛。")
        return

    sorted_rankings = sorted(rankings.items(), key=lambda item: item[1], reverse=True)
    
    # 使用 Pandas DataFrame 美化显示
    df = pd.DataFrame(sorted_rankings, columns=['学员姓名', '总积分'])
    df.index = df.index + 1
    df['排名'] = df.index
    df = df[['排名', '学员姓名', '总积分']]
    
    st.dataframe(df, use_container_width=True)

def page_history():
    st.title("📊 查询选手参赛历史")
    history = load_data(HISTORY_FILE, [])
    rankings = load_data(RANKINGS_FILE, {})

    if not rankings:
        st.warning("目前没有任何选手记录。")
        return

    player_names = sorted(list(rankings.keys()))
    selected_player = st.selectbox("请选择要查询的选手：", player_names)

    if selected_player:
        found_records = []
        for tournament in history:
            for participant in tournament["participants"]:
                if participant["name"] == selected_player:
                    found_records.append({
                        "比赛名称": tournament["name"],
                        "成绩": participant["outcome"],
                        "胜场数": participant["wins"],
                        "获得积分": participant["points_earned"]
                    })
        
        if not found_records:
            st.info(f"选手 **{selected_player}** 还没有参赛记录。")
        else:
            st.subheader(f"选手 **{selected_player}** 的历史战绩")
            df = pd.DataFrame(found_records)
            st.dataframe(df, use_container_width=True)

            total_wins = df['胜场数'].sum()
            total_points = df['获得积分'].sum()
            st.markdown(f"**总计 -> 参赛次数: `{len(df)}`, 总胜场: `{total_wins}`, 当前总积分: `{rankings.get(selected_player, 0)}`**")

def page_tournament():
    st.title("🏆 举办一场新比赛")

    # 步骤1: 设置比赛
    if st.session_state.tournament_step == "setup":
        st.subheader("步骤 1: 设置比赛信息")
        draw_size = st.selectbox("选择比赛签位数：", [4, 8, 16], key="draw_size_selector")
        
        st.info("请在下方文本框中输入所有参赛选手姓名，每行一个。")
        player_names_str = st.text_area(f"输入 {draw_size} 位选手的姓名:", height=200)
        players = [name.strip() for name in player_names_str.strip().split('\n') if name.strip()]

        if st.button("开始比赛", type="primary"):
            if len(players) != draw_size:
                st.error(f"输入的选手数量 ({len(players)}) 与所选签位数 ({draw_size}) 不匹配！")
            else:
                st.session_state.tournament_data = {
                    "draw_size": draw_size,
                    "rounds": {draw_size: players},
                    "current_round_players": players
                }
                st.session_state.tournament_step = "playing"
                st.experimental_rerun()

    # 步骤2: 进行比赛
    elif st.session_state.tournament_step == "playing":
        data = st.session_state.tournament_data
        current_players = data["current_round_players"]
        draw_size = data["draw_size"]
        round_name_num = len(current_players)

        st.subheader(f"步骤 2: 进行比赛 - 第 {draw_size // round_name_num} 轮 ({round_name_num}进{round_name_num//2})")

        next_round_players = data.get("next_round_players", [])
        
        # 显示对阵
        matches_to_play = []
        for i in range(0, len(current_players), 2):
            p1 = current_players[i]
            # 检查p2是否存在，防止单数选手轮空（理论上不会，但做健壮性处理）
            p2 = current_players[i+1] if i+1 < len(current_players) else None
            if p2 is None: # 轮空
                next_round_players.append(p1)
                continue
            
            # 检查这场比赛是否已经打完
            winner_found = False
            for p in next_round_players:
                if p == p1 or p == p2:
                    winner_found = True
                    break
            
            if not winner_found:
                 matches_to_play.append((p1,p2))
        
        for p1, p2 in matches_to_play:
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.write(f"**{p1}** vs **{p2}**")
            with cols[1]:
                if st.button(f"👈 {p1} 胜", key=f"win_{p1}_{p2}"):
                    next_round_players.append(p1)
                    st.session_state.tournament_data["next_round_players"] = next_round_players
                    st.experimental_rerun()
            with cols[2]:
                if st.button(f"{p2} 胜 👉", key=f"win_{p2}_{p1}"):
                    next_round_players.append(p2)
                    st.session_state.tournament_data["next_round_players"] = next_round_players
                    st.experimental_rerun()

        # 如果本轮所有比赛都打完
        if len(next_round_players) == round_name_num / 2:
            data["rounds"][len(next_round_players)] = next_round_players
            data["current_round_players"] = next_round_players
            data.pop("next_round_players") # 清理临时数据

            # 检查比赛是否结束
            if len(next_round_players) == 1:
                st.session_state.tournament_step = "finished"
            
            st.experimental_rerun()

    # 步骤3: 比赛结束
    elif st.session_state.tournament_step == "finished":
        data = st.session_state.tournament_data
        winner = data["current_round_players"][0]
        
        st.subheader("比赛结束！🎉")
        st.balloons()
        st.success(f"**本次比赛的冠军是: {winner}**")

        # 保存结果
        update_rankings_and_history(data["draw_size"], data["rounds"])

        if st.button("返回首页"):
            st.session_state.tournament_step = "setup"
            st.session_state.page = "home"
            st.experimental_rerun()


def update_rankings_and_history(draw_size, results):
    """结算并保存数据，返回本次比赛的总结"""
    rankings = load_data(RANKINGS_FILE, {})
    history = load_data(HISTORY_FILE, [])
    points_map = POINTS_STRUCTURE[draw_size]

    all_players = set(results[draw_size])
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tournament_record = {
        "id": timestamp,
        "name": f"{timestamp} ({draw_size}签位赛)",
        "draw_size": draw_size,
        "participants": []
    }
    
    summary = []
    for player in all_players:
        if player not in rankings: rankings[player] = 0
        wins = sum(1 for r_winners in results.values() if player in r_winners and len(r_winners) < draw_size)
        points, outcome = 0, ""

        if player in results.get(1, []): points, outcome = points_map["winner"], "冠军"
        elif player in results.get(2, []): points, outcome = points_map["finalist"], "亚军"
        elif draw_size >= 4 and player in results.get(4, []): points, outcome = points_map["semifinalist"], "四强"
        elif draw_size >= 8 and player in results.get(8, []): points, outcome = points_map["quarterfinalist"], "八强"
        elif draw_size >= 16 and player in results.get(16, []): points, outcome = points_map.get("round_of_16", 0), "十六强"
        
        rankings[player] += points
        tournament_record["participants"].append({"name": player, "outcome": outcome, "wins": wins, "points_earned": points})
        summary.append({"选手": player, "成绩": outcome, "胜场": wins, "获得积分": points})

    history.append(tournament_record)
    save_data(history, HISTORY_FILE)
    save_data(rankings, RANKINGS_FILE)
    
    st.subheader("本次比赛积分结算详情")
    st.dataframe(pd.DataFrame(summary), use_container_width=True)


# --- 侧边栏导航 ---
st.sidebar.title("导航")
if st.sidebar.button("主页 🏠", use_container_width=True):
    st.session_state.page = "home"
if st.sidebar.button("举办新比赛 🏆", use_container_width=True):
    st.session_state.page = "tournament"
if st.sidebar.button("查看积分榜 📈", use_container_width=True):
    st.session_state.page = "rankings"
if st.sidebar.button("查询历史 📊", use_container_width=True):
    st.session_state.page = "history"
if st.sidebar.button("赛事规则 📜", use_container_width=True):
    st.session_state.page = "rules"

# --- 根据页面状态渲染主内容区 ---
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "tournament":
    page_tournament()
elif st.session_state.page == "rankings":
    page_rankings()
elif st.session_state.page == "history":
    page_history()
elif st.session_state.page == "rules":
    page_rules()