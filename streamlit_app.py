import streamlit as st
import json
import os
import datetime
import pandas as pd
import math
import graphviz

# --- 1. 初始化与配置 ---
st.set_page_config(page_title="精英网球巡回赛系统", layout="wide", initial_sidebar_state="expanded")

# --- 2. 图标定义 (提升UI/UX) ---
ICONS = {
    "home": "🏟️",
    "tournament": "🏆",
    "rankings": "📊",
    "history": "📜",
    "rules": "⚖️",
    "warning": "⚠️",
    "info": "ℹ️",
    "player": "👤",
    "vs": "⚔️"
}

# --- 3. 数据文件路径 ---
DATA_DIR = 'data'
RANKINGS_FILE = os.path.join(DATA_DIR, 'rankings.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'tournament_history.json')
os.makedirs(DATA_DIR, exist_ok=True)

# --- 4. 积分规则 ---
POINTS_STRUCTURE = {
    4: {"winner": 100, "finalist": 60, "semifinalist": 30},
    8: {"winner": 200, "finalist": 120, "semifinalist": 70, "quarterfinalist": 30},
    16: {"winner": 400, "finalist": 240, "semifinalist": 140, "quarterfinalist": 80, "round_of_16": 40},
    32: {"winner": 800, "finalist": 480, "semifinalist": 280, "quarterfinalist": 160, "round_of_16": 80, "round_of_32": 40}
}

# --- 5. 数据处理函数 ---
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

# --- 6. 核心逻辑：状态管理初始化 (遵循最佳实践) ---
def initialize_state():
    if 'page' not in st.session_state:
        st.session_state.page = "home"
    if 'tournament_step' not in st.session_state:
        st.session_state.tournament_step = "setup"
    if 'tournament_data' not in st.session_state:
        st.session_state.tournament_data = {}

initialize_state()

# --- 7. 赛事核心逻辑函数 (模块化) ---

def get_next_power_of_two(n):
    """计算大于等于n的最小的2的幂。"""
    return 1 if n == 0 else 2**math.ceil(math.log2(n))

def create_seeded_bracket(players):
    """根据种子顺序创建第一轮对阵。"""
    num_players = len(players)
    bracket_size = get_next_power_of_two(num_players)
    num_byes = bracket_size - num_players

    # 分配轮空名额给高顺位种子
    byes = players[:num_byes]
    players_in_first_round = players[num_byes:]

    # 标准种子配对
    # FIX 1: Initialized 'matches' as an empty list.
    matches = []
    head, tail = 0, len(players_in_first_round) - 1
    while head < tail:
        matches.append((players_in_first_round[head], players_in_first_round[tail]))
        head += 1
        tail -= 1
    
    return matches, byes, bracket_size

def generate_bracket_graph(tournament_data):
    """生成并显示可视化的对阵图。"""
    if not tournament_data or "rounds" not in tournament_data:
        return

    dot = graphviz.Digraph(comment='Tournament Bracket')
    dot.attr('graph', rankdir='LR', splines='ortho', nodesep='0.5', ranksep='1.5')
    dot.attr('node', shape='record', style='rounded,filled', fillcolor='lightblue', fontname='sans-serif')
    dot.attr('edge', arrowhead='none')

    rounds = tournament_data.get("rounds", {})
    all_players = tournament_data.get("initial_players", [])
    
    # 建立一个从轮次和选手到比赛节点的映射
    node_map = {}

    # 从第一轮开始正向创建节点
    for round_size_str, players in sorted(rounds.items(), key=lambda x: int(x[0]), reverse=True):
        round_size = int(round_size_str)
        # 跳过最终的"冠军"轮，因为它不是一场比赛
        if round_size == 1:
            winner = players[0]
            # 确保冠军节点存在
            if winner in node_map:
                 dot.node(node_map[winner], f"🏆 {winner}", fillcolor='gold')
            continue

        players_in_round = list(players)
        # 处理轮空选手，他们可能不在这一轮的比赛中，但需要被连接
        if round_size == tournament_data.get("bracket_size"):
             players_in_round.extend(["BYE"] * (round_size - len(players_in_round)))


        for i in range(0, len(players_in_round), 2):
            p1 = players_in_round[i]
            p2 = players_in_round[i+1] if i+1 < len(players_in_round) else "BYE"

            # 确定比赛胜者
            next_round_size = round_size // 2
            next_round_players = rounds.get(str(next_round_size), [])
            winner = None
            if p1 in next_round_players:
                winner = p1
            elif p2 != "BYE" and p2 in next_round_players:
                winner = p2

            # 创建标签
            p1_label = f"<b>{p1}</b>" if winner == p1 else str(p1)
            p2_label = f"<b>{p2}</b>" if winner == p2 else str(p2)
            label = f"{{{p1_label} | {p2_label}}}"
            
            node_id = f"R{round_size}_{i}"
            fill_color = 'lightgreen' if winner else 'lightblue'
            dot.node(node_id, label, fillcolor=fill_color)
            
            # 存储节点ID用于后续连接
            if p1 != "BYE": node_map[p1] = node_id
            if p2 != "BYE": node_map[p2] = node_id

            # 连接到下一轮的比赛
            if winner:
                if next_round_size > 1:
                    # 找到胜者在下一轮的比赛节点并连接
                    for j in range(0, len(next_round_players), 2):
                        next_p1 = next_round_players[j]
                        next_p2 = next_round_players[j+1] if j+1 < len(next_round_players) else "BYE"
                        if winner in [next_p1, next_p2]:
                            next_node_id = f"R{next_round_size}_{j}"
                            dot.edge(node_id, next_node_id)
                            break
                else: # 连接到最终的冠军节点
                    winner_node_id = f"R1_WINNER"
                    dot.node(winner_node_id, f"🏆 {winner}", fillcolor='gold')
                    dot.edge(node_id, winner_node_id)


    st.graphviz_chart(dot, use_container_width=True)

# --- 8. 页面渲染函数 ---

def page_home():
    st.title(f"{ICONS['home']} 精英网球巡回赛管理系统")
    st.markdown("---")
    st.header("欢迎使用！")
    st.info(f"{ICONS['info']} 使用左侧导航栏切换功能页面。本系统已全面升级，支持任意人数参赛、专业种子排序及可视化对阵图。")
    
    col1, col2 = st.columns(2)
    with col1:
        rankings = load_data(RANKINGS_FILE, {})
        st.metric("注册选手总数", len(rankings))
    with col2:
        # FIX: Provided a default value for load_data
        history = load_data(HISTORY_FILE, [])
        st.metric("已举办比赛场次", len(history))

def page_rules():
    st.title(f"{ICONS['rules']} 赛事章程与规则")
    st.markdown("""
    ### **一、 赛事结构**
    - **新秀赛 (Rookie Cup)**: 4-7人
    - **挑战赛 (Challenger Tour)**: 8-15人
    - **大师赛 (Masters Finals)**: 16人及以上

    ### **二、 比赛计分规则：Fast4 (短盘快胜制)**
    - **三盘两胜**: 先赢两盘者胜。
    - **短盘制**: 每盘先赢 **4** 局者胜。
    - **3-3 抢七**: 局分3-3时，进行抢七决胜。
    - **无占先**: 局分40-40时，接球方选边，一分定胜负。

    ### **三、 积分与排名系统**
    根据赛事级别和最终轮次获得相应积分，不累加。
    """)
    # 动态生成积分表
    df = pd.DataFrame(POINTS_STRUCTURE).T.fillna('-').astype(str)
    df.index.name = "签位数"
    df.columns = ["冠军", "亚军", "四强", "八强", "十六强", "三十二强"]
    st.dataframe(df, use_container_width=True)


def page_rankings():
    st.title(f"{ICONS['rankings']} 学员总积分排行榜")
    rankings = load_data(RANKINGS_FILE, {})
    if not rankings:
        st.warning(f"{ICONS['warning']} 目前没有排名数据，请先举办一场比赛。")
        return

    sorted_rankings = sorted(rankings.items(), key=lambda item: item[1], reverse=True)
    
    df = pd.DataFrame(sorted_rankings, columns=['学员姓名', '总积分'])
    df['排名'] = range(1, len(df) + 1)
    df = df[['排名', '学员姓名', '总积分']]
    
    st.dataframe(df, use_container_width=True, hide_index=True)

def page_history():
    st.title(f"{ICONS['history']} 查询选手参赛历史")
    # FIX: Provided a default value for load_data
    history = load_data(HISTORY_FILE, [])
    rankings = load_data(RANKINGS_FILE, {})

    if not rankings:
        st.warning(f"{ICONS['warning']} 目前没有任何选手记录。")
        return

    player_names = sorted(list(rankings.keys()))
    selected_player = st.selectbox(f"{ICONS['player']} 请选择要查询的选手：", player_names)

    if selected_player:
        records = [
            {
                "比赛名称": t["name"],
                "成绩": p["outcome"],
                "胜场数": p["wins"],
                "获得积分": p["points_earned"]
            }
            for t in history for p in t["participants"] if p["name"] == selected_player
        ]
        
        if not records:
            st.info(f"选手 **{selected_player}** 还没有参赛记录。")
        else:
            st.subheader(f"选手 **{selected_player}** 的历史战绩")
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True, hide_index=True)
            total_wins = df['胜场数'].sum()
            st.markdown(f"**总计 -> 参赛次数: `{len(df)}`, 总胜场: `{int(total_wins)}`, 当前总积分: `{rankings.get(selected_player, 0)}`**")

def page_tournament():
    st.title(f"{ICONS['tournament']} 举办一场新比赛")

    if st.session_state.tournament_step != "setup":
        if st.sidebar.button("🔴 取消并重置当前比赛", use_container_width=True):
            st.session_state.tournament_step = "setup"
            st.session_state.tournament_data = {}
            st.rerun()

    # 步骤1: 设置比赛
    if st.session_state.tournament_step == "setup":
        st.subheader("步骤 1: 设置比赛信息")
        st.info(f"{ICONS['info']} 请按种子顺位输入参赛选手姓名，每行一个。系统将自动处理轮空和对阵。")
        player_names_str = st.text_area("输入选手姓名 (按1号、2号...种子顺序):", height=250, placeholder="1. 阿尔卡拉斯\n2. 辛纳\n3. 德约科维奇\n...")
        players = [name.strip() for name in player_names_str.strip().split('\n') if name.strip()]

        if st.button("生成对阵并开始比赛", type="primary", disabled=len(players) < 2):
            matches, byes, bracket_size = create_seeded_bracket(players)
            
            # 第二轮选手 = 轮空选手 + 第一轮比赛的选手
            # 请注意：第一轮比赛的胜者才能进入第二轮，这里先将所有参赛者放入，后面再通过选择胜者来推进
            round_two_players = byes + [p for match in matches for p in match]
            
            st.session_state.tournament_data = {
                "bracket_size": bracket_size,
                "initial_players": players,
                "rounds": {str(bracket_size): players},
                "matches": matches, # 初始对阵
                "byes": byes,
                "current_round_num": bracket_size, # 从最大轮次开始
                "current_round_players": players, # 初始为所有选手
                "winners": {} # 存储每轮的胜者
            }
            st.session_state.tournament_step = "playing"
            st.rerun()

    # 步骤2: 进行比赛
    elif st.session_state.tournament_step == "playing":
        data = st.session_state.tournament_data
        
        current_round_players = data['current_round_players']
        current_round_num = len(current_round_players)

        # 比赛结束条件
        if current_round_num == 1:
            st.session_state.tournament_step = "finished"
            st.rerun()

        round_name = f"{current_round_num}强" if current_round_num > 2 else "决赛" if current_round_num == 2 else ""
        st.subheader(f"步骤 2: 进行比赛 - {round_name}")
        
        # 显示可视化对阵图
        generate_bracket_graph(data)

        # 本轮已经记录的获胜者
        round_winners = data["winners"].get(str(current_round_num), [])
        
        next_round_players = []

        # 处理轮空选手 (仅在第一轮发生)
        if data['byes'] and current_round_num == data['bracket_size']:
             next_round_players.extend(data['byes'])
             st.info(f"轮空选手: {', '.join(data['byes'])} 直接晋级下一轮。")


        # 创建本轮的对阵
        matches_to_play = []
        players_for_matches = [p for p in current_round_players if p not in data['byes']]
        for i in range(0, len(players_for_matches), 2):
            matches_to_play.append((players_for_matches[i], players_for_matches[i+1]))

        if not matches_to_play and data['byes']: # 如果第一轮全是轮空
             data['current_round_players'] = data['byes']
             data['rounds'][str(len(data['byes']))] = data['byes']
             st.session_state.tournament_data = data
             st.rerun()


        for p1, p2 in matches_to_play:
            # 如果这场比赛的胜者已经选出，则跳过
            if p1 in round_winners or p2 in round_winners:
                winner = p1 if p1 in round_winners else p2
                if winner not in next_round_players:
                    next_round_players.append(winner)
                continue

            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"**{p1}** {ICONS['vs']} **{p2}**")
            with col2:
                if st.button(f"👈 {p1} 胜", key=f"win_{p1}_{p2}", use_container_width=True):
                    round_winners.append(p1)
                    st.session_state.tournament_data["winners"][str(current_round_num)] = round_winners
                    st.rerun()
            with col3:
                if st.button(f"{p2} 胜 👉", key=f"win_{p2}_{p1}", use_container_width=True):
                    round_winners.append(p2)
                    st.session_state.tournament_data["winners"][str(current_round_num)] = round_winners
                    st.rerun()

        # 检查本轮是否结束
        if len(round_winners) == len(matches_to_play):
            next_round_players.extend(round_winners)
            
            # 更新状态进入下一轮
            data['current_round_players'] = next_round_players
            data['rounds'][str(len(next_round_players))] = next_round_players
            st.session_state.tournament_data = data
            st.success(f"{round_name} 比赛结束，晋级选手已确定！")
            st.rerun()

    # 步骤3: 比赛结束
    elif st.session_state.tournament_step == "finished":
        data = st.session_state.tournament_data
        winner = data["current_round_players"][0]
        
        st.subheader("比赛结束！🎉")
        st.balloons()
        st.success(f"**本次比赛的冠军是: {winner}**")
        
        # 把冠军信息加入rounds，方便绘图和结算
        data["rounds"]["1"] = [winner]
        generate_bracket_graph(data)
        update_rankings_and_history(data)

        if st.button("返回首页"):
            st.session_state.tournament_step = "setup"
            st.session_state.tournament_data = {}
            st.session_state.page = "home"
            st.rerun()

def update_rankings_and_history(data):
    """结算并保存数据。"""
    rankings = load_data(RANKINGS_FILE, {})
    # FIX: Provided a default value for load_data
    history = load_data(HISTORY_FILE, [])
    
    bracket_size = data["bracket_size"]
    rounds = data["rounds"]
    
    # 找到最接近的积分规则
    points_key = min(POINTS_STRUCTURE.keys(), key=lambda k: abs(k - bracket_size))
    points_map = POINTS_STRUCTURE[points_key]

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tournament_record = {
        "id": timestamp,
        "name": f"{timestamp} ({bracket_size}签位赛)",
        "draw_size": bracket_size,
        # FIX 2: Initialized 'participants' as an empty list.
        "participants": []
    }
    
    # FIX 3: Initialized 'summary' as an empty list.
    summary = []
    initial_players = data.get("initial_players", [])
    for player in initial_players:
        if player not in rankings: rankings[player] = 0
        
        # 计算胜场数：选手出现在了比初始轮次更小的轮次中
        wins = sum(1 for round_size_str, players_in_round in rounds.items() if int(round_size_str) < bracket_size and player in players_in_round)
        points, outcome = 0, "参与"

        round_outcomes = {
            1: ("winner", "冠军"), 2: ("finalist", "亚军"), 4: ("semifinalist", "四强"),
            8: ("quarterfinalist", "八强"), 16: ("round_of_16", "十六强"), 32: ("round_of_32", "三十二强")
        }
        
        # 从最高成绩开始检查
        for round_size, (key, name) in sorted(round_outcomes.items()):
            if player in rounds.get(str(round_size), []):
                points = points_map.get(key, 0)
                outcome = name
                break # 只取最高成绩
        
        rankings[player] += points
        tournament_record["participants"].append({"name": player, "outcome": outcome, "wins": wins, "points_earned": points})
        summary.append({"选手": player, "成绩": outcome, "胜场": wins, "获得积分": points})

    history.append(tournament_record)
    save_data(history, HISTORY_FILE)
    save_data(rankings, RANKINGS_FILE)
    
    st.subheader("本次比赛积分结算详情")
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

# --- 9. 侧边栏导航 (使用回调函数) ---
st.sidebar.title("导航")

def set_page(page_name):
    st.session_state.page = page_name

for page, name in [("home", "主页"), ("tournament", "举办新比赛"), ("rankings", "查看积分榜"), ("history", "查询历史"), ("rules", "赛事规则")]:
    st.sidebar.button(f"{ICONS[page]} {name}", on_click=set_page, args=(page,), use_container_width=True)

# --- 10. 主内容区渲染 ---
PAGES = {
    "home": page_home,
    "tournament": page_tournament,
    "rankings": page_rankings,
    "history": page_history,
    "rules": page_rules
}
PAGES[st.session_state.page]()
